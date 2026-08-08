"""FFmpeg capability probe — checks availability and capabilities."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

# Required capabilities for LFO video/audio processing
REQUIRED_FILTERS = ["scale", "pad", "crop", "concat"]
REQUIRED_DECODERS = ["h264", "hevc"]
REQUIRED_ENCODERS = ["libx264"]
REQUIRED_AUDIO_ENCODERS = ["aac"]


@dataclass
class ProbeResult:
    """Result of probing FFmpeg availability and capabilities."""

    available: bool
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    ffmpeg_version: str | None = None
    ffprobe_version: str | None = None
    capabilities: dict = field(default_factory=dict)
    error: str | None = None


def find_executable(name: str) -> str | None:
    """Find executable in PATH or with common extensions."""
    path = shutil.which(name)
    if path:
        return path
    # Try with .exe on Windows
    if not name.endswith(".exe"):
        path = shutil.which(name + ".exe")
        if path:
            return path
    return None


def parse_version(output: str) -> str | None:
    """Extract version string from ffmpeg -version output."""
    match = re.search(r"version\s+(\S+)", output)
    return match.group(1) if match else None


def check_filter(ffmpeg_path: str, filter_name: str) -> bool:
    """Check if a specific filter is available."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Filters list format: " T.. filter_name    V->V    ..."
        # Use word-boundary match to avoid false positives (e.g. "scale" vs "scale2ref")
        return bool(
            re.search(rf"\b{re.escape(filter_name)}\b", result.stdout)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def check_encoder(ffmpeg_path: str, encoder_name: str) -> bool:
    """Check if a specific encoder is available."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(
            re.search(rf"\b{re.escape(encoder_name)}\b", result.stdout)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _check_lavfi(ffmpeg_path: str) -> bool:
    """Check lavfi availability by trying to generate a test source."""
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=0.1:size=32x32:rate=1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def probe_ffmpeg(
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
) -> ProbeResult:
    """
    Probe FFmpeg availability and capabilities.

    Resolution order for binary discovery:
    1. Explicitly provided arguments
    2. LFO_FFMPEG / LFO_FFPROBE env vars
    3. System PATH

    Returns ProbeResult with capabilities dict containing:
    - lavfi: bool (required for test fixture generation)
    - scale, pad, crop, concat: bool (required filters)
    - libx264: bool (required video encoder)
    - aac: bool (required audio encoder)
    """
    # Resolution order: args > env vars > PATH
    if not ffmpeg_path:
        ffmpeg_path = os.environ.get("LFO_FFMPEG") or find_executable("ffmpeg")
    if not ffprobe_path:
        ffprobe_path = os.environ.get("LFO_FFPROBE") or find_executable("ffprobe")

    if not ffmpeg_path:
        return ProbeResult(
            available=False, error="FFmpeg not found in PATH"
        )

    # Verify executable works and get version
    try:
        version_result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if version_result.returncode != 0:
            return ProbeResult(
                available=False,
                ffmpeg_path=ffmpeg_path,
                error=f"FFmpeg returned non-zero: {version_result.stderr[:200]}",
            )
        ffmpeg_version = parse_version(version_result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return ProbeResult(
            available=False,
            ffmpeg_path=ffmpeg_path,
            error=f"FFmpeg execution failed: {e}",
        )

    result = ProbeResult(
        available=True,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        ffmpeg_version=ffmpeg_version,
    )

    # Probe ffprobe version
    if ffprobe_path:
        try:
            probe_version = subprocess.run(
                [ffprobe_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if probe_version.returncode == 0:
                result.ffprobe_version = parse_version(probe_version.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Probe capabilities
    caps: dict[str, bool] = {}
    caps["lavfi"] = _check_lavfi(ffmpeg_path)
    for f in REQUIRED_FILTERS:
        caps[f] = check_filter(ffmpeg_path, f)
    for enc in REQUIRED_ENCODERS:
        caps[enc] = check_encoder(ffmpeg_path, enc)
    for audio_enc in REQUIRED_AUDIO_ENCODERS:
        caps[audio_enc] = check_encoder(ffmpeg_path, audio_enc)

    result.capabilities = caps
    return result


def probe_ffmpeg_json() -> str:
    """Convenience: return probe result as JSON string."""
    result = probe_ffmpeg()
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(probe_ffmpeg_json())
