"""Visual Result Service — import manifest + approve with binding.

Imports a VisualResultManifest, creates an asset row, transitions the
task to QC_PENDING + RESULT_IMPORTED. Then approve() creates an
AssetBindingService binding and transitions to APPROVED + APPROVED.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from lfo.application.asset_service import AssetBindingService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.errors import VisualResultError
from lfo.visual.result_manifest import validate_result_manifest
from lfo.visual.stages import VisualStage


class VisualResultService:
    """Import visual results and approve with binding."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._task_svc = VisualTaskService(db)
        self._binding_svc = AssetBindingService(db)

    def import_manifest(self, manifest: dict[str, Any], *, source_root: str) -> str:
        """Import a visual result manifest.

        Validates the manifest, creates an asset row, stores the
        result manifest, and transitions the task to
        QC_PENDING + RESULT_IMPORTED.

        Args:
            manifest: Raw manifest dict.
            source_root: Root directory for resolving file paths.

        Returns:
            The new asset_id.

        Raises:
            VisualResultError: On invalid manifest or re-import.
        """
        validated = validate_result_manifest(manifest)
        task_id = validated.task_id

        # Idempotency check BEFORE transition
        existing = self.db.fetchone(
            "SELECT manifest_id FROM visual_result_manifests WHERE task_id = ?",
            (task_id,),
        )
        if existing is not None:
            raise VisualResultError(
                f"Result already imported for task {task_id}"
            )

        # Transition (establishes QC_PENDING + RESULT_IMPORTED)
        self._task_svc.transition(
            task_id,
            expected_task_status=TaskStatus.PLANNED,
            expected_visual_stage=VisualStage.UNROUTED,
            new_task_status=TaskStatus.QC_PENDING,
            new_visual_stage=VisualStage.RESULT_IMPORTED,
            reason="result imported",
        )

        row = self.db.fetchone(
            "SELECT project_id FROM tasks WHERE task_id = ?", (task_id,)
        )
        if row is None:
            raise VisualResultError(f"Task {task_id} not found")

        now = _now()
        asset_id = str(uuid.uuid4())
        manifest_id = str(uuid.uuid4())

        content = validated.content
        file_path = f"project://assets/visual/{task_id}/{asset_id}.png"
        width = content.get("width")
        height = content.get("height")

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash,
                width, height, mime_type, metadata,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id, task_id, "image", file_path,
                validated.file_hash,
                width, height,
                content.get("mime_type", "image/png"),
                json.dumps({"purpose": content.get("purpose", "")},
                          ensure_ascii=False),
                now, now,
            ),
        )

        self.db.execute(
            """INSERT INTO visual_result_manifests
               (manifest_id, task_id, content, content_hash, file_hash,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                manifest_id, task_id,
                json.dumps(content, ensure_ascii=False),
                validated.content_hash,
                validated.file_hash,
                "imported",
                now, now,
            ),
        )

        return asset_id

    def approve(
        self,
        task_id: str,
        *,
        asset_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
        reviewer: str,
    ) -> None:
        """Approve a visual result, creating/revising a binding.

        Creates or revises an asset binding via AssetBindingService,
        then transitions the task to APPROVED + APPROVED.

        Args:
            task_id: The visual task ID.
            asset_id: The asset to bind.
            entity_type: The entity type (e.g. 'character', 'scene').
            entity_id: The entity ID.
            asset_role: The binding role.
            reviewer: The reviewer identifier.
        """
        row = self.db.fetchone(
            "SELECT project_id FROM tasks WHERE task_id = ?", (task_id,)
        )
        if row is None:
            raise VisualResultError(f"Task {task_id} not found")
        project_id = row["project_id"]

        # Check if a current binding already exists
        existing = self.db.fetchone(
            """SELECT binding_id FROM asset_bindings
               WHERE project_id = ? AND entity_type = ?
                 AND entity_id = ? AND asset_role = ?
                 AND validity = 'current'""",
            (project_id, entity_type, entity_id, asset_role),
        )

        if existing is None:
            self._binding_svc.create_binding(
                asset_id=asset_id,
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                asset_role=asset_role,
            )
        else:
            self._binding_svc.create_revision(
                asset_id=asset_id,
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                asset_role=asset_role,
            )

        # Transition → APPROVED + APPROVED
        self._task_svc.transition(
            task_id,
            expected_task_status=TaskStatus.WAITING_USER,
            expected_visual_stage=VisualStage.AWAITING_REVIEW,
            new_task_status=TaskStatus.APPROVED,
            new_visual_stage=VisualStage.APPROVED,
            reason=f"approved by {reviewer}",
        )


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%fZ"
    )
