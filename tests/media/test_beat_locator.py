from __future__ import annotations

import array
import math
import wave
from itertools import pairwise
from pathlib import Path

import pytest

from lfo.media._ffmpeg import run_command
from lfo.media.beat_locator import analyze_window


def _write_click_track(path: Path, *, bpm: float = 120.0, seconds: float = 12.0, rate: int = 22050) -> None:
    """Write a click track whose attacks land on a known tempo."""
    period = 60.0 / bpm
    samples = array.array("h")
    for index in range(int(rate * seconds)):
        moment = index / rate
        value = 0.0
        if (moment % period) < 0.03:
            value = 0.7 * math.sin(2 * math.pi * 900 * moment)
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


class TestBuiltinBeatLocator:
    def test_click_track_reports_the_known_tempo_as_candidate(self, tmp_path):
        path = tmp_path / "click.wav"
        _write_click_track(path, bpm=120.0)
        located = analyze_window(path, start_ms=0, end_ms=12000)
        bpm_values = [entry["bpm"] for entry in located["bpm_candidates"]]
        assert any(abs(value - 120.0) <= 3.0 for value in bpm_values), bpm_values
        assert all(entry["status"] == "candidate" for entry in located["bpm_candidates"])

    def test_beats_land_on_the_click_positions(self, tmp_path):
        path = tmp_path / "click.wav"
        _write_click_track(path, bpm=120.0)
        located = analyze_window(path, start_ms=0, end_ms=12000)
        beats = located["beats"]
        assert len(beats) >= 15, len(beats)
        assert all(beat["status"] == "candidate" for beat in beats)
        times = [beat["time_ms"] for beat in beats]
        assert times == sorted(times) and len(set(times)) == len(times)
        for moment in times:
            offset = moment % 500
            assert min(offset, 500 - offset) <= 90, moment
        intervals = [later - earlier for earlier, later in pairwise(times)]
        assert all(430 <= gap <= 570 for gap in intervals), intervals

    def test_silence_produces_no_tempo_or_beat(self, tmp_path):
        path = tmp_path / "silence.flac"
        run_command(["ffmpeg", "-v", "error", "-f", "lavfi",
                     "-i", "anullsrc=r=22050:cl=mono", "-t", "3", "-c:a", "flac", str(path)])
        located = analyze_window(path, start_ms=0, end_ms=3000)
        assert located["bpm_candidates"] == []
        assert located["beats"] == []
        assert located["energy"]


class TestAnalyzeMusicFallback:
    def test_analysis_runs_without_librosa_and_records_its_analyzer(self, tmp_path):
        from lfo.media.music_analysis import analyze_music

        path = tmp_path / "click.wav"
        _write_click_track(path, bpm=120.0)
        result = analyze_music(path)
        assert result["schema"] == "lfo.mv.music-timeline.v1"
        assert result["analysis"]["analyzer"] in {"builtin.autocorrelation", "librosa.beat"}
        assert result["lyrics"] == result["sections"] == []
        assert result["listening_status"] == "INCONCLUSIVE"
        assert all(beat["status"] == "candidate" for beat in result["beats"])


@pytest.mark.parametrize("bpm", [90.0, 120.0, 150.0])
def test_several_tempos_are_recovered(bpm, tmp_path):
    path = tmp_path / f"click-{int(bpm)}.wav"
    _write_click_track(path, bpm=bpm)
    located = analyze_window(path, start_ms=0, end_ms=12000)
    values = [entry["bpm"] for entry in located["bpm_candidates"]]
    assert any(abs(value - bpm) <= 4.0 for value in values), values
    times = [beat["time_ms"] for beat in located["beats"]]
    period = 60.0 / bpm
    for moment in times:
        offset = moment % (period * 1000)
        assert min(offset, period * 1000 - offset) <= 90, moment
