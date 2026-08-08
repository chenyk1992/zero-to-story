"""Panel planning — derive execution panels from narrative beats."""
from __future__ import annotations

import uuid

from lfo.planning.panel_density import panel_beat_ranges, panel_duration_ms

from .storyboard import Beat, Panel


def derive_panels_from_beats(beats: list[Beat], total_duration_ms: int) -> list[Panel]:
    """Partition beats into panels using Hub density rules.

    Beat sequences are 1-based. Overlapping beat ranges (shared boundary beat)
    follow ``panel_beat_ranges`` semantics from panel_density.
    """
    if not beats:
        return []

    beat_count = len(beats)
    ranges = panel_beat_ranges(beat_count)
    panel_count = len(ranges)
    duration_per_panel = panel_duration_ms(total_duration_ms, panel_count)

    panels: list[Panel] = []
    for seq, (start, end) in enumerate(ranges, start=1):
        beat_ids = [beats[i - 1].beat_id for i in range(start, end + 1)]
        panel_id = f"panel_{seq:03d}_{uuid.uuid4().hex[:6]}"
        panels.append(
            Panel(
                panel_id=panel_id,
                sequence=seq,
                beat_range=(start, end),
                beat_ids=beat_ids,
                desired_duration_ms=duration_per_panel,
            )
        )
    return panels
