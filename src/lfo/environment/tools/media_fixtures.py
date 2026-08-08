"""Dynamic media test fixture generation using FFmpeg lavfi."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple


class MediaFixture(NamedTuple):
    """Metadata for a generated test media file."""

    path: Path
    width: int
    height: int
    fps: int
    duration: float
    has_audio: bool
    sample_rate: int | None
    channels: int | None


def generate_test_video(
    output_path: Path,
    width: int = 320,
    height: int = 180,
    fps: int = 24,
    duration: float = 1.0,
    with_audio: bool = True,
    sample_rate: int = 48000,
    ffmpeg_path: str = "ffmpeg",
) -> MediaFixture:
    """
    Generate a test video with FFmpeg lavfi testsrc + sine.

    Uses subprocess list args (shell=False) to handle paths with spaces.
    Requires lavfi support in the FFmpeg build.
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
    ]
    if with_audio:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:sample_rate={sample_rate}:duration={duration}",
        ]
    cmd += [
        "-shortest",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(output_path),
    ]

    subprocess.run(cmd, capture_output=True, timeout=60)

    return MediaFixture(
        path=output_path,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        has_audio=with_audio,
        sample_rate=sample_rate if with_audio else None,
        channels=1 if with_audio else None,
    )


def generate_corrupted_media(
    output_path: Path, base_fixture: MediaFixture
) -> Path:
    """Create a corrupted version by truncating the file to first 10% of bytes."""
    data = base_fixture.path.read_bytes()
    corrupted = data[: max(1, len(data) // 10)]
    output_path.write_bytes(corrupted)
    return output_path


def generate_temp_fixture(
    width: int = 320,
    height: int = 180,
    fps: int = 24,
    duration: float = 1.0,
    with_audio: bool = True,
    ffmpeg_path: str = "ffmpeg",
) -> MediaFixture:
    """Generate a test video in a temp directory. Caller is responsible for cleanup."""
    tmp_dir = tempfile.mkdtemp(prefix="lfo_fixture_")
    output_path = Path(tmp_dir) / "test_video.mp4"
    return generate_test_video(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        with_audio=with_audio,
        ffmpeg_path=ffmpeg_path,
    )
