"""Small, safe FFmpeg helpers shared by the media pipeline."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class MediaCommandError(RuntimeError):
    """An FFmpeg/FFprobe command failed."""


def run_command(
    command: list[str], *, timeout_s: float = 300.0
) -> subprocess.CompletedProcess[str]:
    """Run a media command without a shell and retain a useful error summary."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise MediaCommandError(f"Media executable not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaCommandError(
            f"Media command timed out after {timeout_s}s: {command[0]}"
        ) from exc
    if result.returncode:
        stderr = (result.stderr or result.stdout or "").strip().replace("\n", " ")[-1200:]
        raise MediaCommandError(f"Media command failed ({result.returncode}): {stderr}")
    return result


def probe(
    path: str | Path, *, ffprobe_bin: str = "ffprobe", timeout_s: float = 30.0
) -> dict[str, Any]:
    """Return normalized, ffprobe-derived media metadata."""
    file_path = Path(path)
    if not file_path.is_file():
        raise MediaCommandError(f"Media file does not exist: {file_path}")
    result = run_command(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(file_path),
        ],
        timeout_s=timeout_s,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = float(payload.get("format", {}).get("duration") or 0)
    fps = 0.0
    if video and video.get("r_frame_rate") not in (None, "0/0"):
        numerator, denominator = str(video["r_frame_rate"]).split("/", 1)
        fps = float(numerator) / float(denominator)
    return {
        "duration_ms": round(duration * 1000),
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": fps or None,
        "codec": video.get("codec_name") if video else None,
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        "channels": audio.get("channels") if audio else None,
    }


def atomic_replace(temp_path: Path, output_path: Path) -> None:
    """Publish a verified temporary output beside its requested destination."""
    if not temp_path.is_file() or temp_path.stat().st_size == 0:
        raise MediaCommandError(f"Media command did not produce an output file: {temp_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.replace(output_path)
