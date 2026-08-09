"""Normalizer — resolution/fps normalization and audio loudness normalization.

In production this would call FFmpeg. Here we define the interface and
validation logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizeTarget:
    """Target normalization parameters."""

    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate: int | None = None
    loudness_db: float | None = None  # target integrated loudness (LUFS)
    codec: str | None = None
    container: str | None = None


@dataclass
class NormalizeResult:
    """Result of normalization."""

    success: bool
    output_metadata: dict[str, Any] | None = None
    error: str | None = None
    command: list[str] | None = None  # the FFmpeg command that would run


class Normalizer:
    """Normalize media to a target specification."""

    def normalize(
        self,
        source_metadata: dict[str, Any],
        target: NormalizeTarget,
    ) -> NormalizeResult:
        """Compute the normalization operation needed.

        Args:
            source_metadata: Probe result of the source media.
            target: Desired output specification.

        Returns:
            NormalizeResult with the computed command and expected output.
        """
        # Validate target
        if target.width is not None and target.width <= 0:
            return NormalizeResult(success=False, error="Invalid target width")
        if target.height is not None and target.height <= 0:
            return NormalizeResult(success=False, error="Invalid target height")

        # Build FFmpeg filter chain
        filters: list[str] = []
        if target.width and target.height:
            filters.append(f"scale={target.width}:{target.height}")
        if target.fps:
            filters.append(f"fps={target.fps}")

        # Compute expected output metadata
        output_meta = dict(source_metadata)
        if target.width:
            output_meta["width"] = target.width
        if target.height:
            output_meta["height"] = target.height
        if target.fps:
            output_meta["fps"] = target.fps
        if target.sample_rate:
            output_meta["sample_rate"] = target.sample_rate
        if target.codec:
            output_meta["codec"] = target.codec

        # Build command (for audit/debugging)
        cmd = ["ffmpeg", "-i", "input"]
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        if target.sample_rate:
            cmd.extend(["-ar", str(target.sample_rate)])
        if target.loudness_db is not None:
            cmd.extend(["-af", f"loudnorm=I={target.loudness_db}"])
        if target.codec:
            cmd.extend(["-c:v", target.codec])
        cmd.append("output")

        return NormalizeResult(
            success=True,
            output_metadata=output_meta,
            command=cmd,
        )

    def needs_normalization(
        self,
        source_metadata: dict[str, Any],
        target: NormalizeTarget,
    ) -> bool:
        """Check if source already matches the target."""
        if target.width and source_metadata.get("width") != target.width:
            return True
        if target.height and source_metadata.get("height") != target.height:
            return True
        if target.fps and abs(float(source_metadata.get("fps", 0)) - float(target.fps)) > 0.01:
            return True
        if target.codec and source_metadata.get("codec") != target.codec:
            return True
        return False
