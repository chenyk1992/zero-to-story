"""Visual Task Service — create + atomic transition.

Creates visual tasks (tasks row + visual_task_contracts) and performs
atomic CAS transitions on (TaskStatus, VisualStage) pairs. The visual
happy path never uses SUCCEEDED.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.errors import VisualContractError
from lfo.visual.purpose import derive_operation, derive_task_type
from lfo.visual.stages import VisualStage, assert_legal_pair
from lfo.visual.task_compiler import compiler_identity_json
from lfo.visual.task_contract import validate_task_package


class VisualTaskService:
    """Create and transition visual tasks with atomic CAS."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_visual_task(
        self,
        *,
        purpose: str,
        project_id: str,
        shot_id: str | None,
        references: list[dict[str, Any]],
        prompt: dict[str, Any] | None = None,
        provider_override: str | None = None,
    ) -> str:
        """Create a visual task with its contract.

        Derives task_type/operation from purpose, inserts a tasks row
        (PLANNED) and a visual_task_contracts row (UNROUTED).

        Args:
            purpose: The visual purpose (e.g. 'character_reference').
            project_id: The project ID.
            shot_id: Optional shot ID.
            references: List of reference dicts (asset_id, role, ...).
            prompt: Optional prompt dict.
            provider_override: Optional provider ID override.

        Returns:
            The new task_id.

        Raises:
            VisualContractError: On invalid purpose or unknown derivation.
        """
        try:
            task_type = derive_task_type(purpose)
            operation = derive_operation(purpose, has_references=bool(references))
        except ValueError as e:
            raise VisualContractError(str(e))

        task_id = str(uuid.uuid4())
        now = _now()

        with self.db.transaction() as conn:
            # 1. Insert task
            conn.execute(
                """INSERT INTO tasks
                   (task_id, project_id, task_type, status, dependencies,
                    content_hash, dependency_hash, params_hash, idempotency_key,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id, project_id, task_type,
                    TaskStatus.PLANNED.value,
                    "[]",  # dependencies
                    "",  # content_hash (filled on promote)
                    "",  # dependency_hash
                    "",  # params_hash
                    str(uuid.uuid4()),  # idempotency_key
                    now, now,
                ),
            )

            # 2. Build contract package for content hash
            pkg_data: dict[str, Any] = {
                "purpose": purpose,
                "operation": operation,
                "task_type": task_type,
                "reference_list": references,
            }
            if prompt is not None:
                pkg_data["prompt"] = prompt
            package = validate_task_package(pkg_data)
            content_hash = package.content_hash()

            # 3. Insert contract
            conn.execute(
                """INSERT INTO visual_task_contracts
                   (task_id, visual_stage, purpose, operation, task_type,
                    reference_list, prompt, compiler_identity_json,
                    provider_id, content_hash,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    VisualStage.UNROUTED.value,
                    purpose,
                    operation,
                    task_type,
                    json.dumps(references, ensure_ascii=False),
                    json.dumps(prompt, ensure_ascii=False) if prompt is not None else None,
                    compiler_identity_json(),
                    provider_override,
                    content_hash,
                    now, now,
                ),
            )

        return task_id

    def transition(
        self,
        task_id: str,
        *,
        expected_task_status: TaskStatus,
        expected_visual_stage: VisualStage,
        new_task_status: TaskStatus,
        new_visual_stage: VisualStage,
        reason: str,
    ) -> None:
        """Atomically transition a visual task's (status, stage) pair.

        Performs CAS on both tasks.status and visual_task_contracts.visual_stage
        in a single transaction. Rejects illegal (status, stage) pairs and
        visual happy-path SUCCEEDED.

        Args:
            task_id: The task to transition.
            expected_task_status: Expected current task status (CAS guard).
            expected_visual_stage: Expected current visual stage (CAS guard).
            new_task_status: New task status.
            new_visual_stage: New visual stage.
            reason: Human-readable reason for the transition.

        Raises:
            IllegalStateTransitionError: If (new_task_status, new_visual_stage)
                is not a legal combination.
            VisualContractError: If CAS fails (state mismatch).
        """
        # Validate the target pair before attempting the transition
        assert_legal_pair(new_task_status, new_visual_stage)

        now = _now()

        with self.db.transaction() as conn:
            # CAS: update tasks.status only if it matches expected
            cursor = conn.execute(
                """UPDATE tasks
                   SET status = ?, updated_at = ?
                   WHERE task_id = ? AND status = ?""",
                (
                    new_task_status.value,
                    now,
                    task_id,
                    expected_task_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise VisualContractError(
                    f"CAS conflict on tasks.status for {task_id}: "
                    f"expected {expected_task_status.value}, "
                    f"target {new_task_status.value}"
                )

            # CAS: update visual_stage only if it matches expected
            cursor = conn.execute(
                """UPDATE visual_task_contracts
                   SET visual_stage = ?, updated_at = ?
                   WHERE task_id = ? AND visual_stage = ?""",
                (
                    new_visual_stage.value,
                    now,
                    task_id,
                    expected_visual_stage.value,
                ),
            )
            if cursor.rowcount != 1:
                raise VisualContractError(
                    f"CAS conflict on visual_stage for {task_id}: "
                    f"expected {expected_visual_stage.value}, "
                    f"target {new_visual_stage.value}"
                )

            # Log event
            row = conn.execute(
                "SELECT project_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.execute(
                """INSERT INTO events
                   (project_id, task_id, event_type, payload)
                   VALUES (?, ?, ?, ?)""",
                (
                    row["project_id"],
                    task_id,
                    "visual_transition",
                    json.dumps({
                        "from_status": expected_task_status.value,
                        "to_status": new_task_status.value,
                        "from_stage": expected_visual_stage.value,
                        "to_stage": new_visual_stage.value,
                        "reason": reason,
                    }, ensure_ascii=False),
                ),
            )


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%fZ"
    )
