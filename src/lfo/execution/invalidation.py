"""Invalidation scope — determine which tasks are affected by a change.

When a clip is modified, only its downstream tasks (and the global
timeline/export) are invalidated. Unrelated clips' outputs remain valid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Invalidation scope types
INVALIDATE_REGENERATE_CLIP = "regenerate_clip"
INVALIDATE_RE_QC_CLIP = "re_qc_clip"
INVALIDATE_REMIX_AUDIO = "remix_audio"
INVALIDATE_REGENERATE_SUBTITLES = "regenerate_subtitles"
INVALIDATE_REASSEMBLE_TIMELINE = "reassemble_timeline"
INVALIDATE_REEXPORT = "reexport"


@dataclass
class InvalidationEvent:
    """Records which tasks are invalidated by a change."""

    source_task: str
    reason: str
    affected_tasks: list[str] = field(default_factory=list)
    scope: dict[str, Any] = field(default_factory=dict)


def invalidate_scope(
    source_task: str,
    reason: str,
    task_graph: dict[str, list[str]],
    clip_task_prefix: str | None = None,
) -> InvalidationEvent:
    """Compute the set of tasks affected by a change to source_task.

    Args:
        source_task: The task_id that changed.
        reason: One of the INVALIDATE_* constants.
        task_graph: Adjacency map: task_id -> list of task_ids that depend on it.
        clip_task_prefix: The clip-specific prefix (e.g. "clip-clip-001.") to
            identify clip-local tasks.

    Returns:
        InvalidationEvent with the full list of affected tasks.
    """
    affected: set[str] = set()

    # BFS/DFS forward propagation through the dependency graph
    _propagate(source_task, task_graph, affected)

    return InvalidationEvent(
        source_task=source_task,
        reason=reason,
        affected_tasks=sorted(affected),
        scope={
            "clip_prefix": clip_task_prefix,
            "propagation": "forward",
        },
    )


def _propagate(
    start: str,
    graph: dict[str, list[str]],
    visited: set[str],
) -> None:
    """Recursively find all downstream tasks."""
    for downstream in graph.get(start, []):
        if downstream not in visited:
            visited.add(downstream)
            _propagate(downstream, graph, visited)


def build_forward_graph(
    tasks: list[tuple[str, list[str]]],
) -> dict[str, list[str]]:
    """Build a forward dependency graph from task (id, dependencies) pairs.

    The result maps each task_id to the list of tasks that directly
    depend on it (its downstream dependents).
    """
    graph: dict[str, list[str]] = {}
    all_ids: set[str] = set()

    for task_id, deps in tasks:
        all_ids.add(task_id)
        if task_id not in graph:
            graph[task_id] = []
        for dep in deps:
            all_ids.add(dep)
            if dep not in graph:
                graph[dep] = []
            graph[dep].append(task_id)

    # Ensure all ids are in the graph
    for tid in all_ids:
        if tid not in graph:
            graph[tid] = []

    return graph


def clip_local_tasks(
    clip_id: str,
    all_task_ids: list[str],
) -> list[str]:
    """Return task ids that belong to a specific clip."""
    prefix = f"clip-{clip_id}."
    return [t for t in all_task_ids if t.startswith(prefix)]
