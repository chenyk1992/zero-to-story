"""DAG builder — construct a task graph from a materialized run.

Standard task types:
- video.generate
- video.upscale (optional)
- media.qc
- audio.mix
- subtitle.render
- timeline.assemble
- export.finalize
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

from lfo.contracts.upscale import resolve_upscale_options
from lfo.execution.materializer import MaterializedRun
from lfo.services.artifact_layout import safe_component

# Standard task types
TASK_VIDEO_GENERATE = "video.generate"
TASK_VIDEO_UPSCALE = "video.upscale"
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

    def validate(self) -> None:
        """Reject malformed graphs before a scheduler can observe them."""
        ids = self.task_ids
        if len(ids) != len(set(ids)):
            raise ValueError("Task graph contains duplicate task ids")
        known = set(ids)
        for task in self.tasks:
            for dependency in task.dependencies:
                if dependency == task.task_id:
                    raise ValueError(f"Task {task.task_id!r} cannot depend on itself")
                if dependency not in known:
                    raise ValueError(
                        f"Task {task.task_id!r} depends on unknown task {dependency!r}"
                    )
        if not self.is_acyclic():
            raise ValueError("Task graph contains a cycle")


def build_dag(materialized_run: MaterializedRun) -> TaskGraph:
    """Build a task graph from a materialized run.

    Structure per clip:
    - video.generate (depends on clip dependencies' generate tasks)
    - video.upscale (optional; depends on generate)
    - media.qc (depends on generate or upscale)
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
    # ``tasks.task_id`` is the database primary key, so it must be unique
    # across runs rather than only inside one graph. ``logical_key`` remains
    # the stable run-independent identity used for idempotency and reporting.
    task_prefix = f"{materialized_run.run_id}."
    layout = materialized_run.artifact_layout
    if not layout:
        raise ValueError("Materialized run is missing its project artifact layout")
    # Build the complete map before adding edges. This deliberately permits a
    # clip to depend on a later sequence item, while still validating cycles.
    clip_ids = [clip.clip_id for clip in materialized_run.clips]
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError("Materialized run contains duplicate clip ids")
    generate_tasks = {
        clip_id: f"{task_prefix}clip-{clip_id}.video.generate" for clip_id in clip_ids
    }

    # Build clip-level tasks
    for clip in materialized_run.clips:
        clip_id = clip.clip_id
        base = f"{task_prefix}clip-{clip_id}"

        # Determine dependencies from Package-level clip dependencies
        clip_deps: list[str] = []
        for dep_clip_id in clip.dependencies:
            if dep_clip_id == clip_id:
                raise ValueError(f"Clip {clip_id!r} cannot depend on itself")
            if dep_clip_id not in generate_tasks:
                raise ValueError(f"Clip {clip_id!r} depends on unknown clip {dep_clip_id!r}")
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
                "run_id": materialized_run.run_id,
                "backend_id": clip.backend_id,
                "backend_revision": clip.backend_revision,
                "workflow_hash": clip.workflow_hash,
                "operation": clip.operation,
                "prompt": clip.prompt,
                "negative_prompt": clip.negative_prompt,
                "seed": clip.seed,
                "duration_ms": clip.duration_ms,
                "aspect_ratio": clip.aspect_ratio,
                "megapixels": clip.megapixels,
                "width": clip.width,
                "height": clip.height,
                "fps": clip.fps,
                "native_audio": clip.native_audio,
                "reference_image_size": clip.reference_image_size,
                "resolved_references": list(clip.resolved_references),
                "output_policy": dict(materialized_run.output_policy),
                "output_path": _task_output_path(layout, "video.generate", clip.clip_id),
                "artifact_layout": dict(layout),
            },
        )
        tasks.append(gen_task)

        upstream_video_id = gen_id
        upscale = resolve_upscale_options(materialized_run.extensions, clip.extensions)
        if upscale.enabled:
            upscale_id = f"{base}.video.upscale"
            tasks.append(
                TaskNode(
                    task_id=upscale_id,
                    task_type=TASK_VIDEO_UPSCALE,
                    logical_key=f"{clip_id}:video.upscale",
                    dependencies=[gen_id],
                    clip_id=clip_id,
                    metadata={
                        "run_id": materialized_run.run_id,
                        "clip_id": clip_id,
                        "input_task_ids": [gen_id],
                        "upscale": upscale.to_dict(),
                        "output_policy": dict(materialized_run.output_policy),
                        "output_path": _task_output_path(layout, "video.upscale", clip.clip_id),
                        "artifact_layout": dict(layout),
                    },
                )
            )
            upstream_video_id = upscale_id

        # 2. media.qc
        qc_id = f"{base}.media.qc"
        qc_task = TaskNode(
            task_id=qc_id,
            task_type=TASK_MEDIA_QC,
            logical_key=f"{clip_id}:media.qc",
            dependencies=[upstream_video_id],
            clip_id=clip_id,
            metadata={
                "run_id": materialized_run.run_id,
                "clip_id": clip_id,
                "duration_ms": clip.duration_ms,
                "input_task_ids": [upstream_video_id],
                "output_policy": dict(materialized_run.output_policy),
                "artifact_layout": dict(layout),
            },
        )
        tasks.append(qc_task)

        # 3. audio.mix
        mix_id = f"{base}.audio.mix"
        mix_task = TaskNode(
            task_id=mix_id,
            task_type=TASK_AUDIO_MIX,
            logical_key=f"{clip_id}:audio.mix",
            dependencies=[qc_id],
            clip_id=clip_id,
            metadata={
                "run_id": materialized_run.run_id,
                "clip_id": clip_id,
                "duration_ms": clip.duration_ms,
                "audio_policy": dict(clip.audio_policy),
                "input_task_ids": [qc_id],
                "output_policy": dict(materialized_run.output_policy),
                "output_path": _task_output_path(layout, "audio.mix", clip.clip_id),
                "artifact_layout": dict(layout),
            },
        )
        tasks.append(mix_task)

        # 4. subtitle.render
        sub_id = f"{base}.subtitle.render"
        sub_task = TaskNode(
            task_id=sub_id,
            task_type=TASK_SUBTITLE_RENDER,
            logical_key=f"{clip_id}:subtitle.render",
            dependencies=[qc_id],
            clip_id=clip_id,
            metadata={
                "run_id": materialized_run.run_id,
                "clip_id": clip_id,
                "sequence": clip.sequence,
                "duration_ms": clip.duration_ms,
                "subtitles": dict(clip.subtitles),
                "input_task_ids": [qc_id],
                "output_policy": dict(materialized_run.output_policy),
                "output_path": _task_output_path(layout, "subtitle.render", clip.clip_id),
                "artifact_layout": dict(layout),
            },
        )
        tasks.append(sub_task)

    # Global tasks
    all_mix_ids = [t.task_id for t in tasks if t.task_type == TASK_AUDIO_MIX]
    all_sub_ids = [t.task_id for t in tasks if t.task_type == TASK_SUBTITLE_RENDER]

    # 5. timeline.assemble
    timeline_id = f"{task_prefix}timeline.assemble"
    timeline_task = TaskNode(
        task_id=timeline_id,
        task_type=TASK_TIMELINE_ASSEMBLE,
        logical_key="timeline.assemble",
        dependencies=all_mix_ids,
        metadata={
            "run_id": materialized_run.run_id,
            "segments": [
                {
                    "clip_id": clip.clip_id,
                    "sequence": clip.sequence,
                    "duration_ms": clip.duration_ms,
                    "input_task_id": f"{task_prefix}clip-{clip.clip_id}.audio.mix",
                }
                for clip in sorted(materialized_run.clips, key=lambda item: item.sequence)
            ],
            "input_task_ids": list(all_mix_ids),
            "output_policy": dict(materialized_run.output_policy),
            "output_path": _task_output_path(layout, "timeline.assemble"),
            "artifact_layout": dict(layout),
        },
    )
    tasks.append(timeline_task)

    # 6. export.finalize
    export_id = f"{task_prefix}export.finalize"
    export_deps = [timeline_id] + all_sub_ids
    export_task = TaskNode(
        task_id=export_id,
        task_type=TASK_EXPORT_FINALIZE,
        logical_key="export.finalize",
        dependencies=export_deps,
        metadata={
            "run_id": materialized_run.run_id,
            "package_id": materialized_run.package_id,
            "package_hash": materialized_run.package_hash,
            "materialization_hash": materialized_run.materialization_hash,
            "segments": timeline_task.metadata["segments"],
            "backend_ids": sorted({clip.backend_id for clip in materialized_run.clips}),
            "workflow_hashes": sorted({clip.workflow_hash for clip in materialized_run.clips}),
            "input_task_ids": list(export_deps),
            "output_policy": dict(materialized_run.output_policy),
            "output_path": _task_output_path(layout, "export.finalize"),
            "artifact_layout": dict(layout),
        },
    )
    tasks.append(export_task)

    graph = TaskGraph(run_id=materialized_run.run_id, tasks=tasks)

    graph.validate()

    return graph


def _task_output_path(
    layout: dict[str, Any], task_type: str, clip_id: str | None = None,
) -> str:
    """Resolve a concrete task path from the immutable layout snapshot."""
    clips_root = pathlib.Path(str(layout["clips_root"]))
    global_root = pathlib.Path(str(layout["global_root"]))
    container = str(layout.get("container") or "mp4").lstrip(".")
    if task_type == "video.generate":
        if clip_id is None:
            raise ValueError("video.generate requires clip_id")
        return str(clips_root / safe_component(clip_id, field="clip_id") / "generated.mp4")
    if task_type == "video.upscale":
        if clip_id is None:
            raise ValueError("video.upscale requires clip_id")
        return str(clips_root / safe_component(clip_id, field="clip_id") / "upscaled.mp4")
    if task_type == "audio.mix":
        if clip_id is None:
            raise ValueError("audio.mix requires clip_id")
        return str(clips_root / safe_component(clip_id, field="clip_id") / f"mixed.{container}")
    if task_type == "subtitle.render":
        if clip_id is None:
            raise ValueError("subtitle.render requires clip_id")
        return str(clips_root / safe_component(clip_id, field="clip_id") / "subtitles.srt")
    if task_type == "timeline.assemble":
        return str(global_root / f"timeline.{container}")
    if task_type == "export.finalize":
        return str(layout["final_path"])
    raise ValueError(f"Unknown task type for output path: {task_type}")
