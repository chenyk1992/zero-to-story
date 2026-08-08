"""Visual Profile Service — per-project profile revision lifecycle.

Each project has at most one active profile revision. Revisions form
a linear lineage via parent_revision_id (rollback = clone → activate).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.errors import VisualContractError
from lfo.visual.profile import hash_profile_content, validate_profile_content
from lfo.visual.stages import VisualStage


class VisualProfileService:
    """Manage visual generation profile revisions."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_draft(
        self,
        project_id: str,
        content: dict[str, Any],
        *,
        created_by: str = "system",
    ) -> str:
        """Create a new profile revision draft.

        Args:
            project_id: The project ID.
            content: Raw profile content dict (validated).
            created_by: User/system that created this revision.

        Returns:
            The new revision_id.

        Raises:
            VisualContractError: On invalid content.
        """
        # Validates content (raises VisualContractError on invalid)
        profile = validate_profile_content(content)

        revision_id = str(uuid.uuid4())
        content_hash = hash_profile_content(content)
        now = _now()

        # Parent = current active revision (linear lineage)
        parent = self._find_active_revision(project_id)

        self.db.execute(
            """INSERT INTO visual_generation_profile_revisions
               (revision_id, project_id, content, content_hash,
                visual_input_policy, status, parent_revision_id,
                created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                revision_id, project_id,
                json.dumps(profile.to_dict(), ensure_ascii=False),
                content_hash,
                profile.visual_input_policy,
                "draft",
                parent,
                created_by,
                now, now,
            ),
        )
        return revision_id

    def activate(self, revision_id: str, *, allow_unavailable_provider: bool = False) -> None:
        """Activate a profile revision, superseding any active one for project.

        Args:
            revision_id: The revision to activate.
            allow_unavailable_provider: If True, skip provider availability check.

        Raises:
            VisualContractError: If revision not found or not a draft.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                """SELECT project_id, status
                   FROM visual_generation_profile_revisions
                   WHERE revision_id = ?""",
                (revision_id,),
            ).fetchone()
            if row is None:
                raise VisualContractError(
                    f"Profile revision '{revision_id}' not found"
                )
            if row["status"] != "draft":
                raise VisualContractError(
                    f"Cannot activate revision in state '{row['status']}'"
                )

            project_id = row["project_id"]
            now = _now()

            # Supersede existing active revision for this project
            conn.execute(
                """UPDATE visual_generation_profile_revisions
                   SET status = 'superseded', updated_at = ?
                   WHERE project_id = ? AND status = 'active'""",
                (now, project_id),
            )

            # Activate this revision
            cursor = conn.execute(
                """UPDATE visual_generation_profile_revisions
                   SET status = 'active', updated_at = ?
                   WHERE revision_id = ? AND status = 'draft'""",
                (now, revision_id),
            )
            if cursor.rowcount != 1:
                raise VisualContractError(
                    f"Failed to activate revision '{revision_id}': "
                    "concurrent modification detected"
                )

            # Stale unstarted visual tasks for this project.
            # Running (SUBMITTED/AWAITING_RESULT) keep old profile revision;
            # terminal (RESULT_IMPORTED/AWAITING_REVIEW/APPROVED/REJECTED) stay valid.
            _stale_unstarted_visual_tasks(conn, project_id, now)

    def clone(self, revision_id: str) -> str:
        """Clone an existing revision as a new draft.

        The clone's parent is the given revision. Useful for rollback
        (clone old → activate).

        Args:
            revision_id: The revision to clone.

        Returns:
            The new draft revision_id.

        Raises:
            VisualContractError: If revision not found.
        """
        row = self.db.fetchone(
            """SELECT project_id, content, content_hash, visual_input_policy
               FROM visual_generation_profile_revisions
               WHERE revision_id = ?""",
            (revision_id,),
        )
        if row is None:
            raise VisualContractError(
                f"Profile revision '{revision_id}' not found"
            )

        new_id = str(uuid.uuid4())
        now = _now()

        self.db.execute(
            """INSERT INTO visual_generation_profile_revisions
               (revision_id, project_id, content, content_hash,
                visual_input_policy, status, parent_revision_id,
                created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id, row["project_id"],
                row["content"],
                row["content_hash"],
                row["visual_input_policy"],
                "draft",
                revision_id,  # parent = source revision
                "system",
                now, now,
            ),
        )
        return new_id

    def get_active(self, project_id: str) -> dict[str, Any] | None:
        """Get the active profile revision for a project.

        Returns:
            Dict with revision_id, content, etc., or None if no active.
        """
        row = self.db.fetchone(
            """SELECT revision_id, project_id, content, content_hash,
                      visual_input_policy, status, parent_revision_id
               FROM visual_generation_profile_revisions
               WHERE project_id = ? AND status = 'active'
               ORDER BY created_at DESC
               LIMIT 1""",
            (project_id,),
        )
        if row is None:
            return None

        return {
            "revision_id": row["revision_id"],
            "project_id": row["project_id"],
            "content": json.loads(row["content"]),
            "content_hash": row["content_hash"],
            "visual_input_policy": row["visual_input_policy"],
            "status": row["status"],
            "parent_revision_id": row["parent_revision_id"],
        }

    def _find_active_revision(self, project_id: str) -> str | None:
        """Find the currently active revision for a project (for parent linkage)."""
        row = self.db.fetchone(
            """SELECT revision_id FROM visual_generation_profile_revisions
               WHERE project_id = ? AND status = 'active'
               LIMIT 1""",
            (project_id,),
        )
        return row["revision_id"] if row else None


def _stale_unstarted_visual_tasks(
    conn, project_id: str, now: str
) -> None:
    """Mark unstarted visual tasks as STALE after a profile switch.

    Only UNROUTED / BLOCKED / ROUTED tasks are affected.  Running
    (SUBMITTED, AWAITING_RESULT) and terminal tasks keep their current
    state — running managed executions retain their old profile revision
    and approved assets stay valid.
    """
    rows = conn.execute(
        """SELECT vtc.task_id
           FROM visual_task_contracts vtc
           JOIN tasks t ON vtc.task_id = t.task_id
           WHERE t.project_id = ?
             AND vtc.visual_stage IN (?, ?, ?)""",
        (
            project_id,
            VisualStage.UNROUTED.value,
            VisualStage.BLOCKED.value,
            VisualStage.ROUTED.value,
        ),
    ).fetchall()

    for row in rows:
        conn.execute(
            """UPDATE tasks
               SET status = ?, updated_at = ?
               WHERE task_id = ?""",
            (TaskStatus.STALE.value, now, row["task_id"]),
        )
        conn.execute(
            """UPDATE visual_task_contracts
               SET visual_stage = ?, updated_at = ?
               WHERE task_id = ?""",
            (VisualStage.STALE.value, now, row["task_id"]),
        )


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%fZ"
    )
