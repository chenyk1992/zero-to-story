"""LFO Invalidation — scoped dirty propagation.

When an upstream entity changes, only related downstream assets should be
marked stale, not the entire project.
"""
from __future__ import annotations

from .database import Database
from .runtime import _log_event, _now, get_task, update_task_status
from .state_machine import TaskStatus


def invalidate_upstream(
    db: Database,
    source_task_id: str,
    reason: str = "upstream_changed",
    scope: dict | None = None,
) -> list[str]:
    """Propagate invalidation from a source task to its downstream dependents.

    Returns the list of task_ids that were invalidated.
    """
    source_task = get_task(db, source_task_id)
    if source_task is None:
        return []

    project_id = source_task["project_id"]
    invalidated = []

    # Find all tasks that depend on source_task_id
    all_tasks = db.fetchall(
        "SELECT task_id, dependencies FROM tasks WHERE project_id = ?",
        (project_id,),
    )

    for row in all_tasks:
        deps = row["dependencies"]
        if isinstance(deps, str):
            import json
            deps = json.loads(deps)

        if source_task_id in deps:
            target_id = row["task_id"]
            # Mark as STALE
            update_task_status(db, target_id, TaskStatus.STALE)
            # Record invalidation
            db.execute(
                """INSERT INTO invalidations
                   (source_task_id, target_task_id, reason, scope)
                   VALUES (?, ?, ?, ?)""",
                (
                    source_task_id,
                    target_id,
                    reason,
                    json.dumps(scope or {}) if scope else "{}",
                ),
            )
            invalidated.append(target_id)

    _log_event(
        db, project_id, task_id=source_task_id,
        event_type="invalidation_propagated",
        payload={"reason": reason, "invalidated": invalidated},
    )

    return invalidated


def resolve_invalidation(db: Database, target_task_id: str) -> int:
    """Mark invalidations for a task as resolved (e.g., after re-generation).

    Returns the number of invalidation records resolved.
    """
    now = _now()
    cursor = db.execute(
        """UPDATE invalidations SET resolved = 1, resolved_at = ?
           WHERE target_task_id = ? AND resolved = 0""",
        (now, target_task_id),
    )
    return cursor.rowcount


def get_active_invalidations(db: Database, project_id: str) -> list[dict]:
    """Get all unresolved invalidations for a project."""
    rows = db.fetchall(
        """SELECT i.* FROM invalidations i
           JOIN tasks t ON i.target_task_id = t.task_id
           WHERE t.project_id = ? AND i.resolved = 0
           ORDER BY i.created_at""",
        (project_id,),
    )
    return [
        {
            "invalidation_id": r["invalidation_id"],
            "source_task_id": r["source_task_id"],
            "target_task_id": r["target_task_id"],
            "reason": r["reason"],
            "scope": r["scope"],
            "resolved": bool(r["resolved"]),
            "resolved_at": r["resolved_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
