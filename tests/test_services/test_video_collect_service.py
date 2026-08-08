"""Tests for VideoCollectService."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lfo.comfy.collect import (
    AssetRecord,
    CollectResult,
    ComfyOutputCollector,
    MediaInfo,
)
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.core.state_machine import SubmissionState, TaskStatus
from lfo.services.video_collect_service import VideoCollectService


@pytest.fixture
def db() -> Database:
    """Create a fresh in-memory database."""
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def attempt_row(db):
    """Create a task and attempt record, return (attempt_id, task_id, project_id)."""
    task_id = "task-001"
    project_id = "proj-001"
    attempt_id = "att-001"
    prompt_id = "prompt-abc"

    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, project_id, "video.h3", "RUNNING", "phash", "dhash", "ikey"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (attempt_id, task_id, "ikey", SubmissionState.SUBMITTED.value, "{}", "chash", "dhash", "phash"),
    )
    # prompt_id lives in submission_journal
    db.execute(
        """INSERT INTO submission_journal (journal_id, attempt_id, task_id, state, provider_job_id)
           VALUES (?, ?, ?, ?, ?)""",
        ("journal-001", attempt_id, task_id, SubmissionState.SUBMITTED.value, prompt_id),
    )
    return attempt_id, task_id, project_id, prompt_id


@pytest.fixture
def mock_monitor():
    """Create a mock ComfyMonitor."""
    return MagicMock(spec=ComfyMonitor)


@pytest.fixture
def mock_collector():
    """Create a mock ComfyOutputCollector."""
    return MagicMock(spec=ComfyOutputCollector)


def _make_asset_record(task_id: str, attempt_id: str, filename: str = "video_00001_.mp4") -> AssetRecord:
    """Create a test AssetRecord."""
    return AssetRecord(
        path=Path(f"/tmp/output/{filename}"),
        sha256="abc123",
        project_id="proj-001",
        task_id=task_id,
        attempt_id=attempt_id,
        media_info=MediaInfo(
            codec="h264",
            width=864,
            height=480,
            frames=124,
            fps=24.0,
            duration=5.167,
            has_audio=True,
        ),
        size_bytes=1024000,
    )


class TestCollectSuccess:
    """Test successful collection flow."""

    def test_collect_success_updates_status(self, db, attempt_row, mock_monitor, mock_collector):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        # Mock monitor: prompt completed
        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "status": "completed",
            "completed": True,
        }

        # Mock collector: found 1 asset
        asset = _make_asset_record(task_id, attempt_id)
        mock_collector.collect.return_value = CollectResult(
            success=True,
            assets=[asset],
        )

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        result = service.collect(attempt_id)

        assert result.success is True
        assert result.task_id == task_id
        assert len(result.assets) == 1
        assert result.status == TaskStatus.SUCCEEDED.value

        # Verify DB status updates
        task_row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
        assert task_row[0] == TaskStatus.SUCCEEDED.value

        attempt_row_db = db.fetchone("SELECT status FROM attempts WHERE attempt_id = ?", (attempt_id,))
        assert attempt_row_db[0] == SubmissionState.COMPLETED.value

    def test_collect_registers_asset_in_db(self, db, attempt_row, mock_monitor, mock_collector):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "completed": True,
        }

        asset = _make_asset_record(task_id, attempt_id)
        mock_collector.collect.return_value = CollectResult(success=True, assets=[asset])

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        service.collect(attempt_id)

        # Verify asset row exists
        asset_rows = db.fetchall("SELECT * FROM assets WHERE task_id = ?", (task_id,))
        assert len(asset_rows) == 1
        assert asset_rows[0][4] == str(asset.path)  # file_path column
        assert asset_rows[0][5] == "abc123"  # file_hash

    def test_collect_with_multiple_assets(self, db, attempt_row, mock_monitor, mock_collector):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "completed": True,
        }

        assets = [
            _make_asset_record(task_id, attempt_id, "video_00001_.mp4"),
            _make_asset_record(task_id, attempt_id, "video_00002_.mp4"),
        ]
        mock_collector.collect.return_value = CollectResult(success=True, assets=assets)

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        result = service.collect(attempt_id)

        assert result.success is True
        assert len(result.assets) == 2

        asset_rows = db.fetchall("SELECT * FROM assets WHERE task_id = ?", (task_id,))
        assert len(asset_rows) == 2


class TestCollectPolling:
    """Test polling behavior."""

    def test_poll_timeout_marks_failed(self, db, attempt_row, mock_monitor, mock_collector):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "status": "timeout",
        }

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
            poll_timeout=0.1,
        )
        result = service.collect(attempt_id)

        assert result.success is False
        assert "timed out" in result.errors[0].lower() or "timeout" in result.errors[0].lower()

        # Verify task marked as FAILED_RETRYABLE
        task_row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
        assert task_row[0] == TaskStatus.FAILED_RETRYABLE.value

    def test_execution_error_marks_failed(self, db, attempt_row, mock_monitor, mock_collector):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "completed": False,
            "error": "CUDA out of memory",
        }

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        result = service.collect(attempt_id)

        assert result.success is False
        assert "error" in result.errors[0].lower() or "CUDA" in result.errors[0]

        task_row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
        assert task_row[0] == TaskStatus.FAILED_RETRYABLE.value


class TestCollectNoPromptId:
    """Test handling of attempts without prompt_id."""

    def test_no_prompt_id_fails_gracefully(self, db, mock_monitor, mock_collector):
        # Create attempt without prompt_id in submission_journal
        task_id = "task-noprompt"
        attempt_id = "att-noprompt"
        db.execute(
            """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, "proj", "video.h3", "RUNNING", "ph", "dh", "ik"),
        )
        db.execute(
            """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (attempt_id, task_id, "ik", SubmissionState.PREPARED.value, "{}", "ch", "dh", "ph"),
        )
        # No submission_journal row → no prompt_id

        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        result = service.collect(attempt_id)

        assert result.success is False
        assert "prompt_id" in result.errors[0].lower()


class TestCollectAttemptNotFound:
    """Test handling of non-existent attempt."""

    def test_nonexistent_attempt_returns_error(self, db, mock_monitor, mock_collector):
        service = VideoCollectService(
            db=db,
            collector=mock_collector,
            monitor=mock_monitor,
        )
        result = service.collect("nonexistent-attempt")

        assert result.success is False
        assert "not found" in result.errors[0].lower()


class TestCollectNoCollector:
    """Test behavior when no collector is configured."""

    def test_no_collector_fails(self, db, attempt_row, mock_monitor):
        attempt_id, task_id, project_id, prompt_id = attempt_row

        mock_monitor.poll_until_done.return_value = {
            "prompt_id": prompt_id,
            "found": True,
            "completed": True,
        }

        service = VideoCollectService(
            db=db,
            collector=None,
            monitor=mock_monitor,
        )
        result = service.collect(attempt_id)

        assert result.success is False
        assert "no collector" in result.errors[0].lower() or "collector" in result.errors[0].lower()


class TestAssetTypeGuessing:
    """Test asset type guessing from file extension."""

    @pytest.mark.parametrize("ext,expected", [
        (".mp4", "video"),
        (".avi", "video"),
        (".mov", "video"),
        (".png", "image"),
        (".jpg", "image"),
        (".jpeg", "image"),
        (".webp", "image"),
        (".wav", "audio"),
        (".mp3", "audio"),
        (".aac", "audio"),
    ])
    def test_guess_asset_type(self, ext, expected):
        from lfo.services.video_collect_service import VideoCollectService
        assert VideoCollectService._guess_asset_type(Path(f"file{ext}")) == expected

    def test_unknown_extension_defaults_to_video(self):
        from lfo.services.video_collect_service import VideoCollectService
        assert VideoCollectService._guess_asset_type(Path("file.xyz")) == "video"
