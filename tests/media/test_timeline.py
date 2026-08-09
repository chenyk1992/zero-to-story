"""Tests for timeline assembler."""
from __future__ import annotations

from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec


class TestTimelineAssembler:
    def test_assemble_single_segment(self) -> None:
        assembler = TimelineAssembler()
        spec = TimelineSpec(segments=[
            ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=5000),
        ])
        result = assembler.assemble(spec)
        assert result.success
        assert result.total_duration_ms == 5000

    def test_assemble_multiple_segments(self) -> None:
        assembler = TimelineAssembler()
        spec = TimelineSpec(segments=[
            ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=5000),
            ClipSegment(clip_id="c2", file_path="/tmp/c2.mp4", duration_ms=3000),
        ])
        result = assembler.assemble(spec)
        assert result.success
        assert result.total_duration_ms == 8000
        assert result.segment_count == 2

    def test_empty_segments_fails(self) -> None:
        assembler = TimelineAssembler()
        result = assembler.assemble(TimelineSpec())
        assert not result.success

    def test_segment_layout(self) -> None:
        assembler = TimelineAssembler()
        layout = assembler.compute_segment_layout([5000, 3000, 2000])
        assert layout == [(0, 5000), (5000, 8000), (8000, 10000)]

    def test_start_times_computed(self) -> None:
        assembler = TimelineAssembler()
        segments = [
            ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=4000),
            ClipSegment(clip_id="c2", file_path="/tmp/c2.mp4", duration_ms=6000),
        ]
        spec = TimelineSpec(segments=segments)
        assembler.assemble(spec)
        assert spec.segments[0].start_ms == 0
        assert spec.segments[1].start_ms == 4000
