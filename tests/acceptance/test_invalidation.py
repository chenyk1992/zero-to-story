"""Invalidation scope — verify partial re-do correctness.

When clip 2 is modified, only clip 2's tasks + timeline + export should
be invalidated. Clip 1 and clip 3 outputs must remain valid.
"""
from __future__ import annotations

from lfo.execution.invalidation import (
    INVALIDATE_REGENERATE_CLIP,
    build_forward_graph,
    invalidate_scope,
)


class TestInvalidationScope:
    def test_modify_clip2_only_affects_clip2_and_downstream(self) -> None:
        """3-clip timeline: modifying clip 2 should not affect clip 1 or 3."""
        # Task structure:
        #   gen-1 → qc-1 ┐
        #   gen-2 → qc-2 ├→ timeline → export
        #   gen-3 → qc-3 ┘
        tasks = [
            ("gen-1", []),
            ("qc-1", ["gen-1"]),
            ("gen-2", []),
            ("qc-2", ["gen-2"]),
            ("gen-3", []),
            ("qc-3", ["gen-3"]),
            ("timeline", ["qc-1", "qc-2", "qc-3"]),
            ("export", ["timeline"]),
        ]
        graph = build_forward_graph(tasks)

        # Invalidate gen-2 (clip 2's generation)
        event = invalidate_scope("gen-2", INVALIDATE_REGENERATE_CLIP, graph)

        # Affected downstream: qc-2, timeline, export
        # (gen-2 is the source — already known to be invalidated)
        # NOT affected: gen-1, qc-1, gen-3, qc-3
        affected = set(event.affected_tasks)
        assert "qc-2" in affected
        assert "timeline" in affected
        assert "export" in affected

        # Source task excluded by design
        assert "gen-2" not in affected
        # Other clips unaffected
        assert "gen-1" not in affected
        assert "qc-1" not in affected
        assert "gen-3" not in affected
        assert "qc-3" not in affected

    def test_modify_clip1_does_not_affect_clip3(self) -> None:
        """Modifying clip 1 should not affect clip 3."""
        tasks = [
            ("gen-1", []),
            ("qc-1", ["gen-1"]),
            ("gen-3", []),
            ("qc-3", ["gen-3"]),
            ("timeline", ["qc-1", "qc-3"]),
            ("export", ["timeline"]),
        ]
        graph = build_forward_graph(tasks)

        event = invalidate_scope("gen-1", INVALIDATE_REGENERATE_CLIP, graph)
        affected = set(event.affected_tasks)

        # Downstream of gen-1: qc-1, timeline, export (not gen-1 itself)
        assert "qc-1" in affected
        assert "timeline" in affected
        assert "export" in affected

        assert "gen-1" not in affected
        assert "gen-3" not in affected
        assert "qc-3" not in affected

    def test_isolated_clip_not_affected(self) -> None:
        """Two fully independent clips: changing one doesn't affect the other."""
        tasks = [
            ("gen-A", []),
            ("qc-A", ["gen-A"]),
            ("gen-B", []),
            ("qc-B", ["gen-B"]),
        ]
        graph = build_forward_graph(tasks)

        event = invalidate_scope("gen-A", INVALIDATE_REGENERATE_CLIP, graph)
        affected = set(event.affected_tasks)

        # Only qc-A downstream; gen-A itself excluded (it's the source)
        assert "qc-A" in affected
        assert "gen-A" not in affected
        assert "gen-B" not in affected
        assert "qc-B" not in affected


class TestForwardGraph:
    def test_simple_chain(self) -> None:
        tasks = [("A", []), ("B", ["A"]), ("C", ["B"])]
        graph = build_forward_graph(tasks)
        assert graph["A"] == ["B"]
        assert graph["B"] == ["C"]
        assert graph["C"] == []

    def test_diamond(self) -> None:
        tasks = [("A", []), ("B", ["A"]), ("C", ["A"]), ("D", ["B", "C"])]
        graph = build_forward_graph(tasks)
        assert set(graph["A"]) == {"B", "C"}
        assert graph["B"] == ["D"]
        assert graph["C"] == ["D"]
        assert graph["D"] == []
