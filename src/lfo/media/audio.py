"""FFmpeg-backed audio mixing for generated video and external tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command


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
        command = ["ffmpeg", "-y", "-i", str(source_video)]
        for track in request.tracks:
            command += ["-i", track.asset_key]
        has_native = request.native_audio_present and request.native_audio_strategy in {
            "preserve",
            "mix",
        }
        if not has_native and not request.tracks:
            return command + ["-map", "0:v:0", "-c:v", "copy", "-an", str(output)]
        filters: list[str] = []
        labels: list[str] = []
        if has_native:
            filters.append("[0:a]aresample=48000,asetpts=PTS-STARTPTS[native]")
            labels.append("[native]")
        foreground = any(track.duck_group != "background" for track in request.tracks)
        for index, track in enumerate(request.tracks, start=1):
            chain = ["aresample=48000", "asetpts=PTS-STARTPTS"]
            if track.offset_ms:
                chain.append(f"adelay={max(0, track.offset_ms)}:all=1")
            gain = track.gain_db + self.compute_duck(track, foreground)
            if gain:
                chain.append(f"volume={gain}dB")
            if track.fade_in_ms:
                chain.append(f"afade=t=in:st=0:d={track.fade_in_ms / 1000:.3f}")
            if track.fade_out_ms and track.duration_ms:
                start = max(0, track.duration_ms - track.fade_out_ms) / 1000
                chain.append(f"afade=t=out:st={start:.3f}:d={track.fade_out_ms / 1000:.3f}")
            label = f"track{index}"
            filters.append(f"[{index}:a]{','.join(chain)}[{label}]")
            labels.append(f"[{label}]")
        mix_chain = (
            "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0"
        )
        mix_chain += f",aformat=sample_rates={request.target_sample_rate}:channel_layouts={'mono' if request.output_channels == 1 else 'stereo'}"
        if request.target_loudness_db is not None:
            mix_chain += f",loudnorm=I={request.target_loudness_db}:TP=-1.5:LRA=11"
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
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
        return command

    def compute_duck(self, track: AudioTrack, foreground_present: bool) -> float:
        return -12.0 if track.duck_group == "background" and foreground_present else 0.0
