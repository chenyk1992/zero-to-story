"""DAG Builder — constructs task dependency graph.

Dependency rules:
- Video task depends on keyframe tasks for its start_frame/end_frame requirements
- Tasks in the same continuity chain are ordered (previous → next)
- Serial group assignment for continuity chains
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Storyboard

from .schema import PlannedTask


def build_task_dependencies(
    planned_tasks: list[PlannedTask],
    storyboard: Storyboard,
) -> list[PlannedTask]:
    """Build task dependency graph. Returns tasks with populated depends_on.

    Rules:
    - Tasks in the same continuity chain are ordered sequentially
    - All dependencies reference valid task_ids within the plan

    Args:
        planned_tasks: List of planned tasks (from segmenter).
        storyboard: The storyboard (for continuity chain info).

    Returns:
        New list of PlannedTask with depends_on populated.
    """
    if not planned_tasks:
        return []

    # Build lookup: task_id → PlannedTask
    task_map: dict[str, PlannedTask] = {t.task_id: t for t in planned_tasks}

    # Build lookup: shot_id → task_id
    shot_to_task: dict[str, str] = {}
    for task in planned_tasks:
        for target_id in task.target_ids:
            shot_to_task[target_id] = task.task_id

    # For each continuity chain, create sequential dependencies
    for chain in storyboard.continuity_chains:
        prev_task_id: str | None = None
        for shot_id in chain.shot_ids:
            current_task_id = shot_to_task.get(shot_id)
            if current_task_id is None:
                continue
            if prev_task_id is not None and prev_task_id != current_task_id:
                current_task = task_map[current_task_id]
                if prev_task_id not in current_task.depends_on:
                    current_task.depends_on.append(prev_task_id)
            prev_task_id = current_task_id

    # Return tasks in original order
    return planned_tasks
