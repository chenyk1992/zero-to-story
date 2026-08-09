"""Tests for DAG builder."""
from __future__ import annotations

from lfo.execution.dag import (
    TASK_AUDIO_MIX,
    TASK_EXPORT_FINALIZE,
    TASK_MEDIA_NORMALIZE,
    TASK_MEDIA_QC,
    TASK_SUBTITLE_RENDER,
    TASK_TIMELINE_ASSEMBLE,
    TASK_VIDEO_GENERATE,
    TaskGraph,
    TaskNode,
    build_dag,
)
from lfo.execution.materializer import MaterializedClip, MaterializedRun


def _make_clip(
    clip_id: str = "clip-001",
    sequence: int = 1,
    operation: str = "video.text_to_video",
    dependencies: list[str] | None = None,
) -> MaterializedClip:
    return MaterializedClip(
        clip_id=clip_id,
        sequence=sequence,
        duration_ms=5000,
        operation=operation,
        prompt=f"Prompt for {clip_id}",
        negative_prompt=None,
        seed=None,
        backend_id="comfyui.h3",
        backend_revision="1.0.0",
        workflow_hash="wf123",
        dependencies=dependencies or [],
    )


def _make_run(clips: list[MaterializedClip]) -> MaterializedRun:
    return MaterializedRun(
        run_id="run-1",
        package_id="pkg-1",
        package_revision=1,
        package_hash="pkghash",
        materialization_hash="mathash",
        clips=clips,
    )


class TestBuildDag:
    def test_single_clip(self) -> None:
        run = _make_run([_make_clip()])
        graph = build_dag(run)
        # Should have 6 tasks: generate, normalize, qc, mix, subtitle, timeline, export
        # Actually: 5 per clip + timeline + export = 7
        assert len(graph.tasks) == 7
        types = [t.task_type for t in graph.tasks]
        assert types.count(TASK_VIDEO_GENERATE) == 1
        assert types.count(TASK_MEDIA_NORMALIZE) == 1
        assert types.count(TASK_MEDIA_QC) == 1
        assert types.count(TASK_AUDIO_MIX) == 1
        assert types.count(TASK_SUBTITLE_RENDER) == 1
        assert types.count(TASK_TIMELINE_ASSEMBLE) == 1
        assert types.count(TASK_EXPORT_FINALIZE) == 1

    def test_two_clips_no_deps(self) -> None:
        clips = [_make_clip("clip-001"), _make_clip("clip-002", sequence=2)]
        graph = build_dag(_make_run(clips))
        assert len(graph.tasks) == 12  # 5 per clip + timeline + export

    def test_timeline_depends_on_all_mix_tasks(self) -> None:
        clips = [_make_clip("clip-001"), _make_clip("clip-002", sequence=2)]
        graph = build_dag(_make_run(clips))
        timeline = graph.task_by_id("timeline.assemble")
        assert timeline is not None
        mix_tasks = graph.tasks_by_type(TASK_AUDIO_MIX)
        for mt in mix_tasks:
            assert mt.task_id in timeline.dependencies

    def test_export_depends_on_timeline_and_subtitles(self) -> None:
        clips = [_make_clip("clip-001"), _make_clip("clip-002", sequence=2)]
        graph = build_dag(_make_run(clips))
        export = graph.task_by_id("export.finalize")
        assert export is not None
        assert "timeline.assemble" in export.dependencies
        sub_tasks = graph.tasks_by_type(TASK_SUBTITLE_RENDER)
        for st in sub_tasks:
            assert st.task_id in export.dependencies

    def test_chain_dependencies_within_clip(self) -> None:
        graph = build_dag(_make_run([_make_clip()]))
        gen = graph.task_by_id("clip-clip-001.video.generate")
        norm = graph.task_by_id("clip-clip-001.media.normalize")
        qc = graph.task_by_id("clip-clip-001.media.qc")
        mix = graph.task_by_id("clip-clip-001.audio.mix")
        assert gen is not None and norm is not None and qc is not None and mix is not None
        assert gen.task_id in norm.dependencies
        assert norm.task_id in qc.dependencies
        assert qc.task_id in mix.dependencies

    def test_clip_dependencies_wired(self) -> None:
        """Clip 2 depends on Clip 1 — generate task of clip 2 depends on generate of clip 1."""
        clips = [
            _make_clip("clip-001"),
            _make_clip("clip-002", sequence=2, dependencies=["clip-001"]),
        ]
        graph = build_dag(_make_run(clips))
        gen2 = graph.task_by_id("clip-clip-002.video.generate")
        gen1 = graph.task_by_id("clip-clip-001.video.generate")
        assert gen2 is not None and gen1 is not None
        assert gen1.task_id in gen2.dependencies

    def test_is_acyclic(self) -> None:
        graph = build_dag(_make_run([_make_clip()]))
        assert graph.is_acyclic()

    def test_roots_are_generate_tasks(self) -> None:
        clips = [_make_clip("clip-001"), _make_clip("clip-002", sequence=2)]
        graph = build_dag(_make_run(clips))
        roots = graph.roots()
        for r in roots:
            assert r.task_type == TASK_VIDEO_GENERATE

    def test_leaves_include_export(self) -> None:
        graph = build_dag(_make_run([_make_clip()]))
        leaves = graph.leaves()
        leaf_ids = {t.task_id for t in leaves}
        assert "export.finalize" in leaf_ids

    def test_stable_task_ids(self) -> None:
        """Same run produces same task ids."""
        run = _make_run([_make_clip()])
        g1 = build_dag(run)
        g2 = build_dag(run)
        assert g1.task_ids == g2.task_ids


class TestTaskGraph:
    def test_empty_graph_is_acyclic(self) -> None:
        g = TaskGraph(run_id="test", tasks=[])
        assert g.is_acyclic()

    def test_cycle_detection(self) -> None:
        g = TaskGraph(run_id="test", tasks=[
            TaskNode(task_id="a", task_type="x", logical_key="a", dependencies=["c"]),
            TaskNode(task_id="b", task_type="x", logical_key="b", dependencies=["a"]),
            TaskNode(task_id="c", task_type="x", logical_key="c", dependencies=["b"]),
        ])
        assert not g.is_acyclic()

    def test_tasks_by_clip(self) -> None:
        g = TaskGraph(run_id="test", tasks=[
            TaskNode(task_id="t1", task_type="x", logical_key="t1", clip_id="c1"),
            TaskNode(task_id="t2", task_type="x", logical_key="t2", clip_id="c2"),
            TaskNode(task_id="t3", task_type="x", logical_key="t3"),
        ])
        assert len(g.tasks_by_clip("c1")) == 1
        assert len(g.tasks_by_clip("nonexistent")) == 0

    def test_task_by_id_missing(self) -> None:
        g = TaskGraph(run_id="test", tasks=[])
        assert g.task_by_id("missing") is None
