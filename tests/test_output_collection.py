"""Unit tests for ComfyOutputCollector."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lfo.comfy.collect import ComfyOutputCollector, MediaInfo
from lfo.comfy.exceptions import OutputNotFoundError, OutputUnstableError

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Create a temporary output root with a sample attempt directory."""
    attempt_dir = tmp_path / "lfo" / "attempt-001"
    attempt_dir.mkdir(parents=True)
    # Create a fake video file
    (attempt_dir / "video_00001_.mp4").write_bytes(b"fake video data" * 100)
    return tmp_path


@pytest.fixture
def collector(tmp_output: Path, tmp_path: Path) -> ComfyOutputCollector:
    assets_dir = tmp_path / "assets"
    return ComfyOutputCollector(output_root=tmp_output, assets_dir=assets_dir)


@pytest.fixture
def db_record() -> dict:
    return {
        "attempt_dir": "lfo/attempt-001",
        "project_id": "proj-1",
        "task_id": "task-1",
        "attempt_id": "attempt-001",
    }


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


class TestDiscover:
    def test_discovers_matching_files(self, collector, tmp_output):
        files = collector.discover("lfo/attempt-001")
        assert len(files) == 1
        assert files[0].name == "video_00001_.mp4"

    def test_empty_dir_returns_empty(self, collector, tmp_output):
        empty_dir = tmp_output / "lfo" / "empty-attempt"
        empty_dir.mkdir(parents=True)
        files = collector.discover("lfo/empty-attempt")
        assert files == []

    def test_missing_dir_raises(self, collector):
        with pytest.raises(OutputNotFoundError):
            collector.discover("lfo/nonexistent")

    def test_custom_extensions(self, collector, tmp_output):
        # Add a .png file
        attempt_dir = tmp_output / "lfo" / "attempt-001"
        (attempt_dir / "thumb.png").write_bytes(b"png")
        files = collector.discover("lfo/attempt-001", extensions={".png"})
        assert len(files) == 1
        assert files[0].suffix == ".png"


class TestWaitUntilStable:
    def test_stable_file_passes(self, collector, tmp_output):
        fpath = tmp_output / "lfo" / "attempt-001" / "video_00001_.mp4"
        assert collector.wait_until_stable(fpath, checks=2, interval=0.01) is True

    def test_missing_file_raises(self, collector, tmp_output):
        fpath = tmp_output / "nonexistent.mp4"
        with pytest.raises(OutputNotFoundError):
            collector.wait_until_stable(fpath)


class TestValidateMedia:
    def test_returns_empty_info_when_ffprobe_missing(self, collector, tmp_output):
        fpath = tmp_output / "lfo" / "attempt-001" / "video_00001_.mp4"
        with patch("subprocess.run", side_effect=FileNotFoundError):
            info = collector.validate_media(fpath)
        assert isinstance(info, MediaInfo)
        assert info.codec == ""

    def test_parses_ffprobe_output(self, collector, tmp_output):
        fpath = tmp_output / "lfo" / "attempt-001" / "video_00001_.mp4"
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "nb_frames": "124",
                    "r_frame_rate": "24/1",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "5.167"},
        }

        mock_result = type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps(ffprobe_output),
            "stderr": "",
        })()

        with patch("subprocess.run", return_value=mock_result):
            info = collector.validate_media(fpath)

        assert info.codec == "h264"
        assert info.width == 1920
        assert info.height == 1080
        assert info.frames == 124
        assert info.fps == 24.0
        assert info.duration == 5.167
        assert info.has_audio is True


class TestRegisterAsset:
    def test_registers_with_sha256(self, collector, tmp_output):
        fpath = tmp_output / "lfo" / "attempt-001" / "video_00001_.mp4"
        record = collector.register_asset(
            fpath, "proj-1", "task-1", "attempt-001"
        )
        # When assets_dir is configured, file is copied there
        assert record.path.name == fpath.name
        assert record.path.exists()
        assert len(record.sha256) == 64
        assert record.project_id == "proj-1"
        assert record.size_bytes > 0

    def test_copies_to_assets_dir(self, collector, tmp_output):
        fpath = tmp_output / "lfo" / "attempt-001" / "video_00001_.mp4"
        record = collector.register_asset(
            fpath, "proj-1", "task-1", "attempt-001"
        )
        assert record.path.parent.name == "attempt-001"
        assert record.path.exists()

    def test_missing_file_raises(self, collector):
        with pytest.raises(FileNotFoundError):
            collector.register_asset(
                Path("/nonexistent/file.mp4"), "p", "t", "a"
            )


class TestCollect:
    def test_full_pipeline(self, collector, db_record, tmp_output):
        # Mock validate_media to return valid info
        with patch.object(
            collector,
            "validate_media",
            return_value=MediaInfo(codec="h264", width=1920, height=1080, frames=124),
        ):
            result = collector.collect(db_record)
        assert result.success is True
        assert len(result.assets) == 1
        assert result.assets[0].media_info.codec == "h264"

    def test_missing_dir_fails_gracefully(self, collector):
        record = {
            "attempt_dir": "lfo/missing",
            "project_id": "p",
            "task_id": "t",
            "attempt_id": "a",
        }
        result = collector.collect(record)
        assert result.success is False
        assert len(result.errors) > 0

    def test_unstable_file_skipped(self, collector, db_record, tmp_output):
        with patch.object(
            collector, "wait_until_stable", side_effect=OutputUnstableError("still writing")
        ):
            result = collector.collect(db_record)
        assert result.success is False
        assert any("Unstable" in e for e in result.errors)
