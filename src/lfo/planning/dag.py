"""DAG Builder — constructs task dependency graph.

Dependency rules:
- Panel video tasks are ordered sequentially by narrative panel order
- Continuity chains add ordering within chains (panel_ids stored in chain.shot_ids)
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
    - Default: sequential panel order (panel_n depends on panel_{n-1})
    - Continuity chains add ordering for panels in the same chain
    - All dependencies reference valid task_ids within the plan

    Args:
        planned_tasks: List of planned tasks (from segmenter).
        storyboard: The storyboard (for panel order and continuity chains).

    Returns:
        New list of PlannedTask with depends_on populated.
    """
    if not planned_tasks:
        return []

    task_map: dict[str, PlannedTask] = {t.task_id: t for t in planned_tasks}

    # Build lookup: panel_id → task_id
    panel_to_task: dict[str, str] = {}
    for task in planned_tasks:
        for target_id in task.target_ids:
            panel_to_task[target_id] = task.task_id

    # Default sequential panel order edges
    panel_order = [p.panel_id for p in storyboard.panels]
    prev_task_id: str | None = None
    for panel_id in panel_order:
        current_task_id = panel_to_task.get(panel_id)
        if current_task_id is None:
            continue
        if prev_task_id is not None and prev_task_id != current_task_id:
            current_task = task_map[current_task_id]
            if prev_task_id not in current_task.depends_on:
                current_task.depends_on.append(prev_task_id)
        prev_task_id = current_task_id

    # Continuity chains (panel_ids stored in chain.shot_ids)
    for chain in storyboard.continuity_chains:
        chain_prev: str | None = None
        for panel_id in chain.shot_ids:
            current_task_id = panel_to_task.get(panel_id)
            if current_task_id is None:
                continue
            if chain_prev is not None and chain_prev != current_task_id:
                current_task = task_map[current_task_id]
                if chain_prev not in current_task.depends_on:
                    current_task.depends_on.append(chain_prev)
            chain_prev = current_task_id

    return planned_tasks
