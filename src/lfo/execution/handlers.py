"""Task handler interface and registry.

Handlers execute tasks and produce artifacts. The base interface is
task-type agnostic; concrete handlers implement specific task types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HandlerResult:
    """Result of a handler execution."""

    success: bool
    # Artifact metadata to record on success
    artifact_type: str | None = None
    artifact_metadata: dict[str, Any] = field(default_factory=dict)
    # Error info on failure
    error: str | None = None
    retryable: bool = True  # False means terminal failure
    # Whether the output passed QC (for QC tasks)
    qc_passed: bool | None = None


class TaskHandler:
    """Base interface for task handlers."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        """Execute a task.

        Args:
            task_id: The task being executed.
            task_type: The task type string.
            logical_key: Stable logical key for this task.
            metadata: Task metadata from the materialized run.
            attempt_id: The attempt being executed.

        Returns:
            HandlerResult indicating success or failure.
        """
        raise NotImplementedError


class FakeVideoHandler(TaskHandler):
    """Fake video handler for testing — simulates various outcomes.

    Behavior is controlled via metadata["fake_result"]:
    - "success": produces a successful result
    - "qc_fail": produces a successful generation but QC fails
    - "transient_fail": produces a retryable failure
    - "terminal_fail": produces a terminal failure
    """

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        result_type = metadata.get("fake_result", "success")
        if result_type == "success":
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={
                    "duration_ms": metadata.get("duration_ms", 5000),
                    "width": metadata.get("width", 864),
                    "height": metadata.get("height", 480),
                    "fps": 24.0,
                    "codec": "h264",
                },
                qc_passed=True,
            )
        elif result_type == "qc_fail":
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={"duration_ms": 100, "width": 100, "height": 100},
                qc_passed=False,
                error="QC failed: duration too short",
            )
        elif result_type == "transient_fail":
            return HandlerResult(
                success=False,
                error="Backend temporarily unavailable",
                retryable=True,
            )
        elif result_type == "terminal_fail":
            return HandlerResult(
                success=False,
                error="Invalid prompt: content policy violation",
                retryable=False,
            )
        else:
            return HandlerResult(
                success=False,
                error=f"Unknown fake_result: {result_type}",
                retryable=True,
            )


class FakeQCHandler(TaskHandler):
    """Fake handler for media.qc tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        result_type = metadata.get("fake_result", "success")
        if task_type == "media.qc" and result_type == "qc_fail":
            return HandlerResult(
                success=True,
                artifact_type="qc_report",
                artifact_metadata={"passed": False},
                error="QC failed",
                qc_passed=False,
            )
        if result_type == "success":
            return HandlerResult(success=True, artifact_type="qc_video")
        return HandlerResult(success=False, error="QC failed", retryable=True)


class FakeAudioHandler(TaskHandler):
    """Fake handler for audio.mix tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        return HandlerResult(success=True, artifact_type="mixed_audio")


class FakeSubtitleHandler(TaskHandler):
    """Fake handler for subtitle.render tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        return HandlerResult(success=True, artifact_type="subtitle_srt")


class FakeTimelineHandler(TaskHandler):
    """Fake handler for timeline.assemble tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        return HandlerResult(success=True, artifact_type="timeline_video")


class FakeExportHandler(TaskHandler):
    """Fake handler for export.finalize tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        return HandlerResult(success=True, artifact_type="exported_video")


class HandlerRegistry:
    """Registry mapping task types to handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    def get(self, task_type: str) -> TaskHandler | None:
        return self._handlers.get(task_type)

    def has_handler(self, task_type: str) -> bool:
        return task_type in self._handlers


def default_fake_registry() -> HandlerRegistry:
    """Create a registry with all fake handlers for testing."""
    reg = HandlerRegistry()
    reg.register("video.generate", FakeVideoHandler())
    reg.register("video.upscale", FakeVideoHandler())
    reg.register("media.qc", FakeQCHandler())
    reg.register("audio.mix", FakeAudioHandler())
    reg.register("subtitle.render", FakeSubtitleHandler())
    reg.register("timeline.assemble", FakeTimelineHandler())
    reg.register("export.finalize", FakeExportHandler())
    return reg
