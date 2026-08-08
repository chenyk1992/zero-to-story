"""Assembly Compiler — concatenate clips via FFmpeg.

Uses the concat demuxer for same-codec clips (fast, stream copy).
Falls back to concat filter with re-encode if stream copy fails.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.assembly.schema import AssemblyClip, AssemblyInputSnapshot, AssemblyResult
from lfo.core.database import Database


@dataclass
class StreamInfo:
    """Minimal stream info for a clip."""
    width: int
    height: int
    fps: float
    has_audio: bool
    duration_sec: float


class AssemblyCompiler:
    """Concatenate clips into a single MP4 via FFmpeg."""

    def __init__(
        self,
        db: Database,
        ffmpeg_path: str | None = None,
        ffprobe_path: str | None = None,
        output_dir: str = "",
    ) -> None:
        self.db = db
        self.ffmpeg_path = ffmpeg_path if ffmpeg_path is not None else (shutil.which("ffmpeg") or "")
        self.ffprobe_path = ffprobe_path if ffprobe_path is not None else (shutil.which("ffprobe") or "")
        self.output_dir = output_dir or os.path.join(os.getcwd(), "assembly_output")

    def assemble(
        self,
        snapshot: AssemblyInputSnapshot,
        output_filename: str = "",
    ) -> AssemblyResult:
        """Concatenate all clips in the snapshot into one MP4.

        Args:
            snapshot: Resolved clips + export profile.
            output_filename: Optional output filename (without extension).

        Returns:
            AssemblyResult with output details.
        """
        result = AssemblyResult()

        if not snapshot.clips:
            result.error = "No clips to assemble"
            return result

        if not self.ffmpeg_path:
            result.error = "ffmpeg not found in PATH"
            return result

        for clip in snapshot.clips:
            if not os.path.exists(clip.file_path):
                result.error = f"Clip file not found: {clip.file_path}"
                return result

        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(
            self.output_dir,
            output_filename or f"assembly_{uuid.uuid4().hex}.mp4",
        )

        # Determine expected FPS from first clip
        expected_fps = snapshot.clips[0].fps if snapshot.clips[0].fps > 0 else 24.0

        # Try concat demuxer first (fast, stream copy)
        concat_file = self._write_concat_file(snapshot.clips)
        demux_err = ""
        try:
            success, demux_err = self._run_concat_demuxer(concat_file, output_path)
            if success and os.path.exists(output_path):
                # Verify FPS — demuxer can alter timebase
                info = self._probe(output_path)
                if info and abs(info.fps - expected_fps) > 0.5:
                    success = False
            if not success:
                if os.path.exists(output_path):
                    os.remove(output_path)
                success, filter_err = self._run_concat_filter(snapshot.clips, output_path)
                if not success:
                    result.error = (
                        f"FFmpeg concatenation failed. "
                        f"Demuxer: {demux_err[-500:]} | "
                        f"Filter: {filter_err[-500:]}"
                    )
                    return result
        finally:
            if os.path.exists(concat_file):
                os.remove(concat_file)

        if not success:
            result.error = f"FFmpeg concatenation failed. Demuxer: {demux_err[:200]}"
            return result

        if not os.path.exists(output_path):
            result.error = "FFmpeg completed but output file not created"
            return result

        # Verify output
        out_info = self._probe(output_path)
        result.success = True
        result.output_file_path = output_path
        result.duration_sec = out_info.duration_sec if out_info else 0.0
        return result

    # -- concat demuxer (fast, stream copy) ------------------------------- #

    def _write_concat_file(self, clips: list[AssemblyClip]) -> str:
        """Write an FFmpeg concat demuxer input file."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="concat_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for clip in clips:
                # Escape single quotes in file paths
                escaped = clip.file_path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        return path

    def _run_concat_demuxer(self, concat_file: str, output_path: str) -> tuple[bool, str]:
        """Run FFmpeg with concat demuxer (stream copy). Returns (success, stderr)."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, str(exc)
        return proc.returncode == 0, proc.stderr[-2000:]

    # -- concat filter (re-encode fallback) -------------------------------- #

    def _run_concat_filter(self, clips: list[AssemblyClip], output_path: str) -> tuple[bool, str]:
        """Run FFmpeg with concat filter (re-encodes to H.264/AAC)."""
        cmd = [self.ffmpeg_path, "-y"]
        for clip in clips:
            cmd.extend(["-i", clip.file_path])

        n = len(clips)
        filter_parts = []
        for i in range(n):
            filter_parts.append(f"[{i}:v][{i}:a]")
        filter_str = "".join(filter_parts) + f"concat=n={n}:v=1:a=1[v][a]"

        expected_fps = clips[0].fps if clips and clips[0].fps > 0 else 24.0
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-map", "[a]",
            "-r", str(int(expected_fps)),
            "-c:v", "libx264",
            "-preset", "medium",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            output_path,
        ])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1200,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, str(exc)
        return proc.returncode == 0, proc.stderr[-2000:]

    # -- probing --------------------------------------------------------- #

    def _probe(self, file_path: str) -> StreamInfo | None:
        """Get basic stream info via ffprobe."""
        if not self.ffprobe_path or not os.path.exists(file_path):
            return None

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None

        if proc.returncode != 0:
            return None

        import json
        data = json.loads(proc.stdout)
        info = StreamInfo(
            width=0, height=0, fps=0.0,
            has_audio=False, duration_sec=0.0,
        )

        fmt = data.get("format", {})
        info.duration_sec = float(fmt.get("duration", 0))

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not info.width:
                info.width = int(stream.get("width", 0))
                info.height = int(stream.get("height", 0))
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    info.fps = float(num) / float(den) if float(den) != 0 else 0
            elif stream.get("codec_type") == "audio":
                info.has_audio = True

        return info


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
