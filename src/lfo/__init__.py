"""LFO — Local Film Orchestrator.

A stable, recoverable local video execution engine.
Submit a VideoExecutionPackage; LFO handles the rest.
"""
from __future__ import annotations

from lfo.application.video_runtime import VideoRuntime
from lfo.contracts.package import VideoExecutionPackage

__all__ = ["VideoExecutionPackage", "VideoRuntime"]
