from lfo.planning.panel_density import (
    beat_count_for_duration_ms,
    panel_count_for_beat_count,
    panel_beat_ranges,
    panel_duration_ms,
)


def test_standard_durations():
    assert beat_count_for_duration_ms(15_000) == 8
    assert beat_count_for_duration_ms(30_000) == 15
    assert beat_count_for_duration_ms(45_000) == 22
    assert beat_count_for_duration_ms(60_000) == 29


def test_panel_count_from_beats():
    assert panel_count_for_beat_count(8) == 1
    assert panel_count_for_beat_count(15) == 2
    assert panel_count_for_beat_count(22) == 3
    assert panel_count_for_beat_count(29) == 4


def test_ranges_with_carry():
    # Panel1: 1-8; Panel2: 8-15 (beat 8 carried)
    assert panel_beat_ranges(15) == [(1, 8), (8, 15)]
    assert panel_beat_ranges(22) == [(1, 8), (8, 15), (15, 22)]


def test_panel_duration_splits_evenly():
    assert panel_duration_ms(45_000, 3) == 15_000
