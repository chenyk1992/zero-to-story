"""LFO Runtime — high-level operations on the SQLite database.

Provides:
- Task lifecycle management (CRUD + state transitions)
- Attempt tracking
- Submission journal with CAS transitions
- Project state computation
- Recovery helpers
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from .database import Database
from .state_machine import (
    TASK_TERMINAL_STATES,
    ProjectState,
    SubmissionState,
    Task,
    TaskStatus,
    compute_project_state,
)


def _now() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")


def _gen_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def _ensure_json(data) -> str:
    """Ensure data is a JSON string."""
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)


def _load_json(raw: str, default=None):
    """Load JSON string, return default on error."""
    if not raw:
        return default if default is not None else None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else None


# ===========================================================================
# Task operations
# ===========================================================================


def create_task(
    db: Database,
    project_id: str,
    task_type: str,
    task_id: str | None = None,
    dependencies: list[str] | None = None,
    serial_group: str | None = None,
    priority_class: int = 30,
    priority_override: int | None = None,
    content_hash: str | None = None,
    dependency_hash: str | None = None,
    params_hash: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    """Create a new task. Returns task_id."""
    tid = task_id or _gen_id("task_")
    now = _now()
    db.execute(
        """INSERT INTO tasks
           (task_id, project_id, task_type, status, dependencies, serial_group,
            priority_class, priority_override, content_hash, dependency_hash,
            params_hash, idempotency_key, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tid, project_id, task_type,
            TaskStatus.PLANNED.value,
            _ensure_json(dependencies or []),
            serial_group,
            priority_class,
            priority_override,
            content_hash,
            dependency_hash,
            params_hash,
            idempotency_key,
            now, now,
        ),
    )
    _log_event(db, project_id, task_id=tid, event_type="task_created",
               payload={"task_type": task_type})
    return tid


def get_task(db: Database, task_id: str) -> dict | None:
    """Get a task by ID."""
    row = db.fetchone("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    if row is None:
        return None
    return _task_from_row(row)


def get_tasks_by_project(db: Database, project_id: str) -> list[dict]:
    """Get all tasks for a project."""
    rows = db.fetchall(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at",
        (project_id,),
    )
    return [_task_from_row(r) for r in rows]


def update_task_status(
    db: Database,
    task_id: str,
    new_status: TaskStatus,
    error: str | None = None,
) -> bool:
    """Update task status. Returns True if the task was found and updated.

    Raises ValueError if attempting to set READY directly — use
    promote_task_to_ready() instead, which validates fingerprints atomically.
    """
    if new_status == TaskStatus.READY:
        raise ValueError(
            "Cannot set READY through update_task_status(). "
            "Use promote_task_to_ready() which requires complete fingerprints."
        )

    now = _now()
    updates = ["status = ?", "updated_at = ?"]
    params: list = [new_status.value, now]

    if error is not None:
        updates.append("error = ?")
        params.append(error)

    params.append(task_id)
    cursor = db.execute(
        f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
        params,
    )
    return cursor.rowcount > 0


def promote_task_to_ready(
    db: Database,
    task_id: str,
    *,
    content_hash: str,
    dependency_hash: str,
    params_hash: str,
    idempotency_key: str,
) -> None:
    """Promote a task to READY with complete fingerprints.

    This is the ONLY way to transition a task to READY status.
    All four fingerprints (content_hash, dependency_hash, params_hash,
    idempotency_key) must be provided.

    Performs in a single transaction:
    1. Validates task exists and is in an promotable state
    2. Checks all dependencies are in terminal states
    3. Updates fingerprints
    4. Sets status to READY
    5. Writes event log

    Raises ValueError if task not found, wrong state, or dependencies not met.
    Raises sqlite3.IntegrityError if fingerprints are missing.
    """
    with db.transaction() as conn:
        # 1. Check current state
        row = conn.execute(
            "SELECT status, project_id, dependencies FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Task {task_id} not found")

        current_status = row["status"]
        project_id = row["project_id"]
        dependencies = _load_json(row["dependencies"], [])

        # Can only promotable from PLANNED, STALE, FAILED_RETRYABLE,
        # or active states (RUNNING/QUEUED) for crash recovery
        promotable = {"PLANNED", "STALE", "FAILED_RETRYABLE", "RUNNING", "QUEUED"}
        if current_status not in promotable:
            raise ValueError(
                f"Cannot promote task {task_id} from {current_status} to READY. "
                f"Must be one of: {promotable}"
            )

        # 2. Check dependencies
        for dep_id in dependencies:
            dep_row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (dep_id,)
            ).fetchone()
            if dep_row is None:
                raise ValueError(f"Dependency {dep_id} not found")
            if dep_row["status"] not in {s.value for s in TASK_TERMINAL_STATES}:
                raise ValueError(
                    f"Dependency {dep_id} is in state {dep_row['status']}, "
                    f"not a terminal state. Cannot promote."
                )

        # 3 & 4. Update fingerprints + set READY in one statement
        now = _now()
        conn.execute(
            """UPDATE tasks
               SET content_hash = ?, dependency_hash = ?, params_hash = ?,
                   idempotency_key = ?, status = ?, updated_at = ?
               WHERE task_id = ?""",
            (
                content_hash, dependency_hash, params_hash,
                idempotency_key, TaskStatus.READY.value,
                now, task_id,
            ),
        )

        # 5. Event log
        conn.execute(
            """INSERT INTO events (project_id, task_id, event_type, payload)
               VALUES (?, ?, ?, ?)""",
            (
                project_id, task_id, "task_promoted_to_ready",
                json.dumps({
                    "content_hash": content_hash,
                    "dependency_hash": dependency_hash,
                    "params_hash": params_hash,
                    "idempotency_key": idempotency_key,
                    "from_status": current_status,
                }),
            ),
        )


def update_task_hashes(
    db: Database,
    task_id: str,
    content_hash: str | None = None,
    dependency_hash: str | None = None,
    params_hash: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Update hash fields on a task."""
    updates = []
    params: list = []

    if content_hash is not None:
        updates.append("content_hash = ?")
        params.append(content_hash)
    if dependency_hash is not None:
        updates.append("dependency_hash = ?")
        params.append(dependency_hash)
    if params_hash is not None:
        updates.append("params_hash = ?")
        params.append(params_hash)
    if idempotency_key is not None:
        updates.append("idempotency_key = ?")
        params.append(idempotency_key)

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(_now())
    params.append(task_id)

    db.execute(
        f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
        params,
    )


def _task_from_row(row) -> dict:
    """Convert a database row to a task dict."""
    return {
        "task_id": row["task_id"],
        "project_id": row["project_id"],
        "task_type": row["task_type"],
        "status": TaskStatus(row["status"]),
        "dependencies": _load_json(row["dependencies"], []),
        "serial_group": row["serial_group"],
        "priority_class": row["priority_class"],
        "priority_override": row["priority_override"],
        "attempt_ids": _load_json(row["attempt_ids"], []),
        "latest_attempt_id": row["latest_attempt_id"],
        "error": row["error"],
        "content_hash": row["content_hash"],
        "dependency_hash": row["dependency_hash"],
        "params_hash": row["params_hash"],
        "idempotency_key": row["idempotency_key"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ===========================================================================
# Attempt operations
# ===========================================================================


def create_attempt(
    db: Database,
    task_id: str,
    idempotency_key: str,
    content_hash: str,
    dependency_hash: str,
    params_hash: str,
    workflow_id: str | None = None,
    params: dict | None = None,
) -> str:
    """Create a new attempt for a task. Returns attempt_id."""
    aid = _gen_id("att_")
    now = _now()
    db.execute(
        """INSERT INTO attempts
           (attempt_id, task_id, idempotency_key, workflow_id, params,
            content_hash, dependency_hash, params_hash, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            aid, task_id, idempotency_key, workflow_id,
            _ensure_json(params or {}),
            content_hash, dependency_hash, params_hash,
            SubmissionState.PREPARED.value, now, now,
        ),
    )

    # Link attempt to task
    task = get_task(db, task_id)
    if task:
        attempt_ids = task["attempt_ids"]
        attempt_ids.append(aid)
        db.execute(
            "UPDATE tasks SET attempt_ids = ?, latest_attempt_id = ?, updated_at = ? WHERE task_id = ?",
            (_ensure_json(attempt_ids), aid, _now(), task_id),
        )

    _log_event(db, task["project_id"] if task else "", task_id=task_id,
               attempt_id=aid, event_type="attempt_created",
               payload={"workflow_id": workflow_id})
    return aid


def get_attempt(db: Database, attempt_id: str) -> dict | None:
    """Get an attempt by ID."""
    row = db.fetchone("SELECT * FROM attempts WHERE attempt_id = ?", (attempt_id,))
    if row is None:
        return None
    return {
        "attempt_id": row["attempt_id"],
        "task_id": row["task_id"],
        "idempotency_key": row["idempotency_key"],
        "workflow_id": row["workflow_id"],
        "params": _load_json(row["params"], {}),
        "content_hash": row["content_hash"],
        "dependency_hash": row["dependency_hash"],
        "params_hash": row["params_hash"],
        "status": SubmissionState(row["status"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_attempts_by_task(db: Database, task_id: str) -> list[dict]:
    """Get all attempts for a task."""
    rows = db.fetchall(
        "SELECT * FROM attempts WHERE task_id = ? ORDER BY created_at",
        (task_id,),
    )
    return [get_attempt(db, r["attempt_id"]) for r in rows]


# ===========================================================================
# Submission Journal — CAS transitions
# ===========================================================================


def create_journal_entry(
    db: Database,
    attempt_id: str,
    task_id: str,
    journal_id: str | None = None,
) -> str:
    """Create a new submission journal entry."""
    jid = journal_id or _gen_id("jrnl_")
    now = _now()
    db.execute(
        """INSERT INTO submission_journal
           (journal_id, attempt_id, task_id, state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (jid, attempt_id, task_id, SubmissionState.PREPARED.value, now, now),
    )
    return jid


def transition_journal(
    db: Database,
    journal_id: str,
    from_state: SubmissionState,
    to_state: SubmissionState,
    **fields,
) -> bool:
    """CAS transition on submission journal.

    Only succeeds if the current state matches from_state.
    Returns True if the transition was applied, False if state mismatch.
    """
    now = _now()

    # Build the SET clause
    set_parts = ["state = ?", "from_state = ?", "updated_at = ?"]
    params: list = [to_state.value, from_state.value, now]

    # Optional fields
    field_map = {
        "provider_job_id": "provider_job_id",
        "prompt_id": "prompt_id",
        "error": "error",
    }
    for key, col in field_map.items():
        if key in fields:
            set_parts.append(f"{col} = ?")
            params.append(fields[key])

    if "submitted_at" in fields:
        set_parts.append("submitted_at = ?")
        params.append(fields["submitted_at"])
    elif to_state == SubmissionState.SUBMITTED:
        set_parts.append("submitted_at = ?")
        params.append(now)

    if "collected_at" in fields:
        set_parts.append("collected_at = ?")
        params.append(fields["collected_at"])
    elif to_state == SubmissionState.COMPLETED:
        set_parts.append("collected_at = ?")
        params.append(now)

    if "metadata" in fields:
        set_parts.append("metadata = ?")
        params.append(_ensure_json(fields["metadata"]))

    # WHERE clause: CAS check
    params.extend([journal_id, from_state.value])

    cursor = db.execute(
        f"UPDATE submission_journal SET {', '.join(set_parts)} "
        f"WHERE journal_id = ? AND state = ?",
        params,
    )

    return cursor.rowcount > 0


def get_journal(db: Database, journal_id: str) -> dict | None:
    """Get a journal entry by ID."""
    row = db.fetchone(
        "SELECT * FROM submission_journal WHERE journal_id = ?", (journal_id,)
    )
    if row is None:
        return None
    return {
        "journal_id": row["journal_id"],
        "attempt_id": row["attempt_id"],
        "task_id": row["task_id"],
        "state": SubmissionState(row["state"]),
        "from_state": SubmissionState(row["from_state"]) if row["from_state"] else None,
        "provider_job_id": row["provider_job_id"],
        "prompt_id": row["prompt_id"],
        "submitted_at": row["submitted_at"],
        "collected_at": row["collected_at"],
        "error": row["error"],
        "metadata": _load_json(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_journal_by_attempt(db: Database, attempt_id: str) -> dict | None:
    """Get the latest journal entry for an attempt."""
    row = db.fetchone(
        """SELECT * FROM submission_journal
           WHERE attempt_id = ? ORDER BY created_at DESC LIMIT 1""",
        (attempt_id,),
    )
    if row is None:
        return None
    return {
        "journal_id": row["journal_id"],
        "attempt_id": row["attempt_id"],
        "task_id": row["task_id"],
        "state": SubmissionState(row["state"]),
        "from_state": SubmissionState(row["from_state"]) if row["from_state"] else None,
        "provider_job_id": row["provider_job_id"],
        "prompt_id": row["prompt_id"],
        "submitted_at": row["submitted_at"],
        "collected_at": row["collected_at"],
        "error": row["error"],
        "metadata": _load_json(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ===========================================================================
# Asset operations
# ===========================================================================


def create_asset(
    db: Database,
    task_id: str,
    asset_type: str,
    file_path: str,
    attempt_id: str | None = None,
    file_hash: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
    frame_count: int | None = None,
    content_hash: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Register an asset. Returns asset_id."""
    aid = _gen_id("asset_")
    now = _now()
    db.execute(
        """INSERT INTO assets
           (asset_id, task_id, attempt_id, asset_type, file_path, file_hash,
            file_size, mime_type, width, height, duration, frame_count,
            content_hash, metadata, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            aid, task_id, attempt_id, asset_type, file_path, file_hash,
            file_size, mime_type, width, height, duration, frame_count,
            content_hash, _ensure_json(metadata or {}), now, now,
        ),
    )
    return aid


def get_assets_by_task(db: Database, task_id: str) -> list[dict]:
    """Get all assets for a task."""
    rows = db.fetchall(
        "SELECT * FROM assets WHERE task_id = ? ORDER BY created_at",
        (task_id,),
    )
    return [_asset_from_row(r) for r in rows]


def _asset_from_row(row) -> dict:
    return {
        "asset_id": row["asset_id"],
        "task_id": row["task_id"],
        "attempt_id": row["attempt_id"],
        "asset_type": row["asset_type"],
        "file_path": row["file_path"],
        "file_hash": row["file_hash"],
        "file_size": row["file_size"],
        "mime_type": row["mime_type"],
        "width": row["width"],
        "height": row["height"],
        "duration": row["duration"],
        "frame_count": row["frame_count"],
        "content_hash": row["content_hash"],
        "metadata": _load_json(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ===========================================================================
# Project state
# ===========================================================================


def get_project_state(db: Database, project_id: str) -> ProjectState:
    """Compute the current project state from database tasks."""
    tasks_data = get_tasks_by_project(db, project_id)
    tasks = [
        Task(
            task_id=t["task_id"],
            task_type=t["task_type"],
            status=t["status"],
            dependencies=t["dependencies"],
            serial_group=t["serial_group"],
            priority_class=t["priority_class"],
            priority_override=t["priority_override"],
            attempt_ids=t["attempt_ids"],
            latest_attempt_id=t["latest_attempt_id"],
            error=t["error"],
        )
        for t in tasks_data
    ]
    return compute_project_state(tasks)


# ===========================================================================
# Event logging
# ===========================================================================


def _log_event(
    db: Database,
    project_id: str,
    task_id: str | None = None,
    attempt_id: str | None = None,
    event_type: str = "",
    payload: dict | None = None,
) -> None:
    """Append an event to the audit log."""
    db.execute(
        """INSERT INTO events (project_id, task_id, attempt_id, event_type, payload)
           VALUES (?, ?, ?, ?, ?)""",
        (project_id, task_id, attempt_id, event_type, _ensure_json(payload or {})),
    )


def get_events(db: Database, project_id: str, limit: int = 100) -> list[dict]:
    """Get recent events for a project."""
    rows = db.fetchall(
        """SELECT * FROM events WHERE project_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (project_id, limit),
    )
    return [
        {
            "event_id": r["event_id"],
            "project_id": r["project_id"],
            "task_id": r["task_id"],
            "attempt_id": r["attempt_id"],
            "event_type": r["event_type"],
            "payload": _load_json(r["payload"], {}),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
