"""FFmpeg-backed, atomic media normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command


@dataclass
class NormalizeTarget:
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate: int | None = None
    loudness_db: float | None = None
    codec: str | None = None
    container: str | None = None


@dataclass
class NormalizeResult:
    success: bool
    output_metadata: dict[str, Any] | None = None
    error: str | None = None
    command: list[str] | None = None
    output_path: str | None = None


class Normalizer:
    """Normalize a media file using a temporary file and atomic publication."""

    def build_command(
        self, source: str | Path, output: str | Path, target: NormalizeTarget
    ) -> list[str]:
        self._validate_target(target)
        filters: list[str] = []
        if target.width and target.height:
            filters.append(
                f"scale={target.width}:{target.height}:force_original_aspect_ratio=decrease"
            )
            filters.append(f"pad={target.width}:{target.height}:(ow-iw)/2:(oh-ih)/2")
        if target.fps:
            filters.append(f"fps={target.fps}")
        command = ["ffmpeg", "-y", "-i", str(source)]
        if filters:
            command += ["-vf", ",".join(filters)]
        if target.sample_rate:
            command += ["-ar", str(target.sample_rate)]
        if target.loudness_db is not None:
            command += ["-af", f"loudnorm=I={target.loudness_db}:TP=-1.5:LRA=11"]
        command += ["-c:v", target.codec or "libx264", "-pix_fmt", "yuv420p"]
        command += ["-c:a", "aac", "-movflags", "+faststart", str(output)]
        return command

    def normalize(
        self,
        source: str | Path | dict[str, Any],
        output_or_target: str | Path | NormalizeTarget,
        target: NormalizeTarget | None = None,
        *,
        timeout_s: float = 300.0,
    ) -> NormalizeResult:
        """Normalize a real file, or retain legacy metadata-only planning.

        Real invocation is ``normalize(source_path, output_path, target)``. The
        two-argument ``normalize(metadata, target)`` form remains a pure plan.
        """
        if isinstance(source, dict):
            if not isinstance(output_or_target, NormalizeTarget):
                return NormalizeResult(False, error="Planning requires NormalizeTarget")
            return self._plan(source, output_or_target)
        if target is None or isinstance(output_or_target, NormalizeTarget):
            return NormalizeResult(
                False, error="Real normalization requires source, output, and target"
            )
        source_path, output_path = Path(source), Path(output_or_target)
        if not source_path.is_file():
            return NormalizeResult(False, error=f"Source media does not exist: {source_path}")
        temp_path = output_path.with_name(
            f".{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}"
        )
        command = self.build_command(source_path, temp_path, target)
        try:
            run_command(command, timeout_s=timeout_s)
            atomic_replace(temp_path, output_path)
            return NormalizeResult(
                True, probe(output_path), command=command, output_path=str(output_path)
            )
        except MediaCommandError as exc:
            temp_path.unlink(missing_ok=True)
            return NormalizeResult(False, error=str(exc), command=command)

    def _plan(self, source_metadata: dict[str, Any], target: NormalizeTarget) -> NormalizeResult:
        self._validate_target(target)
        output_meta = dict(source_metadata)
        for field in ("width", "height", "fps", "sample_rate", "codec"):
            value = getattr(target, field)
            if value is not None:
                output_meta[field] = value
        return NormalizeResult(
            True, output_meta, command=self.build_command("input", "output", target)
        )

    def _validate_target(self, target: NormalizeTarget) -> None:
        if target.width is not None and target.width <= 0:
            raise ValueError("Invalid target width")
        if target.height is not None and target.height <= 0:
            raise ValueError("Invalid target height")
        if target.fps is not None and target.fps <= 0:
            raise ValueError("Invalid target fps")

    def needs_normalization(self, source_metadata: dict[str, Any], target: NormalizeTarget) -> bool:
        return any(
            value is not None and source_metadata.get(field) != value
            for field, value in (
                ("width", target.width),
                ("height", target.height),
                ("codec", target.codec),
            )
        ) or (
            target.fps is not None and abs(float(source_metadata.get("fps", 0)) - target.fps) > 0.01
        )
