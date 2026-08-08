"""Normalize Profile registry — defines output format contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizeProfile:
    """Output format specification for normalization."""
    profile_id: str
    width: int
    height: int
    fps: str
    video_codec: str
    pixel_format: str
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    fit_policy: str       # 'cover_crop' | 'contain_pad'
    crop_anchor: str      # 'left' | 'center' | 'right'


# MVP profile: 9:16 vertical video
VERTICAL_H264_V1 = NormalizeProfile(
    profile_id="vertical_h264_v1",
    width=1080,
    height=1920,
    fps="24/1",
    video_codec="libx264",
    pixel_format="yuv420p",
    audio_codec="aac",
    audio_sample_rate=48000,
    audio_channels=2,
    fit_policy="cover_crop",
    crop_anchor="center",
)

_PROFILES: dict[str, NormalizeProfile] = {
    VERTICAL_H264_V1.profile_id: VERTICAL_H264_V1,
}


def get_profile(profile_id: str) -> NormalizeProfile:
    """Look up a profile by ID. Falls back to vertical_h264_v1."""
    return _PROFILES.get(profile_id, VERTICAL_H264_V1)


def register_profile(profile: NormalizeProfile) -> None:
    """Register a profile for use."""
    _PROFILES[profile.profile_id] = profile
