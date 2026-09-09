"""DAG builder — construct a task graph from a materialized run.

Standard task types:
- video.generate
- video.upscale (optional)
- media.qc (minimal technical generation-output gate)
- audio.mix / subtitle.render (assembly only)
- timeline.assemble / export.finalize (assembly only)
- media.qc (final exported-video gate for assembly)
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

from lfo.contracts.timeline import TimelineSegment
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
    - media.qc (generation-output gate; depends on generate or upscale)

    A one-Clip generation run ends at ``media.qc``.  A pure passthrough
    assembly (with one or more Clips) adds audio, subtitle, timeline and
    export tasks.

    Global tasks:
    - timeline.assemble (depends on all clips' audio.mix)
    - export.finalize (depends on timeline.assemble + all subtitle.render)
    - final media.qc (depends on export.finalize)

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
    ordered_clips = sorted(materialized_run.clips, key=lambda clip: clip.sequence)
    if not ordered_clips:
        raise ValueError("production execution requires at least one clip")
    single_generation = (
        len(ordered_clips) == 1
        and ordered_clips[0].operation != "video.passthrough"
    )
    passthrough_assembly = all(
        clip.operation == "video.passthrough" for clip in ordered_clips
    )
    if len(ordered_clips) > 1 and not passthrough_assembly:
        raise ValueError(
            "multi-clip execution is reserved for pure passthrough assembly"
        )
    # Build the complete map before adding edges so explicit references can be
    # checked before the single execution path is wired.
    clip_ids = [clip.clip_id for clip in ordered_clips]
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError("Materialized run contains duplicate clip ids")
    generate_tasks = {
        clip_id: f"{task_prefix}clip-{clip_id}.video.generate" for clip_id in clip_ids
    }
    # Build clip-level tasks
    previous_qc_id: str | None = None
    for clip in ordered_clips:
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
        if previous_qc_id is not None and previous_qc_id not in clip_deps:
            clip_deps.append(previous_qc_id)

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
                "clip_id": clip_id,
                "generation_task_id": gen_id,
                "backend_id": clip.backend_id,
                "backend_revision": clip.backend_revision,
                "workflow_hash": clip.workflow_hash,
                "operation": clip.operation,
                "prompt": clip.prompt,
                "seed": clip.seed,
                "duration_ms": clip.duration_ms,
                "aspect_ratio": clip.aspect_ratio,
                "megapixels": clip.megapixels,
                "width": clip.width,
                "height": clip.height,
                "fps": clip.fps,
                "native_audio": clip.native_audio,
                "reference_image_size": clip.reference_image_size,
                "sampler_profile": clip.sampler_profile,
                "steps": clip.steps,
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
                        "generation_task_id": gen_id,
                        "input_task_ids": [gen_id],
                        "upscale": upscale.to_dict(),
                        "output_policy": dict(materialized_run.output_policy),
                        "output_path": _task_output_path(layout, "video.upscale", clip.clip_id),
                        "artifact_layout": dict(layout),
                    },
                )
            )
            upstream_video_id = upscale_id

        # 2. minimal technical generation-quality gate
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
                "generation_task_id": gen_id,
                "input_task_ids": [upstream_video_id],
                "qc_scope": ["decodable", "video_stream", "duration", "resolution"],
                "output_policy": dict(materialized_run.output_policy),
                "artifact_layout": dict(layout),
            },
        )
        tasks.append(qc_task)
        previous_qc_id = qc_id

        # A normal production run ends at the current Panel's verified video.
        # Audio, subtitle, timeline and export work belongs to the caller's
        # final assembly, not to this synchronous one-Panel execution.
        if single_generation:
            continue

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
                "generation_task_id": gen_id,
                "duration_ms": clip.duration_ms,
                "audio_policy": dict(clip.audio_policy),
                "clip_extensions": dict(clip.extensions),
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

    if single_generation:
        graph = TaskGraph(run_id=materialized_run.run_id, tasks=tasks)
        graph.validate()
        return graph

    # Global tasks
    all_mix_ids = [t.task_id for t in tasks if t.task_type == TASK_AUDIO_MIX]
    all_sub_ids = [t.task_id for t in tasks if t.task_type == TASK_SUBTITLE_RENDER]

    # The explicit edit list owns both assembly order and the source range
    # used from each accepted passthrough clip.
    clips_by_id = {clip.clip_id: clip for clip in materialized_run.clips}
    timeline_segments = materialized_run.timeline.segments
    if not timeline_segments:
        timeline_segments = [
            TimelineSegment(clip.clip_id)
            for clip in sorted(materialized_run.clips, key=lambda item: item.sequence)
        ]
    segment_metadata: list[dict[str, Any]] = []
    for index, segment in enumerate(timeline_segments):
        clip = clips_by_id.get(segment.clip_id)
        if clip is None:
            raise ValueError(f"Timeline references unknown clip {segment.clip_id!r}")
        edited_duration_ms = segment.duration_ms(clip.duration_ms)
        segment_metadata.append(
            {
                "clip_id": clip.clip_id,
                "sequence": clip.sequence,
                "timeline_index": index,
                "duration_ms": clip.duration_ms,
                "edited_duration_ms": edited_duration_ms,
                "source_in_ms": segment.source_in_ms,
                "source_out_ms": segment.source_out_ms,
                "input_task_id": f"{task_prefix}clip-{clip.clip_id}.audio.mix",
            }
        )
    timeline_id = f"{task_prefix}timeline.assemble"
    timeline_dependencies = list(all_mix_ids)
    timeline_task = TaskNode(
        task_id=timeline_id,
        task_type=TASK_TIMELINE_ASSEMBLE,
        logical_key="timeline.assemble",
        dependencies=timeline_dependencies,
        metadata={
            "run_id": materialized_run.run_id,
            "segments": segment_metadata,
            "input_task_ids": timeline_dependencies,
            "output_policy": dict(materialized_run.output_policy),
            "output_path": _task_output_path(layout, "timeline.assemble"),
            "artifact_layout": dict(layout),
        },
    )
    tasks.append(timeline_task)

    # 7. export.finalize
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

    # The generated/passthrough Clip gates above only prove that each input
    # is usable.  Assembly and optional subtitle burn-in can still produce an
    # unreadable final file, so completion must pass the same objective media
    # QC once more on the actual exported path.  Keep this as the existing
    # ``media.qc`` handler rather than introducing a second QC contract.
    final_qc_id = f"{task_prefix}final.media.qc"
    tasks.append(
        TaskNode(
            task_id=final_qc_id,
            task_type=TASK_MEDIA_QC,
            logical_key="final.media.qc",
            dependencies=[export_id],
            metadata={
                "run_id": materialized_run.run_id,
                "input_task_ids": [export_id],
                "qc_scope": ["decodable", "video_stream", "duration", "resolution"],
                "artifact_layout": dict(layout),
            },
        )
    )

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
