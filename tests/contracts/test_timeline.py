"""Tests for the explicit edit timeline contract."""
from __future__ import annotations

import pytest

from lfo.contracts import TimelineSegment, VideoExecutionPackage, package_content_hash


def _package(timeline: dict | None = None) -> dict:
    data = {
        "schema": "lfo.video-execution.v1",
        "package_id": "pkg",
        "revision": 1,
        "project": {"title": "Test", "project_id": "test"},
        "assets": [],
        "clips": [
            {
                "clip_id": "a",
                "sequence": 1,
                "duration_ms": 10_000,
                "generation": {"operation": "video.text_to_video", "prompt": "a"},
            },
            {
                "clip_id": "b",
                "sequence": 2,
                "duration_ms": 8_000,
                "generation": {"operation": "video.text_to_video", "prompt": "b"},
            },
        ],
        "output": {},
    }
    if timeline is not None:
        data["timeline"] = timeline
    return data


def test_timeline_round_trip_preserves_order_and_trim() -> None:
    package = VideoExecutionPackage.from_dict(
        _package({
            "segments": [
                {"clip_id": "b", "source_in_ms": 1_000, "source_out_ms": 6_000},
                {"clip_id": "a"},
            ]
        })
    )
    assert package.timeline.segments == [
        TimelineSegment("b", 1_000, 6_000),
        TimelineSegment("a"),
    ]
    assert VideoExecutionPackage.from_dict(package.to_dict()).to_dict() == package.to_dict()


@pytest.mark.parametrize(
    "timeline, message",
    [
        ({"segments": [{"clip_id": "a"}, {"clip_id": "a"}]}, "duplicate"),
        ({"segments": [{"clip_id": "missing"}]}, "unknown clip"),
        ({"segments": [{"clip_id": "a", "source_in_ms": 10_000}]}, "exceeds"),
        ({"segments": [{"clip_id": "a", "source_in_ms": 4_000, "source_out_ms": 4_000}]}, "greater"),
    ],
)
def test_timeline_rejects_invalid_ranges_and_clip_ids(timeline: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        VideoExecutionPackage.from_dict(_package(timeline))


def test_direct_timeline_segment_rejects_zero_source_out() -> None:
    with pytest.raises(ValueError, match="greater"):
        TimelineSegment("a", source_out_ms=0).duration_ms(10_000)


def test_timeline_changes_package_hash() -> None:
    base = VideoExecutionPackage.from_dict(_package({"segments": [{"clip_id": "a"}, {"clip_id": "b"}]}))
    trimmed = VideoExecutionPackage.from_dict(
        _package({"segments": [{"clip_id": "a", "source_in_ms": 100}, {"clip_id": "b"}]})
    )
    assert package_content_hash(base) != package_content_hash(trimmed)
