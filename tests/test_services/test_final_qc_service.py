"""Tests for FinalQCService."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lfo.core.database import Database
from lfo.services.final_qc_service import FinalQCService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
        ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"),
    )
    return db


def _make_probe_output(
    width=1080,
    height=1920,
    fps="24/1",
    duration="10.0",
    video_codec="h264",
    has_audio=True,
    audio_codec="aac",
    sample_rate="48000",
    channels=2,
) -> dict:
    streams = [
        {
            "codec_type": "video",
            "codec_name": video_codec,
            "width": width,
            "height": height,
            "r_frame_rate": fps,
        }
    ]
    if has_audio:
        streams.append({
            "codec_type": "audio",
            "codec_name": audio_codec,
            "sample_rate": sample_rate,
            "channels": channels,
        })
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": duration},
        "streams": streams,
    }


class TestFinalQCService:
    def _make_video_asset(self, db, tmp_path, asset_id="video-1"):
        path = tmp_path / f"{asset_id}.mp4"
        path.write_bytes(b"fake_video_data")
        db.execute(
            """INSERT INTO assets (asset_id, task_id, asset_type, file_path, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (asset_id, "task-1", "video", str(path), "{}"),
        )
        return str(path)

    def test_validate_passes_for_valid_video(self, db, tmp_path):
        video_path = self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output()

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1", expected_duration_sec=10.0)

        assert result.success
        assert len(result.issues) == 0

    def test_validate_detects_wrong_resolution(self, db, tmp_path):
        self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output(width=1920, height=1080)

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1")

        assert not result.success
        width_issues = [i for i in result.issues if "Width" in i or "Height" in i]
        assert len(width_issues) > 0

    def test_validate_detects_wrong_fps(self, db, tmp_path):
        self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output(fps="30/1")

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1")

        assert not result.success
        fps_issues = [i for i in result.issues if "FPS" in i]
        assert len(fps_issues) > 0

    def test_validate_detects_no_audio(self, db, tmp_path):
        self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output(has_audio=False)

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1")

        assert not result.success
        audio_issues = [i for i in result.issues if "audio" in i.lower()]
        assert len(audio_issues) > 0

    def test_validate_detects_duration_mismatch(self, db, tmp_path):
        self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output(duration="5.0")

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1", expected_duration_sec=10.0)

        assert not result.success
        dur_issues = [i for i in result.issues if "Duration mismatch" in i]
        assert len(dur_issues) > 0

    def test_validate_video_not_found(self, db, tmp_path):
        svc = FinalQCService(db=db)
        result = svc.validate("nonexistent")
        assert not result.success
        assert any("not found" in i for i in result.issues)

    def test_validate_srt_time_exceeds_video(self, db, tmp_path):
        video_path = self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output(duration="5.0")

        # Create SRT asset with cue ending after video duration
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:10,000\nText exceeds video\n",
            encoding="utf-8",
        )
        db.execute(
            """INSERT INTO assets (asset_id, task_id, asset_type, file_path, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            ("srt-1", "task-1", "subtitle", str(srt_path), "{}"),
        )

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            result = svc.validate("video-1", srt_asset_id="srt-1")

        assert not result.success
        srt_issues = [i for i in result.issues if "SRT cue ends" in i]
        assert len(srt_issues) > 0

    def test_validate_writes_qc_report(self, db, tmp_path):
        self._make_video_asset(db, tmp_path)
        probe_data = _make_probe_output()

        svc = FinalQCService(db=db, ffprobe_path="/usr/bin/ffprobe")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)

        with patch("subprocess.run", return_value=mock_proc):
            svc.validate("video-1")

        # Verify qc_reports row was written
        row = db.fetchone(
            "SELECT status FROM qc_reports WHERE asset_id = ?",
            ("video-1",),
        )
        assert row is not None
        assert row[0] == "PASS"
