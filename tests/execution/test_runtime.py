"""Tests for Runtime scheduler."""
from __future__ import annotations

import pytest

from lfo.execution.dag import build_dag
from lfo.execution.handlers import default_fake_registry
from lfo.execution.materializer import MaterializedClip, MaterializedRun
from lfo.execution.runtime import Runtime
from lfo.execution.states import TaskState


def _make_run(clip_ids: list[str]) -> MaterializedRun:
    clips = [
        MaterializedClip(
            clip_id=cid,
            sequence=i + 1,
            duration_ms=5000,
            operation="video.text_to_video",
            prompt=f"Prompt for {cid}",
            negative_prompt=None,
            seed=None,
            backend_id="comfyui.h3",
            backend_revision="1.0.0",
            workflow_hash="wf123",
        )
        for i, cid in enumerate(clip_ids)
    ]
    return MaterializedRun(
        run_id="run-1",
        package_id="pkg-1",
        package_revision=1,
        package_hash="h",
        materialization_hash="mh",
        clips=clips,
    )


class TestRuntime:
    def test_single_clip_full_execution(self) -> None:
        """Single clip: generate → normalize → qc → mix → subtitle → timeline → export."""
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)

        # Tick until complete
        max_ticks = 20
        ticks = 0
        while not rt.is_complete() and ticks < max_ticks:
            rt.tick()
            ticks += 1

        assert rt.is_complete()
        assert not rt.has_failures()
        # All tasks should be SUCCEEDED
        for task in rt.tasks.values():
            assert task.status == TaskState.SUCCEEDED.value

    def test_two_clips_parallel(self) -> None:
        """Two independent clips should both succeed."""
        run = _make_run(["clip-001", "clip-002"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)

        max_ticks = 30
        ticks = 0
        while not rt.is_complete() and ticks < max_ticks:
            rt.tick()
            ticks += 1

        assert rt.is_complete()
        assert not rt.has_failures()

    def test_task_depends_on_previous(self) -> None:
        """Timeline should not run until all audio.mix tasks succeed."""
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)

        # First tick should process video.generate
        result = rt.tick()
        assert result.tasks_processed >= 1
        # timeline.assemble should still be BLOCKED
        timeline_task = rt.tasks["timeline.assemble"]
        assert timeline_task.status == TaskState.BLOCKED.value

    def test_retry_transient_failure(self) -> None:
        """A transient failure should be retried up to max_retries."""
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry(), max_retries=2)
        rt.load_graph(graph)
        # Force the video.generate task to fail transiently
        gen_task = rt.tasks["clip-clip-001.video.generate"]
        gen_task.metadata["fake_result"] = "transient_fail"

        # Tick: should fail and become FAILED_RETRYABLE
        rt.tick()
        assert gen_task.status == TaskState.FAILED_RETRYABLE.value
        assert gen_task.retry_count == 1

        # Reset to READY and tick again
        rt.reset_retryable()
        rt.tick()
        assert gen_task.status == TaskState.FAILED_RETRYABLE.value
        assert gen_task.retry_count == 2

        # Third time should exhaust retries → FAILED_TERMINAL
        rt.reset_retryable()
        rt.tick()
        assert gen_task.status == TaskState.FAILED_TERMINAL.value

    def test_terminal_failure_stops_clip(self) -> None:
        """A terminal failure stops the clip but doesn't affect unrelated clips."""
        run = _make_run(["clip-001", "clip-002"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)
        # Force clip-001's generate to fail terminally
        gen_task = rt.tasks["clip-clip-001.video.generate"]
        gen_task.metadata["fake_result"] = "terminal_fail"

        # Run to completion
        max_ticks = 30
        ticks = 0
        while not rt.is_complete() and ticks < max_ticks:
            rt.tick()
            ticks += 1

        assert rt.has_failures()
        assert gen_task.status == TaskState.FAILED_TERMINAL.value

    def test_find_ready_tasks(self) -> None:
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)
        ready = rt.find_ready_tasks()
        # Only video.generate should be initially READY
        assert len(ready) == 1
        assert ready[0].task_type == "video.generate"

    def test_create_attempt(self) -> None:
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)
        task_id = "clip-clip-001.video.generate"
        attempt_id = rt.create_attempt(task_id)
        assert attempt_id is not None
        assert task_id in [a.task_id for a in rt.attempts.values()]

    def test_dispatch_unknown_task_type(self) -> None:
        from lfo.execution.handlers import HandlerRegistry, TaskHandler
        from lfo.execution.materializer import MaterializedClip, MaterializedRun
        from lfo.execution.dag import TaskGraph, TaskNode

        rt = Runtime(HandlerRegistry())
        # Manually add a task with no handler
        rt.tasks["orphan"] = rt.tasks.get("orphan") or type("obj", (), {})()
        from lfo.execution.runtime import RuntimeTask
        rt.tasks["orphan"] = RuntimeTask(
            task_id="orphan", task_type="unknown.type", logical_key="orphan",
        )
        result = rt.dispatch("orphan", "att-1")
        assert not result.success
        assert "No handler" in result.error

    def test_is_complete_empty(self) -> None:
        rt = Runtime(default_fake_registry())
        assert rt.is_complete()
