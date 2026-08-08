"""VideoCollectService — poll ComfyUI completion, collect outputs, register assets.

Responsibilities:
- Poll ComfyUI for prompt completion (via ComfyMonitor)
- Discover output files (via ComfyOutputCollector)
- Register asset rows in the database
- Update Attempt and Task status on success/failure

Standard flow:
1. Load attempt record (prompt_id, task_id, project_id)
2. Poll ComfyUI until completion or timeout
3. On success: discover → validate → register assets
4. Update attempt status → COMPLETED, task status → SUCCEEDED
5. On failure: update attempt status → FAILED, task → FAILED_RETRYABLE
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import AssetRecord, CollectResult, ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.core.state_machine import SubmissionState, TaskStatus


@dataclass
class VideoCollectResult:
    """Result of video collection for one attempt."""

    attempt_id: str
    task_id: str
    success: bool = False
    assets: list[AssetRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = ""  # final task status


class VideoCollectService:
    """Poll ComfyUI, collect outputs, register assets, update status."""

    def __init__(
        self,
        db: Database,
        collector: ComfyOutputCollector | None = None,
        monitor: ComfyMonitor | None = None,
        poll_interval: float = 2.0,
        poll_timeout: float = 900.0,  # 15 min default
    ) -> None:
        self.db = db
        self.collector = collector
        self.monitor = monitor
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    # -- public API ------------------------------------------------------- #

    def collect(self, attempt_id: str) -> VideoCollectResult:
        """Collect outputs for an attempt.

        Steps:
        1. Load attempt record
        2. Poll ComfyUI for completion
        3. On success: discover → register assets → update status
        4. On failure: mark attempt/task as failed

        Args:
            attempt_id: The attempt to collect outputs for.

        Returns:
            VideoCollectResult with asset records and final status.
        """
        result = VideoCollectResult(attempt_id=attempt_id, task_id="")

        # 1. Load attempt
        attempt_row = self.db.fetchone(
            """SELECT a.attempt_id, a.task_id, t.project_id, a.status
               FROM attempts a
               JOIN tasks t ON a.task_id = t.task_id
               WHERE a.attempt_id = ?""",
            (attempt_id,),
        )
        if attempt_row is None:
            result.errors.append(f"Attempt {attempt_id} not found")
            return result

        attempt_id, task_id, project_id = (
            attempt_row[0], attempt_row[1], attempt_row[2],
        )
        result.task_id = task_id

        # Get prompt_id from submission_journal
        prompt_id = self._get_prompt_id(attempt_id)
        if not prompt_id:
            result.errors.append(f"Attempt {attempt_id} has no prompt_id in submission_journal")
            self._mark_attempt_failed(attempt_id, task_id, "NO_PROMPT_ID")
            return result

        # 2. Poll ComfyUI for completion
        poll_status = self._poll_completion(prompt_id)

        if poll_status.get("status") == "timeout":
            result.errors.append(
                f"Polling timed out after {self.poll_timeout}s for prompt {prompt_id}"
            )
            self._mark_attempt_failed(attempt_id, task_id, "POLL_TIMEOUT")
            return result

        if poll_status.get("error"):
            result.errors.append(
                f"Prompt {prompt_id} execution error: {poll_status['error']}"
            )
            self._mark_attempt_failed(attempt_id, task_id, "EXECUTION_ERROR")
            return result

        if not poll_status.get("completed"):
            result.errors.append(
                f"Prompt {prompt_id} not completed (status: {poll_status.get('status')})"
            )
            self._mark_attempt_failed(attempt_id, task_id, "NOT_COMPLETED")
            return result

        # 3. Collect outputs
        collect_result = self._collect_outputs(attempt_id, task_id, project_id)
        result.assets = collect_result.assets
        result.errors.extend(collect_result.errors)

        if not collect_result.success:
            self._mark_attempt_failed(attempt_id, task_id, "COLLECTION_FAILED")
            return result

        # 4. Register assets in DB
        try:
            self._register_assets_in_db(collect_result.assets)
        except Exception as exc:
            result.errors.append(f"Asset registration failed: {exc}")
            self._mark_attempt_failed(attempt_id, task_id, "ASSET_REGISTRATION_FAILED")
            return result

        # 5. Update status: attempt → COMPLETED, task → SUCCEEDED
        self._mark_completed(attempt_id, task_id, collect_result.assets)
        result.success = True
        result.status = TaskStatus.SUCCEEDED.value

        return result

    # -- helpers --------------------------------------------------------- #

    def _get_prompt_id(self, attempt_id: str) -> str | None:
        """Get the prompt_id from submission_journal for an attempt."""
        row = self.db.fetchone(
            """SELECT provider_job_id FROM submission_journal
               WHERE attempt_id = ? AND provider_job_id IS NOT NULL
               ORDER BY created_at DESC LIMIT 1""",
            (attempt_id,),
        )
        if row is not None:
            return row[0]
        return None

    # -- polling --------------------------------------------------------- #

    def _poll_completion(self, prompt_id: str) -> dict:
        """Poll ComfyUI until prompt completes or timeout."""
        if self.monitor is None:
            # No monitor configured — create one from client
            self.monitor = ComfyMonitor(ComfyApiClient())

        return self.monitor.poll_until_done(
            prompt_id,
            interval=self.poll_interval,
            timeout=self.poll_timeout,
        )

    # -- output collection ---------------------------------------------- #

    def _collect_outputs(
        self,
        attempt_id: str,
        task_id: str,
        project_id: str,
    ) -> CollectResult:
        """Discover and validate output files for an attempt."""
        if self.collector is None:
            # No collector configured — cannot collect
            collect_result = CollectResult()
            collect_result.errors.append("No collector configured")
            return collect_result

        db_record = {
            "attempt_dir": attempt_id,
            "project_id": project_id,
            "task_id": task_id,
            "attempt_id": attempt_id,
        }

        return self.collector.collect(db_record)

    # -- asset DB registration ------------------------------------------ #

    def _register_assets_in_db(self, assets: list[AssetRecord]) -> None:
        """Insert asset rows into the database."""
        now = _utc_now()
        for asset in assets:
            asset_id = uuid.uuid4().hex
            metadata = {}
            if asset.media_info:
                metadata = {
                    "codec": asset.media_info.codec,
                    "width": asset.media_info.width,
                    "height": asset.media_info.height,
                    "frames": asset.media_info.frames,
                    "fps": asset.media_info.fps,
                    "duration": asset.media_info.duration,
                    "has_audio": asset.media_info.has_audio,
                }

            self.db.execute(
                """INSERT INTO assets
                   (asset_id, task_id, attempt_id, asset_type, file_path,
                    file_hash, file_size, width, height, duration,
                    frame_count, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset_id,
                    asset.task_id,
                    asset.attempt_id,
                    self._guess_asset_type(asset.path),
                    str(asset.path),
                    asset.sha256,
                    asset.size_bytes,
                    asset.media_info.width if asset.media_info else None,
                    asset.media_info.height if asset.media_info else None,
                    asset.media_info.duration if asset.media_info else None,
                    asset.media_info.frames if asset.media_info else None,
                    json.dumps(metadata),
                    now,
                    now,
                ),
            )

    @staticmethod
    def _guess_asset_type(path: Path) -> str:
        """Guess asset type from file extension."""
        ext = path.suffix.lower()
        if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            return "video"
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            return "image"
        if ext in (".wav", ".mp3", ".aac", ".flac", ".ogg"):
            return "audio"
        return "video"  # default

    # -- status updates -------------------------------------------------- #

    def _mark_completed(
        self,
        attempt_id: str,
        task_id: str,
        assets: list[AssetRecord],
    ) -> None:
        """Mark attempt as COMPLETED and task as SUCCEEDED."""
        now = _utc_now()

        # Update attempt status
        self.db.execute(
            "UPDATE attempts SET status = ?, updated_at = ? WHERE attempt_id = ?",
            (SubmissionState.COMPLETED.value, now, attempt_id),
        )

        # Update task status
        self.db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (TaskStatus.SUCCEEDED.value, now, task_id),
        )

    def _mark_attempt_failed(
        self,
        attempt_id: str,
        task_id: str,
        reason: str,
    ) -> None:
        """Mark attempt as FAILED and task as FAILED_RETRYABLE."""
        now = _utc_now()

        # Update attempt status
        self.db.execute(
            "UPDATE attempts SET status = ?, updated_at = ? WHERE attempt_id = ?",
            (SubmissionState.FAILED.value, now, attempt_id),
        )

        # Update task status
        self.db.execute(
            "UPDATE tasks SET status = ?, error = ?, updated_at = ? WHERE task_id = ?",
            (TaskStatus.FAILED_RETRYABLE.value, reason, now, task_id),
        )


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
