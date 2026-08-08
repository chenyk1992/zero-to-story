"""lfo status command — aggregated pipeline status panel.

Shows project phase, tasks by status, blockers, next actions,
invalidations, selected clip reviews, waiting assets, and a GPU panel.
"""
from __future__ import annotations

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.comfy.gpu_guard import get_gpu_status
from lfo.core.database import Database


def cmd_status(
    project_id: str = "",
    db_path: str = "",
) -> dict:
    """lfo status: aggregated pipeline status panel."""
    if not project_id:
        return {"success": False, "error": "project_id is required"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    # Project info
    proj = db.fetchone(
        "SELECT project_id, name, status FROM projects WHERE project_id = ?",
        (project_id,),
    )
    if proj is None:
        return {
            "success": True,
            "project_id": project_id,
            "message": "Project not found",
        }

    # Tasks by status
    task_rows = db.fetchall(
        "SELECT status, COUNT(*) as cnt FROM tasks WHERE project_id = ? GROUP BY status",
        (project_id,),
    )
    tasks_by_status = {status: cnt for status, cnt in task_rows}
    total_tasks = sum(tasks_by_status.values())

    # Completion
    completed = tasks_by_status.get("SUCCEEDED", 0) + tasks_by_status.get("APPROVED", 0)
    completion_pct = (completed / total_tasks * 100) if total_tasks > 0 else 0

    # Blockers: tasks in FAILED_TERMINAL or STALE
    blockers = db.fetchall(
        """SELECT task_id, status, error FROM tasks
           WHERE project_id = ? AND status IN ('FAILED_TERMINAL', 'STALE', 'NEEDS_REMATERIALIZATION')
           ORDER BY updated_at DESC LIMIT 10""",
        (project_id,),
    )
    blocker_list = [
        {"task_id": b[0], "status": b[1], "error": b[2] or ""}
        for b in blockers
    ]

    # Next actions: tasks ready to proceed
    next_actions = db.fetchall(
        """SELECT task_id, status FROM tasks
           WHERE project_id = ? AND status IN ('PLANNED', 'READY', 'WAITING_ASSETS', 'WAITING_USER')
           ORDER BY priority_class ASC, created_at ASC LIMIT 10""",
        (project_id,),
    )
    next_action_list = [
        {"task_id": n[0], "status": n[1]}
        for n in next_actions
    ]

    # Invalidations (unresolved)
    inval_rows = db.fetchall(
        """SELECT source_task_id, target_task_id, reason FROM invalidations
           WHERE resolved = 0 AND target_task_id IN (
               SELECT task_id FROM tasks WHERE project_id = ?
           ) LIMIT 10""",
        (project_id,),
    )
    invalidations = [
        {"source": i[0], "target": i[1], "reason": i[2]}
        for i in inval_rows
    ]

    # Selected clips awaiting review
    clip_reviews = db.fetchall(
        """SELECT selected_clip_id, shot_id, status FROM selected_clips
           WHERE project_id = ? AND status = 'awaiting_review'
           ORDER BY created_at DESC LIMIT 10""",
        (project_id,),
    )
    clip_review_list = [
        {"selected_clip_id": c[0], "shot_id": c[1], "status": c[2]}
        for c in clip_reviews
    ]

    # Waiting assets (tasks stuck in WAITING_ASSETS)
    waiting = db.fetchall(
        """SELECT task_id FROM tasks
           WHERE project_id = ? AND status = 'WAITING_ASSETS'
           LIMIT 10""",
        (project_id,),
    )
    waiting_assets = [w[0] for w in waiting]

    # Project phase
    phase = _compute_phase(tasks_by_status, total_tasks)

    # GPU resource panel — best-effort, never raises
    gpu_status = get_gpu_status()

    return {
        "success": True,
        "project_id": project_id,
        "project_name": proj[1],
        "project_status": proj[2],
        "phase": phase,
        "total_tasks": total_tasks,
        "completed": completed,
        "completion_pct": round(completion_pct, 1),
        "tasks_by_status": tasks_by_status,
        "blockers": blocker_list,
        "next_actions": next_action_list,
        "invalidations": invalidations,
        "clip_reviews_pending": clip_review_list,
        "waiting_assets": waiting_assets,
        "gpu_status": gpu_status,
    }


def _compute_phase(tasks_by_status: dict, total: int) -> str:
    """Determine project phase from task status distribution."""
    if total == 0:
        return "empty"

    succeeded = tasks_by_status.get("SUCCEEDED", 0) + tasks_by_status.get("APPROVED", 0)
    if succeeded == total:
        return "complete"

    running = tasks_by_status.get("RUNNING", 0) + tasks_by_status.get("QUEUED", 0)
    if running > 0:
        return "running"

    planned = tasks_by_status.get("PLANNED", 0)
    if planned == total:
        return "planned"

    waiting = tasks_by_status.get("WAITING_ASSETS", 0) + tasks_by_status.get("WAITING_USER", 0)
    if waiting > 0:
        return "waiting"

    return "in_progress"


@CommandRegistry.register
class StatusCommand:
    """CLI adapter for cmd_status."""

    name = "status"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("project_id", help="Project identifier")
        parser.add_argument("--db", default="", help="Database path")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_status(
            project_id=args.project_id,
            db_path=args.db,
        )
        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="status", data=result)
        else:
            return CommandResult(
                ok=False,
                command="status",
                error={"code": "E_STATUS", "message": result.get("error", "unknown")},
            )
