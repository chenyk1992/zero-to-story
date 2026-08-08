"""LFO Crash Recovery — resume from interrupted states.

After a process crash, the database may contain:
- Tasks in RUNNING / QUEUED state (execution interrupted)
- Journal entries in SUBMITTING / SUBMITTED / COLLECTING (uncertain)
- Leases that expired but were never released

Recovery resolves these to deterministic states.
"""
from __future__ import annotations

from datetime import UTC

from .database import Database
from .runtime import (
    get_journal_by_attempt,
    get_tasks_by_project,
    promote_task_to_ready,
    update_task_status,
)
from .state_machine import SubmissionState, TaskStatus


def recover_project(db: Database, project_id: str) -> dict:
    """Run full crash recovery for a project.

    Returns a summary of what was recovered.
    """
    summary = {
        "tasks_reset": 0,
        "journals_marked_uncertain": 0,
        "leases_released": 0,
    }

    # 1. Reset active tasks that were interrupted
    tasks = get_tasks_by_project(db, project_id)
    for task in tasks:
        if task["status"] in TASK_ACTIVE_STATES_RESET:
            # Check if there's a journal entry for the latest attempt
            if task["latest_attempt_id"]:
                journal = get_journal_by_attempt(db, task["latest_attempt_id"])
                if journal and journal["state"] in JOURNAL_UNCERTAIN_STATES:
                    # Need to check with provider
                    summary["journals_marked_uncertain"] += 1

            # Reset task: promote to READY if fingerprints exist, else PLANNED
            if task["content_hash"] and task["dependency_hash"] and task["params_hash"] and task["idempotency_key"]:
                promote_task_to_ready(
                    db, task["task_id"],
                    content_hash=task["content_hash"],
                    dependency_hash=task["dependency_hash"],
                    params_hash=task["params_hash"],
                    idempotency_key=task["idempotency_key"],
                )
            else:
                update_task_status(db, task["task_id"], TaskStatus.PLANNED)
            summary["tasks_reset"] += 1

    # 2. Release expired leases
    from datetime import datetime
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")

    expired = db.fetchall(
        """SELECT lease_id FROM task_leases
           WHERE released = 0 AND expires_at < ?""",
        (now,),
    )
    for row in expired:
        db.execute(
            """UPDATE task_leases SET released = 1, released_at = ?
               WHERE lease_id = ?""",
            (now, row["lease_id"]),
        )
        summary["leases_released"] += 1

    return summary


# States that should be reset on crash recovery
TASK_ACTIVE_STATES_RESET = {TaskStatus.RUNNING, TaskStatus.QUEUED}

# Journal states that indicate uncertain submission
JOURNAL_UNCERTAIN_STATES = {
    SubmissionState.SUBMITTING,
    SubmissionState.SUBMITTED,
    SubmissionState.COLLECTING,
}


def recover_uncertain_journal(
    db: Database,
    journal_id: str,
    provider_has_job: bool,
) -> str:
    """Resolve an uncertain journal entry.

    Args:
        db: Database
        journal_id: The uncertain journal entry
        provider_has_job: Whether the provider (ComfyUI) still has this job

    Returns:
        The resolved state
    """
    journal = db.fetchone(
        "SELECT * FROM submission_journal WHERE journal_id = ?", (journal_id,)
    )
    if journal is None:
        raise ValueError(f"Journal {journal_id} not found")

    current_state = journal["state"]

    if provider_has_job:
        # Job exists at provider, continue monitoring
        # Transition to SUBMITTED to resume monitoring
        if current_state == SubmissionState.SUBMITTING:
            _force_transition(db, journal_id, SubmissionState.SUBMITTED)
            return SubmissionState.SUBMITTED.value
        return current_state
    else:
        # Job doesn't exist — the submission was lost
        if current_state in (SubmissionState.SUBMITTING, SubmissionState.SUBMITTED):
            _force_transition(db, journal_id, SubmissionState.FAILED)
            return SubmissionState.FAILED.value
        return current_state


def _force_transition(db: Database, journal_id: str, to_state: SubmissionState) -> None:
    """Force a journal transition (bypass CAS, for recovery only)."""
    db.execute(
        """UPDATE submission_journal
           SET state = ?, from_state = state, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE journal_id = ?""",
        (to_state.value, journal_id),
    )
