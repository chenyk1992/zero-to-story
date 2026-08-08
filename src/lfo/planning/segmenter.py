"""Task Segmenter — converts a Storyboard into logical tasks.

MVP rule: 1 Shot = 1 Video Logical Task.

Pure function (no side effects, no DB access).
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Storyboard

from .schema import PlannedTask


def _make_task_id(logical_key: str) -> str:
    """Convert logical key to stable task_id.

    Example: 'video/shot_003' → 'task_video_shot_003'
    """
    return "task_" + logical_key.replace("/", "_")


def segment_storyboard(storyboard: Storyboard, project_id: str = "") -> list[PlannedTask]:
    """Convert a Storyboard into an ordered list of PlannedTask.

    MVP: each shot becomes exactly one video task.

    Args:
        storyboard: The approved storyboard.
        project_id: Override project ID (defaults to storyboard.project.project_id).

    Returns:
        Ordered list of PlannedTask, one per shot.
    """
    pid = project_id or storyboard.project.project_id
    tasks: list[PlannedTask] = []

    # Build a lookup: shot_id → continuity chain_id
    shot_chain: dict[str, str] = {}
    for chain in storyboard.continuity_chains:
        for shot_id in chain.shot_ids:
            shot_chain[shot_id] = chain.chain_id

    for shot in storyboard.shots:
        logical_key = f"video/{shot.shot_id}"
        task_id = _make_task_id(logical_key)
        serial_group = shot_chain.get(shot.shot_id, "")

        task = PlannedTask(
            logical_task_key=logical_key,
            task_id=task_id,
            project_id=pid,
            task_type="video.h3",
            target_ids=[shot.shot_id],
            serial_group=serial_group,
            priority_class=30,
        )
        tasks.append(task)

    return tasks
