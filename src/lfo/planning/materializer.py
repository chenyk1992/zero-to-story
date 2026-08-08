"""Plan Materializer — writes execution_plan.json to SQLite tasks table.

Behavior:
- Upsert tasks by task_id (stable)
- New tasks -> INSERT
- Existing tasks -> UPDATE
- Tasks in DB but not in plan -> mark SUPERSEDED
- Does NOT delete old attempts
- Does NOT execute tasks
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus

from .schema import ExecutionPlan, PlannedTask


@dataclass
class MaterializationSummary:
    """Summary of materialization changes."""
    inserted: int = 0
    updated: int = 0
    superseded: int = 0
    total: int = 0


class PlanMaterializer:
    """Write execution_plan.json to SQLite tasks table."""

    def __init__(self, db: Database):
        self.db = db

    def apply(
        self,
        execution_plan: ExecutionPlan,
        mark_superceded: bool = True,
    ) -> dict:
        """Sync execution plan to SQLite.

        Args:
            execution_plan: The execution plan to materialize.
            mark_superceded: If True, tasks in DB but not in plan are marked SUPERSEDED.

        Returns:
            Dict summary of changes with keys: inserted, updated, superseded, total.
        """
        summary = MaterializationSummary()

        # Get existing task IDs from DB
        existing_rows = self.db.fetchall(
            "SELECT task_id, status FROM tasks WHERE project_id = ?",
            (execution_plan.project_id,),
        )
        existing_task_ids = {row["task_id"] for row in existing_rows}
        plan_task_ids = {t.task_id for t in execution_plan.planned_tasks}

        with self.db.transaction():
            for task in execution_plan.planned_tasks:
                if task.task_id in existing_task_ids:
                    # UPDATE existing task
                    self._update_task(task)
                    summary.updated += 1
                else:
                    # INSERT new task
                    self._insert_task(task)
                    summary.inserted += 1

            # Mark superseded tasks
            if mark_superceded:
                superseded_ids = existing_task_ids - plan_task_ids
                for tid in superseded_ids:
                    self.db.execute(
                        "UPDATE tasks SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                        "WHERE task_id = ? AND status != ?",
                        (TaskStatus.SUPERSEDED.value, tid, TaskStatus.SUPERSEDED.value),
                    )
                    summary.superseded += 1

        summary.total = len(execution_plan.planned_tasks)
        return {
            "inserted": summary.inserted,
            "updated": summary.updated,
            "superseded": summary.superseded,
            "total": summary.total,
        }

    def _insert_task(self, task: PlannedTask) -> None:
        """Insert a new task into the database."""
        self.db.execute(
            """INSERT INTO tasks (
                task_id, project_id, task_type, status, dependencies,
                serial_group, priority_class, content_hash,
                dependency_hash, params_hash, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.task_id,
                task.project_id,
                task.task_type,
                task.status,
                json.dumps(task.depends_on),
                task.serial_group,
                task.priority_class,
                task.content_hash or None,
                task.dependency_hash or None,
                task.params_hash or None,
                task.idempotency_key or None,
            ),
        )

    def _update_task(self, task: PlannedTask) -> None:
        """Update an existing task in the database."""
        self.db.execute(
            """UPDATE tasks SET
                project_id = ?, task_type = ?, status = ?, dependencies = ?,
                serial_group = ?, priority_class = ?, content_hash = ?,
                dependency_hash = ?, params_hash = ?, idempotency_key = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE task_id = ?""",
            (
                task.project_id,
                task.task_type,
                task.status,
                json.dumps(task.depends_on),
                task.serial_group,
                task.priority_class,
                task.content_hash or None,
                task.dependency_hash or None,
                task.params_hash or None,
                task.idempotency_key or None,
                task.task_id,
            ),
        )
