"""Tests for Wave 2-B: advanced Final QC (black frame, freeze frame, AV sync)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lfo.core.database import Database
from lfo.services.final_qc_service import FinalQCService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def _make_probe_output(
    width=1080, height=1920, fps="24/1", duration="10.0",
    video_codec="h264", has_audio=True, audio_codec="aac",
    sample_rate="48000", channels=2,
) -> dict:
    streams = [
        {"codec_type": "video", "codec_name": video_codec, "width": width, "height": height, "r_frame_rate": fps},
    ]
    if has_audio:
        streams.append({"codec_type": "audio", "codec_name": audio_codec, "sample_rate": sample_rate, "channels": channels})
    return {"format": {"format_name": "mov,mp4", "duration": duration}, "streams": streams}


class TestAdvancedQC:
    def test_black_frame_check_pass(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg")

        mock_proc = MagicMock()
        mock_proc.stderr = "[blackframe @ 0x123] pblack: 5%"
        with patch("subprocess.run", return_value=mock_proc):
            check = svc._check_black_frames(str(video))

        assert check.name == "black_frames"
        assert check.passed is True

    def test_black_frame_check_fail(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg")

        mock_proc = MagicMock()
        mock_proc.stderr = "[blackframe @ 0x123] pblack: 95%"
        with patch("subprocess.run", return_value=mock_proc):
            check = svc._check_black_frames(str(video))

        assert check.passed is False
        assert "95.0%" in check.actual

    def test_freeze_frame_check_pass(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg")

        mock_proc = MagicMock()
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc):
            check = svc._check_freeze_frames(str(video))

        assert check.name == "freeze_frames"
        assert check.passed is True

    def test_freeze_frame_check_fail(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg")

        mock_proc = MagicMock()
        mock_proc.stderr = "[freezedetect @ 0x1] freeze_start: 1.0\n[freezedetect @ 0x1] freeze_end: 3.0"
        with patch("subprocess.run", return_value=mock_proc):
            check = svc._check_freeze_frames(str(video))

        assert check.passed is False
        assert check.actual == "2"

    def test_av_sync_pass(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg", ffprobe_path="/usr/bin/ffprobe")

        probe_output = _make_probe_output(duration="10.0")
        audio_dur_output = "10.0"

        def mock_run(cmd, **kwargs):
            m = MagicMock()
            if "-show_streams" in cmd:
                m.returncode = 0
                m.stdout = json.dumps(probe_output)
            elif "-select_streams" in cmd:
                m.returncode = 0
                m.stdout = audio_dur_output
            else:
                m.returncode = 0
                m.stdout = ""
            return m

        import json
        with patch("subprocess.run", side_effect=mock_run):
            check = svc._check_av_sync(str(video))

        assert check.name == "av_sync"
        assert check.passed is True

    def test_av_sync_fail(self, db, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg", ffprobe_path="/usr/bin/ffprobe")

        probe_output = _make_probe_output(duration="10.0")
        audio_dur_output = "8.0"  # 2 second delta

        import json
        def mock_run(cmd, **kwargs):
            m = MagicMock()
            if "-show_streams" in cmd:
                m.returncode = 0
                m.stdout = json.dumps(probe_output)
            elif "-select_streams" in cmd:
                m.returncode = 0
                m.stdout = audio_dur_output
            else:
                m.returncode = 0
                m.stdout = ""
            return m

        with patch("subprocess.run", side_effect=mock_run):
            check = svc._check_av_sync(str(video))

        assert check.passed is False
        assert "2.0" in check.actual

    def test_validate_advanced_runs_all_checks(self, db, tmp_path):
        """validate_advanced should include black frame, freeze frame, AV sync."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("task-1", "proj-1", "video", "SUCCEEDED"))
        db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path) VALUES (?, ?, ?, ?)",
                   ("vid-1", "task-1", "video", str(video)))

        svc = FinalQCService(db=db, ffmpeg_path="/usr/bin/ffmpeg", ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = ""

        probe_output = _make_probe_output(duration="5.0")

        import json
        def mock_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "-show_streams" in cmd:
                m.stdout = json.dumps(probe_output)
            elif "-select_streams" in cmd:
                m.stdout = "5.0"
            else:
                m.stdout = ""
                m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=mock_run):
            result = svc.validate_advanced("vid-1", expected_duration_sec=5.0)

        check_names = [c.name for c in result.checks]
        assert "black_frames" in check_names
        assert "freeze_frames" in check_names
        assert "av_sync" in check_names
