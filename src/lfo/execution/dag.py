"""DAG builder — construct a task graph from a materialized run.

Standard task types:
- video.generate
- media.normalize
- media.qc
- audio.mix
- subtitle.render
- timeline.assemble
- export.finalize
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lfo.execution.materializer import MaterializedClip, MaterializedRun


# Standard task types
TASK_VIDEO_GENERATE = "video.generate"
TASK_MEDIA_NORMALIZE = "media.normalize"
TASK_MEDIA_QC = "media.qc"
TASK_AUDIO_MIX = "audio.mix"
TASK_SUBTITLE_RENDER = "subtitle.render"
TASK_TIMELINE_ASSEMBLE = "timeline.assemble"
TASK_EXPORT_FINALIZE = "export.finalize"


@dataclass
class TaskNode:
    """A single task in the DAG."""

    task_id: str
    task_type: str
    logical_key: str
    # task_ids this task depends on
    dependencies: list[str] = field(default_factory=list)
    # Clip this task belongs to (if clip-specific)
    clip_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskGraph:
    """An acyclic task graph for a run."""

    run_id: str
    tasks: list[TaskNode] = field(default_factory=list)

    def task_by_id(self, task_id: str) -> TaskNode | None:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def tasks_by_type(self, task_type: str) -> list[TaskNode]:
        return [t for t in self.tasks if t.task_type == task_type]

    def tasks_by_clip(self, clip_id: str) -> list[TaskNode]:
        return [t for t in self.tasks if t.clip_id == clip_id]

    def roots(self) -> list[TaskNode]:
        """Tasks with no dependencies."""
        return [t for t in self.tasks if not t.dependencies]

    def leaves(self) -> list[TaskNode]:
        """Tasks that no other task depends on."""
        dep_ids = set()
        for t in self.tasks:
            dep_ids.update(t.dependencies)
        return [t for t in self.tasks if t.task_id not in dep_ids]

    @property
    def task_ids(self) -> list[str]:
        return [t.task_id for t in self.tasks]

    def is_acyclic(self) -> bool:
        """Check the graph has no cycles using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        adj: dict[str, list[str]] = {t.task_id: [] for t in self.tasks}
        for t in self.tasks:
            for dep in t.dependencies:
                if dep in adj:
                    adj[dep].append(t.task_id)

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for t in self.tasks:
            if t.task_id not in visited:
                if dfs(t.task_id):
                    return False
        return True


def build_dag(materialized_run: MaterializedRun) -> TaskGraph:
    """Build a task graph from a materialized run.

    Structure per clip:
    - video.generate (depends on clip dependencies' generate tasks)
    - media.normalize (depends on generate)
    - media.qc (depends on normalize)
    - audio.mix (depends on qc)
    - subtitle.render (depends on qc)

    Global tasks:
    - timeline.assemble (depends on all clips' audio.mix)
    - export.finalize (depends on timeline.assemble + all subtitle.render)

    Args:
        materialized_run: The immutable run snapshot.

    Returns:
        TaskGraph that is guaranteed to be acyclic.

    Raises:
        ValueError if the resulting graph has a cycle.
    """
    tasks: list[TaskNode] = []
    # Track generate tasks per clip for dependency wiring
    generate_tasks: dict[str, str] = {}  # clip_id -> task_id

    # Build clip-level tasks
    for clip in materialized_run.clips:
        clip_id = clip.clip_id
        base = f"clip-{clip_id}"

        # Determine dependencies from Package-level clip dependencies
        clip_deps: list[str] = []
        for dep_clip_id in clip.dependencies:
            if dep_clip_id in generate_tasks:
                clip_deps.append(generate_tasks[dep_clip_id])

        # 1. video.generate
        gen_id = f"{base}.video.generate"
        gen_task = TaskNode(
            task_id=gen_id,
            task_type=TASK_VIDEO_GENERATE,
            logical_key=f"{clip_id}:video.generate",
            dependencies=clip_deps,
            clip_id=clip_id,
            metadata={
                "backend_id": clip.backend_id,
                "backend_revision": clip.backend_revision,
                "workflow_hash": clip.workflow_hash,
                "operation": clip.operation,
                "prompt": clip.prompt,
                "duration_ms": clip.duration_ms,
            },
        )
        tasks.append(gen_task)
        generate_tasks[clip_id] = gen_id

        # 2. media.normalize
        norm_id = f"{base}.media.normalize"
        norm_task = TaskNode(
            task_id=norm_id,
            task_type=TASK_MEDIA_NORMALIZE,
            logical_key=f"{clip_id}:media.normalize",
            dependencies=[gen_id],
            clip_id=clip_id,
        )
        tasks.append(norm_task)

        # 3. media.qc
        qc_id = f"{base}.media.qc"
        qc_task = TaskNode(
            task_id=qc_id,
            task_type=TASK_MEDIA_QC,
            logical_key=f"{clip_id}:media.qc",
            dependencies=[norm_id],
            clip_id=clip_id,
        )
        tasks.append(qc_task)

        # 4. audio.mix
        mix_id = f"{base}.audio.mix"
        mix_task = TaskNode(
            task_id=mix_id,
            task_type=TASK_AUDIO_MIX,
            logical_key=f"{clip_id}:audio.mix",
            dependencies=[qc_id],
            clip_id=clip_id,
        )
        tasks.append(mix_task)

        # 5. subtitle.render
        sub_id = f"{base}.subtitle.render"
        sub_task = TaskNode(
            task_id=sub_id,
            task_type=TASK_SUBTITLE_RENDER,
            logical_key=f"{clip_id}:subtitle.render",
            dependencies=[qc_id],
            clip_id=clip_id,
        )
        tasks.append(sub_task)

    # Global tasks
    all_mix_ids = [t.task_id for t in tasks if t.task_type == TASK_AUDIO_MIX]
    all_sub_ids = [t.task_id for t in tasks if t.task_type == TASK_SUBTITLE_RENDER]

    # 6. timeline.assemble
    timeline_id = "timeline.assemble"
    timeline_task = TaskNode(
        task_id=timeline_id,
        task_type=TASK_TIMELINE_ASSEMBLE,
        logical_key="timeline.assemble",
        dependencies=all_mix_ids,
    )
    tasks.append(timeline_task)

    # 7. export.finalize
    export_id = "export.finalize"
    export_deps = [timeline_id] + all_sub_ids
    export_task = TaskNode(
        task_id=export_id,
        task_type=TASK_EXPORT_FINALIZE,
        logical_key="export.finalize",
        dependencies=export_deps,
    )
    tasks.append(export_task)

    graph = TaskGraph(run_id=materialized_run.run_id, tasks=tasks)

    if not graph.is_acyclic():
        raise ValueError("Generated task graph contains a cycle")

    return graph
