from __future__ import annotations

import math

_STANDARD = {15_000: 8, 30_000: 15, 45_000: 22, 60_000: 29}


def beat_count_for_duration_ms(duration_ms: int) -> int:
    if duration_ms in _STANDARD:
        return _STANDARD[duration_ms]
    panels = max(1, math.ceil(duration_ms / 15_000))
    return 8 + 7 * (panels - 1)


def panel_count_for_beat_count(beat_count: int) -> int:
    if beat_count <= 8:
        return 1
    return 1 + math.ceil((beat_count - 8) / 7)


def panel_beat_ranges(beat_count: int) -> list[tuple[int, int]]:
    n = panel_count_for_beat_count(beat_count)
    ranges: list[tuple[int, int]] = []
    for i in range(n):
        if i == 0:
            ranges.append((1, min(8, beat_count)))
        else:
            start = ranges[-1][1]  # carry last beat
            end = min(start + 7, beat_count)
            ranges.append((start, end))
    return ranges


def panel_duration_ms(total_duration_ms: int, panel_count: int) -> int:
    if panel_count <= 0:
        raise ValueError("panel_count must be positive")
    return total_duration_ms // panel_count
