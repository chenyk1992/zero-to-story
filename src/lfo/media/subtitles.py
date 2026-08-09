"""Strict subtitle serialization, validation, and FFmpeg burn-in."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, run_command

_SRT_TIME = re.compile(r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})$")
_VTT_TIME = re.compile(
    r"^(\d{2,}):(\d{2}):(\d{2})\.(\d{3}) --> (\d{2,}):(\d{2}):(\d{2})\.(\d{3})(?: .*)?$"
)


@dataclass
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


def _ms_to_srt_time(ms: int) -> str:
    hours, remainder = divmod(max(0, ms), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _ms_to_vtt_time(ms: int) -> str:
    return _ms_to_srt_time(ms).replace(",", ".")


def _validate_cues(cues: list[SubtitleCue], duration_ms: int | None = None) -> list[str]:
    errors: list[str] = []
    previous_end = 0
    for index, cue in enumerate(cues, 1):
        if cue.start_ms < 0 or cue.end_ms <= cue.start_ms:
            errors.append(f"Cue {index}: invalid time range")
        if not cue.text.strip():
            errors.append(f"Cue {index}: empty text")
        if cue.start_ms < previous_end:
            errors.append(f"Cue {index}: overlaps previous cue")
        if duration_ms is not None and cue.end_ms > duration_ms:
            errors.append(f"Cue {index}: exceeds media duration")
        previous_end = max(previous_end, cue.end_ms)
    return errors


def cues_to_srt(cues: list[SubtitleCue]) -> str:
    errors = _validate_cues(cues)
    if errors:
        raise ValueError("; ".join(errors))
    return "\n".join(
        line
        for index, cue in enumerate(cues, 1)
        for line in (
            str(index),
            f"{_ms_to_srt_time(cue.start_ms)} --> {_ms_to_srt_time(cue.end_ms)}",
            cue.text,
            "",
        )
    )


def cues_to_vtt(cues: list[SubtitleCue]) -> str:
    errors = _validate_cues(cues)
    if errors:
        raise ValueError("; ".join(errors))
    return "WEBVTT\n\n" + "\n".join(
        line
        for cue in cues
        for line in (
            f"{_ms_to_vtt_time(cue.start_ms)} --> {_ms_to_vtt_time(cue.end_ms)}",
            cue.text,
            "",
        )
    )


def _time_ms(match: re.Match[str]) -> tuple[int, int]:
    values = [int(value) for value in match.groups()]
    start = ((values[0] * 60 + values[1]) * 60 + values[2]) * 1000 + values[3]
    end = ((values[4] * 60 + values[5]) * 60 + values[6]) * 1000 + values[7]
    return start, end


def validate_srt(srt_text: str, duration_ms: int | None = None) -> list[str]:
    errors: list[str] = []
    cues: list[SubtitleCue] = []
    for index, block in enumerate(re.split(r"\r?\n\r?\n", srt_text.strip()), 1):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            errors.append(f"Block {index}: expected numeric cue identifier and text")
            continue
        match = _SRT_TIME.match(lines[1].strip())
        if not match:
            errors.append(f"Block {index}: invalid timecode")
            continue
        start, end = _time_ms(match)
        cues.append(SubtitleCue(start, end, "\n".join(lines[2:])))
    return errors + _validate_cues(cues, duration_ms)


def validate_vtt(vtt_text: str, duration_ms: int | None = None) -> list[str]:
    lines = vtt_text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WEBVTT":
        return ["Missing WEBVTT header"]
    errors: list[str] = []
    cues: list[SubtitleCue] = []
    for index, block in enumerate("\n".join(lines[1:]).strip().split("\n\n"), 1):
        row = block.splitlines()
        if len(row) < 2:
            errors.append(f"Block {index}: expected timecode and text")
            continue
        match = _VTT_TIME.match(row[0].strip())
        if not match:
            errors.append(f"Block {index}: invalid timecode")
            continue
        start, end = _time_ms(match)
        cues.append(SubtitleCue(start, end, "\n".join(row[1:])))
    return errors + _validate_cues(cues, duration_ms)


def clip_local_to_global_cues(cues: list[SubtitleCue], clip_start_ms: int) -> list[SubtitleCue]:
    return [SubtitleCue(c.start_ms + clip_start_ms, c.end_ms + clip_start_ms, c.text) for c in cues]


class SubtitleRenderer:
    def render_srt(
        self,
        cues: list[SubtitleCue],
        output_path: str | Path | None = None,
        *,
        duration_ms: int | None = None,
    ) -> str:
        errors = _validate_cues(cues, duration_ms)
        if errors:
            raise ValueError("; ".join(errors))
        content = cues_to_srt(cues)
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return content

    def render_vtt(
        self,
        cues: list[SubtitleCue],
        output_path: str | Path | None = None,
        *,
        duration_ms: int | None = None,
    ) -> str:
        errors = _validate_cues(cues, duration_ms)
        if errors:
            raise ValueError("; ".join(errors))
        content = cues_to_vtt(cues)
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return content

    def validate_external(
        self, content: str, format: str, duration_ms: int | None = None
    ) -> list[str]:
        if format == "srt":
            return validate_srt(content, duration_ms)
        if format == "vtt":
            return validate_vtt(content, duration_ms)
        return [f"Unknown format: {format}"]

    def build_burnin_command(
        self, video_path: str | Path, subtitle_path: str | Path, output_path: str | Path
    ) -> list[str]:
        # FFmpeg filter option quoting is distinct from shell quoting; the argv is still safe.
        escaped = (
            str(Path(subtitle_path).resolve())
            .replace("\\", "/")
            .replace(":", "\\:")
            .replace("'", "\\'")
        )
        return [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"subtitles='{escaped}'",
            "-c:a",
            "copy",
            str(output_path),
        ]

    def burn_in(
        self,
        video_path: str | Path,
        subtitle_path: str | Path,
        output_path: str | Path,
        *,
        timeout_s: float = 300.0,
    ) -> list[str]:
        source, subtitle, output = Path(video_path), Path(subtitle_path), Path(output_path)
        if not source.is_file() or not subtitle.is_file():
            raise ValueError("Video and subtitle files must exist")
        temp = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix}")
        command = self.build_burnin_command(source, subtitle, temp)
        try:
            run_command(command, timeout_s=timeout_s)
            atomic_replace(temp, output)
            return command
        except MediaCommandError:
            temp.unlink(missing_ok=True)
            raise
