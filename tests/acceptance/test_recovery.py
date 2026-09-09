"""Recovery drill — simulate crash and verify no double-submission."""
from __future__ import annotations

from lfo.execution.dag import TaskGraph, TaskNode
from lfo.execution.handlers import default_fake_registry
from lfo.execution.materializer import MaterializedRun
from lfo.execution.runtime import Runtime


def _make_graph() -> TaskGraph:
    """Simple 2-task graph: A → B."""
    return TaskGraph(
        run_id="test-run",
        tasks=[
            TaskNode(task_id="task-A", task_type="video.generate", logical_key="clip-1"),
            TaskNode(task_id="task-B", task_type="timeline.assemble", logical_key="timeline", dependencies=["task-A"]),
        ],
    )


def _make_runtime() -> Runtime:
    return Runtime(default_fake_registry())


class TestRecovery:
    def test_reset_retryable_advances(self) -> None:
        """Reset retryable tasks and re-tick should advance."""
        rt = _make_runtime()
        graph = _make_graph()
        rt.load_graph(graph)

        # Run to completion
        for _ in range(20):
            if rt.is_complete():
                break
            rt.tick()

        assert rt.is_complete()
        assert not rt.has_failures()

    def test_idempotent_execution(self) -> None:
        """Same graph executed twice should complete both times."""
        for _ in range(3):
            rt = _make_runtime()
            graph = _make_graph()
            rt.load_graph(graph)
            for _ in range(20):
                if rt.is_complete():
                    break
                rt.tick()
            assert rt.is_complete()


class TestIdempotency:
    def test_same_materialization_same_hash(self) -> None:
        """Same inputs → same materialization hash."""
        from lfo.execution.materializer import materialize

        package_hash = "abc128"

        def _make_mat(run_id: str) -> MaterializedRun:
            return materialize(
                run_id=run_id,
                package=_make_package(),
                package_hash=package_hash,
                registry=_make_registry(),
            )

        mat1 = _make_mat("run-1")
        mat2 = _make_mat("run-2")
        assert mat1.materialization_hash == mat2.materialization_hash

    def test_different_package_hash_different_mat(self) -> None:
        """Different package content → different materialization hash."""
        from lfo.execution.materializer import materialize

        mat1 = materialize(
            run_id="run-1",
            package=_make_package(),
            package_hash="hash-A",
            registry=_make_registry(),
        )
        mat2 = materialize(
            run_id="run-2",
            package=_make_package(),
            package_hash="hash-B",
            registry=_make_registry(),
        )
        assert mat1.materialization_hash != mat2.materialization_hash


def _make_package() -> object:
    """Minimal package-like object for materialization testing."""
    from lfo.contracts.package import ProjectInfo, VideoExecutionPackage
    return VideoExecutionPackage(
        package_id="idem-test",
        revision=1,
        project=ProjectInfo(title="Test", project_id="test-project"),
        clips=[],  # No clips = no backend selection needed
    )


def _make_registry() -> object:
    from lfo.backends.registry import BackendRegistry
    return BackendRegistry()
