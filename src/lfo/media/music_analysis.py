"""Optional, unverified beat and energy candidates for an adopted song."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from lfo.media.music_timeline import inspect_music, validate_music_timeline


def analyze_music(path: Path, *, start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
    timeline = inspect_music(path, start_ms=start_ms, end_ms=end_ms)
    try:
        librosa = import_module("librosa")
        np = import_module("numpy")
    except ImportError as exc:
        raise RuntimeError("音乐候选分析需要已安装 librosa 的 Python 环境") from exc
    window = timeline["window"]
    duration_seconds = (window["end_ms"] - window["start_ms"]) / 1000
    samples, sample_rate = librosa.load(str(Path(path)), sr=22050, mono=True,
                                        offset=window["start_ms"] / 1000,
                                        duration=duration_seconds)
    if len(samples) == 0:
        return timeline
    hop = 512
    rms = librosa.feature.rms(y=samples, hop_length=hop)[0]
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
