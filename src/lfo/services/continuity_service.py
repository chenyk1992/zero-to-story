"""ContinuityService — manage shot-to-shot continuity.

Level 0 (MVP): Approved Selected Clip → End Frame → bind as Next Shot Start Frame.

The `continuity_states` table captures semantic-level state (character, costume,
pose, props, scene end-state) — complementary to `asset_relations` which only
tracks asset-level file lineage.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.core.database import Database

CONTINUITY_STATUSES = frozenset({
    "pending",
    "ready",
    "approved",
    "rejected",
    "superseded",
})


@dataclass
class ContinuityRecord:
    """A continuity state row."""

    continuity_id: str
    project_id: str
    shot_id: str
    source_shot_id: str
    end_frame_asset_id: str
    state_json: dict
    status: str
    created_at: str
    approved_at: str
    approved_by: str


class ContinuityService:
    """Manage shot-to-shot continuity for film production."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_continuity_edit(
        self,
        project_id: str,
        source_shot_id: str,
        target_shot_id: str,
        end_frame_asset_id: str,
        prompt: dict | None = None,
    ) -> str:
        """Create a Level 1 continuity edit (visual.edit) from an end frame.

        Creates a visual.edit task that edits the source end frame to
        produce a new start frame for the target shot.  The continuity
        record is stored with status='pending' until the edit result is
        approved and bound.

        Args:
            project_id: The project ID.
            source_shot_id: The shot providing the end frame.
            target_shot_id: The shot needing the edited start frame.
            end_frame_asset_id: The end frame asset to edit.
            prompt: Optional edit prompt dict.

        Returns:
            The visual edit task_id.
        """
        from lfo.application.visual_task_service import VisualTaskService

        vs = VisualTaskService(self.db)
        task_id = vs.create_visual_task(
            purpose="continuity_edit",
            project_id=project_id,
            shot_id=target_shot_id,
            references=[{"asset_id": end_frame_asset_id, "role": "end_frame"}],
            prompt=prompt,
        )

        continuity_id = uuid.uuid4().hex
        now = _utc_now()
        state = json.dumps(
            {"edit_task_id": task_id, "kind": "continuity_edit"},
            ensure_ascii=False,
        )
        self.db.execute(
            """INSERT INTO continuity_states
               (continuity_id, project_id, shot_id, source_shot_id,
                end_frame_asset_id, state_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (continuity_id, project_id, target_shot_id, source_shot_id,
             end_frame_asset_id, state, "pending", now),
        )
        return task_id

    def bind_end_frame_to_shot(
        self,
        project_id: str,
        source_shot_id: str,
        target_shot_id: str,
        end_frame_asset_id: str,
        state_json: dict | None = None,
    ) -> ContinuityRecord:
        """Bind an end frame from source_shot as the start frame for target_shot.

        This is Level 0 continuity: automated end-frame → next-shot binding.
        Creates a continuity_states row with status='ready' awaiting approval.
        """
        continuity_id = uuid.uuid4().hex
        now = _utc_now()
        state = json.dumps(state_json or {}, ensure_ascii=False)

        self.db.execute(
            """INSERT INTO continuity_states
               (continuity_id, project_id, shot_id, source_shot_id,
                end_frame_asset_id, state_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (continuity_id, project_id, target_shot_id, source_shot_id,
             end_frame_asset_id, state, "ready", now),
        )
        return self._load(continuity_id)

    def approve_continuity(self, continuity_id: str, approved_by: str = "") -> ContinuityRecord:
        """Approve a continuity binding."""
        row = self._load(continuity_id)
        if row is None:
            raise ValueError(f"Continuity state {continuity_id} not found")
        if row.status not in ("ready", "pending"):
            raise ValueError(f"Cannot approve continuity in status '{row.status}'")

        now = _utc_now()
        self.db.execute(
            """UPDATE continuity_states
               SET status = 'approved', approved_at = ?, approved_by = ?
               WHERE continuity_id = ?""",
            (now, approved_by, continuity_id),
        )
        return self._load(continuity_id)

    def reject_continuity(self, continuity_id: str) -> ContinuityRecord:
        """Reject a continuity binding."""
        row = self._load(continuity_id)
        if row is None:
            raise ValueError(f"Continuity state {continuity_id} not found")
        if row.status not in ("ready", "pending"):
            raise ValueError(f"Cannot reject continuity in status '{row.status}'")

        self.db.execute(
            "UPDATE continuity_states SET status = 'rejected' WHERE continuity_id = ?",
            (continuity_id,),
        )
        return self._load(continuity_id)

    def get_continuity_for_shot(self, project_id: str, shot_id: str) -> ContinuityRecord | None:
        """Get the current approved continuity state for a shot."""
        row = self.db.fetchone(
            """SELECT continuity_id, project_id, shot_id, source_shot_id,
                      end_frame_asset_id, state_json, status, created_at,
                      approved_at, approved_by
               FROM continuity_states
               WHERE project_id = ? AND shot_id = ? AND status = 'approved'
               ORDER BY approved_at DESC LIMIT 1""",
            (project_id, shot_id),
        )
        return self._row_to_record(row) if row else None

    def get_pending_for_project(self, project_id: str) -> list[ContinuityRecord]:
        """Get all pending/ready continuity states for a project."""
        rows = self.db.fetchall(
            """SELECT continuity_id, project_id, shot_id, source_shot_id,
                      end_frame_asset_id, state_json, status, created_at,
                      approved_at, approved_by
               FROM continuity_states
               WHERE project_id = ? AND status IN ('ready', 'pending')
               ORDER BY created_at""",
            (project_id,),
        )
        return [self._row_to_record(r) for r in rows]

    def update_state_json(self, continuity_id: str, state_json: dict) -> ContinuityRecord:
        """Update the semantic state JSON (character, costume, pose, etc.)."""
        self.db.execute(
            "UPDATE continuity_states SET state_json = ? WHERE continuity_id = ?",
            (json.dumps(state_json, ensure_ascii=False), continuity_id),
        )
        return self._load(continuity_id)

    # -- internal helpers -------------------------------------------------

    def _load(self, continuity_id: str) -> ContinuityRecord | None:
        row = self.db.fetchone(
            """SELECT continuity_id, project_id, shot_id, source_shot_id,
                      end_frame_asset_id, state_json, status, created_at,
                      approved_at, approved_by
               FROM continuity_states WHERE continuity_id = ?""",
            (continuity_id,),
        )
        return self._row_to_record(row) if row else None

    @staticmethod
    def _row_to_record(row) -> ContinuityRecord:
        return ContinuityRecord(
            continuity_id=row[0],
            project_id=row[1],
            shot_id=row[2],
            source_shot_id=row[3] or "",
            end_frame_asset_id=row[4] or "",
            state_json=json.loads(row[5]) if row[5] else {},
            status=row[6],
            created_at=row[7],
            approved_at=row[8] or "",
            approved_by=row[9] or "",
        )


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
