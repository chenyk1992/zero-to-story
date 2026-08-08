"""EditorialService — selected clip lifecycle management.

Responsibilities:
- create_selection(): draft a new clip selection
- render_selected_clip(): extract clip via MediaService, register asset, run QC
- approve_selected_clip(): supersede old approved, approve new (transactional)
- reject_selected_clip(): mark as rejected with reason

Status state machine:
    draft → rendering → awaiting_review → approved
                                  ↘ rejected
              ↘ technical_failed
    any → stale (when dependency_hash no longer matches)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.core.database import Database
from lfo.core.hashing import compute_content_hash, compute_dependency_hash
from lfo.services.media_service import MediaService
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService

SELECTED_CLIP_STATUSES = frozenset({
    "draft",
    "rendering",
    "technical_failed",
    "awaiting_review",
    "approved",
    "rejected",
    "stale",
    "superseded",
})

DEFAULT_RENDER_POLICY_ID = "selected_clip_v1"


@dataclass
class SelectedClipRecord:
    """A selected clip row."""

    selected_clip_id: str
    project_id: str
    shot_id: str
    normalized_asset_id: str
    output_asset_id: str
    selected_in_frame: int
    selected_out_frame_exclusive: int
    fps_num: int
    fps_den: int
    render_policy_id: str
    revision: int
    status: str
    content_hash: str
    dependency_hash: str
    created_at: str
    approved_at: str
    superseded_by: str


class EditorialService:
    """Manage the selected clip lifecycle."""

    def __init__(
        self,
        db: Database,
        media_service: MediaService | None = None,
        qc_service: TechnicalQCService | None = None,
    ) -> None:
        self.db = db
        self.media_service = media_service or MediaService(db)
        self.qc_service = qc_service or TechnicalQCService(db)

    # -- public API -------------------------------------------------------

    def create_selection(
        self,
        project_id: str,
        shot_id: str,
        normalized_asset_id: str,
        in_frame: int = 0,
        out_frame_exclusive: int | None = None,
        render_policy_id: str = DEFAULT_RENDER_POLICY_ID,
    ) -> SelectedClipRecord:
        """Create a draft selected clip.

        If out_frame_exclusive is not provided, it is read from the
        normalized asset's frame_count (full-range selection).
        """
        norm_row = self.db.fetchone(
            "SELECT frame_count, file_hash, content_hash FROM assets WHERE asset_id = ?",
            (normalized_asset_id,),
        )
        if norm_row is None:
            raise ValueError(f"Normalized asset {normalized_asset_id} not found")

        frame_count = norm_row[0] or 0
        out_frame = out_frame_exclusive if out_frame_exclusive is not None else frame_count
        if out_frame <= in_frame:
            raise ValueError(
                f"out_frame_exclusive ({out_frame}) must be > in_frame ({in_frame})"
            )

        fps_num, fps_den = self._resolve_fps(normalized_asset_id)
        revision = self._next_revision(project_id, shot_id)
        content_hash = self._compute_content_hash(
            project_id, shot_id, normalized_asset_id,
            in_frame, out_frame, fps_num, fps_den, render_policy_id,
        )
        dependency_hash = self._compute_dependency_hash(
            normalized_asset_id, norm_row[1], norm_row[2],
            None, None, content_hash,
        )

        clip_id = uuid.uuid4().hex
        now = _utc_now()
        self.db.execute(
            """INSERT INTO selected_clips
               (selected_clip_id, project_id, shot_id, normalized_asset_id,
                selected_in_frame, selected_out_frame_exclusive,
                fps_num, fps_den, render_policy_id, revision, status,
                content_hash, dependency_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clip_id, project_id, shot_id, normalized_asset_id,
                in_frame, out_frame,
                fps_num, fps_den, render_policy_id, revision, "draft",
                content_hash, dependency_hash, now,
            ),
        )
        return self._load_clip(clip_id)

    def render_selected_clip(
        self,
        selected_clip_id: str,
    ) -> SelectedClipRecord:
        """Render a draft selected clip to an output asset.

        Steps:
        1. Extract clip via MediaService.create_selected_clip()
        2. Validate output file
        3. Register output in assets
        4. Link asset_relations (normalized_from → selected_from)
        5. Update selected_clips.output_asset_id
        6. Run technical QC
        7. Status → awaiting_review (or technical_failed)
        """
        clip = self._load_clip(selected_clip_id)
        if clip is None:
            raise ValueError(f"Selected clip {selected_clip_id} not found")
        if clip.status not in ("draft", "technical_failed"):
            raise ValueError(
                f"Cannot render clip in status '{clip.status}'"
            )

        self._update_status(selected_clip_id, "rendering")

        try:
            result = self.media_service.create_selected_clip(
                clip.normalized_asset_id,
                clip.selected_in_frame,
                clip.selected_out_frame_exclusive,
            )
        except Exception as exc:
            self._update_status(selected_clip_id, "technical_failed")
            raise RuntimeError(f"Clip extraction failed: {exc}") from exc

        if not result.file_path or not __import__("os").path.exists(result.file_path):
            self._update_status(selected_clip_id, "technical_failed")
            raise RuntimeError("Clip extraction produced no output file")

        task_id = self._resolve_task_id(clip.normalized_asset_id)
        output_asset_id = uuid.uuid4().hex
        now = _utc_now()

        # Probe output file for accurate stream metadata (fall back to defaults)
        try:
            out_sig = self.media_service.get_stream_signature(result.file_path)
        except Exception:
            out_sig = None

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, file_size,
                width, height, duration, frame_count, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                output_asset_id,
                task_id,
                "video",
                result.file_path,
                "",
                __import__("os").path.getsize(result.file_path),
                out_sig.video_width if out_sig else None,
                out_sig.video_height if out_sig else None,
                result.duration_sec,
                result.frame_count,
                json.dumps({
                    "source": "selected_clip",
                    "selected_clip_id": selected_clip_id,
                    "in_frame": result.in_frame,
                    "out_frame_exclusive": result.out_frame_exclusive,
                    "fps": out_sig.video_fps if out_sig else 0.0,
                    "codec": out_sig.video_codec if out_sig else "",
                    "has_audio": out_sig.has_audio if out_sig else False,
                    "audio_codec": out_sig.audio_codec if out_sig else "",
                    "audio_sample_rate": out_sig.audio_sample_rate if out_sig else 0,
                    "audio_channels": out_sig.audio_channels if out_sig else 0,
                }),
                now,
                now,
            ),
        )

        self.db.execute(
            """INSERT INTO asset_relations
               (source_asset_id, target_asset_id, relation_type, metadata)
               VALUES (?, ?, ?, ?)""",
            (
                clip.normalized_asset_id,
                output_asset_id,
                "selected_from",
                json.dumps({"selected_clip_id": selected_clip_id}),
            ),
        )

        self.db.execute(
            "UPDATE selected_clips SET output_asset_id = ? WHERE selected_clip_id = ?",
            (output_asset_id, selected_clip_id),
        )

        spec = QCSpec(
            requires_audio=True,
            expected_video_codec="h264",
            expected_audio_codec="aac",
            expected_sample_rate=48000,
            expected_channels=2,
        )
        qc_result = self.qc_service.check_asset(output_asset_id, spec)

        new_status = "awaiting_review" if qc_result.passed else "technical_failed"
        self._update_status(selected_clip_id, new_status)

        return self._load_clip(selected_clip_id)

    def approve_selected_clip(
        self,
        selected_clip_id: str,
    ) -> SelectedClipRecord:
        """Approve a selected clip, superseding any previous approved revision.

        Transactional: old approved → superseded, new → approved, event written.
        """
        clip = self._load_clip(selected_clip_id)
        if clip is None:
            raise ValueError(f"Selected clip {selected_clip_id} not found")
        if clip.status != "awaiting_review":
            raise ValueError(
                f"Cannot approve clip in status '{clip.status}'"
            )

        now = _utc_now()
        with self.db.transaction():
            # Find and supersede existing approved clip for this shot
            old = self.db.fetchone(
                """SELECT selected_clip_id FROM selected_clips
                   WHERE project_id = ? AND shot_id = ? AND status = 'approved'""",
                (clip.project_id, clip.shot_id),
            )
            if old is not None:
                old_id = old[0]
                self.db.execute(
                    """UPDATE selected_clips
                       SET status = 'superseded', superseded_by = ?
                       WHERE selected_clip_id = ?""",
                    (selected_clip_id, old_id),
                )

            self.db.execute(
                """UPDATE selected_clips
                   SET status = 'approved', approved_at = ?
                   WHERE selected_clip_id = ?""",
                (now, selected_clip_id),
            )

            self.db.execute(
                """INSERT INTO events
                   (project_id, event_type, payload, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    clip.project_id,
                    "selected_clip_approved",
                    json.dumps({
                        "selected_clip_id": selected_clip_id,
                        "shot_id": clip.shot_id,
                        "revision": clip.revision,
                    }),
                    now,
                ),
            )

        return self._load_clip(selected_clip_id)

    def reject_selected_clip(
        self,
        selected_clip_id: str,
        reason: str,
    ) -> SelectedClipRecord:
        """Reject a selected clip with a reason."""
        clip = self._load_clip(selected_clip_id)
        if clip is None:
            raise ValueError(f"Selected clip {selected_clip_id} not found")
        if clip.status != "awaiting_review":
            raise ValueError(
                f"Cannot reject clip in status '{clip.status}'"
            )

        self.db.execute(
            """UPDATE selected_clips SET status = 'rejected'
               WHERE selected_clip_id = ?""",
            (selected_clip_id,),
        )
        return self._load_clip(selected_clip_id)

    # -- internal helpers -------------------------------------------------

    def _load_clip(self, clip_id: str) -> SelectedClipRecord | None:
        row = self.db.fetchone(
            """SELECT selected_clip_id, project_id, shot_id, normalized_asset_id,
                      output_asset_id, selected_in_frame, selected_out_frame_exclusive,
                      fps_num, fps_den, render_policy_id, revision, status,
                      content_hash, dependency_hash, created_at, approved_at,
                      superseded_by
               FROM selected_clips WHERE selected_clip_id = ?""",
            (clip_id,),
        )
        if row is None:
            return None
        return SelectedClipRecord(
            selected_clip_id=row[0],
            project_id=row[1],
            shot_id=row[2],
            normalized_asset_id=row[3],
            output_asset_id=row[4] or "",
            selected_in_frame=row[5],
            selected_out_frame_exclusive=row[6],
            fps_num=row[7],
            fps_den=row[8],
            render_policy_id=row[9],
            revision=row[10],
            status=row[11],
            content_hash=row[12],
            dependency_hash=row[13],
            created_at=row[14],
            approved_at=row[15] or "",
            superseded_by=row[16] or "",
        )

    def _update_status(self, clip_id: str, status: str) -> None:
        if status not in SELECTED_CLIP_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        self.db.execute(
            "UPDATE selected_clips SET status = ? WHERE selected_clip_id = ?",
            (status, clip_id),
        )

    def _next_revision(self, project_id: str, shot_id: str) -> int:
        row = self.db.fetchone(
            """SELECT MAX(revision) FROM selected_clips
               WHERE project_id = ? AND shot_id = ?""",
            (project_id, shot_id),
        )
        return (row[0] or 0) + 1

    def _resolve_task_id(self, asset_id: str) -> str:
        row = self.db.fetchone(
            "SELECT task_id FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        return row[0] if row else ""

    def _resolve_fps(self, asset_id: str) -> tuple[int, int]:
        row = self.db.fetchone(
            "SELECT metadata FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        if row and row[0]:
            meta = json.loads(row[0])
            fps = meta.get("fps", 24.0)
            return _fps_to_rational(fps)
        return (24, 1)

    def _compute_content_hash(
        self,
        project_id: str,
        shot_id: str,
        normalized_asset_id: str,
        in_frame: int,
        out_frame: int,
        fps_num: int,
        fps_den: int,
        render_policy_id: str,
    ) -> str:
        entity = {
            "project_id": project_id,
            "shot_id": shot_id,
            "normalized_asset_id": normalized_asset_id,
            "selected_in_frame": in_frame,
            "selected_out_frame_exclusive": out_frame,
            "fps": f"{fps_num}/{fps_den}",
            "render_policy_id": render_policy_id,
        }
        return compute_content_hash(entity)

    def _compute_dependency_hash(
        self,
        normalized_asset_id: str,
        normalized_asset_file_hash: str | None,
        normalized_asset_content_hash: str | None,
        normalize_profile_hash: str | None,
        media_compiler_identity: str | None,
        content_hash: str,
    ) -> str:
        entity = {
            "normalized_asset_file_hash": normalized_asset_file_hash or "",
            "normalized_asset_content_hash": normalized_asset_content_hash or "",
            "normalize_profile_hash": normalize_profile_hash or "",
            "media_compiler_identity": media_compiler_identity or "",
            "content_hash": content_hash,
        }
        return compute_dependency_hash([
            entity["normalized_asset_file_hash"],
            entity["normalized_asset_content_hash"],
            entity["normalize_profile_hash"],
            entity["media_compiler_identity"],
            entity["content_hash"],
        ])


def _fps_to_rational(fps: float) -> tuple[int, int]:
    """Convert a float fps to a rational (num, den) pair."""
    if abs(fps - 24.0) < 0.01:
        return (24, 1)
    if abs(fps - 25.0) < 0.01:
        return (25, 1)
    if abs(fps - 30.0) < 0.01:
        return (30, 1)
    if abs(fps - 23.976) < 0.01:
        return (24000, 1001)
    if abs(fps - 29.97) < 0.01:
        return (30000, 1001)
    # Generic: express as num/1000 rounded
    return (round(fps * 1000), 1000)


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
