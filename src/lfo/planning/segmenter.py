"""Task Segmenter — converts a Storyboard into logical tasks.

Rule: 1 Panel = 1 Video Logical Task.

Pure function (no side effects, no DB access).
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Storyboard

from .schema import PlannedTask


def _make_task_id(logical_key: str) -> str:
    """Convert logical key to stable task_id.

    Example: 'video/panel_01' → 'task_video_panel_01'
    """
    return "task_" + logical_key.replace("/", "_")


def segment_storyboard(storyboard: Storyboard, project_id: str = "") -> list[PlannedTask]:
    """Convert a Storyboard into an ordered list of PlannedTask.

    Each panel becomes exactly one video task.

    Args:
        storyboard: The approved storyboard.
        project_id: Override project ID (defaults to storyboard.project.project_id).

    Returns:
        Ordered list of PlannedTask, one per panel.
    """
    pid = project_id or storyboard.project.project_id
    tasks: list[PlannedTask] = []

    # Build a lookup: panel_id → continuity chain_id (chain stores panel_ids in shot_ids)
    panel_chain: dict[str, str] = {}
    for chain in storyboard.continuity_chains:
        for panel_id in chain.shot_ids:
            panel_chain[panel_id] = chain.chain_id

    for panel in storyboard.panels:
        logical_key = f"video/{panel.panel_id}"
        task_id = _make_task_id(logical_key)
        serial_group = panel_chain.get(panel.panel_id, "")

        task = PlannedTask(
            logical_task_key=logical_key,
            task_id=task_id,
            project_id=pid,
            task_type="video.h3",
            target_ids=[panel.panel_id],
            serial_group=serial_group,
            priority_class=30,
        )
        tasks.append(task)

    return tasks
