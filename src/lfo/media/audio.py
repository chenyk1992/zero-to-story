"""Audio mixer — mix native audio + external tracks with gain, fade, duck."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioTrack:
    """An audio track to be mixed."""

    asset_key: str
    role: str  # dialogue | sfx | music | ambient
    offset_ms: int = 0
    gain_db: float = 0.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    duck_group: str | None = None
    duration_ms: int | None = None


@dataclass
class AudioMixRequest:
    """Request to mix audio for a clip."""

    # Native audio from the generated video (if any)
    native_audio_present: bool = False
    native_audio_strategy: str = "preserve"  # preserve | mute | mix | replace
    # External tracks to mix
    tracks: list[AudioTrack] = field(default_factory=list)
    # Global output
    target_loudness_db: float | None = None
    target_sample_rate: int = 48000
    output_channels: int = 2
    clip_duration_ms: int = 0


@dataclass
class AudioMixResult:
    """Result of audio mixing."""

    success: bool
    has_audio: bool = False
    applied_tracks: list[str] = field(default_factory=list)
    native_handling: str = ""
    error: str | None = None
    command: list[str] | None = None


class AudioMixer:
    """Mix audio tracks with gain, fade, and ducking."""

    def mix(self, request: AudioMixRequest) -> AudioMixResult:
        """Compute the audio mix operation.

        Args:
            request: The audio mix specification.

        Returns:
            AudioMixResult describing the operation.
        """
        # Validate
        if request.native_audio_strategy not in ("preserve", "mute", "mix", "replace"):
            return AudioMixResult(
                success=False,
                error=f"Unknown native_audio_strategy: {request.native_audio_strategy}",
            )

        has_audio = False
        applied: list[str] = []

        # Determine native audio handling
        native_handling = request.native_audio_strategy
        if request.native_audio_present and request.native_audio_strategy != "mute":
            has_audio = True
            applied.append("native")

        # Add external tracks
        for track in request.tracks:
            applied.append(track.asset_key)
            has_audio = True

        # Build FFmpeg filter graph (conavlis for audit)
        filter_parts: list[str] = []
        input_idx = 0

        if request.native_audio_present and request.native_audio_strategy != "mute":
            filter_parts.append(f"[{input_idx}:a]volume=1.0[native]")
            input_idx += 1

        for i, track in enumerate(request.tracks):
            filters = []
            if track.gain_db != 0:
                filters.append(f"volume={track.gain_db}dB")
            if track.fade_in_ms > 0:
                filters.append(f"afade=t=in:st=0:d={track.fade_in_ms / 1000.0}")
            label = f"track{i}"
            if filters:
                filter_parts.append(f"[{input_idx}:a]{','.join(filters)}[{label}]")
            else:
                filter_parts.append(f"[{input_idx}:a]acopy[{label}]")
            input_idx += 1

        return AudioMixResult(
            success=True,
            has_audio=has_audio,
            applied_tracks=applied,
            native_handling=native_handling,
            command=["ffmpeg"] if has_audio else None,
        )

    def compute_duck(self, track: AudioTrack, foreground_present: bool) -> float:
        """Compute duck gain reduction when foreground is present."""
        if track.duck_group == "background" and foreground_present:
            return -12.0  # dB reduction
        return 0.0
