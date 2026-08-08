"""Tests for EndFrameExtractor."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from lfo.core.database import Database
from lfo.services.end_frame_extractor import EndFrameExtractor, EndFrameResult


@pytest.fixture
def db() -> Database:
    """Create a fresh in-memory database."""
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def video_asset(db):
    """Create a video asset row, return asset_id."""
    asset_id = "asset-video-001"
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
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, frame_count, width, height)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, task_id, attempt_id, "video", "/tmp/fake_video.mp4",
            json.dumps({"codec": "h264", "fps": 24.0, "frames": 124}),
            124, 864, 480,
        ),
    )
    return asset_id, task_id


class TestExtractSuccess:
    """Test successful end frame extraction."""

    def test_extract_registers_frame_asset(self, db, video_asset, tmp_path):
        asset_id, task_id = video_asset
        output_dir = str(tmp_path / "frames")
        os.makedirs(output_dir, exist_ok=True)

        # Create a fake video file so os.path.exists passes
        fake_video = tmp_path / "test_video.mp4"
        fake_video.write_bytes(b"fake_video_data")

        # Update asset to point to the real temp file
        db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?",
                    (str(fake_video), asset_id))

        extractor = EndFrameExtractor(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            output_dir=output_dir,
        )

        with patch.object(extractor, "_extract_frame") as mock_extract:
            # Create a fake output file (as if FFmpeg wrote it)
            expected_output = os.path.join(output_dir, "frame.png")
            with open(expected_output, "wb") as f:
                f.write(b"fake_png_data")
            mock_extract.return_value = None

            result = extractor.extract(asset_id)

        # The result should have a frame_asset_id
        assert result.source_asset_id == asset_id
        assert result.success is True
        assert result.frame_asset_id != ""

    def test_extract_creates_asset_relation(self, db, video_asset, tmp_path):
        asset_id, task_id = video_asset
        output_dir = str(tmp_path / "frames")
        os.makedirs(output_dir, exist_ok=True)

        fake_video = tmp_path / "test_video.mp4"
        fake_video.write_bytes(b"fake_video_data")
        db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?",
                    (str(fake_video), asset_id))

        extractor = EndFrameExtractor(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            output_dir=output_dir,
        )

        with patch.object(extractor, "_extract_frame") as mock_extract:
            expected_output = os.path.join(output_dir, "frame.png")
            with open(expected_output, "wb") as f:
                f.write(b"fake_png_data")
            mock_extract.return_value = None
            result = extractor.extract(asset_id)

        # Check asset_relation was created
        rows = db.fetchall(
            "SELECT * FROM asset_relations WHERE source_asset_id = ?",
            (asset_id,),
        )
        assert len(rows) == 1
        assert rows[0][1] == asset_id  # source_asset_id
        assert rows[0][2] == result.frame_asset_id  # target_asset_id
        assert rows[0][3] == "derived_from"  # relation_type


class TestExtractAssetNotFound:
    """Test handling of non-existent asset."""

    def test_nonexistent_asset_returns_error(self, db, tmp_path):
        extractor = EndFrameExtractor(
            db=db,
            output_dir=str(tmp_path / "frames"),
        )
        result = extractor.extract("nonexistent-asset")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestExtractFrameFFmpeg:
    """Test the actual FFmpeg extraction logic (mocked subprocess)."""

    def test_extract_frame_calls_ffmpeg(self, db, video_asset, tmp_path):
        asset_id, task_id = video_asset
        output_dir = str(tmp_path / "frames")
        os.makedirs(output_dir, exist_ok=True)

        extractor = EndFrameExtractor(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            output_dir=output_dir,
        )

        output_path = os.path.join(output_dir, "test.png")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Create the expected output file
            with open(output_path, "wb") as f:
                f.write(b"png")

            extractor._extract_frame("/tmp/fake_video.mp4", output_path)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "ffmpeg" in call_args[0] or "-sseof" in call_args
            assert "-frames:v" in call_args

    def test_extract_frame_failure_raises(self, db, video_asset, tmp_path):
        asset_id, task_id = video_asset
        output_dir = str(tmp_path / "frames")
        os.makedirs(output_dir, exist_ok=True)

        extractor = EndFrameExtractor(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            output_dir=output_dir,
        )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: No such file"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="FFmpeg failed"):
                extractor._extract_frame("/tmp/fake_video.mp4", "/tmp/out.png")


class TestExtractFromClip:
    """Test extract_from_clip domain entry point."""

    def _create_approved_clip(self, db, clip_id="clip-1", asset_id="norm-1"):
        """Helper to insert an approved selected clip with output_asset_id."""
        db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            ("proj-1", "Test"),
        )
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
            ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"),
        )
        db.execute(
            """INSERT INTO assets (asset_id, task_id, asset_type, file_path, metadata, frame_count, width, height)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id, "task-1", "video", "/tmp/fake_video.mp4",
                json.dumps({"codec": "h264", "fps": 24.0, "frames": 124}),
                124, 864, 480,
            ),
        )
        db.execute(
            """INSERT INTO selected_clips
               (selected_clip_id, project_id, shot_id, normalized_asset_id,
                output_asset_id, selected_in_frame, selected_out_frame_exclusive,
                fps_num, fps_den, render_policy_id, revision, status,
                content_hash, dependency_hash, created_at, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clip_id, "proj-1", "shot-1", asset_id,
                asset_id, 0, 124, 24, 1, "selected_clip_v1", 1, "approved",
                "ch", "dh", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
            ),
        )

    def test_extract_from_approved_clip(self, db, tmp_path):
        self._create_approved_clip(db)
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"fake")
        db.execute(
            "UPDATE assets SET file_path = ? WHERE asset_id = ?",
            (str(fake_video), "norm-1"),
        )

        output_dir = tmp_path / "frames"
        output_dir.mkdir(parents=True, exist_ok=True)
        extractor = EndFrameExtractor(db=db, output_dir=str(output_dir))

        with patch.object(extractor, "_extract_frame") as mock_extract:
            expected_output = output_dir / "frame.png"
            expected_output.write_bytes(b"png")
            mock_extract.return_value = None

            result = extractor.extract_from_clip("clip-1")

        assert result.success is True
        assert result.source_asset_id == "norm-1"

        # Verify end_frame_from relation was created (in addition to derived_from)
        rel = db.fetchone(
            """SELECT relation_type, metadata FROM asset_relations
               WHERE source_asset_id = ? AND relation_type = 'end_frame_from'""",
            ("norm-1",),
        )
        assert rel is not None
        assert rel[0] == "end_frame_from"
        meta = json.loads(rel[1])
        assert meta["selected_clip_id"] == "clip-1"
        assert meta["shot_id"] == "shot-1"

    def test_clip_not_found_raises(self, db, tmp_path):
        extractor = EndFrameExtractor(db=db, output_dir=str(tmp_path / "frames"))
        with pytest.raises(ValueError, match="not found"):
            extractor.extract_from_clip("nonexistent")

    def test_clip_not_approved_raises(self, db, tmp_path):
        self._create_approved_clip(db, clip_id="clip-draft")
        db.execute(
            "UPDATE selected_clips SET status = 'draft' WHERE selected_clip_id = ?",
            ("clip-draft",),
        )
        extractor = EndFrameExtractor(db=db, output_dir=str(tmp_path / "frames"))
        with pytest.raises(ValueError, match="must be 'approved'"):
            extractor.extract_from_clip("clip-draft")

    def test_clip_no_output_asset_raises(self, db, tmp_path):
        self._create_approved_clip(db, clip_id="clip-no-output")
        db.execute(
            "UPDATE selected_clips SET output_asset_id = NULL WHERE selected_clip_id = ?",
            ("clip-no-output",),
        )
        extractor = EndFrameExtractor(db=db, output_dir=str(tmp_path / "frames"))
        with pytest.raises(ValueError, match="no output_asset_id"):
            extractor.extract_from_clip("clip-no-output")


class TestEndFrameResult:
    """Test EndFrameResult dataclass defaults."""

    def test_default_values(self):
        result = EndFrameResult(source_asset_id="test")
        assert result.success is False
        assert result.frame_asset_id == ""
        assert result.error == ""

    def test_success_result(self):
        result = EndFrameResult(
            source_asset_id="test",
            frame_asset_id="frame-123",
            file_path="/tmp/frame.png",
            frame_number=124,
            success=True,
        )
        assert result.success is True
        assert result.frame_number == 124
