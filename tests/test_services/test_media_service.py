"""Tests for MediaService."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lfo.core.database import Database
from lfo.services.media_service import (
    MediaService,
    StreamSignature,
)


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    # Create project and task for FK constraints
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
        ("task-1", "proj-1", "h3_i2v", "PLANNED"),
    )
    return db


@pytest.fixture
def service(db: Database, tmp_path) -> MediaService:
    return MediaService(
        db,
        ffmpeg_path="/usr/bin/ffmpeg",
        ffprobe_path="/usr/bin/ffprobe",
        output_dir=str(tmp_path / "output"),
    )


def _make_ffprobe_output(
    has_video: bool = True,
    has_audio: bool = True,
    video_codec: str = "h264",
    width: int = 864,
    height: int = 480,
    fps: str = "24/1",
    duration: str = "5.0",
    audio_codec: str = "aac",
    sample_rate: str = "48000",
    channels: int = 2,
) -> dict:
    """Create a mock ffprobe JSON output."""
    streams = []
    if has_video:
        streams.append({
            "codec_type": "video",
            "codec_name": video_codec,
            "width": width,
            "height": height,
            "r_frame_rate": fps,
            "nb_frames": "120",
        })
    if has_audio:
        streams.append({
            "codec_type": "audio",
            "codec_name": audio_codec,
            "sample_rate": sample_rate,
            "channels": channels,
        })
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": duration,
        },
        "streams": streams,
    }


class TestGetStreamSignature:
    def test_extracts_video_info(self, service: MediaService, tmp_path):
        """Extract video stream info from ffprobe output."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")

        ffprobe_output = _make_ffprobe_output()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(ffprobe_output),
                stderr="",
            )
            sig = service.get_stream_signature(str(test_file))

        assert sig.has_video
        assert sig.video_codec == "h264"
        assert sig.video_width == 864
        assert sig.video_height == 480
        assert sig.video_fps == 24.0

    def test_extracts_audio_info(self, service: MediaService, tmp_path):
        """Extract audio stream info from ffprobe output."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")

        ffprobe_output = _make_ffprobe_output()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(ffprobe_output),
                stderr="",
            )
            sig = service.get_stream_signature(str(test_file))

        assert sig.has_audio
        assert sig.audio_codec == "aac"
        assert sig.audio_sample_rate == 48000
        assert sig.audio_channels == 2

    def test_no_audio(self, service: MediaService, tmp_path):
        """Handle file with no audio stream."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")

        ffprobe_output = _make_ffprobe_output(has_audio=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(ffprobe_output),
                stderr="",
            )
            sig = service.get_stream_signature(str(test_file))

        assert sig.has_video
        assert not sig.has_audio

    def test_file_not_found(self, service: MediaService):
        with pytest.raises(FileNotFoundError):
            service.get_stream_signature("/nonexistent/file.mp4")

    def test_ffprobe_failure(self, service: MediaService, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Invalid data",
            )
            with pytest.raises(RuntimeError, match="ffprobe failed"):
                service.get_stream_signature(str(test_file))


class TestNormalize:
    def test_normalize_success(self, service: MediaService, db: Database, tmp_path):
        """Normalize a video asset to standard format."""
        # Create asset in DB
        test_file = tmp_path / "input.mp4"
        test_file.write_text("fake video")
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'video', ?, ?, ?)""",
            ("asset-1", "task-1", str(test_file), "fh", "ch"),
        )

        ffprobe_output = _make_ffprobe_output()

        def mock_run(cmd, **kwargs):
            # Simulate FFmpeg creating the output file
            output_path = cmd[-1]
            with open(output_path, "wb") as f:
                f.write(b"normalized_output")
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(MediaService, "get_stream_signature") as mock_sig:
            # get_stream_signature returns same info for input and output
            mock_sig.return_value = StreamSignature(
                file_path=str(test_file),
                has_video=True,
                video_codec="h264",
                video_width=864,
                video_height=480,
                video_fps=24.0,
                has_audio=True,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration_sec=5.0,
            )
            result = service.normalize("asset-1", "standard")

        assert result.asset_id != "asset-1"  # new asset ID generated
        assert result.video_codec == "h264"
        assert result.audio_codec == "aac"
        assert result.audio_sample_rate == 48000
        assert result.audio_channels == 2

    def test_normalize_asset_not_found(self, service: MediaService):
        with pytest.raises(FileNotFoundError, match="not found in database"):
            service.normalize("nonexistent", "standard")

    def test_normalize_generates_silent_audio(
        self, service: MediaService, db: Database, tmp_path
    ):
        """Generate silent audio when source has no audio."""
        test_file = tmp_path / "no_audio.mp4"
        test_file.write_text("fake video")
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'video', ?, ?, ?)""",
            ("asset-2", "task-1", str(test_file), "fh", "ch"),
        )

        ffprobe_output = _make_ffprobe_output(has_audio=False)

        def mock_run(cmd, **kwargs):
            output_path = cmd[-1]
            with open(output_path, "wb") as f:
                f.write(b"normalized_output")
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(MediaService, "get_stream_signature") as mock_sig:
            mock_sig.return_value = StreamSignature(
                file_path=str(test_file),
                has_video=True,
                video_codec="h264",
                video_width=864,
                video_height=480,
                video_fps=24.0,
                has_audio=False,
                duration_sec=5.0,
            )
            result = service.normalize("asset-2", "standard")

        assert result.audio_codec == "aac"
        assert result.audio_sample_rate == 48000


class TestCreateSelectedClip:
    def test_clip_extraction(self, service: MediaService, db: Database, tmp_path):
        """Extract a clip by frame range."""
        test_file = tmp_path / "normalized.mp4"
        test_file.write_text("fake video")
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'video', ?, ?, ?)""",
            ("norm-1", "task-1", str(test_file), "fh", "ch"),
        )

        ffprobe_output = _make_ffprobe_output(fps="24/1", duration="5.0")
        with patch("subprocess.run") as mock_run, \
             patch.object(MediaService, "get_stream_signature") as mock_sig:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(ffprobe_output),
                stderr="",
            )
            mock_sig.return_value = StreamSignature(
                file_path=str(test_file),
                has_video=True,
                video_codec="h264",
                video_width=864,
                video_height=480,
                video_fps=24.0,
                has_audio=True,
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                duration_sec=5.0,
            )
            result = service.create_selected_clip("norm-1", in_frame=10, out_frame_exclusive=50)

        assert result.in_frame == 10
        assert result.out_frame_exclusive == 50
        assert result.frame_count > 0

    def test_invalid_frame_range(self, service: MediaService, db: Database, tmp_path):
        """Reject invalid frame ranges."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'video', ?, ?, ?)""",
            ("norm-2", "task-1", str(test_file), "fh", "ch"),
        )

        with pytest.raises(ValueError, match="must be > in_frame"):
            service.create_selected_clip("norm-2", in_frame=50, out_frame_exclusive=10)

    def test_negative_in_frame(self, service: MediaService, db: Database, tmp_path):
        """Reject negative in_frame."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("fake")
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'video', ?, ?, ?)""",
            ("norm-3", "task-1", str(test_file), "fh", "ch"),
        )

        with pytest.raises(ValueError, match="in_frame must be >= 0"):
            service.create_selected_clip("norm-3", in_frame=-1, out_frame_exclusive=10)


class TestStreamSignature:
    def test_defaults(self):
        sig = StreamSignature(file_path="/test.mp4")
        assert sig.has_video is False
        assert sig.has_audio is False
        assert sig.video_width == 0
        assert sig.audio_channels == 0
