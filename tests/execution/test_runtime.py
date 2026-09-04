"""Tests for Runtime scheduler."""
from __future__ import annotations

from lfo.execution import ExecutionStore
from lfo.execution.dag import TaskGraph, TaskNode, build_dag
from lfo.execution.handlers import (
    HandlerRegistry,
    HandlerResult,
    TaskHandler,
    default_fake_registry,
)
from lfo.execution.materializer import MaterializedClip, MaterializedRun
from lfo.execution.runtime import PersistentRuntime, Runtime
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
        """Single clip: generate → qc → mix → subtitle → timeline → export."""
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
        timeline_task = rt.tasks["run-1.timeline.assemble"]
        assert timeline_task.status == TaskState.BLOCKED.value

    def test_retry_transient_failure(self) -> None:
        """A transient failure should be retried up to max_retries."""
        run = _make_run(["clip-001"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry(), max_retries=2)
        rt.load_graph(graph)
        # Force the video.generate task to fail transiently
        gen_task = rt.tasks["run-1.clip-clip-001.video.generate"]
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

    def test_qc_failure_is_terminal_failure_not_success(self) -> None:
        run = _make_run(["clip-001"])
        rt = Runtime(default_fake_registry())
        rt.load_graph(build_dag(run))
        qc_task = rt.tasks["run-1.clip-clip-001.media.qc"]
        qc_task.metadata["fake_result"] = "qc_fail"
        for _ in range(5):
            rt.tick()
        assert qc_task.status == TaskState.FAILED_TERMINAL.value
        assert rt.has_failures()

    def test_retryable_failure_is_stalled_not_complete(self) -> None:
        rt = Runtime(default_fake_registry())
        rt.load_graph(build_dag(_make_run(["clip-001"])))
        rt.tasks["run-1.clip-clip-001.video.generate"].metadata["fake_result"] = "transient_fail"
        rt.tick()
        assert not rt.is_complete()
        assert rt.is_stalled()

    def test_terminal_failure_stops_clip(self) -> None:
        """A terminal failure stops the clip but doesn't affect unrelated clips."""
        run = _make_run(["clip-001", "clip-002"])
        graph = build_dag(run)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)
        # Force clip-001's generate to fail terminally
        gen_task = rt.tasks["run-1.clip-clip-001.video.generate"]
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
        task_id = "run-1.clip-clip-001.video.generate"
        attempt_id = rt.create_attempt(task_id)
        assert attempt_id is not None
        assert task_id in [a.task_id for a in rt.attempts.values()]

    def test_dispatch_unknown_task_type(self) -> None:
        from lfo.execution.handlers import HandlerRegistry

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

    def test_persistent_runtime_restores_tasks_and_artifacts(self, tmp_path) -> None:
        store = ExecutionStore(tmp_path / "runtime.db")
        revision_id = store.create_package_revision(
            package_id="pkg-1", project_title="Test", revision=1,
            content_hash="pkg-hash", raw_json="{}",
        )
        store.create_run(run_id="run-1", package_id="pkg-1", revision_id=revision_id)
        runtime = PersistentRuntime(store, default_fake_registry(), "run-1")
        runtime.load_graph(build_dag(_make_run(["clip-001"])))
        runtime.tick()
        assert store.get_task("run-1.clip-clip-001.video.generate")["status"] == "SUCCEEDED"
        qc_row = store.get_task("run-1.clip-clip-001.media.qc")
        assert "run-1.clip-clip-001.video.generate" in qc_row["metadata"]
        restored = PersistentRuntime(store, default_fake_registry(), "run-1")
        restored.restore()
        assert restored.tasks["run-1.clip-clip-001.video.generate"].status == TaskState.SUCCEEDED.value
        assert "run-1.clip-clip-001.video.generate" in restored.artifacts_by_task

    def test_persistent_retry_count_survives_restore(self, tmp_path) -> None:
        store = ExecutionStore(tmp_path / "retry-count.db")
        revision_id = store.create_package_revision(
            package_id="pkg-1", project_title="Test", revision=1,
            content_hash="retry-hash", raw_json="{}",
        )
        store.create_run(run_id="run-retry-count", package_id="pkg-1", revision_id=revision_id)
        runtime = PersistentRuntime(store, default_fake_registry(), "run-retry-count", max_retries=2)
        runtime.load_graph(build_dag(_make_run(["clip-001"])))
        task_id = "run-1.clip-clip-001.video.generate"
        runtime.tasks[task_id].metadata["fake_result"] = "transient_fail"
        runtime.tick()
        assert store.get_task(task_id)["retry_count"] == 1
        restored = PersistentRuntime(store, default_fake_registry(), "run-retry-count")
        restored.restore()
        assert restored.tasks[task_id].retry_count == 1

    def test_prompt_rewrite_waits_without_touching_plan(self) -> None:
        class RewriteOnce(TaskHandler):
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                self.calls += 1
                if self.calls == 1:
                    return HandlerResult(
                        False,
                        error="audio speech timing mismatch",
                        retryable=False,
                        failure_class="audio_quality",
                        recovery_action="rewrite_prompt",
                    )
                return HandlerResult(True, artifact_type="video", artifact_metadata={"file_path": "x"})

        registry = HandlerRegistry()
        handler = RewriteOnce()
        registry.register("video.generate", handler)
        graph = TaskGraph(
            run_id="run-revision",
            tasks=[
                TaskNode(
                    task_id="run-revision.clip-P001.video.generate",
                    task_type="video.generate",
                    logical_key="P001:video.generate",
                    metadata={
                        "prompt": "original",
                        "production_lock": {
                            "schema": "lfo.production-lock.v1",
                            "status": "LOCKED",
                            "max_prompt_revisions": 1,
                        },
                        "plan_hash": "clip-hash",
                    },
                )
            ],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        runtime.tick()
        task = runtime.tasks["run-revision.clip-P001.video.generate"]
        assert task.status == TaskState.WAITING_PROMPT_REVISION.value
        assert task.metadata["failure_class"] == "audio_quality"
        assert task.metadata["prompt_revision_required"] is True
        assert runtime.provide_prompt_revision(task.task_id, "rewritten", plan_hash="clip-hash")
        assert task.status == TaskState.READY.value
        assert task.metadata["prompt"] == "rewritten"
        runtime.tick()
        assert task.status == TaskState.SUCCEEDED.value

    def test_prompt_revision_optional_fields_are_validated_atomically(self) -> None:
        class RevisionHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    False,
                    error="needs wording revision",
                    retryable=False,
                    failure_class="generation_quality",
                    recovery_action="rewrite_prompt",
                )

        registry = HandlerRegistry()
        registry.register("video.generate", RevisionHandler())
        task_id = "run-atomic.clip-P001.video.generate"
        graph = TaskGraph(
            run_id="run-atomic",
            tasks=[
                TaskNode(
                    task_id=task_id,
                    task_type="video.generate",
                    logical_key="P001:video.generate",
                    metadata={
                        "prompt": "original",
                        "production_lock": {
                            "schema": "lfo.production-lock.v1",
                            "status": "LOCKED",
                            "max_prompt_revisions": 1,
                        },
                        "plan_hash": "clip-hash",
                    },
                )
            ],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        runtime.tick()
        task = runtime.tasks[task_id]
        assert not runtime.provide_prompt_revision(
            task_id,
            "new wording",
            plan_hash="clip-hash",
            negative_prompt=object(),
        )
        assert task.metadata["prompt"] == "original"
        assert task.metadata.get("prompt_revision", 0) == 0
        assert runtime.provide_prompt_revision(
            task_id,
            "new wording",
            plan_hash="clip-hash",
            negative_prompt="no red eyes",
            seed=7,
        )
        assert task.metadata["prompt_revision"] == 1


    def test_prompt_revision_rejects_wrong_hash_and_persists_budget_block(self, tmp_path) -> None:
        class AlwaysRewrite(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    False,
                    error="quality mismatch",
                    retryable=False,
                    failure_class="generation_quality",
                    recovery_action="rewrite_prompt",
                )

        registry = HandlerRegistry()
        registry.register("video.generate", AlwaysRewrite())
        graph = TaskGraph(
            run_id="run-persistent-revision",
            tasks=[
                TaskNode(
                    task_id="run-persistent-revision.clip-P001.video.generate",
                    task_type="video.generate",
                    logical_key="P001:video.generate",
                    metadata={
                        "prompt": "original",
                        "production_lock": {
                            "schema": "lfo.production-lock.v1",
                            "status": "LOCKED",
                            "max_prompt_revisions": 0,
                        },
                        "plan_hash": "clip-hash",
                    },
                )
            ],
        )
        store = ExecutionStore(tmp_path / "runtime.db")
        revision_id = store.create_package_revision(
            package_id="pkg", project_title="test", revision=1,
            content_hash="hash", raw_json="{}",
        )
        store.create_run(
            run_id="run-persistent-revision",
            package_id="pkg",
            revision_id=revision_id,
        )
        runtime = PersistentRuntime(store, registry, "run-persistent-revision")
        runtime.load_graph(graph)
        runtime.tick()
        task_id = "run-persistent-revision.clip-P001.video.generate"
        assert not runtime.provide_prompt_revision(task_id, "new", plan_hash="wrong")
        assert runtime.tasks[task_id].status == TaskState.WAITING_PROMPT_REVISION.value
        assert not runtime.provide_prompt_revision(task_id, "new", plan_hash="clip-hash")
        assert runtime.tasks[task_id].status == TaskState.FAILED_TERMINAL.value
        assert store.get_task(task_id)["status"] == TaskState.FAILED_TERMINAL.value

    def test_prompt_rewrite_without_generation_owner_blocks_without_crashing(self) -> None:
        """A global/downstream verdict must not dereference a missing owner."""

        class RewriteHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    False,
                    error="audio contract mismatch",
                    retryable=False,
                    failure_class="audio_quality",
                    recovery_action="rewrite_prompt",
                )

        registry = HandlerRegistry()
        registry.register("audio.mix", RewriteHandler())
        graph = TaskGraph(
            run_id="run-orphan-revision",
            tasks=[
                TaskNode(
                    task_id="run-orphan-revision.audio.mix",
                    task_type="audio.mix",
                    logical_key="audio.mix",
                )
            ],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        runtime.tick()
        task = runtime.tasks["run-orphan-revision.audio.mix"]
        assert task.status == TaskState.FAILED_TERMINAL.value
        assert task.metadata["recovery_action"] == "block_for_user"
        assert task.metadata["prompt_revision_required"] is False

    def test_unknown_recovery_action_fails_closed(self) -> None:
        class UnknownRecovery(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    False,
                    error="extension returned an unsupported route",
                    retryable=True,
                    recovery_action="invented_route",
                )

        registry = HandlerRegistry()
        registry.register("video.generate", UnknownRecovery())
        graph = TaskGraph(
            run_id="run-unknown-recovery",
            tasks=[TaskNode(
                task_id="run-unknown-recovery.video.generate",
                task_type="video.generate",
                logical_key="P001:video.generate",
            )],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        runtime.tick()
        task = runtime.tasks["run-unknown-recovery.video.generate"]
        assert task.status == TaskState.FAILED_TERMINAL.value
        assert task.metadata["recovery_action"] == "block_for_user"
        assert task.metadata["requested_recovery_action"] == "invented_route"

    def test_prompt_rewrite_without_a_production_lock_blocks(self) -> None:
        class RewriteHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    False,
                    error="creative mismatch",
                    retryable=False,
                    recovery_action="rewrite_prompt",
                )

        registry = HandlerRegistry()
        registry.register("video.generate", RewriteHandler())
        graph = TaskGraph(
            run_id="run-unlocked-revision",
            tasks=[TaskNode(
                task_id="run-unlocked-revision.video.generate",
                task_type="video.generate",
                logical_key="P001:video.generate",
            )],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        runtime.tick()
        assert runtime.tasks["run-unlocked-revision.video.generate"].status == TaskState.FAILED_TERMINAL.value

    def test_downstream_prompt_failure_routes_to_generation_and_invalidates_derived_outputs(self) -> None:
        """A downstream audio verdict must revise generation, not audio.mix."""

        class SuccessHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    True,
                    artifact_type=task_type,
                    artifact_metadata={"file_path": f"{task_id}.mp4"},
                )

        registry = HandlerRegistry()
        for task_type in (
            "video.generate",
            "media.qc",
            "audio.mix",
            "timeline.assemble",
            "export.finalize",
        ):
            registry.register(task_type, SuccessHandler())
        graph = TaskGraph(
            run_id="run-downstream-revision",
            tasks=[
                TaskNode(
                    task_id="run-downstream-revision.clip-P001.video.generate",
                    task_type="video.generate",
                    logical_key="P001:video.generate",
                    metadata={
                        "clip_id": "P001",
                        "prompt": "original",
                        "production_lock": {
                            "schema": "lfo.production-lock.v1",
                            "status": "LOCKED",
                            "max_prompt_revisions": 1,
                        },
                        "plan_hash": "clip-hash",
                    },
                ),
                TaskNode(
                    task_id="run-downstream-revision.clip-P001.media.qc",
                    task_type="media.qc",
                    logical_key="P001:media.qc",
                    dependencies=["run-downstream-revision.clip-P001.video.generate"],
                    metadata={"clip_id": "P001", "generation_task_id": "run-downstream-revision.clip-P001.video.generate"},
                ),
                TaskNode(
                    task_id="run-downstream-revision.clip-P001.audio.mix",
                    task_type="audio.mix",
                    logical_key="P001:audio.mix",
                    dependencies=["run-downstream-revision.clip-P001.media.qc"],
                    metadata={"clip_id": "P001", "generation_task_id": "run-downstream-revision.clip-P001.video.generate"},
                ),
                TaskNode(
                    task_id="run-downstream-revision.timeline.assemble",
                    task_type="timeline.assemble",
                    logical_key="timeline.assemble",
                    dependencies=["run-downstream-revision.clip-P001.audio.mix"],
                    metadata={},
                ),
                TaskNode(
                    task_id="run-downstream-revision.export.finalize",
                    task_type="export.finalize",
                    logical_key="export.finalize",
                    dependencies=["run-downstream-revision.timeline.assemble"],
                    metadata={},
                ),
            ],
        )
        runtime = Runtime(registry)
        runtime.load_graph(graph)
        while not runtime.is_complete():
            runtime.tick()

        generation_id = "run-downstream-revision.clip-P001.video.generate"
        audio_id = "run-downstream-revision.clip-P001.audio.mix"
        timeline_id = "run-downstream-revision.timeline.assemble"
        export_id = "run-downstream-revision.export.finalize"
        # Re-open only the downstream task to emulate an analyzer verdict
        # arriving after the artifact was produced; the generation is still
        # the immutable Clip owner of the prompt.
        runtime.tasks[audio_id].status = TaskState.RUNNING.value
        attempt_id = runtime.create_attempt(audio_id)
        runtime.handle_failure(
            audio_id,
            attempt_id,
            HandlerResult(
                False,
                error="speech timing mismatch",
                retryable=False,
                failure_class="audio_quality",
                recovery_action="rewrite_prompt",
            ),
        )
        assert runtime.tasks[generation_id].status == TaskState.WAITING_PROMPT_REVISION.value
        assert runtime.tasks[audio_id].status == TaskState.FAILED_RETRYABLE.value
        assert not runtime.retry(audio_id)

        assert runtime.provide_prompt_revision(
            generation_id,
            "rewritten",
            plan_hash="clip-hash",
        )
        assert runtime.tasks[generation_id].status == TaskState.READY.value
        assert runtime.tasks[audio_id].status == TaskState.BLOCKED.value
        assert runtime.tasks[timeline_id].status == TaskState.BLOCKED.value
        assert runtime.tasks[export_id].status == TaskState.BLOCKED.value
        assert runtime.tasks[generation_id].metadata["prompt"] == "rewritten"

    def test_persistent_downstream_prompt_revision_survives_restore(self, tmp_path) -> None:
        class SuccessHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                return HandlerResult(
                    True,
                    artifact_type=task_type,
                    artifact_metadata={"file_path": f"{task_id}.mp4"},
                )

        registry = HandlerRegistry()
        for task_type in (
            "video.generate",
            "media.qc",
            "audio.mix",
            "timeline.assemble",
            "export.finalize",
        ):
            registry.register(task_type, SuccessHandler())
        generation_id = "run-persisted-downstream.clip-P001.video.generate"
        qc_id = "run-persisted-downstream.clip-P001.media.qc"
        audio_id = "run-persisted-downstream.clip-P001.audio.mix"
        timeline_id = "run-persisted-downstream.timeline.assemble"
        export_id = "run-persisted-downstream.export.finalize"
        graph = TaskGraph(
            run_id="run-persisted-downstream",
            tasks=[
                TaskNode(
                    task_id=generation_id,
                    task_type="video.generate",
                    logical_key="P001:video.generate",
                    metadata={
                        "clip_id": "P001",
                        "prompt": "original",
                        "production_lock": {
                            "schema": "lfo.production-lock.v1",
                            "status": "LOCKED",
                            "max_prompt_revisions": 1,
                        },
                        "plan_hash": "clip-hash",
                    },
                ),
                TaskNode(
                    task_id=qc_id,
                    task_type="media.qc",
                    logical_key="P001:media.qc",
                    dependencies=[generation_id],
                    metadata={"clip_id": "P001", "generation_task_id": generation_id},
                ),
                TaskNode(
                    task_id=audio_id,
                    task_type="audio.mix",
                    logical_key="P001:audio.mix",
                    dependencies=[qc_id],
                    metadata={"clip_id": "P001", "generation_task_id": generation_id},
                ),
                TaskNode(
                    task_id=timeline_id,
                    task_type="timeline.assemble",
                    logical_key="timeline.assemble",
                    dependencies=[audio_id],
                ),
                TaskNode(
                    task_id=export_id,
                    task_type="export.finalize",
                    logical_key="export.finalize",
                    dependencies=[timeline_id],
                ),
            ],
        )
        store = ExecutionStore(tmp_path / "runtime.db")
        revision_id = store.create_package_revision(
            package_id="pkg", project_title="test", revision=1,
            content_hash="hash", raw_json="{}",
        )
        store.create_run(run_id="run-persisted-downstream", package_id="pkg", revision_id=revision_id)
        runtime = PersistentRuntime(store, registry, "run-persisted-downstream")
        runtime.load_graph(graph)
        while not runtime.is_complete():
            runtime.tick()

        # Put the already-published audio task back under a real durable lease
        # so the failure transition mirrors the scheduler path.
        assert store.transition_task(audio_id, "SUCCEEDED", "READY", "test verdict")
        runtime.tasks[audio_id].status = TaskState.READY.value
        assert runtime.acquire_lease(audio_id)
        attempt_id = runtime.create_attempt(audio_id)
        runtime.handle_failure(
            audio_id,
            attempt_id,
            HandlerResult(
                False,
                error="speech timing mismatch",
                retryable=False,
                failure_class="audio_quality",
                recovery_action="rewrite_prompt",
            ),
        )
        assert store.get_task(generation_id)["status"] == TaskState.WAITING_PROMPT_REVISION.value
        assert runtime.provide_prompt_revision(generation_id, "rewritten", plan_hash="clip-hash")
        assert store.get_task(generation_id)["status"] == TaskState.READY.value
        assert store.get_task(audio_id)["status"] == TaskState.BLOCKED.value
        assert store.get_task(timeline_id)["status"] == TaskState.BLOCKED.value

        restored = PersistentRuntime(store, registry, "run-persisted-downstream")
        restored.restore()
        assert restored.tasks[generation_id].status == TaskState.READY.value
        assert restored.tasks[timeline_id].status == TaskState.BLOCKED.value
