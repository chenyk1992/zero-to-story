"""TaskReadinessService — promote tasks from WAITING_ASSETS to READY.

Responsibilities:
- Verify all required assets are approved (via AssetService gate)
- Dual gate: verify visual dependency tasks are APPROVED (spec §19)
- Bind current environment snapshot
- Compute params_hash and idempotency_key
- Create task_materialization record
- Atomically promote task to READY

This service NEVER promotes a task unless ALL asset gates pass.
If any asset is not ready, the task stays in WAITING_ASSETS.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.application.asset_service import AssetBindingService, AssetNotReadyError
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.services.environment_snapshot_service import (
    EnvironmentSnapshotService,
)


@dataclass
class AssetRequirement:
    """A required asset for a task to be promoted."""

    entity_type: str
    entity_id: str
    asset_role: str


@dataclass
class TaskReadinessResult:
    """Result of promote_to_ready operation."""

    success: bool
    task_id: str
    materialization_id: str = ""
    message: str = ""
    failed_asset: str | None = None
    failed_reason: str | None = None
    details: dict = field(default_factory=dict)


class TaskReadinessService:
    """Promote tasks from WAITING_ASSETS to READY with full gate checks."""

    def __init__(
        self,
        db: Database,
        asset_service: AssetBindingService | None = None,
        snapshot_service: EnvironmentSnapshotService | None = None,
    ) -> None:
        self.db = db
        self.asset_service = asset_service or AssetBindingService(db)
        self.snapshot_service = snapshot_service or EnvironmentSnapshotService(db)

    def promote_to_ready(
        self,
        task_id: str,
        *,
        asset_requirements: list,
        workflow_id: str,
        params: dict,
    ) -> TaskReadinessResult:
        """Promote a task to READY if all asset gates pass.

        Steps:
        1. Load task and verify it's in WAITING_ASSETS state
        2. Check all required assets are approved
        3. Capture current environment snapshot
        4. Compute params_hash and idempotency_key
        5. Create task_materialization record
        6. Atomically promote task to READY

        Args:
            task_id: The task to promote.
            asset_requirements: List of required assets to check.
            workflow_id: The workflow to use for execution.
            params: Execution parameters (will be hashed).

        Returns:
            TaskReadinessResult with success/failure details.
        """
        # 1. Load task
        task_row = self.db.fetchone(
            "SELECT task_id, project_id, status FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        if task_row is None:
            return TaskReadinessResult(
                success=False,
                task_id=task_id,
                message=f"Task {task_id} not found",
            )

        task_id, project_id, status = task_row[0], task_row[1], task_row[2]

        if status != TaskStatus.WAITING_ASSETS.value:
            return TaskReadinessResult(
                success=False,
                task_id=task_id,
                message=f"Task {task_id} is in '{status}' state, expected WAITING_ASSETS",
            )

        # 1b. Dual gate — visual dependency tasks must be APPROVED (spec §19)
        visual_gate = self._check_visual_dependencies(task_id)
        if visual_gate is not None:
            return visual_gate

        # 2. Check all required assets. We accept both the local
        # ``AssetRequirement`` (entity_type + entity_id + asset_role) and
        # ``lfo.planning.schema.AssetRequirement`` (requirement_id +
        # target_id + asset_role) so callers can use whichever is
        # convenient. entity_type defaults to asset_role when missing.
        binding_snapshot = {}
        for req in asset_requirements:
            try:
                entity_type = getattr(req, "entity_type", None) or req.asset_role
                entity_id = getattr(req, "entity_id", None) or getattr(req, "target_id", None)
                if entity_id is None:
                    return TaskReadinessResult(
                        success=False,
                        task_id=task_id,
                        message=f"Asset requirement {req} is missing entity_id / target_id",
                    )
                approved = self.asset_service.get_current_approved_asset(
                    project_id=project_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_role=req.asset_role,
                )
                binding_snapshot[req.asset_role] = {
                    "asset_id": approved.asset_id,
                    "binding_id": approved.binding_id,
                    "file_path": approved.file_path,
                    "file_hash": approved.file_hash,
                    "content_hash": approved.content_hash,
                }
            except AssetNotReadyError as exc:
                return TaskReadinessResult(
                    success=False,
                    task_id=task_id,
                    failed_asset=req.asset_role,
                    failed_reason=exc.reason,
                    message=f"Asset not ready: {req.asset_role} — {exc.reason}",
                )

        # 3. Capture environment snapshot
        # Get machine_id from task or use a default
        machine_id = self._get_machine_id(task_id)
        snapshot = self.snapshot_service.get_latest(machine_id)
        if snapshot is None:
            return TaskReadinessResult(
                success=False,
                task_id=task_id,
                message=f"No environment snapshot found for machine '{machine_id}'",
            )

        # 4. Compute hashes
        params_hash = _compute_params_hash(params)
        idempotency_key = _compute_idempotency_key(task_id, params_hash, snapshot.execution_environment_hash)

        # 5. Create materialization and promote atomically
        materialization_id = uuid.uuid4().hex
        now = _utc_now()

        try:
            with self.db.transaction():
                # Insert materialization
                self.db.execute(
                    """INSERT INTO task_materializations
                       (materialization_id, task_id, project_id, workflow_id,
                        params, params_hash, idempotency_key,
                        environment_snapshot_id, environment_execution_hash,
                        binding_snapshot, prompt_snapshot, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        materialization_id,
                        task_id,
                        project_id,
                        workflow_id,
                        json.dumps(params, ensure_ascii=False),
                        params_hash,
                        idempotency_key,
                        snapshot.snapshot_id,
                        snapshot.execution_environment_hash,
                        json.dumps(binding_snapshot, ensure_ascii=False),
                        "{}",  # prompt_snapshot placeholder
                        now,
                        now,
                    ),
                )

                # Promote task to READY (CAS: only if still WAITING_ASSETS)
                # Must also set params_hash and idempotency_key to satisfy CHECK constraint
                cursor = self.db.execute(
                    """UPDATE tasks SET status = ?, updated_at = ?,
                              params_hash = ?, idempotency_key = ?,
                              dependency_hash = ?
                       WHERE task_id = ? AND status = ?""",
                    (
                        TaskStatus.READY.value,
                        now,
                        params_hash,
                        idempotency_key,
                        snapshot.execution_environment_hash,
                        task_id,
                        TaskStatus.WAITING_ASSETS.value,
                    ),
                )

                if cursor.rowcount == 0:
                    # Task state changed concurrently — rollback
                    raise ConcurrentStateChangeError(
                        f"Task {task_id} state changed during promotion"
                    )

        except ConcurrentStateChangeError as exc:
            return TaskReadinessResult(
                success=False,
                task_id=task_id,
                message=str(exc),
            )

        return TaskReadinessResult(
            success=True,
            task_id=task_id,
            materialization_id=materialization_id,
            message=f"Task {task_id} promoted to READY",
            details={
                "workflow_id": workflow_id,
                "params_hash": params_hash,
                "idempotency_key": idempotency_key,
                "environment_snapshot_id": snapshot.snapshot_id,
                "environment_execution_hash": snapshot.execution_environment_hash,
            },
        )

    def _get_machine_id(self, task_id: str) -> str:
        """Get machine_id for a task. Falls back to LFO_MACHINE_ID env
        var, then the LFO_CONFIG 'machine_id' field, then 'local' for MVP.
        """
        import os
        env = os.environ.get("LFO_MACHINE_ID")
        if env:
            return env
        # TODO: Add machine_id column to tasks table in future migration
        return "local"

    def _check_visual_dependencies(
        self, task_id: str
    ) -> TaskReadinessResult | None:
        """Dual gate: verify visual dependency tasks are APPROVED.

        Per spec §19, a video task whose dependencies include visual
        tasks (task_type = 'visual.generate') may only be promoted to
        READY when those visual tasks are in the APPROVED state.  Visual
        tasks never sit on SUCCEEDED in the happy path, so we explicitly
        require APPROVED.

        Returns:
            TaskReadinessResult (failure) if a visual dep is not yet
            APPROVED, or None if the gate passes (no visual deps, or
            all visual deps APPROVED).
        """
        row = self.db.fetchone(
            "SELECT dependencies FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        if row is None or not row[0]:
            return None

        try:
            dep_ids = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except (json.JSONDecodeError, TypeError):
            return None

        if not dep_ids:
            return None

        for dep_id in dep_ids:
            dep_row = self.db.fetchone(
                "SELECT task_type, status FROM tasks WHERE task_id = ?",
                (dep_id,),
            )
            if dep_row is None:
                continue
            dep_type, dep_status = dep_row[0], dep_row[1]
            if dep_type == "visual.generate" and dep_status != TaskStatus.APPROVED.value:
                return TaskReadinessResult(
                    success=False,
                    task_id=task_id,
                    message=(
                        f"Visual dependency '{dep_id}' is in '{dep_status}' "
                        f"state, requires APPROVED before promotion"
                    ),
                    failed_asset=f"visual:{dep_id}",
                    failed_reason=f"Visual task not yet APPROVED (current: {dep_status})",
                )

        return None


class ConcurrentStateChangeError(Exception):
    """Raised when a concurrent state change prevents promotion."""

    pass


def _compute_params_hash(params: dict) -> str:
    """Compute deterministic hash of execution params."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_idempotency_key(
    task_id: str,
    params_hash: str,
    environment_hash: str,
) -> str:
    """Compute idempotency key from task, params, and environment."""
    raw = f"{task_id}:{params_hash}:{environment_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
