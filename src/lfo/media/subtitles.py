"""Subtitle renderer — timed cues to SRT/WebVTT, import, validation, burn-in."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SubtitleCue:
    """A timed subtitle cue."""

    start_ms: int
    end_ms: int
    text: str


def _ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT time format HH:MM:SS,mmm."""
    if ms < 0:
        ms = 0
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    seconds = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _ms_to_vtt_time(ms: int) -> str:
    """Convert milliseconds to WebVTT time format HH:MM:SS.mmm."""
    if ms < 0:
        ms = 0
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    seconds = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def cues_to_srt(cues: list[SubtitleCue]) -> str:
    """Convert timed cues to SRT format string."""
    lines: list[str] = []
    for i, cue in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_ms_to_srt_time(cue.start_ms)} --> {_ms_to_srt_time(cue.end_ms)}")
        lines.append(cue.text)
        lines.append("")  # blank line separator
    return "\n".join(lines)


def cues_to_vtt(cues: list[SubtitleCue]) -> str:
    """Convert timed cues to WebVTT format string."""
    lines: list[str] = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{_ms_to_vtt_time(cue.start_ms)} --> {_ms_to_vtt_time(cue.end_ms)}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)


def validate_srt(srt_text: str) -> list[str]:
    """Validate SRT content. Returns list of errors."""
    errors: list[str] = []
    blocks = srt_text.strip().split("\n\n")
    for i, block in enumerate(blocks):
        lines = block.strip().split("\n")
        if len(lines) < 2:
            errors.append(f"Block {i + 1}: too few lines")
            continue
        # Check timecode line
        time_line = lines[-2] if len(lines) >= 2 else ""
        if "-->" not in time_line:
            errors.append(f"Block {i + 1}: missing timecode arrow '-->'")
    return errors


def clip_local_to_global_cues(
    cues: list[SubtitleCue],
    clip_start_ms: int,
) -> list[SubtitleCue]:
    """Convert clip-local cue timings to global timeline."""
    return [
        SubtitleCue(
            start_ms=c.start_ms + clip_start_ms,
            end_ms=c.end_ms + clip_start_ms,
            text=c.text,
        )
        for c in cues
    ]


class SubtitleRenderer:
    """Render and validate subtitles."""

    def render_srt(self, cues: list[SubtitleCue]) -> str:
        """Render cues to SRT format."""
        return cues_to_srt(cues)

    def render_vtt(self, cues: list[SubtitleCue]) -> str:
        """Render cues to WebVTT format."""
        return cues_to_vtt(cues)

    def validate_external(self, content: str, format: str) -> list[str]:
        """Validate an external subtitle file."""
        if format == "srt":
            return validate_srt(content)
        elif format == "vtt":
            # Basic VTT validation
            if not content.strip().startswith("WEBVTT"):
                return ["Missing WEBVTT header"]
            return []
        return [f"Unknown format: {format}"]
