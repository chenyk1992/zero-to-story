"""LFO — Local Film Orchestrator.

A stable, deterministic local video execution engine.
Submit a VideoExecutionPackage; LFO handles the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfo.application.video_runtime import VideoRuntime
    from lfo.contracts.package import VideoExecutionPackage

__all__ = ["VideoExecutionPackage", "VideoRuntime"]


def __getattr__(name: str):
    """Load the legacy package runtime only when explicitly requested."""
    if name == "VideoRuntime":
        from lfo.application.video_runtime import VideoRuntime

        return VideoRuntime
    if name == "VideoExecutionPackage":
        from lfo.contracts.package import VideoExecutionPackage

        return VideoExecutionPackage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
