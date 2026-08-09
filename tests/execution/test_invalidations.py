"""Tests for invalidation scope."""
from __future__ import annotations

from lfo.execution.invalidation import (
    INVALIDATE_REGENERATE_CLIP,
    build_forward_graph,
    invalidate_scope,
)


class TestBuildForwardGraph:
    def test_simple_chain(self) -> None:
        # a -> b -> c (c depends on b, b depends on a)
        tasks = [
            ("a", []),
            ("b", ["a"]),
            ("c", ["b"]),
        ]
        graph = build_forward_graph(tasks)
        assert graph["a"] == ["b"]
        assert graph["b"] == ["c"]
        assert graph["c"] == []

    def test_diamond(self) -> None:
        # a -> b, a -> c, b -> d, c -> d
        tasks = [
            ("a", []),
            ("b", ["a"]),
            ("c", ["a"]),
            ("d", ["b", "c"]),
        ]
        graph = build_forward_graph(tasks)
        assert set(graph["a"]) == {"b", "c"}
        assert graph["b"] == ["d"]
        assert graph["c"] == ["d"]
        assert graph["d"] == []


class TestInvalidateScope:
    def test_single_task(self) -> None:
        tasks = [("a", [])]
        graph = build_forward_graph(tasks)
        event = invalidate_scope("a", INVALIDATE_REGENERATE_CLIP, graph)
        assert event.affected_tasks == []

    def test_chain_propagation(self) -> None:
        # a -> b -> c
        tasks = [("a", []), ("b", ["a"]), ("c", ["b"])]
        graph = build_forward_graph(tasks)
        event = invalidate_scope("a", INVALIDATE_REGENERATE_CLIP, graph)
        assert "b" in event.affected_tasks
        assert "c" in event.affected_tasks

    def test_diamond_propagation(self) -> None:
        tasks = [
            ("a", []),
            ("b", ["a"]),
            ("c", ["a"]),
            ("d", ["b", "c"]),
        ]
        graph = build_forward_graph(tasks)
        event = invalidate_scope("a", INVALIDATE_REGENERATE_CLIP, graph)
        assert set(event.affected_tasks) == {"b", "c", "d"}

    def test_modify_clip2_only_affects_clip2_downstream(self) -> None:
        """Modifying clip 2's generate task should only redo clip 2's downstream + timeline + export."""
        # Clip 1: gen1 -> norm1 -> qc1 -> mix1
        # Clip 2: gen2 -> norm2 -> qc2 -> mix2
        # Timeline: <- mix1, mix2
        # Export: <- timeline
        tasks = [
            ("gen1", []),
            ("norm1", ["gen1"]),
            ("qc1", ["norm1"]),
            ("mix1", ["qc1"]),
            ("gen2", []),
            ("norm2", ["gen2"]),
            ("qc2", ["norm2"]),
            ("mix2", ["qc2"]),
            ("timeline", ["mix1", "mix2"]),
            ("export", ["timeline"]),
        ]
        graph = build_forward_graph(tasks)

        # Invalidate from gen2
        event = invalidate_scope("gen2", INVALIDATE_REGENERATE_CLIP, graph, clip_task_prefix="clip-002.")
        affected = set(event.affected_tasks)

        # Clip 2 downstream should be affected
        assert "norm2" in affected
        assert "qc2" in affected
        assert "mix2" in affected
        # Timeline and export should be affected
        assert "timeline" in affected
        assert "export" in affected
        # Clip 1 tasks should NOT be affected
        assert "gen1" not in affected
        assert "norm1" not in affected
        assert "qc1" not in affected
        assert "mix1" not in affected

    def test_no_infinite_loop(self) -> None:
        """Even with complex graphs, propagation terminates."""
        tasks = [
            ("a", []),
            ("b", ["a"]),
            ("c", ["b"]),
            ("d", ["c"]),
            ("e", ["d"]),
        ]
        graph = build_forward_graph(tasks)
        event = invalidate_scope("a", INVALIDATE_REGENERATE_CLIP, graph)
        assert len(event.affected_tasks) == 4
