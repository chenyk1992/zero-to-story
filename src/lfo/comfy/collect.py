"""Output discovery (3-path), validation, and asset registration."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from .exceptions import OutputNotFoundError, OutputUnstableError

# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class MediaInfo:
    """Metadata extracted from a media file via ffprobe."""

    codec: str = ""
    width: int = 0
    height: int = 0
    frames: int = 0
    fps: float = 0.0
    duration: float = 0.0
    has_audio: bool = False
    raw: dict | None = None


@dataclass
class AssetRecord:
    """A registered output asset."""

    path: Path
    sha256: str
    project_id: str
    task_id: str
    attempt_id: str
    media_info: MediaInfo | None = None
    size_bytes: int = 0


@dataclass
class CollectResult:
    """Result of the output collection pipeline."""

    success: bool = False
    assets: list[AssetRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Collector                                                                   #
# --------------------------------------------------------------------------- #


class ComfyOutputCollector:
    """Discover, validate, and register ComfyUI outputs."""

    DEFAULT_EXTENSIONS: ClassVar[set[str]] = {
        ".mp4", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".wav"
    }

    def __init__(
        self,
        output_root: Path,
        assets_dir: Path | None = None,
    ):
        self.output_root = Path(output_root)
        self.assets_dir = Path(assets_dir) if assets_dir else None

    # -- Path C: filesystem scan ------------------------------------------- #

    def discover(
        self,
        attempt_dir: str,
        extensions: set[str] | None = None,
    ) -> list[Path]:
        """Scan ``output_root/attempt_dir/**/*`` for files matching *extensions*.

        This is the AUTHORITATIVE path (Path C) — always works regardless of
        WebSocket or history API availability.
        """
        exts = extensions or self.DEFAULT_EXTENSIONS
        search_dir = self.output_root / attempt_dir

        if not search_dir.exists():
            raise OutputNotFoundError(f"Attempt directory not found: {search_dir}")

        found: list[Path] = []
        for ext in exts:
            found.extend(search_dir.rglob(f"*{ext}"))

        return sorted(found)

    # -- stability check --------------------------------------------------- #

    def wait_until_stable(
        self,
        path: Path,
        *,
        checks: int = 3,
        interval: float = 0.5,
    ) -> bool:
        """Wait until file size is stable across *checks* consecutive reads.

        Raises ``OutputUnstableError`` if size never stabilises.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise OutputNotFoundError(f"File not found: {file_path}")

        sizes: list[int] = []
        for _ in range(checks):
            sizes.append(file_path.stat().st_size)
            if len(sizes) < checks:
                time.sleep(interval)

        if len(set(sizes)) > 1:
            raise OutputUnstableError(
                f"File size still changing after {checks} checks: {sizes}"
            )
        return True

    # -- media validation -------------------------------------------------- #

    def validate_media(self, path: Path) -> MediaInfo:
        """Run ``ffprobe`` on *path* and return a :class:`MediaInfo`.

        Returns an empty ``MediaInfo`` if ffprobe is unavailable or fails.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return MediaInfo()

        if result.returncode != 0:
            return MediaInfo()

        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError:
            return MediaInfo()

        video_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        audio_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )

        if not video_stream:
            return MediaInfo(raw=probe)

        # Parse frame count
        nb_frames = video_stream.get("nb_frames")
        frames = int(nb_frames) if nb_frames and nb_frames.isdigit() else 0

        # Parse FPS from r_frame_rate fraction
        fps = 0.0
        fps_str = video_stream.get("r_frame_rate", "")
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            with suppress(ValueError):
                fps = float(num) / float(den) if float(den) != 0 else 0.0

        # Duration from format section
        duration = 0.0
        dur_str = probe.get("format", {}).get("duration")
        if dur_str:
            with suppress(ValueError):
                duration = float(dur_str)

        return MediaInfo(
            codec=video_stream.get("codec_name", ""),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            frames=frames,
            fps=round(fps, 3),
            duration=round(duration, 3),
            has_audio=audio_stream is not None,
            raw=probe,
        )

    # -- asset registration ------------------------------------------------ #

    def register_asset(
        self,
        path: Path,
        project_id: str,
        task_id: str,
        attempt_id: str,
    ) -> AssetRecord:
        """Copy the file into the assets tree, compute SHA-256, return record.

        If ``assets_dir`` is not configured, the file stays in place and the
        record points to the original location.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        size = file_path.stat().st_size
        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        final_path = file_path
        if self.assets_dir:
            dest_dir = self.assets_dir / project_id / task_id / attempt_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / file_path.name
            shutil.copy2(file_path, dest)
            final_path = dest

        return AssetRecord(
            path=final_path,
            sha256=sha256,
            project_id=project_id,
            task_id=task_id,
            attempt_id=attempt_id,
            size_bytes=size,
        )

    # -- full pipeline ----------------------------------------------------- #

    def collect(
        self,
        db_record: dict,
        *,
        expected_count: int = 1,
        stable_checks: int = 3,
        stable_interval: float = 0.5,
    ) -> CollectResult:
        """Run the full collection pipeline for one attempt record.

        Steps: discover → wait_until_stable → validate_media → register_asset.
        """
        result = CollectResult()
        attempt_dir = db_record.get("attempt_dir", "")
        project_id = db_record.get("project_id", "")
        task_id = db_record.get("task_id", "")
        attempt_id = db_record.get("attempt_id", "")

        # Discover
        try:
            files = self.discover(attempt_dir)
        except OutputNotFoundError as exc:
            result.errors.append(str(exc))
            return result

        if not files:
            result.errors.append(f"No output files in '{attempt_dir}'")
            return result

        if len(files) != expected_count:
            result.errors.append(
                f"Expected {expected_count} file(s), found {len(files)}"
            )
            # Continue — partial recovery is still valuable

        # Validate + register each file
        for fpath in files:
            try:
                self.wait_until_stable(fpath, checks=stable_checks, interval=stable_interval)
            except OutputUnstableError as exc:
                result.errors.append(f"Unstable file {fpath.name}: {exc}")
                continue

            media_info = self.validate_media(fpath)
            asset = self.register_asset(fpath, project_id, task_id, attempt_id)
            asset.media_info = media_info
            result.assets.append(asset)

        result.success = len(result.assets) > 0
        return result
