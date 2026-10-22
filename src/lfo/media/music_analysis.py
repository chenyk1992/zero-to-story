"""Optional, unverified beat and energy candidates for an adopted song."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from lfo.media.beat_locator import analyze_window
from lfo.media.music_timeline import inspect_music, validate_music_timeline


def _analyze_builtin(path: Path, timeline: dict[str, Any]) -> dict[str, Any]:
    """Locate candidates with the dependency-free locator."""
    window = timeline["window"]
    located = analyze_window(path, start_ms=window["start_ms"], end_ms=window["end_ms"])
    timeline["analysis"]["analyzer"] = "builtin.autocorrelation"
    timeline["analysis"]["bpm_candidates"] = located["bpm_candidates"]
    timeline["analysis"]["energy"] = located["energy"]
    timeline["beats"] = located["beats"]
    return validate_music_timeline(timeline, verify_source=False)


def analyze_music(path: Path, *, start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
    """Return a music timeline with unverified beat, tempo and energy candidates.

    The librosa path is used when it is installed; otherwise the built-in
    locator keeps the same candidate contract without the extra dependency.
    Every result stays a candidate until a listener confirms it.
    """
    timeline = inspect_music(path, start_ms=start_ms, end_ms=end_ms)
    try:
        librosa = import_module("librosa")
        np = import_module("numpy")
    except ImportError:
        return _analyze_builtin(path, timeline)
    window = timeline["window"]
    duration_seconds = (window["end_ms"] - window["start_ms"]) / 1000
    samples, sample_rate = librosa.load(str(Path(path)), sr=22050, mono=True,
                                        offset=window["start_ms"] / 1000,
                                        duration=duration_seconds)
    if len(samples) == 0:
        return timeline
    hop = 512
    rms = librosa.feature.rms(y=samples, hop_length=hop)[0]
    timeline["analysis"]["analyzer"] = "librosa.beat"
    timeline["analysis"]["energy"] = [
        {"time_ms": window["start_ms"] + round(index * hop * 1000 / sample_rate),
         "rms": round(float(level), 6), "status": "candidate"}
        for index, level in enumerate(rms)
        if window["start_ms"] + round(index * hop * 1000 / sample_rate) < window["end_ms"]
    ]
    if float(np.max(np.abs(samples))) < 1e-5 or float(np.max(rms)) < 1e-5:
        return validate_music_timeline(timeline, verify_source=False)
    onset = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=hop)
    if float(np.max(onset)) < 1e-4:
        return validate_music_timeline(timeline, verify_source=False)
    tempo, frames = librosa.beat.beat_track(onset_envelope=onset, sr=sample_rate, hop_length=hop, trim=False)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    if 35 <= bpm <= 240 and len(frames) >= 2:
        timeline["analysis"]["bpm_candidates"].append({"bpm": round(bpm, 2), "status": "candidate", "source": "librosa.beat"})
        timeline["beats"] = [
            {"time_ms": position, "kind": "beat", "status": "candidate"}
            for frame in frames
            if window["start_ms"] <= (position := window["start_ms"] + round(int(frame) * hop * 1000 / sample_rate)) < window["end_ms"]
        ]
    return validate_music_timeline(timeline, verify_source=False)
