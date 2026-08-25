"""Real FFmpeg timeline assembly with deterministic cut-only semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command


@dataclass
class ClipSegment:
    clip_id: str
    file_path: str
    duration_ms: int
    start_ms: int = 0
    audio_mix: dict[str, object] | None = None
    transition_in: str | None = None
    has_audio: bool | None = None


@dataclass
class TimelineSpec:
    segments: list[ClipSegment] = field(default_factory=list)
    transitions: str = "cut"
    output_width: int = 0
    output_height: int = 0
    output_fps: float = 24.0
    output_codec: str = "libx264"
    output_container: str = "mp4"
    audio_codec: str = "aac"
    output_path: str | None = None


@dataclass
class TimelineResult:
    success: bool
    total_duration_ms: int = 0
    segment_count: int = 0
    error: str | None = None
    command: list[str] | None = None
    output_path: str | None = None


class TimelineAssembler:
    """Assemble source clips. Transitions are deliberately not implicit."""

    def assemble(self, spec: TimelineSpec, *, timeout_s: float = 600.0) -> TimelineResult:
        if not spec.segments:
            return TimelineResult(False, error="No segments to assemble")
        if spec.transitions != "cut" or any(
            s.transition_in not in (None, "cut") for s in spec.segments
        ):
            return TimelineResult(False, error="Only direct cut transitions are supported")
        total = self._layout(spec.segments)
        if not spec.output_path:
            return TimelineResult(True, total, len(spec.segments), command=self.build_command(spec))
        output = Path(spec.output_path)
        missing = [
            segment.file_path for segment in spec.segments if not Path(segment.file_path).is_file()
        ]
        if missing:
            return TimelineResult(
                False, total, len(spec.segments), f"Clip does not exist: {missing[0]}"
            )
        for segment in spec.segments:
            segment.has_audio = probe(segment.file_path).get("has_audio", False)
        temp = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix}")
        command = self.build_command(spec, output_path=temp)
        try:
            run_command(command, timeout_s=timeout_s)
            atomic_replace(temp, output)
            return TimelineResult(
                True, total, len(spec.segments), command=command, output_path=str(output)
            )
        except MediaCommandError as exc:
            temp.unlink(missing_ok=True)
            return TimelineResult(False, total, len(spec.segments), str(exc), command)

    def build_command(self, spec: TimelineSpec, output_path: str | Path | None = None) -> list[str]:
        if not spec.segments:
            raise ValueError("No segments to assemble")
        output = str(output_path or spec.output_path or "output.mp4")
        command = ["ffmpeg", "-y"]
        pairs: list[tuple[int, int]] = []
        input_index = 0
        for segment in spec.segments:
            video_index = input_index
            command += ["-i", segment.file_path]
            if segment.has_audio is False:
                command += [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{segment.duration_ms / 1000:.3f}",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                ]
                pairs.append((video_index, video_index + 1))
                input_index += 2
            else:
                pairs.append((video_index, video_index))
                input_index += 1
        # Planned invocations do not probe paths; assume an audio stream so existing
        # callers can inspect an executable-looking command without file I/O.
        all_audio = all(segment.has_audio is not False for segment in spec.segments)
        labels = "".join(f"[{video}:v][{audio}:a]" for video, audio in pairs)
        if all_audio or any(segment.has_audio is False for segment in spec.segments):
            filter_graph = f"{labels}concat=n={len(pairs)}:v=1:a=1[outv][outa]"
            command += [
                "-filter_complex",
                filter_graph,
                "-map",
                "[outv]",
                "-map",
                "[outa]",
                "-c:v",
                spec.output_codec,
                "-c:a",
                spec.audio_codec,
            ]
        else:
            command += [
                "-filter_complex",
                f"{''.join(f'[{v}:v]' for v, _ in pairs)}concat=n={len(pairs)}:v=1:a=0[outv]",
                "-map",
                "[outv]",
                "-c:v",
                spec.output_codec,
                "-an",
            ]
        return command + ["-movflags", "+faststart", output]

    def compute_segment_layout(self, durations: list[int]) -> list[tuple[int, int]]:
        current = 0
        layout: list[tuple[int, int]] = []
        for duration in durations:
            layout.append((current, current + duration))
            current += duration
        return layout

    def _layout(self, segments: list[ClipSegment]) -> int:
        current = 0
        for segment in segments:
            if segment.duration_ms <= 0:
                raise ValueError(f"Invalid duration for clip {segment.clip_id}")
            segment.start_ms = current
            current += segment.duration_ms
        return current
