from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SOURCE = Path(__file__).resolve().parents[2] / ".agents/skills/comfy-upscale-executor/custom_node/window_plan.py"
_SPEC = importlib.util.spec_from_file_location("seedvr2_window_plan_test", _SOURCE)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
plan_windows = _MODULE.plan_windows


@pytest.mark.parametrize("frame_count", [1, 4, 5, 47, 48, 49, 120, 175, 200, 293, 360])
def test_unique_keep_ranges_reconstruct_exact_selected_frames(frame_count: int) -> None:
    windows = plan_windows(19, frame_count)
    selected: list[int] = []
    for window in windows:
        first = window["source_start_frame"] + window["keep_start_frame"]
        selected.extend(range(first, first + window["keep_frame_count"]))
        assert window["source_start_frame"] >= 19
        assert window["source_start_frame"] + window["source_frame_count"] <= 19 + frame_count
        assert window["source_frame_count"] <= 56
        assert window["padded_frame_count"] <= 57
        assert (window["padded_frame_count"] - 1) % 4 == 0
        assert 0 <= window["padding_frames"] <= 3
        assert window["output_end_frame"] - window["output_start_frame"] == window["keep_frame_count"]
    assert selected == list(range(19, 19 + frame_count))
    assert windows[0]["output_start_frame"] == 0
    assert windows[-1]["output_end_frame"] == frame_count


def test_five_second_sample_keeps_context_and_discards_it_once() -> None:
    windows = plan_windows(0, 120)
    assert [(w["source_start_frame"], w["source_frame_count"], w["keep_start_frame"], w["keep_frame_count"])
            for w in windows] == [
                (0, 20, 0, 16),
                (12, 24, 4, 16),
                (28, 24, 4, 16),
                (44, 24, 4, 16),
                (60, 24, 4, 16),
                (76, 24, 4, 16),
                (92, 24, 4, 16),
                (108, 12, 4, 8),
            ]


def test_default_production_window_uses_16_frame_core_and_four_frame_context() -> None:
    windows = plan_windows(0, 72)

    assert [(w["source_frame_count"], w["keep_start_frame"], w["keep_frame_count"], w["padded_frame_count"])
            for w in windows] == [
                (20, 0, 16, 21),
                (24, 4, 16, 25),
                (24, 4, 16, 25),
                (24, 4, 16, 25),
                (12, 4, 8, 13),
            ]


def test_default_24_frame_window_and_absolute_56_frame_planner_cap_are_distinct() -> None:
    production = plan_windows(0, 72)
    absolute = plan_windows(0, 120, window_frames=48, context_frames=4)

    assert max(w["source_frame_count"] for w in production) == 24
    assert max(w["padded_frame_count"] for w in production) == 25
    assert max(w["source_frame_count"] for w in absolute) == 56
    assert max(w["padded_frame_count"] for w in absolute) == 57
    with pytest.raises(ValueError, match="must not exceed 56"):
        plan_windows(0, 120, window_frames=48, context_frames=8)


@pytest.mark.parametrize(("frame_count", "expected_windows"), [(161, 11), (257, 17)])
def test_long_selection_keeps_single_frame_tail_in_its_own_window(
    frame_count: int,
    expected_windows: int,
) -> None:
    windows = plan_windows(0, frame_count)

    assert len(windows) == expected_windows
    assert windows[-1]["keep_frame_count"] == 1
    assert windows[-1]["output_start_frame"] == frame_count - 1
    assert windows[-1]["output_end_frame"] == frame_count
    assert max(window["source_frame_count"] for window in windows) == 24
    assert max(window["padded_frame_count"] for window in windows) == 25


@pytest.mark.parametrize("window_frames", [16, 24, 32, 48])
def test_smaller_memory_windows_keep_total_output_frames(window_frames: int) -> None:
    windows = plan_windows(0, 293, window_frames=window_frames)
    assert sum(w["keep_frame_count"] for w in windows) == 293
    assert max(w["source_frame_count"] for w in windows) <= window_frames + 8


@pytest.mark.parametrize("kwargs", [
    {"start_frame": -1}, {"start_frame": True}, {"frame_count": 0}, {"frame_count": 1.5},
    {"window_frames": 0}, {"window_frames": 49}, {"window_frames": 52},
    {"context_frames": 1}, {"context_frames": -4}, {"context_frames": 20},
])
def test_invalid_memory_or_frame_ranges_fail_before_decode(kwargs: dict[str, int]) -> None:
    parameters = {"start_frame": 0, "frame_count": 120, **kwargs}
    with pytest.raises(ValueError):
        plan_windows(**parameters)


def test_extended_context_still_obeys_total_pixel_window_bound() -> None:
    windows = plan_windows(0, 293, window_frames=24, context_frames=16)
    assert max(w["source_frame_count"] for w in windows) <= 56
    assert sum(w["keep_frame_count"] for w in windows) == 293
