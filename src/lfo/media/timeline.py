"""Timeline assembler — concatenate clips with optional transitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClipSegment:
    """A segment in the timeline."""

    clip_id: str
    file_path: str
    duration_ms: int
    start_ms: int = 0  # start time on global timeline
    audio_mix: dict[str, Any] | None = None
    transition_in: str | None = None  # cut | dissolve | wipe


@dataclass
class TimelineSpec:
    """Specification for timeline assembly."""

    segments: list[ClipSegment] = field(default_factory=list)
    transitions: str = "cut"  # cut | dissolve
    output_width: int = 0
    output_height: int = 0
    output_fps: float = 24.0
    output_codec: str = "h264"
    output_container: str = "mp4"
    audio_codec: str = "aac"


@dataclass
class TimelineResult:
    """Result of timeline assembly."""

    success: bool
    total_duration_ms: int = 0
    segment_count: int = 0
    error: str | None = None
    command: list[str] | None = None


class TimelineAssembler:
    """Assemble a timeline from clip segments."""

    def assemble(self, spec: TimelineSpec) -> TimelineResult:
        """Compute the timeline assembly operation.

        Args:
            spec: Timeline specification.

        Returns:
            TimelineResult with computed command.
        """
        if not spec.segments:
            return TimelineResult(success=False, error="No segments to assemble")

        # Compute global timeline positions
        current_ms = 0
        for seg in spec.segments:
            seg.start_ms = current_ms
            current_ms += seg.duration_ms

        total_duration = sum(s.duration_ms for s in spec.segments)

        # Build FFmpeg concat command (for audit)
        inputs = []
        for seg in spec.segments:
            inputs.extend(["-i", seg.file_path])

        return TimelineResult(
            success=True,
            total_duration_ms=total_duration,
            segment_count=len(spec.segments),
            command=["ffmpeg"] + inputs + ["-filter_complex", "concat", "output.mp4"],
        )

    def compute_segment_layout(
        self, durations: list[int],
    ) -> list[tuple[int, int]]:
        """Compute (start_ms, end_ms) for each segment given durations."""
        layout: list[tuple[int, int]] = []
        current = 0
        for d in durations:
            layout.append((current, current + d))
            current += d
        return layout
