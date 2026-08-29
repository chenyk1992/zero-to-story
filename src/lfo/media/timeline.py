"""Real FFmpeg timeline assembly with deterministic cut-only semantics.

When every segment shares identical video/audio parameters the assembler uses
the ``concat`` demuxer with ``-c copy`` (stream copy, no re-encoding).  If the
segments differ, or any segment needs silent-audio injection, it falls back to
the ``concat`` filter with full re-encoding.
"""

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
    source_in_ms: int = 0
    source_out_ms: int | None = None
    start_ms: int = 0
    audio_mix: dict[str, object] | None = None
    transition_in: str | None = None
    has_audio: bool | None = None

    def edited_duration_ms(self) -> int:
        if self.duration_ms <= 0:
            raise ValueError(f"Invalid duration for clip {self.clip_id}")
        if self.source_in_ms < 0:
            raise ValueError(f"Invalid source_in_ms for clip {self.clip_id}")
        source_out = (
            self.source_out_ms if self.source_out_ms is not None else self.duration_ms
        )
        if source_out <= self.source_in_ms:
            raise ValueError(f"Invalid source range for clip {self.clip_id}")
        if source_out > self.duration_ms:
            raise ValueError(f"source_out_ms exceeds duration for clip {self.clip_id}")
        return source_out - self.source_in_ms

    @property
    def has_trim(self) -> bool:
        return self.source_in_ms > 0 or (
            self.source_out_ms is not None and self.source_out_ms != self.duration_ms
        )


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
        total = 0
        command: list[str] | None = None
        temporary_output: Path | None = None
        concat_list: Path | None = None
        try:
            output: Path | None = None
            if spec.output_path:
                output = Path(spec.output_path)
                missing = [
                    segment.file_path
                    for segment in spec.segments
                    if not Path(segment.file_path).is_file()
                ]
                if missing:
                    raise ValueError(f"Clip does not exist: {missing[0]}")
                temporary_output = output.with_name(
                    f".{output.stem}.{uuid4().hex}.tmp{output.suffix}"
                )
                command = self.build_command(spec, output_path=temporary_output)
            else:
                command = self.build_command(spec)
            concat_list = self._concat_list_path(command)

            # build_command probes real media and makes its duration authoritative
            # before the edit layout is materialized.
            total = self._layout(spec.segments)
            if output is None:
                return TimelineResult(True, total, len(spec.segments), command=command)
            run_command(command, timeout_s=timeout_s)
            if temporary_output is None:
                raise ValueError("Timeline temporary output was not initialized")
            atomic_replace(temporary_output, output)
            return TimelineResult(
                True, total, len(spec.segments), command=command, output_path=str(output)
            )
        except (MediaCommandError, OSError, TypeError, ValueError, KeyError) as exc:
            if temporary_output is not None:
                temporary_output.unlink(missing_ok=True)
            return TimelineResult(False, total, len(spec.segments), str(exc), command)
        finally:
            if concat_list is not None:
                concat_list.unlink(missing_ok=True)

    def _probe_segments(self, segments: list[ClipSegment]) -> list[dict]:
        """Probe each segment once and return the raw probe results."""
        results: list[dict] = []
        for segment in segments:
            metadata = probe(segment.file_path)
            actual_duration = metadata.get("duration_ms")
            if not isinstance(actual_duration, int) or actual_duration <= 0:
                raise ValueError(f"Clip {segment.clip_id} has no positive media duration")
            source_out = (
                segment.source_out_ms
                if segment.source_out_ms is not None
                else actual_duration
            )
            if segment.source_in_ms < 0:
                raise ValueError(f"Invalid source_in_ms for clip {segment.clip_id}")
            if source_out <= segment.source_in_ms:
                raise ValueError(f"Invalid source range for clip {segment.clip_id}")
            if source_out > actual_duration:
                raise ValueError(
                    f"source_out_ms exceeds actual media duration for clip {segment.clip_id}"
                )
            # The encoded file is the source of truth for the executable edit;
            # declared durations are used only when media is not yet available.
            segment.duration_ms = actual_duration
            results.append(metadata)
        return results

    def _all_segments_compatible(self, probes: list[dict], spec: TimelineSpec) -> bool:
        """Return True iff every segment shares identical A/V parameters and all have audio."""
        if not probes:
            return False
        first = probes[0]
        if not first.get("has_audio"):
            return False
        # Compare video parameters (None-safe) and audio parameters.
        video_keys = ("codec", "width", "height", "fps")
        audio_keys = ("audio_codec", "sample_rate", "channels")
        for key in video_keys + audio_keys:
            target = first.get(key)
            if target is None:
                return False
            for probed in probes[1:]:
                if probed.get(key) != target:
                    return False
        if spec.output_width > 0 and first.get("width") != spec.output_width:
            return False
        if spec.output_height > 0 and first.get("height") != spec.output_height:
            return False
        if spec.output_fps > 0:
            actual_fps = first.get("fps")
            if actual_fps is None or abs(float(actual_fps) - spec.output_fps) > 0.01:
                return False
        return True

    def build_command(self, spec: TimelineSpec, output_path: str | Path | None = None) -> list[str]:
        if not spec.segments:
            raise ValueError("No segments to assemble")
        output = str(output_path or spec.output_path or "output.mp4")

        # Probe each segment once (when files exist) to determine the fastest
        # safe assembly path.  When files are absent (planned invocation) we
        # fall through to the filter path without making filesystem claims.
        probes: list[dict] | None = None
        if all(Path(s.file_path).is_file() for s in spec.segments):
            probes = self._probe_segments(spec.segments)

        # Fast path: every segment shares identical parameters and all have audio.
        # Use the concat demuxer with stream copy to avoid any re-encoding.
        if (
            probes is not None
            and not any(s.has_trim for s in spec.segments)
            and self._all_segments_compatible(probes, spec)
        ):
            return self._build_copy_command(spec, output)

        # Fallback path: re-encode through the concat filter.  Use probe results
        # for has_audio when available; otherwise treat an unknown stream as
        # audio-bearing so planned invocations remain inspectable.
        if probes is not None:
            for segment, probed in zip(spec.segments, probes, strict=True):
                segment.has_audio = probed.get("has_audio", False)
        command = ["ffmpeg", "-y"]
        include_audio = any(segment.has_audio is not False for segment in spec.segments)
        video_indices: list[int] = []
        audio_indices: list[int | None] = []
        input_index = 0
        for segment in spec.segments:
            video_index = input_index
            command += ["-i", segment.file_path]
            video_indices.append(video_index)
            input_index += 1
            if include_audio and segment.has_audio is False:
                command += [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{segment.edited_duration_ms() / 1000:.3f}",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                ]
                audio_indices.append(video_index + 1)
                input_index += 1
            else:
                audio_indices.append(video_index if include_audio else None)

        first_probe = probes[0] if probes else {}
        target_width = spec.output_width or int(first_probe.get("width") or 0)
        target_height = spec.output_height or int(first_probe.get("height") or 0)
        target_fps = spec.output_fps or float(first_probe.get("fps") or 0)
        filter_parts: list[str] = []
        video_labels: list[str] = []
        audio_labels: list[str] = []
        for index, (video, audio, segment) in enumerate(
            zip(video_indices, audio_indices, spec.segments, strict=True)
        ):
            video_chain: list[str] = []
            if segment.has_trim:
                start = segment.source_in_ms / 1000
                source_out = (
                    segment.source_out_ms
                    if segment.source_out_ms is not None
                    else segment.duration_ms
                )
                end = source_out / 1000
                video_chain.append(f"trim=start={start:.3f}:end={end:.3f}")
            video_chain.append("setpts=PTS-STARTPTS")
            if target_width > 0 and target_height > 0:
                video_chain.extend(
                    [
                        f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
                        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
                    ]
                )
            if target_fps > 0:
                video_chain.append(f"fps={target_fps:g}")
            video_chain.extend(["setsar=1", "format=yuv420p"])
            video_label = f"[v{index}]"
            filter_parts.append(f"[{video}:v]{','.join(video_chain)}{video_label}")
            video_labels.append(video_label)

            if include_audio:
                if audio is None:
                    raise ValueError(f"Missing audio input for clip {segment.clip_id}")
                audio_chain: list[str] = []
                if segment.has_trim:
                    start = segment.source_in_ms / 1000
                    source_out = (
                        segment.source_out_ms
                        if segment.source_out_ms is not None
                        else segment.duration_ms
                    )
                    audio_chain.append(
                        f"atrim=start={start:.3f}:end={source_out / 1000:.3f}"
                    )
                else:
                    audio_chain.append(
                        f"atrim=duration={segment.edited_duration_ms() / 1000:.3f}"
                    )
                audio_chain.extend(
                    [
                        "asetpts=PTS-STARTPTS",
                        "aresample=48000",
                        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                        f"apad=whole_dur={segment.edited_duration_ms() / 1000:.3f}",
                    ]
                )
                audio_label = f"[a{index}]"
                filter_parts.append(f"[{audio}:a]{','.join(audio_chain)}{audio_label}")
                audio_labels.append(audio_label)

        concat_inputs = "".join(
            video_label + audio_label
            for video_label, audio_label in zip(video_labels, audio_labels, strict=True)
        ) if include_audio else "".join(video_labels)
        if include_audio:
            filter_graph = ";".join(
                filter_parts + [
                    f"{concat_inputs}concat=n={len(spec.segments)}:v=1:a=1[outv][outa]"
                ]
            )
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
                ";".join(filter_parts + [
                    f"{concat_inputs}concat=n={len(spec.segments)}:v=1:a=0[outv]"
                ]),
                "-map",
                "[outv]",
                "-c:v",
                spec.output_codec,
                "-an",
            ]
        return command + ["-movflags", "+faststart", output]

    def _build_copy_command(self, spec: TimelineSpec, output: str) -> list[str]:
        """Build a concat-demuxer command with -c copy (no re-encoding).

        Requires every segment to have identical video/audio stream parameters
        and an audio stream present so the demuxer can safely stream-copy.
        """
        output_path = Path(output)
        concat_list = output_path.with_name(
            f".{output_path.stem}.{uuid4().hex}.concat.txt"
        )
        with concat_list.open("w", encoding="utf-8") as fh:
            for segment in spec.segments:
                escaped = Path(segment.file_path).resolve().as_posix().replace("'", "'\\''")
                fh.write(f"file '{escaped}'\n")
        return [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            output,
        ]

    @staticmethod
    def _concat_list_path(command: list[str]) -> Path | None:
        try:
            format_index = command.index("-f")
            input_index = command.index("-i")
        except ValueError:
            return None
        if command[format_index + 1] != "concat":
            return None
        return Path(command[input_index + 1])

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
            duration_ms = segment.edited_duration_ms()
            segment.start_ms = current
            current += duration_ms
        return current
