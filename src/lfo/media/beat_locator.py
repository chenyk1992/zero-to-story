"""Dependency-free beat, tempo and energy candidates for an adopted song.

The locator is a positioning aid, not a tempo authority: every value it
produces stays a candidate until a listener confirms it. It uses only the
standard library so it runs in the project environment without librosa or
numpy, and it never writes outside a temporary folder.
"""

from __future__ import annotations

import array
import math
import operator
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import run_command

SAMPLE_RATE = 22050
FRAME_SIZE = 512
HOP_SIZE = 256
ENERGY_STRIDE = 2
MIN_BPM = 60.0
MAX_BPM = 180.0
HOP_RATE = SAMPLE_RATE / HOP_SIZE
MIN_LAG = max(2, int(60.0 * HOP_RATE / MAX_BPM))
MAX_LAG = max(MIN_LAG + 1, int(60.0 * HOP_RATE / MIN_BPM))
MIN_CONFIDENCE = 0.03
PEAK_FLOOR = 1.25
ALTERNATIVE_FLOOR = 0.85
BEAT_RADIUS_SECONDS = 0.08
SOURCE = "builtin.autocorrelation"


def _decode_mono(path: Path, start_ms: int, end_ms: int, workdir: Path) -> array.array:
    """Decode the requested window to mono float samples."""
    target = workdir / "mono.f32"
    command = [
        os.environ.get("LFO_FFMPEG") or "ffmpeg",
        "-v", "error", "-xerror", "-y",
        "-ss", f"{start_ms / 1000:.3f}",
        "-i", str(path),
        "-t", f"{(end_ms - start_ms) / 1000:.3f}",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-f", "f32le",
        str(target),
    ]
    run_command(command, timeout_s=300.0)
    samples = array.array("f")
    samples.frombytes(target.read_bytes())
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _energy_frames(samples: array.array) -> list[float]:
    """Frame the signal into RMS energy values."""
    frames: list[float] = []
    for start in range(0, len(samples) - FRAME_SIZE + 1, HOP_SIZE):
        chunk = samples[start:start + FRAME_SIZE]
        total = sum(map(operator.mul, chunk, chunk))
        frames.append(math.sqrt(total / FRAME_SIZE))
    return frames


def _novelty(energy: list[float]) -> list[float]:
    """Half-wave rectified energy change with a local mean removed."""
    if len(energy) < 2:
        return []
    peak = max(energy)
    if peak <= 1e-6:
        return [0.0] * (len(energy) - 1)
    normalized = [value / peak for value in energy]
    raw = [max(0.0, normalized[index + 1] - normalized[index]) for index in range(len(normalized) - 1)]
    window = max(1, int(0.30 * HOP_RATE))
    result = [0.0] * len(raw)
    running = 0.0
    for index, value in enumerate(raw):
        running += value
        if index >= window:
            running -= raw[index - window]
        mean = running / min(index + 1, window)
        result[index] = value if value >= mean else 0.0
    return result


def _autocorrelation(novelty: list[float], lag: int) -> float:
    """Mean product of the novelty curve and a lagged copy of itself."""
    if lag <= 0 or len(novelty) <= lag:
        return 0.0
    head = novelty[:-lag]
    tail = novelty[lag:]
    return sum(map(operator.mul, head, tail)) / len(head)


def _refine_period(scores: list[tuple[int, float]], lag: int) -> float:
    """Sharpen an integer lag into a fractional period by parabolic interpolation."""
    values = dict(scores)
    peak = values.get(lag, 0.0)
    left = values.get(lag - 1, 0.0)
    right = values.get(lag + 1, 0.0)
    denominator = left - 2 * peak + right
    if denominator == 0:
        return float(lag)
    offset = 0.5 * (left - right) / denominator
    if not -1.0 < offset < 1.0:
        return float(lag)
    return lag + offset


def _tempo_periods(novelty: list[float]) -> list[tuple[float, float]]:
    """Return plausible beat periods in frames, strongest first, with their scores."""
    if len(novelty) <= MAX_LAG:
        return []
    scores = [(lag, _autocorrelation(novelty, lag)) for lag in range(MIN_LAG, MAX_LAG + 1)]
    best_lag, best_score = max(scores, key=lambda item: item[1])
    if best_score <= 0.0:
        return []
    energy = sum(map(operator.mul, novelty, novelty)) / len(novelty)
    if energy <= 0.0 or best_score / energy < MIN_CONFIDENCE:
        return []
    mean_score = sum(score for _, score in scores) / len(scores)
    if mean_score <= 0.0 or best_score < mean_score * PEAK_FLOOR:
        return []
    ranked = dict(scores)
    period = _refine_period(scores, best_lag)
    candidates = [(period, best_score)]
    for factor in (2.0, 0.5):
        alternative = period * factor
        if not MIN_LAG <= alternative <= MAX_LAG:
            continue
        lag = round(alternative)
        score = ranked.get(lag, 0.0)
        if score >= best_score * ALTERNATIVE_FLOOR:
            candidates.append((alternative, score))
    return candidates


def _best_phase(novelty: list[float], period: float) -> float:
    """Find the grid offset whose beats land on the strongest onsets."""
    limit = math.ceil(period)
    steps = int(len(novelty) / period) + 1
    best_offset, best_total = 0.0, -1.0
    for offset in range(limit):
        total = 0.0
        for step in range(steps):
            index = round(offset + step * period)
            if 0 <= index < len(novelty):
                total += novelty[index]
        if total > best_total:
            best_total, best_offset = total, float(offset)
    return best_offset


def _grid_coverage(energy: list[float], novelty: list[float], period: float) -> tuple[float, list[int]]:
    """Place a beat grid on the phase that best matches the novelty curve.

    Returns the onset weight the grid actually lands on together with the
    refined frame indices. A grid that sits on every onset scores higher than
    one that only covers every second onset.
    """
    if not energy or not novelty or period <= 0:
        return 0.0, []
    offset = _best_phase(novelty, period)
    radius = max(1, int(BEAT_RADIUS_SECONDS * HOP_RATE))
    indices: list[int] = []
    coverage = 0.0
    position = offset
    while position < len(energy):
        center = round(position)
        low = max(0, center - radius)
        high = min(len(energy) - 1, center + radius)
        onset_low = max(0, low - 1)
        onset_high = min(len(novelty) - 1, high)
        onset_weight = max(novelty[onset_low:onset_high + 1]) if onset_high >= onset_low else 0.0
        if onset_weight > 0.0:
            peak = max(range(low, high + 1), key=lambda index: energy[index])
            if not indices or peak > indices[-1]:
                indices.append(peak)
                coverage += onset_weight
        position += period
    return coverage, indices


def analyze_window(path: Path, *, start_ms: int, end_ms: int) -> dict[str, Any]:
    """Return tempo, beat and energy candidates for one song window.

    All times are source-song milliseconds, matching the music timeline.
    """
    with tempfile.TemporaryDirectory(prefix=".beat-locator-") as folder:
        samples = _decode_mono(path, start_ms, end_ms, Path(folder))
    energy = _energy_frames(samples)
    novelty = _novelty(energy)
    hop_ms = HOP_SIZE * 1000.0 / SAMPLE_RATE

    grids: list[tuple[float, float, list[int]]] = []
    for period, _score in _tempo_periods(novelty):
        coverage, indices = _grid_coverage(energy, novelty, period)
        grids.append((coverage, period, indices))
    # The grid that lands on the most onset weight drives the beat list; a
    # half-time grid would otherwise hide every second real onset.
    grids.sort(key=lambda item: item[0], reverse=True)

    bpm_candidates = [
        {
            "bpm": round(60.0 * HOP_RATE / period, 2),
            "status": "candidate",
            "source": SOURCE,
        }
        for _coverage, period, _indices in grids
    ]
    beats: list[dict[str, Any]] = []
    if grids:
        for index in grids[0][2]:
            time_ms = start_ms + round(index * hop_ms)
            if start_ms <= time_ms and time_ms + 1 <= end_ms:
                beats.append({"time_ms": time_ms, "kind": "beat", "status": "candidate"})

    energy_entries: list[dict[str, Any]] = []
    for index in range(0, len(energy), ENERGY_STRIDE):
        time_ms = start_ms + round(index * hop_ms)
        if start_ms <= time_ms < end_ms:
            energy_entries.append({
                "time_ms": time_ms,
                "rms": round(energy[index], 6),
                "status": "candidate",
            })
    return {"bpm_candidates": bpm_candidates, "beats": beats, "energy": energy_entries}
