"""Tests for the single-path, fail-fast Runtime scheduler."""
from __future__ import annotations

from lfo.execution import ExecutionStore
from lfo.execution.dag import TaskGraph, TaskNode, build_dag
from lfo.execution.handlers import HandlerRegistry, TaskHandler, default_fake_registry
from lfo.execution.materializer import MaterializedClip, MaterializedRun
from lfo.execution.runtime import PersistentRuntime, Runtime, RuntimeTask
from lfo.execution.states import TaskState


def _make_run(
    clip_ids: list[str],
    operation: str = "video.text_to_video",
) -> MaterializedRun:
    clips = [
        MaterializedClip(
            clip_id=clip_id,
            sequence=index + 1,
            duration_ms=5000,
            operation=operation,
            prompt=f"Prompt for {clip_id}",
            seed=None,
            backend_id="comfyui.h3",
            backend_revision="1.0.0",
            workflow_hash="wf123",
        )
        for index, clip_id in enumerate(clip_ids)
    ]
    return MaterializedRun(
        run_id="run-1",
        package_id="pkg-1",
        package_revision=1,
        package_hash="a" * 64,
        materialization_hash="b" * 64,
        clips=clips,
        artifact_layout={
            "project_id": "test-project",
            "run_id": "run-1",
            "package_id": "pkg-1",
            "container": "mp4",
            "clips_root": "C:/lfo-test/projects/test-project/outputs/run-1/clips",
            "global_root": "C:/lfo-test/projects/test-project/outputs/run-1/global",
            "final_path": "C:/lfo-test/projects/test-project/final/pkg-1/pkg-1-run-1.mp4",
        },
    )


class TestRuntime:
    def test_single_clip_full_execution(self) -> None:
        runtime = Runtime(default_fake_registry())
        runtime.load_graph(build_dag(_make_run(["clip-001"])))

        for _ in range(20):
            if runtime.is_complete() or runtime.has_failures():
                break
            runtime.tick()

        assert runtime.is_complete()
        assert not runtime.has_failures()
        assert all(task.status == TaskState.SUCCEEDED.value for task in runtime.tasks.values())

    def test_multiple_clips_are_serialized_by_previous_qc(self) -> None:
        graph = build_dag(
            _make_run(["clip-001", "clip-002"], operation="video.passthrough")
        )
        first_qc = "run-1.clip-clip-001.media.qc"
        second_generate = next(
            task for task in graph.tasks if task.logical_key == "clip-002:video.generate"
        )
        assert first_qc in second_generate.dependencies

    def test_final_export_qc_failure_keeps_run_incomplete(self) -> None:
        runtime = Runtime(default_fake_registry())
        runtime.load_graph(
            build_dag(_make_run(["clip-001"], operation="video.passthrough"))
        )
        final_qc = runtime.tasks["run-1.final.media.qc"]
        final_qc.metadata["fake_result"] = "qc_fail"

        for _ in range(20):
            if runtime.is_complete() or runtime.has_failures():
                break
            runtime.tick()

        assert runtime.has_failures()
        assert not runtime.is_complete()
        assert final_qc.status == TaskState.FAILED_TERMINAL.value

    def test_failure_is_terminal_and_stops_the_tick(self) -> None:
        runtime = Runtime(default_fake_registry())
        runtime.load_graph(build_dag(_make_run(["clip-001"])))
        generation = runtime.tasks["run-1.clip-clip-001.video.generate"]
        generation.metadata["fake_result"] = "transient_fail"

        tick = runtime.tick()

        assert tick.tasks_failed == 1
        assert generation.status == TaskState.FAILED_TERMINAL.value

    def test_handler_exception_is_terminal(self) -> None:
        class ExplodingHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                raise RuntimeError("boom")

        registry = HandlerRegistry()
        registry.register("video.generate", ExplodingHandler())
        runtime = Runtime(registry)
        graph = TaskGraph(
            run_id="run-error",
            tasks=[TaskNode(
                task_id="run-error.video.generate",
                task_type="video.generate",
                logical_key="clip:video.generate",
            )],
        )
        runtime.load_graph(graph)

        runtime.tick()

        task = runtime.tasks["run-error.video.generate"]
        assert task.status == TaskState.FAILED_TERMINAL.value
        assert "boom" in (task.error or "")

    def test_dispatch_unknown_task_type(self) -> None:
        runtime = Runtime(HandlerRegistry())
        runtime.tasks["orphan"] = RuntimeTask(
            task_id="orphan", task_type="unknown.type", logical_key="orphan",
        )

        result = runtime.dispatch("orphan", "att-1")

        assert not result.success
        assert "No handler" in (result.error or "")

    def test_persistent_runtime_restores_without_auto_recovery(self, tmp_path) -> None:
        store = ExecutionStore(tmp_path / "runtime.db")
        revision_id = store.create_package_revision(
            package_id="pkg-1", project_title="Test", revision=1,
            content_hash="a" * 64, raw_json="{}",
        )
        store.create_run(run_id="run-1", package_id="pkg-1", revision_id=revision_id)
        runtime = PersistentRuntime(store, default_fake_registry(), "run-1")
        runtime.load_graph(build_dag(_make_run(["clip-001"])))
        runtime.tick()

        restored = PersistentRuntime(store, default_fake_registry(), "run-1")
        restored.restore()

        task_id = "run-1.clip-clip-001.video.generate"
        assert restored.tasks[task_id].status == TaskState.SUCCEEDED.value
        assert task_id in restored.artifacts_by_task


def test_persistent_failure_is_recorded_as_terminal(tmp_path) -> None:
    store = ExecutionStore(tmp_path / "runtime.db")
    revision_id = store.create_package_revision(
        package_id="pkg", project_title="test", revision=1,
        content_hash="a" * 64, raw_json="{}",
    )
    store.create_run(run_id="run-fail", package_id="pkg", revision_id=revision_id)

    runtime = PersistentRuntime(store, default_fake_registry(), "run-fail")
    graph = build_dag(_make_run(["clip-001"]))
    for task in graph.tasks:
        task.task_id = task.task_id.replace("run-1", "run-fail")
        task.dependencies = [dependency.replace("run-1", "run-fail") for dependency in task.dependencies]
        task.metadata["run_id"] = "run-fail"
    graph.run_id = "run-fail"
    runtime.load_graph(graph)
    runtime.tasks["run-fail.clip-clip-001.video.generate"].metadata["fake_result"] = "terminal_fail"

    runtime.tick()

    assert store.get_task("run-fail.clip-clip-001.video.generate")["status"] == TaskState.FAILED_TERMINAL.value
