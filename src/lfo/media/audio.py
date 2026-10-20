"""FFmpeg-backed audio mixing for generated video and external tracks."""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command


@dataclass(frozen=True)
class DuckingWindow:
    """Dialogue interval in output time; attack precedes it, release follows it."""

    start_ms: int
    end_ms: int
    gain_db: float = -12.0
    attack_ms: int = 100
    release_ms: int = 200


def parse_ducking_windows(value: object, duration_ms: int) -> list[DuckingWindow]:
    """Validate explicit timeline windows without detecting or changing speech."""
    if not isinstance(value, list):
        raise ValueError("music_ducking must be an array")
    windows = []
    for record in value:
        if not isinstance(record, Mapping) or set(record) - {
            "start_ms", "end_ms", "gain_db", "attack_ms", "release_ms"
        }:
            raise ValueError("Invalid music_ducking window fields")
        try:
            window = DuckingWindow(**record)
        except TypeError as exc:
            raise ValueError("Ducking window requires start_ms and end_ms") from exc
        windows.append(window)
    _validate_ducking(windows, duration_ms)
    return windows


def _validate_ducking(windows: list[DuckingWindow], duration_ms: int) -> None:
    if not isinstance(windows, list):
        raise ValueError("Ducking windows must be a list")
    if windows and (type(duration_ms) is not int or duration_ms <= 0):
        raise ValueError("Ducking windows require a positive clip_duration_ms")
    for window in windows:
        if not isinstance(window, DuckingWindow):
            raise ValueError("Invalid ducking window")
        if any(type(value) is not int for value in (
            window.start_ms, window.end_ms, window.attack_ms, window.release_ms
        )) or not 0 <= window.start_ms < window.end_ms <= duration_ms:
            raise ValueError("Ducking window exceeds the output timeline")
        if window.attack_ms < 0 or window.release_ms < 0:
            raise ValueError("Ducking attack/release must be nonnegative milliseconds")
        if (isinstance(window.gain_db, bool) or not isinstance(window.gain_db, (int, float))
                or not math.isfinite(window.gain_db) or window.gain_db > 0):
            raise ValueError("Ducking gain_db must be finite and nonpositive")


def _ducking_filter(windows: list[DuckingWindow], duration_ms: int) -> str:
    _validate_ducking(windows, duration_ms)
    expressions = []
    for window in windows:
        start, end = window.start_ms / 1000, window.end_ms / 1000
        attack_start = max(0, window.start_ms - window.attack_ms) / 1000
        release_end = min(duration_ms, window.end_ms + window.release_ms) / 1000
        gain = f"{window.gain_db:.12g}"
        attack = (f"{gain}*(t-{attack_start:.9f})/{start-attack_start:.9f}"
                  if start > attack_start else gain)
        release = (f"{gain}*({release_end:.9f}-t)/{release_end-end:.9f}"
                   if release_end > end else "0")
        expressions.append(
            f"if(lt(t,{attack_start:.9f}),0,if(lt(t,{start:.9f}),{attack},"
            f"if(lt(t,{end:.9f}),{gain},if(lt(t,{release_end:.9f}),{release},0))))"
        )
    # Overlaps use the stronger attenuation, never sum independent dB cuts.
    # Keep parser recursion logarithmic for dialogue-dense full-length edits.
    while len(expressions) > 1:
        expressions = [
            f"min({expressions[index]},{expressions[index + 1]})"
            if index + 1 < len(expressions) else expressions[index]
            for index in range(0, len(expressions), 2)
        ]
    envelope = expressions[0] if expressions else "0"
    return f"volume='pow(10,({envelope})/20)':eval=frame"


@dataclass
class AudioTrack:
    asset_key: str
    role: str
    offset_ms: int = 0
    gain_db: float = 0.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    duck_group: str | None = None
    duration_ms: int | None = None
    # None preserves legacy group ducking; [] explicitly requests no ducking.
    ducking_windows: list[DuckingWindow] | None = None


@dataclass
class AudioMixRequest:
    native_audio_present: bool = False
    native_audio_strategy: str = "preserve"
    tracks: list[AudioTrack] = field(default_factory=list)
    target_loudness_db: float | None = None
    target_sample_rate: int = 48000
    output_channels: int = 2
    clip_duration_ms: int = 0
    source_video_path: str | None = None
    output_path: str | None = None
    normalize_inputs: bool = True


@dataclass
class AudioMixResult:
    success: bool
    has_audio: bool = False
    applied_tracks: list[str] = field(default_factory=list)
    native_handling: str = ""
    error: str | None = None
    command: list[str] | None = None
    output_path: str | None = None


class AudioMixer:
    """Mix and publish audio atomically; without paths, build a deterministic plan."""

    def mix(self, request: AudioMixRequest, *, timeout_s: float = 300.0) -> AudioMixResult:
        try:
            for track in request.tracks:
                if track.ducking_windows is not None:
                    _validate_ducking(track.ducking_windows, request.clip_duration_ms)
        except ValueError as exc:
            return AudioMixResult(False, error=str(exc))
        if request.native_audio_strategy not in {"preserve", "mute", "mix", "replace"}:
            return AudioMixResult(
                False, error=f"Unknown native_audio_strategy: {request.native_audio_strategy}"
            )
        has_native = request.native_audio_present and request.native_audio_strategy in {
            "preserve",
            "mix",
        }
        applied = (["native"] if has_native else []) + [track.asset_key for track in request.tracks]
        has_audio = bool(applied)
        if not request.source_video_path or not request.output_path:
            return AudioMixResult(
                True,
                has_audio,
                applied,
                request.native_audio_strategy,
                command=self.build_command(request, "input", "output") if has_audio else None,
            )
        source, output = Path(request.source_video_path), Path(request.output_path)
        if not source.is_file():
            return AudioMixResult(False, error=f"Source video does not exist: {source}")
        for track in request.tracks:
            if not Path(track.asset_key).is_file():
                return AudioMixResult(False, error=f"Audio track does not exist: {track.asset_key}")
        temp = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix}")
        command = self.build_command(request, source, temp)
        try:
            with tempfile.TemporaryDirectory(prefix="lfo-audio-filter-") as folder:
                # Windows CreateProcess limits the complete command line. Keep
                # large envelopes out of argv without changing the filter graph.
                if "-filter_complex" in command and len(subprocess.list2cmdline(command)) > 24000:
                    index = command.index("-filter_complex")
                    graph_path = Path(folder) / "mix.ffscript"
                    graph_path.write_text(command[index + 1], encoding="utf-8")
                    command[index:index + 2] = ["-/filter_complex", str(graph_path)]
                run_command(command, timeout_s=timeout_s)
            atomic_replace(temp, output)
            return AudioMixResult(
                True,
                probe(output)["has_audio"],
                applied,
                request.native_audio_strategy,
                command=command,
                output_path=str(output),
            )
        except MediaCommandError as exc:
            temp.unlink(missing_ok=True)
            return AudioMixResult(
                False, has_audio, applied, request.native_audio_strategy, str(exc), command
            )

    def build_command(
        self, request: AudioMixRequest, source_video: str | Path, output: str | Path
    ) -> list[str]:
        """Build the exact FFmpeg argv without invoking a shell."""
        command = [os.environ.get("LFO_FFMPEG") or "ffmpeg", "-y", "-i", str(source_video)]
        for track in request.tracks:
            command += ["-i", track.asset_key]
        has_native = request.native_audio_present and request.native_audio_strategy in {
            "preserve",
            "mix",
        }
        if not has_native and not request.tracks:
            command += ["-map", "0:v:0", "-c:v", "copy", "-an"]
            if request.clip_duration_ms > 0:
                command += ["-t", f"{request.clip_duration_ms / 1000:.3f}"]
            return command + [str(output)]
        filters: list[str] = []
        labels: list[str] = []
        target_duration = (
            f"{request.clip_duration_ms / 1000:.3f}" if request.clip_duration_ms > 0 else None
        )
        if has_native:
            native_chain = ["aresample=48000", "asetpts=PTS-STARTPTS"]
            if target_duration is not None:
                native_chain.extend(
                    [f"atrim=duration={target_duration}", f"apad=whole_dur={target_duration}"]
                )
            filters.append(f"[0:a]{','.join(native_chain)}[native]")
            labels.append("[native]")
        foreground = any(track.duck_group != "background" for track in request.tracks)
        for index, track in enumerate(request.tracks, start=1):
            chain = ["aresample=48000", "asetpts=PTS-STARTPTS"]
            if track.offset_ms:
                chain.append(f"adelay={max(0, track.offset_ms)}:all=1")
            gain = track.gain_db + (
                self.compute_duck(track, foreground) if track.ducking_windows is None else 0
            )
            if gain:
                chain.append(f"volume={gain}dB")
            if track.ducking_windows:
                chain.append(_ducking_filter(track.ducking_windows, request.clip_duration_ms))
            if track.fade_in_ms:
                chain.append(f"afade=t=in:st=0:d={track.fade_in_ms / 1000:.3f}")
            if track.fade_out_ms and track.duration_ms:
                start = max(0, track.duration_ms - track.fade_out_ms) / 1000
                chain.append(f"afade=t=out:st={start:.3f}:d={track.fade_out_ms / 1000:.3f}")
            if target_duration is not None:
                # Delay/gain/fades must be applied before the bounded pad so a
                # short or offset track cannot terminate the output stream.
                chain.extend(
                    [f"atrim=duration={target_duration}", f"apad=whole_dur={target_duration}"]
                )
            label = f"track{index}"
            filters.append(f"[{index}:a]{','.join(chain)}[{label}]")
            labels.append(f"[{label}]")
        mix_chain = (
            "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize={int(request.normalize_inputs)}"
        )
        if not request.normalize_inputs:
            mix_chain += ",alimiter=limit=0.95:level=false:latency=1"
        mix_chain += f",aformat=sample_rates={request.target_sample_rate}:channel_layouts={'mono' if request.output_channels == 1 else 'stereo'}"
        if target_duration is not None:
            mix_chain += f",atrim=duration={target_duration}"
        if request.target_loudness_db is not None:
            # loudnorm may promote the working sample rate and can leave a
            # small AAC true-peak overshoot. Re-apply the requested rate and
            # a conservative -1.5 dBTP-equivalent ceiling before encoding.
            mix_chain += (
                f",loudnorm=I={request.target_loudness_db}:TP=-1.5:LRA=11"
                ",alimiter=limit=0.841395:level=false"
                f",aresample={request.target_sample_rate}"
            )
        filters.append(f"{mix_chain}[outa]")
        command += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[outa]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
        ]
        if target_duration is not None:
            command += ["-t", target_duration]
        else:
            command.append("-shortest")
        return command + [str(output)]

    def compute_duck(self, track: AudioTrack, foreground_present: bool) -> float:
        return -12.0 if track.duck_group == "background" and foreground_present else 0.0
