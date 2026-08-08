"""Environment Snapshot Service — persist + query environment snapshots.

Responsibilities:
- Create snapshots from discovery results + machine profile
- Persist to environment_snapshots table
- Load latest snapshot per machine
- Compute execution_environment_hash (delegates to fingerprint module)
- Provide current snapshot for TaskReadinessService binding
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.config.machine_profile import MachineProfile
from lfo.core.database import Database
from lfo.environment.discovery import discover_environment
from lfo.environment.fingerprint import (
    EnvironmentSnapshot,
    create_environment_snapshot,
)


@dataclass
class SnapshotRecord:
    """A persisted environment snapshot."""

    snapshot_id: str
    machine_id: str
    captured_at: str
    snapshot_json: dict
    execution_environment_hash: str


class EnvironmentSnapshotService:
    """Persist and query environment snapshots."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def capture_and_save(
        self,
        machine_profile: MachineProfile,
        *,
        extra: dict | None = None,
    ) -> SnapshotRecord:
        """Discover current environment, create snapshot, and persist.

        Args:
            machine_profile: The machine profile for context.
            extra: Optional extra metadata to include in the snapshot.

        Returns:
            SnapshotRecord with the persisted snapshot.
        """
        discovery = discover_environment()
        snapshot = create_environment_snapshot(
            machine_id=machine_profile.machine_id,
            discovery=discovery,
            comfyui_root=machine_profile.comfyui.root,
            python_version=str(
                discovery.python_path
            ),
            extra=extra,
        )
        return self.save_snapshot(snapshot)

    def save_snapshot(self, snapshot: EnvironmentSnapshot) -> SnapshotRecord:
        """Persist an EnvironmentSnapshot to the database.

        Args:
            snapshot: The snapshot to persist.

        Returns:
            SnapshotRecord with the persisted data.
        """
        snapshot_id = uuid.uuid4().hex
        snapshot_json = snapshot.to_dict()
        exec_hash = snapshot.execution_environment_hash

        self.db.execute(
            """INSERT INTO environment_snapshots
               (snapshot_id, machine_id, captured_at, snapshot_json,
                execution_environment_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                snapshot.machine_id,
                snapshot.captured_at,
                json.dumps(snapshot_json, ensure_ascii=False),
                exec_hash,
            ),
        )

        return SnapshotRecord(
            snapshot_id=snapshot_id,
            machine_id=snapshot.machine_id,
            captured_at=snapshot.captured_at,
            snapshot_json=snapshot_json,
            execution_environment_hash=exec_hash,
        )

    def get_latest(self, machine_id: str) -> SnapshotRecord | None:
        """Get the most recent snapshot for a machine.

        Args:
            machine_id: The machine to query.

        Returns:
            The most recent SnapshotRecord, or None if no snapshots exist.
        """
        row = self.db.fetchone(
            """SELECT snapshot_id, machine_id, captured_at, snapshot_json,
                      execution_environment_hash
               FROM environment_snapshots
               WHERE machine_id = ?
               ORDER BY captured_at DESC
               LIMIT 1""",
            (machine_id,),
        )
        if row is None:
            return None
        return SnapshotRecord(
            snapshot_id=row[0],
            machine_id=row[1],
            captured_at=row[2],
            snapshot_json=json.loads(row[3]),
            execution_environment_hash=row[4],
        )

    def get_by_id(self, snapshot_id: str) -> SnapshotRecord | None:
        """Get a snapshot by its ID.

        Args:
            snapshot_id: The snapshot ID to look up.

        Returns:
            The SnapshotRecord, or None if not found.
        """
        row = self.db.fetchone(
            """SELECT snapshot_id, machine_id, captured_at, snapshot_json,
                      execution_environment_hash
               FROM environment_snapshots
               WHERE snapshot_id = ?""",
            (snapshot_id,),
        )
        if row is None:
            return None
        return SnapshotRecord(
            snapshot_id=row[0],
            machine_id=row[1],
            captured_at=row[2],
            snapshot_json=json.loads(row[3]),
            execution_environment_hash=row[4],
        )

    def list_snapshots(self, machine_id: str, limit: int = 10) -> list[SnapshotRecord]:
        """List recent snapshots for a machine.

        Args:
            machine_id: The machine to query.
            limit: Maximum number of snapshots to return.

        Returns:
            List of SnapshotRecord, most recent first.
        """
        rows = self.db.fetchall(
            """SELECT snapshot_id, machine_id, captured_at, snapshot_json,
                      execution_environment_hash
               FROM environment_snapshots
               WHERE machine_id = ?
               ORDER BY captured_at DESC
               LIMIT ?""",
            (machine_id, limit),
        )
        return [
            SnapshotRecord(
                snapshot_id=row[0],
                machine_id=row[1],
                captured_at=row[2],
                snapshot_json=json.loads(row[3]),
                execution_environment_hash=row[4],
            )
            for row in rows
        ]

    def hash_matches(
        self,
        snapshot_id: str,
        current_hash: str,
    ) -> bool:
        """Check if a stored snapshot's hash matches the current environment.

        Used to detect ENVIRONMENT_CHANGED_AFTER_MATERIALIZATION.

        Args:
            snapshot_id: The snapshot to compare.
            current_hash: The current execution_environment_hash.

        Returns:
            True if the hashes match, False otherwise.
        """
        record = self.get_by_id(snapshot_id)
        if record is None:
            return False
        return record.execution_environment_hash == current_hash


def get_current_utc() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
