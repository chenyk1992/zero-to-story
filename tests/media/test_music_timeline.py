from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lfo.media._ffmpeg import run_command


def make_audio(path: Path, duration: float = 2) -> None:
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", f"sine=frequency=440:duration={duration}", "-c:a", "flac", str(path)])


def test_inspect_binds_actual_audio_and_middle_window(tmp_path):
    from lfo.media.music_timeline import inspect_music, validate_music_timeline

    path = tmp_path / "song.flac"
    make_audio(path)
    timeline = inspect_music(path, start_ms=500, end_ms=1500)
    assert timeline["schema"] == "lfo.mv.music-timeline.v1"
    assert timeline["source"]["duration_ms"] == 2000
    assert timeline["window"] == {"start_ms": 500, "end_ms": 1500}
    assert timeline["lyrics"] == timeline["sections"] == timeline["beats"] == []
    assert validate_music_timeline(timeline) == timeline


def test_same_named_replacement_invalidates_verified_timing(tmp_path):
    from lfo.media.music_timeline import inspect_music, validate_music_timeline

    path = tmp_path / "song.flac"
    make_audio(path)
    timeline = inspect_music(path)
    path.unlink()
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=880:duration=2", "-c:a", "flac", str(path)])
    with pytest.raises(ValueError, match="SHA-256"):
        validate_music_timeline(timeline)


def test_window_and_lyric_layers_are_validated(tmp_path):
    from lfo.media.music_timeline import inspect_music, validate_music_timeline

    path = tmp_path / "song.flac"
    make_audio(path)
    timeline = inspect_music(path, start_ms=300, end_ms=1700)
    timeline["lyrics"] = [
        {"start_ms": 400, "end_ms": 1000, "text": "雨停了", "layer": "lead", "status": "verified"},
        {"start_ms": 700, "end_ms": 1100, "text": "和声", "layer": "backing", "status": "verified"},
    ]
    validate_music_timeline(timeline)
    conflicting = copy.deepcopy(timeline)
    conflicting["lyrics"][1]["layer"] = "lead"
    with pytest.raises(ValueError, match="重叠"):
        validate_music_timeline(conflicting)
    for invalid in (True, float("nan"), -1, 2001, 10**1000):
        changed = copy.deepcopy(timeline)
        changed["window"]["end_ms"] = invalid
        with pytest.raises(ValueError):
            validate_music_timeline(changed, verify_source=False)
    changed = copy.deepcopy(timeline)
    changed["lyrics"][0]["start_ms"] = 200
    with pytest.raises(ValueError):
        validate_music_timeline(changed, verify_source=False)


def test_music_tools_cli_inspect_and_refuse_overwrite(tmp_path):
    path = tmp_path / "song.flac"
    make_audio(path)
    script = Path(__file__).resolve().parents[2] / ".agents/skills/music-video-creator/scripts/music_tools.py"
    output = tmp_path / "timeline.json"
    command = [sys.executable, str(script), "inspect", "--audio", str(path), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    saved = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0 and output.read_bytes() == saved
