"""Dry Run Renderer — execution_plan -> dry_run_report.md.

Report sections:
1. Project summary (project_id, total tasks, ready vs blocked)
2. Per-task detail (workflow, mode, frame count, dependencies, missing assets)
3. Continuity chain visualization
4. Blocked tasks and reasons
5. Asset requirement summary
"""
from __future__ import annotations

from lfo.rendering.markdown import (
    md_heading,
    md_success,
    md_table,
    md_task_id,
    md_warning,
)

from .schema import AssetRequirement, ExecutionPlan, PlannedTask


def render_dry_run_report(plan: ExecutionPlan) -> str:
    """Render execution plan to Markdown dry-run report.

    Args:
        plan: The execution plan to render.

    Returns:
        Markdown string of the dry-run report.
    """
    lines: list[str] = []

    # Section 1: Project summary
    lines.extend(_render_summary(plan))

    # Section 2: Per-task detail
    lines.extend(_render_task_details(plan))

    # Section 3: Continuity chain visualization
    lines.extend(_render_continuity_chains(plan))

    # Section 4: Blocked tasks
    lines.extend(_render_blocked_tasks(plan))

    # Section 5: Asset requirement summary
    lines.extend(_render_asset_summary(plan))

    return "\n".join(lines)


def _count_by_status(plan: ExecutionPlan) -> dict[str, int]:
    """Count tasks by status."""
    counts: dict[str, int] = {}
    for task in plan.planned_tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    return counts


def _render_summary(plan: ExecutionPlan) -> list[str]:
    """Render project summary section."""
    lines: list[str] = []
    lines.append(md_heading("Execution Plan — Dry Run Report", level=1))
    lines.append("")
    lines.append(f"**Project ID**: {md_task_id(plan.project_id)}")
    lines.append(f"**Schema Version**: {plan.schema_version}")
    lines.append(f"**Total Tasks**: {len(plan.planned_tasks)}")
    lines.append("")

    # Status breakdown
    counts = _count_by_status(plan)
    if counts:
        lines.append(md_heading("Status Breakdown", level=3))
        lines.append("")
        status_rows = [[status, str(count)] for status, count in sorted(counts.items())]
        lines.append(md_table(["Status", "Count"], status_rows))
        lines.append("")

    # Ready vs blocked summary
    blocked_count = counts.get("blocked", 0) + counts.get("waiting_assets", 0)
    ready_count = counts.get("planned", 0)

    if blocked_count == 0:
        lines.append(md_success(f"All {ready_count} tasks are planned and ready for execution."))
    else:
        lines.append(md_warning(
            f"{blocked_count} task(s) blocked or waiting for assets, "
            f"{ready_count} task(s) planned."
        ))
    lines.append("")

    return lines


def _render_task_details(plan: ExecutionPlan) -> list[str]:
    """Render per-task detail section."""
    lines: list[str] = []
    lines.append(md_heading("Task Details", level=2))
    lines.append("")

    if not plan.planned_tasks:
        lines.append("*(no tasks)*")
        lines.append("")
        return lines

    # Summary table
    rows: list[list[str]] = []
    for task in plan.planned_tasks:
        deps = ", ".join(task.depends_on) if task.depends_on else "—"
        rows.append([
            md_task_id(task.task_id),
            task.workflow_id or "—",
            task.workflow_mode or "—",
            str(task.aligned_frames) if task.aligned_frames else "—",
            deps,
            task.status,
        ])

    lines.append(md_table(
        ["Task ID", "Workflow", "Mode", "Frames", "Depends On", "Status"],
        rows,
    ))
    lines.append("")

    # Detailed per-task breakdown
    for task in plan.planned_tasks:
        lines.append(md_heading(f"Task: {task.task_id}", level=3))
        lines.append("")
        lines.append(f"- **Type**: {task.task_type}")
        lines.append(f"- **Workflow**: {task.workflow_id} ({task.workflow_family})")
        lines.append(f"- **Mode**: {task.workflow_mode}")
        lines.append(f"- **Reason**: {task.selection_reason}")
        if task.aligned_frames:
            lines.append(f"- **Aligned Frames**: {task.aligned_frames}")
        if task.depends_on:
            deps = ", ".join(md_task_id(d) for d in task.depends_on)
            lines.append(f"- **Dependencies**: {deps}")
        if task.serial_group:
            lines.append(f"- **Serial Group**: {task.serial_group}")
        if task.prompt_blueprint_id:
            lines.append(f"- **Prompt Blueprint**: {task.prompt_blueprint_id}")

        # Missing assets
        missing = [a for a in task.asset_requirements if a.status == "missing"]
        if missing:
            lines.append(f"- **Missing Assets**: {len(missing)}")
            for asset in missing:
                lines.append(f"  - {asset.asset_role} ({asset.requirement_id})")
        lines.append("")

    return lines


def _render_continuity_chains(plan: ExecutionPlan) -> list[str]:
    """Render continuity chain visualization."""
    lines: list[str] = []
    lines.append(md_heading("Continuity Chains", level=2))
    lines.append("")

    # Group tasks by serial_group
    chains: dict[str, list[PlannedTask]] = {}
    for task in plan.planned_tasks:
        if task.serial_group:
            chains.setdefault(task.serial_group, []).append(task)

    if not chains:
        lines.append("*(no continuity chains)*")
        lines.append("")
        return lines

    for chain_id, tasks in sorted(chains.items()):
        task_ids = " → ".join(md_task_id(t.task_id) for t in tasks)
        lines.append(f"- **{chain_id}**: {task_ids}")
    lines.append("")

    return lines


def _render_blocked_tasks(plan: ExecutionPlan) -> list[str]:
    """Render blocked tasks section."""
    lines: list[str] = []
    lines.append(md_heading("Blocked Tasks", level=2))
    lines.append("")

    blocked = [t for t in plan.planned_tasks if t.status in ("blocked", "waiting_assets")]

    if not blocked:
        lines.append(md_success("No blocked tasks."))
        lines.append("")
        return lines

    rows: list[list[str]] = []
    for task in blocked:
        blocking_reasons: list[str] = []
        for asset in task.asset_requirements:
            if asset.blocking_reason:
                blocking_reasons.append(asset.blocking_reason)
        reason = "; ".join(blocking_reasons) if blocking_reasons else task.status
        rows.append([md_task_id(task.task_id), task.status, reason])

    lines.append(md_table(["Task ID", "Status", "Reason"], rows))
    lines.append("")

    return lines


def _render_asset_summary(plan: ExecutionPlan) -> list[str]:
    """Render asset requirement summary."""
    lines: list[str] = []
    lines.append(md_heading("Asset Requirements", level=2))
    lines.append("")

    all_requirements: list[AssetRequirement] = list(plan.asset_requirements)
    for task in plan.planned_tasks:
        all_requirements.extend(task.asset_requirements)

    if not all_requirements:
        lines.append(md_success("No asset requirements."))
        lines.append("")
        return lines

    # Count by role and status
    role_counts: dict[str, dict[str, int]] = {}
    for req in all_requirements:
        if req.asset_role not in role_counts:
            role_counts[req.asset_role] = {}
        role_counts[req.asset_role][req.status] = role_counts[req.asset_role].get(req.status, 0) + 1

    rows: list[list[str]] = []
    for role in sorted(role_counts.keys()):
        status_counts = role_counts[role]
        status_str = ", ".join(f"{s}: {c}" for s, c in sorted(status_counts.items()))
        rows.append([role, status_str])

    lines.append(md_table(["Asset Role", "Status"], rows))
    lines.append("")

    return lines
