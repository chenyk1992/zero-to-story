"""MediaService — FFmpeg-based media processing.

Responsibilities:
- get_stream_signature(file_path): extract stream info via ffprobe
- normalize(asset_id, profile_id): normalize video/audio to standard format
- create_selected_clip(normalized_asset_id, in_frame, out_frame_exclusive): extract clip

Standard audio contract (MVP):
- AAC, 48kHz, 2 channels, same length as video
- Silent track generated if source has no audio
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.config.normalize_profile import NormalizeProfile
from lfo.core.database import Database


@dataclass
class StreamSignature:
    """Extracted stream information from a media file."""

    file_path: str
    format_name: str = ""
    duration_sec: float = 0.0
    video_codec: str = ""
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0.0
    video_frame_count: int = 0
    audio_codec: str = ""
    audio_sample_rate: int = 0
    audio_channels: int = 0
    has_video: bool = False
    has_audio: bool = False
    raw_streams: list = field(default_factory=list)


@dataclass
class NormalizedAsset:
    """Result of normalization."""

    asset_id: str
    file_path: str
    duration_sec: float
    video_codec: str
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    width: int
    height: int
    fps: float


@dataclass
class SelectedClipAsset:
    """Result of selected clip extraction."""

    asset_id: str
    file_path: str
    in_frame: int
    out_frame_exclusive: int
    duration_sec: float
    frame_count: int


class MediaService:
    """FFmpeg-based media processing service."""

    # Standard audio contract
    TARGET_AUDIO_CODEC = "aac"
    TARGET_AUDIO_SAMPLE_RATE = 48000
    TARGET_AUDIO_CHANNELS = 2
    TARGET_VIDEO_CODEC = "libx264"

    def __init__(
        self,
        db: Database,
        ffmpeg_path: str | None = None,
        ffprobe_path: str | None = None,
        output_dir: str = "",
    ) -> None:
        self.db = db
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or ""
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or ""
        self.output_dir = output_dir or os.path.join(os.getcwd(), "media_output")

    def get_stream_signature(self, file_path: str) -> StreamSignature:
        """Extract stream information from a media file using ffprobe.

        Args:
            file_path: Path to the media file.

        Returns:
            StreamSignature with extracted metadata.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            RuntimeError: If ffprobe fails.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file not found: {file_path}")

        if not self.ffprobe_path:
            raise RuntimeError("ffprobe not found in PATH")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"ffprobe execution failed: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr[:500]}")

        data = json.loads(result.stdout)
        sig = StreamSignature(file_path=file_path)

        # Parse format
        fmt = data.get("format", {})
        sig.format_name = fmt.get("format_name", "")
        sig.duration_sec = float(fmt.get("duration", 0))

        # Parse streams
        for stream in data.get("streams", []):
            stream_type = stream.get("codec_type", "")
            if stream_type == "video":
                sig.has_video = True
                sig.video_codec = stream.get("codec_name", "")
                sig.video_width = int(stream.get("width", 0))
                sig.video_height = int(stream.get("height", 0))
                # Parse frame rate
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    sig.video_fps = float(num) / float(den) if float(den) != 0 else 0
                else:
                    sig.video_fps = float(fps_str)
                # Frame count
                nb_frames = stream.get("nb_frames")
                if nb_frames:
                    sig.video_frame_count = int(nb_frames)
                elif sig.duration_sec and sig.video_fps:
                    sig.video_frame_count = int(sig.duration_sec * sig.video_fps)
            elif stream_type == "audio":
                sig.has_audio = True
                sig.audio_codec = stream.get("codec_name", "")
                sig.audio_sample_rate = int(stream.get("sample_rate", 0))
                sig.audio_channels = int(stream.get("channels", 0))

            sig.raw_streams.append(stream)

        return sig

    def normalize(
        self,
        asset_id: str,
        profile_id: str,
    ) -> NormalizedAsset:
        """Normalize a video asset to the profile's output format.

        Applies the profile's fit_policy to transform any input aspect ratio
        into the target resolution (e.g. 1080x1920 9:16).

        Args:
            asset_id: The asset to normalize.
            profile_id: The normalization profile (determines output settings).

        Returns:
            NormalizedAsset with the output file path and metadata.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
            RuntimeError: If FFmpeg fails.
        """
        from lfo.config.normalize_profile import get_profile

        profile = get_profile(profile_id)

        # Load asset from DB
        row = self.db.fetchone(
            "SELECT file_path, asset_type FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        if row is None:
            raise FileNotFoundError(f"Asset {asset_id} not found in database")

        file_path = row[0]
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Asset file missing: {file_path}")

        # Get source signature
        sig = self.get_stream_signature(file_path)

        # Build output path
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(
            self.output_dir,
            f"{asset_id}_normalized_{profile_id}.mp4",
        )

        # Build video filter for aspect-ratio transform
        vf = self._build_scale_filter(sig, profile)

        # Build FFmpeg command (always re-encode for the transform)
        fps_num, fps_den = profile.fps.split("/")
        fps_val = str(int(fps_num) / int(fps_den))

        if sig.has_audio:
            # Single input: video filter applies directly
            cmd = [self.ffmpeg_path, "-y", "-i", file_path]
            cmd.extend(["-vf", vf])
            cmd.extend(["-c:v", profile.video_codec, "-preset", "medium"])
            cmd.extend(["-pix_fmt", profile.pixel_format])
            cmd.extend(["-r", fps_val])
            cmd.extend([
                "-c:a", profile.audio_codec,
                "-ar", str(profile.audio_sample_rate),
                "-ac", str(profile.audio_channels),
            ])
        else:
            # No audio in source: add silent audio via second input + filter_complex
            cmd = [self.ffmpeg_path, "-y", "-i", file_path,
                   "-f", "lavfi", "-i", f"anullsrc=r={profile.audio_sample_rate}:cl=mono"]
            cmd.extend([
                "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", profile.video_codec,
                "-preset", "medium",
                "-pix_fmt", profile.pixel_format,
                "-r", fps_val,
                "-c:a", profile.audio_codec,
                "-ac", str(profile.audio_channels),
                "-shortest",
            ])

        cmd.append(output_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"FFmpeg normalization failed: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg normalization failed: {result.stderr[:500]}")

        # Verify output
        out_sig = self.get_stream_signature(output_path)

        # Register normalized output as a new asset
        normalized_asset_id = str(uuid.uuid4().hex)
        task_row = self.db.fetchone(
            "SELECT task_id FROM assets WHERE asset_id = ?", (asset_id,),
        )
        task_id = task_row[0] if task_row else ""
        now = _utc_now()
        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, file_size,
                width, height, duration, frame_count, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                normalized_asset_id,
                task_id,
                "video",
                output_path,
                "",
                os.path.getsize(output_path),
                out_sig.video_width,
                out_sig.video_height,
                out_sig.duration_sec,
                out_sig.video_frame_count,
                json.dumps({
                    "source": "normalize",
                    "source_asset_id": asset_id,
                    "profile_id": profile_id,
                    "fps": out_sig.video_fps,
                    "codec": "h264",
                    "has_audio": out_sig.has_audio,
                }),
                now,
                now,
            ),
        )
        self.db.execute(
            """INSERT INTO asset_relations
               (source_asset_id, target_asset_id, relation_type, metadata)
               VALUES (?, ?, ?, ?)""",
            (asset_id, normalized_asset_id, "normalized_from",
             json.dumps({"profile_id": profile_id})),
        )

        return NormalizedAsset(
            asset_id=normalized_asset_id,
            file_path=output_path,
            duration_sec=out_sig.duration_sec,
            video_codec="h264",
            audio_codec=profile.audio_codec,
            audio_sample_rate=profile.audio_sample_rate,
            audio_channels=profile.audio_channels,
            width=out_sig.video_width,
            height=out_sig.video_height,
            fps=out_sig.video_fps,
        )

    @staticmethod
    def _build_scale_filter(sig: StreamSignature, profile: NormalizeProfile) -> str:
        """Build FFmpeg filter string for aspect-ratio transform.

        cover_crop: scale to fill target, then crop overflow.
        contain_pad: scale to fit inside, then pad with black.
        """
        tw, th = profile.width, profile.height

        if profile.fit_policy == "contain_pad":
            # Scale to fit, pad to exact size, anchor determines padding bias
            if profile.crop_anchor == "left":
                pad_x, pad_y = 0, "(oh-ih)/2"
            elif profile.crop_anchor == "right":
                pad_x, pad_y = "(ow-iw)", "(oh-ih)/2"
            else:
                pad_x, pad_y = "(ow-iw)/2", "(oh-ih)/2"
            return (
                f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                f"pad={tw}:{th}:{pad_x}:{pad_y}:black,"
                f"setsar=1"
            )

        # cover_crop (default): scale to fill, then crop
        if profile.crop_anchor == "left":
            crop_x, crop_y = "0", f"(ih-{th})/2"
        elif profile.crop_anchor == "right":
            crop_x, crop_y = f"(iw-{tw})", f"(ih-{th})/2"
        else:
            crop_x, crop_y = f"(iw-{tw})/2", f"(ih-{th})/2"
        return (
            f"scale={tw}:{th}:force_original_aspect_ratio=increase,"
            f"crop={tw}:{th}:{crop_x}:{crop_y},"
            f"setsar=1"
        )

    def create_selected_clip(
        self,
        normalized_asset_id: str,
        in_frame: int,
        out_frame_exclusive: int,
    ) -> SelectedClipAsset:
        """Extract a selected clip from a normalized asset by frame range.

        Args:
            normalized_asset_id: The normalized asset ID.
            in_frame: Start frame (inclusive).
            out_frame_exclusive: End frame (exclusive).

        Returns:
            SelectedClipAsset with the output file path and metadata.

        Raises:
            ValueError: If frame range is invalid.
            FileNotFoundError: If the source file doesn't exist.
            RuntimeError: If FFmpeg fails.
        """
        if in_frame < 0:
            raise ValueError(f"in_frame must be >= 0, got {in_frame}")
        if out_frame_exclusive <= in_frame:
            raise ValueError(
                f"out_frame_exclusive ({out_frame_exclusive}) must be > in_frame ({in_frame})"
            )

        # Load asset
        row = self.db.fetchone(
            "SELECT file_path FROM assets WHERE asset_id = ?",
            (normalized_asset_id,),
        )
        if row is None:
            raise FileNotFoundError(f"Asset {normalized_asset_id} not found")

        file_path = row[0]
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Asset file missing: {file_path}")

        # Get source signature for frame rate
        sig = self.get_stream_signature(file_path)
        if not sig.video_fps:
            raise RuntimeError(f"Cannot determine FPS for {file_path}")

        # Convert frames to time
        in_time = in_frame / sig.video_fps
        duration_frames = out_frame_exclusive - in_frame

        # Build output path
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(
            self.output_dir,
            f"{normalized_asset_id}_clip_{in_frame}_{out_frame_exclusive}.mp4",
        )

        # Build FFmpeg command (frame-accurate seek)
        cmd = [
            self.ffmpeg_path, "-y",
            "-ss", str(in_time),
            "-i", file_path,
            "-frames:v", str(duration_frames),
            "-r", str(int(sig.video_fps)),
            "-vf", "setsar=1",
            "-c:v", self.TARGET_VIDEO_CODEC,
            "-preset", "medium",
            "-c:a", self.TARGET_AUDIO_CODEC,
            "-ar", str(self.TARGET_AUDIO_SAMPLE_RATE),
            "-ac", str(self.TARGET_AUDIO_CHANNELS),
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"FFmpeg clip extraction failed: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg clip extraction failed: {result.stderr[:500]}")

        # Verify output
        out_sig = self.get_stream_signature(output_path)

        return SelectedClipAsset(
            asset_id=str(uuid.uuid4().hex),
            file_path=output_path,
            in_frame=in_frame,
            out_frame_exclusive=out_frame_exclusive,
            duration_sec=out_sig.duration_sec,
            frame_count=int(out_sig.duration_sec * sig.video_fps) if sig.video_fps else 0,
        )


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
