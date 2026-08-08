"""Tests for TechnicalQCService."""
from __future__ import annotations

import json

import pytest

from lfo.core.database import Database
from lfo.services.technical_qc_service import (
    QCSpec,
    TechnicalQCService,
)


@pytest.fixture
def db() -> Database:
    """Create a fresh in-memory database."""
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def asset_row(db):
    """Create an asset row, return asset_id."""
    asset_id = "asset-001"
    task_id = "task-001"
    attempt_id = "att-001"
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, "proj-1", "video.h3", "SUCCEEDED", "ph", "dh", "ik"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (attempt_id, task_id, "ik", "COMPLETED", "{}", "ch", "dh", "ph"),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path,
                               file_hash, file_size, width, height, duration, frame_count, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, task_id, attempt_id, "video", "/tmp/video.mp4",
            "sha256abc", 1024000, 864, 480, 5.167, 124,
            json.dumps({"codec": "h264", "fps": 24.0, "has_audio": True}),
        ),
    )
    return asset_id, task_id, attempt_id


class TestQCPass:
    """Test QC pass scenarios."""

    def test_all_checks_pass(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(
            width=864,
            height=480,
            fps=24.0,
            duration_sec=5.167,
            requires_audio=True,
            expected_video_codec="h264",
        )
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.passed is True
        assert result.status == "PASS"
        assert len(result.issues) == 0

    def test_qc_report_written_to_db(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(width=864, height=480)
        service = TechnicalQCService(db)
        service.check_asset(asset_id, spec)

        rows = db.fetchall("SELECT * FROM qc_reports WHERE asset_id = ?", (asset_id,))
        assert len(rows) == 1
        assert rows[0][4] == "PASS"  # status column


class TestQCFail:
    """Test QC fail scenarios."""

    def test_width_mismatch_fails(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(width=1920)  # asset is 864
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert result.status == "FAIL"
        assert any("width" in issue.lower() for issue in result.issues)

    def test_height_mismatch_fails(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(height=1080)  # asset is 480
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert any("height" in issue.lower() for issue in result.issues)

    def test_fps_mismatch_fails(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(fps=30.0)  # asset is 24.0
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert any("fps" in issue.lower() for issue in result.issues)

    def test_duration_out_of_range_fails(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(duration_sec=10.0, duration_tolerance_sec=0.5)  # asset is 5.167
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert any("duration" in issue.lower() for issue in result.issues)

    def test_missing_audio_fails(self, db):
        asset_id = "asset-noaudio"
        task_id = "task-noaudio"
        db.execute(
            """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, "proj-1", "video.h3", "SUCCEEDED", "ph", "dh", "ik"),
        )
        db.execute(
            """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (asset_id, task_id, None, "video", "/tmp/video.mp4",
             json.dumps({"has_audio": False})),
        )

        spec = QCSpec(requires_audio=True)
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert any("audio" in issue.lower() for issue in result.issues)

    def test_wrong_codec_fails(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(expected_video_codec="h265")  # asset is h264
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.failed is True
        assert any("codec" in issue.lower() for issue in result.issues)


class TestQCAssetNotFound:
    """Test handling of non-existent asset."""

    def test_nonexistent_asset_returns_fail(self, db):
        spec = QCSpec(width=864)
        service = TechnicalQCService(db)
        result = service.check_asset("nonexistent", spec)

        assert result.failed is True
        assert "not found" in result.issues[0].lower()


class TestQCDurationTolerance:
    """Test duration tolerance edge cases."""

    def test_duration_within_tolerance_passes(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        # Asset duration is 5.167, spec is 5.0 with tolerance 0.5
        spec = QCSpec(duration_sec=5.0, duration_tolerance_sec=0.5)
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.passed is True

    def test_duration_at_tolerance_boundary(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        # Asset duration is 5.167, spec is 5.667 with tolerance 0.5 → boundary
        spec = QCSpec(duration_sec=5.667, duration_tolerance_sec=0.5)
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        assert result.passed is True  # exactly at boundary


class TestQCChecksStructure:
    """Test the structure of QC check results."""

    def test_checks_have_names(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(width=864, height=480, fps=24.0)
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        check_names = [c.name for c in result.checks]
        assert "width" in check_names
        assert "height" in check_names
        assert "fps" in check_names

    def test_failed_check_has_message(self, db, asset_row):
        asset_id, task_id, _ = asset_row
        spec = QCSpec(width=1920)  # wrong
        service = TechnicalQCService(db)
        result = service.check_asset(asset_id, spec)

        width_check = next(c for c in result.checks if c.name == "width")
        assert width_check.passed is False
        assert len(width_check.message) > 0
        assert "1920" in width_check.expected
        assert "864" in width_check.actual
