"""Media probing — identify media type and extract technical metadata.

Uses file-header sniffing and ffprobe (when available) to:
- Confirm media type (not trust extension).
- Extract width, height, duration, fps, codec, audio channels, sample rate.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import struct
from dataclasses import dataclass, field
from typing import Any

# File-header magic bytes for common formats.
_MAGIC_MAP: list[tuple[bytes, str, str]] = [
    # (magic, media_type, subtype)
    (b"\x89PNG\r\n\x1a\n", "image", "png"),
    (b"\xff\xd8\xff", "image", "jpeg"),
    (b"GIF87a", "image", "gif"),
    (b"GIF89a", "image", "gif"),
    (b"RIFF", "video", "riff"),  # could be webp, avi — need deeper check
    (b"\x00\x00\x00\x1cftyp", "video", "mp4"),
    (b"\x00\x00\x00\x20ftyp", "video", "mp4"),
    (b"ftyp", "video", "mp4"),
    (b"\x1aE\xdf\xa3", "video", "mkv"),  # Matroska
    (b"OggS", "audio", "ogg"),
    (b"ID3", "audio", "mp3"),
    (b"\xff\xfb", "audio", "mp3"),
    (b"\xff\xf3", "audio", "mp3"),
    (b"RIFF", "audio", "wav"),  # RIFF could be wav
    (b"WEBVTT", "subtitle", "vtt"),
    (b"1\r\n", "subtitle", "srt"),
    (b"1\n", "subtitle", "srt"),
    (b"%PDF", "document", "pdf"),
]


@dataclass
class ProbeResult:
    """Result of probing a media file."""
    media_type: str
    width: int | None = None
    height: int | None = None
    duration_ms: float | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False
    audio_codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    format_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"media_type": self.media_type}
        if self.width is not None:
            d["width"] = self.width
        if self.height is not None:
            d["height"] = self.height
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.fps is not None:
            d["fps"] = self.fps
        if self.codec is not None:
            d["codec"] = self.codec
        if self.has_audio:
            d["has_audio"] = True
        if self.audio_codec is not None:
            d["audio_codec"] = self.audio_codec
        if self.sample_rate is not None:
            d["sample_rate"] = self.sample_rate
        if self.channels is not None:
            d["channels"] = self.channels
        if self.format_name is not None:
            d["format_name"] = self.format_name
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class MediaProbe:
    """Probe media files to extract technical metadata."""

    def __init__(
        self,
        ffprobe_path: str | None = None,
        max_file_size: int = 2 * 1024 * 1024 * 1024,  # 2 GB
    ) -> None:
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe")
        self.max_file_size = max_file_size

    def probe(self, path: pathlib.Path) -> ProbeResult:
        """Probe a media file.

        Args:
            path: Absolute path to the file.

        Returns:
            ProbeResult with extracted metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is too large or type cannot be determined.
        """
        if not path.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
        size = path.stat().st_size
        if size == 0:
            raise ValueError(f"File is empty: {path}")
        if size > self.max_file_size:
            raise ValueError(
                f"File exceeds max size {self.max_file_size}: {path}"
            )

        # Step 1: header sniffing for fast type detection.
        header_type = self._sniff_header(path)

        # Step 2: ffprobe for rich metadata (if available).
        if self.ffprobe_path:
            try:
                return self._probe_ffprobe(path, header_type)
            except Exception:
                # Fall back to header-only result.
                pass

        return ProbeResult(media_type=header_type or "document")

    def _sniff_header(self, path: pathlib.Path) -> str | None:
        """Read file header and guess media type."""
        try:
            header = path.read_bytes()[:32]
        except OSError:
            return None
        for magic, media_type, _subtype in _MAGIC_MAP:
            if header.startswith(magic):
                # RIFF ambiguity: could be AVI, WAV, WEBP.
                if magic == b"RIFF":
                    if header[8:12] == b"WEBP":
                        return "image"
                    if header[8:12] == b"WAVE":
                        return "audio"
                    if header[8:12] == b"AVI ":
                        return "video"
                    return "video"  # default RIFF
                # ftyp at offset 4 (MP4).
                if magic == b"ftyp" and len(header) > 4:
                    return "video"
                return media_type
        # SRT without leading number (starts with text).
        try:
            text = header.decode("utf-8", errors="ignore")
            if "WEBVTT" in text:
                return "subtitle"
        except Exception:
            pass
        return None

    def _probe_ffprobe(
        self, path: pathlib.Path, fallback_type: str | None
    ) -> ProbeResult:
        """Run ffprobe and parse JSON output."""
        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ValueError(f"ffprobe failed: {e}") from e

        if result.returncode != 0:
            raise ValueError(f"ffprobe error: {result.stderr}")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise ValueError(f"ffprobe JSON parse error: {e}") from e

        return self._parse_ffprobe(data, fallback_type)

    def _parse_ffprobe(
        self, data: dict[str, Any], fallback_type: str | None
    ) -> ProbeResult:
        """Parse ffprobe JSON output into ProbeResult."""
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Find video and audio streams.
        video_stream = None
        audio_stream = None
        for s in streams:
            codec_type = s.get("codec_type")
            if codec_type == "video" and video_stream is None:
                # Skip image streams (album art, etc.) if possible.
                video_stream = s
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = s

        # Determine media type.
        media_type = fallback_type
        if video_stream and not media_type:
            media_type = "video"
        elif audio_stream and not media_type:
            media_type = "audio"
        elif not media_type:
            media_type = "document"

        # Duration and fps.
        duration_ms = None
        if fmt.get("duration"):
            try:
                duration_ms = float(fmt["duration"]) * 1000
            except (ValueError, TypeError):
                pass

        fps = None
        if video_stream:
            fps = self._parse_fps(video_stream.get("r_frame_rate"))

        # Video dimensions.
        width = None
        height = None
        if video_stream:
            try:
                width = int(video_stream.get("width", 0)) or None
                height = int(video_stream.get("height", 0)) or None
            except (ValueError, TypeError):
                pass

        # Audio metadata.
        has_audio = audio_stream is not None
        audio_codec = audio_stream.get("codec_name") if audio_stream else None
        sample_rate = None
        channels = None
        if audio_stream:
            try:
                sample_rate = (
                    int(audio_stream.get("sample_rate", 0)) or None
                )
            except (ValueError, TypeError):
                pass
            try:
                channels = int(audio_stream.get("channels", 0)) or None
            except (ValueError, TypeError):
                pass

        return ProbeResult(
            media_type=media_type or "document",
            width=width,
            height=height,
            duration_ms=duration_ms,
            fps=fps,
            codec=video_stream.get("codec_name") if video_stream else None,
            has_audio=has_audio,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
            channels=channels,
            format_name=fmt.get("format_name"),
        )

    def _parse_fps(self, rate_str: str | None) -> float | None:
        """Parse a frame rate string like '30/1' or '29.970000'."""
        if not rate_str:
            return None
        try:
            if "/" in rate_str:
                num, den = rate_str.split("/", 1)
                n, d = float(num), float(den)
                if d == 0:
                    return None
                return n / d
            return float(rate_str)
        except (ValueError, ZeroDivisionError):
            return None
