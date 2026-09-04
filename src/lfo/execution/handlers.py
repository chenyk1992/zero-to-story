"""Task handler interface and registry.

Handlers execute tasks and produce artifacts. The base interface is
task-type agnostic; concrete handlers implement specific task types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RECOVERY_ACTIONS = frozenset({"retry_same", "rewrite_prompt", "block_for_user"})


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
    # Structured recovery hints.  ``failure_class`` is deliberately generic
    # so LFO can route execution failures without understanding story meaning.
    # ``recovery_action`` may be ``retry_same``, ``rewrite_prompt`` or
    # ``block_for_user``; the creative skill owns any prompt rewrite.
    failure_class: str | None = None
    recovery_action: str | None = None


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
    - "qc_fail": produces a successful generation but the generation gate fails
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
                artifact_metadata={"generation_output": True},
                qc_passed=True,
            )
        elif result_type == "qc_fail":
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={"generation_output": True},
                qc_passed=False,
                error="Generation quality gate failed",
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
    """Fake handler for the compatibility media.qc generation gate."""

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
                artifact_metadata={
                    "qc_passed": False,
                    "qc_scope": ["decodable", "video_stream", "duration", "resolution"],
                    "qc_results": [],
                },
                error="Generation quality gate failed",
                qc_passed=False,
            )
        if result_type == "success":
            return HandlerResult(
                success=True,
                artifact_type="qc_video",
                artifact_metadata={
                    "qc_passed": True,
                    "qc_scope": ["decodable", "video_stream", "duration", "resolution"],
                    "qc_results": [],
                },
                qc_passed=True,
            )
        return HandlerResult(success=False, error="Generation quality gate failed", retryable=True)


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


class FakeBoundaryEvidenceHandler(TaskHandler):
    """Fake handler for objective adjacent-clip evidence tasks."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        return HandlerResult(
            success=True,
            artifact_type="boundary_evidence",
            artifact_metadata={"boundary_id": metadata.get("boundary_id")},
        )


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
    reg.register("media.boundary_evidence", FakeBoundaryEvidenceHandler())
    reg.register("timeline.assemble", FakeTimelineHandler())
    reg.register("export.finalize", FakeExportHandler())
    return reg
