"""Isolation tests for the lightweight video review helper."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "qc_video.py"
_SPEC = importlib.util.spec_from_file_location("_lfo_test_qc_video", _SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load {_SCRIPT_PATH}")
qc_video = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qc_video)


def _probe_payload(*, audio: bool = True, duration: object = "2.0") -> str:
    streams = [{"codec_type": "video", "codec_name": "h264", "width": 720, "height": 1280}]
    if audio:
        streams.append({"codec_type": "audio", "codec_name": "aac", "channels": 2, "sample_rate": "48000"})
    return json.dumps({"format": {"duration": duration}, "streams": streams})


def _run_stub(monkeypatch, payload: str, *, volume: str = "") -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> str:
        calls.append(command)
        if command[0] == "ffprobe":
            return payload
        if "-frames:v" in command:
            Path(command[-1]).write_bytes(b"frame")
            return ""
        return volume

    monkeypatch.setattr(qc_video, "run", fake_run)
    return calls


def test_audio_review_runs_one_overall_volume_command(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fixture")
    outdir = tmp_path / "review"
    calls = _run_stub(
        monkeypatch,
        _probe_payload(),
        volume="mean_volume: -20 dB\nmax_volume: -3 dB\n",
    )
    monkeypatch.setattr(sys, "argv", ["qc_video.py", str(video), str(outdir), "2"])

    qc_video.main()

    volume_calls = [call for call in calls if "volumedetect" in call]
    assert len(volume_calls) == 1
    assert (outdir / "audio_report.txt").read_text(encoding="utf-8") == (
        "== overall volumedetect ==\nmean_volume: -20 dB\nmax_volume: -3 dB\n"
    )
    assert len(list(outdir.glob("frame_*.jpg"))) == 2


def test_silent_video_writes_explicit_no_audio_report(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"fixture")
    outdir = tmp_path / "review"
    calls = _run_stub(monkeypatch, _probe_payload(audio=False))
    monkeypatch.setattr(sys, "argv", ["qc_video.py", str(video), str(outdir), "2"])

    qc_video.main()

    assert not any("volumedetect" in call for call in calls)
    assert (outdir / "audio_report.txt").read_text(encoding="utf-8") == (
        "No audio stream; no listening evidence inferred.\n"
    )


def test_missing_video_stream_is_rejected_before_output_directory_creation(
    monkeypatch, tmp_path: Path
) -> None:
    video = tmp_path / "audio-only.mp4"
    video.write_bytes(b"fixture")
    outdir = tmp_path / "review"
    monkeypatch.setattr(
        qc_video,
        "run",
        lambda _command: json.dumps(
            {
                "format": {"duration": "2.0"},
                "streams": [{"codec_type": "audio"}],
            }
        ),
    )
    monkeypatch.setattr(sys, "argv", ["qc_video.py", str(video), str(outdir)])

    with pytest.raises(ValueError, match="no video stream"):
        qc_video.main()
    assert not outdir.exists()


@pytest.mark.parametrize("duration", ["NaN", "Infinity"])
def test_nonfinite_duration_is_rejected(monkeypatch, tmp_path: Path, duration: str) -> None:
    video = tmp_path / "bad-duration.mp4"
    video.write_bytes(b"fixture")
    outdir = tmp_path / "review"
    _run_stub(monkeypatch, _probe_payload(duration=duration))
    monkeypatch.setattr(sys, "argv", ["qc_video.py", str(video), str(outdir)])

    with pytest.raises(ValueError, match="duration"):
        qc_video.main()
    assert not outdir.exists()


def test_frame_extraction_failure_stops_before_audio_analysis(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "bad-frame.mp4"
    video.write_bytes(b"fixture")
    outdir = tmp_path / "review"
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> str:
        calls.append(command)
        if command[0] == "ffprobe":
            return _probe_payload()
        return ""

    monkeypatch.setattr(qc_video, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["qc_video.py", str(video), str(outdir), "2"])

    with pytest.raises(RuntimeError, match="no file"):
        qc_video.main()
    assert not any("volumedetect" in call for call in calls)


def test_media_command_timeout_is_bounded(monkeypatch) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 300)

    monkeypatch.setattr(qc_video.subprocess, "run", timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        qc_video.run(["ffmpeg", "-version"])
