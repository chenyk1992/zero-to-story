"""LFO Task and Submission state machine.

States, transitions, and project-level aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""
    PLANNED = "PLANNED"
    WAITING_ASSETS = "WAITING_ASSETS"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    SUCCEEDED = "SUCCEEDED"
    QC_PENDING = "QC_PENDING"
    APPROVED = "APPROVED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    STALE = "STALE"
    NEEDS_REMATERIALIZATION = "NEEDS_REMATERIALIZATION"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class SubmissionState(str, Enum):
    """Submission journal states."""
    PREPARED = "PREPARED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    COLLECTING = "COLLECTING"
    COMPLETED = "COMPLETED"
    SUBMISSION_UNCERTAIN = "SUBMISSION_UNCERTAIN"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Terminal states for tasks
TASK_TERMINAL_STATES = {
    TaskStatus.SUCCEEDED,
    TaskStatus.APPROVED,
    TaskStatus.FAILED_TERMINAL,
    TaskStatus.CANCELLED,
    TaskStatus.SUPERSEDED,
}

# Active states (task is or may be doing work)
TASK_ACTIVE_STATES = {
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
}

# States that block downstream tasks
TASK_BLOCKING_STATES = {
    TaskStatus.WAITING_USER,
    TaskStatus.WAITING_ASSETS,
    TaskStatus.FAILED_TERMINAL,
    TaskStatus.STALE,
    TaskStatus.NEEDS_REMATERIALIZATION,
}


class FailureClassification(str, Enum):
    """Classification of failures for retry decisions."""
    TRANSIENT = "transient"      # retry same contract
    PERSISTENT = "persistent"    # must modify, new idempotency_key
    EXHAUSTED = "exhausted"      # terminal blocker


@dataclass
class Task:
    """Reproduction of a task from the design doc."""
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PLANNED
    dependencies: list[str] = field(default_factory=list)
    serial_group: str | None = None
    priority_class: int = 30
    priority_override: int | None = None
    attempt_ids: list[str] = field(default_factory=list)
    latest_attempt_id: str | None = None
    error: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TASK_TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        return self.status in TASK_ACTIVE_STATES

    @property
    def blocks_downstream(self) -> bool:
        return self.status in TASK_BLOCKING_STATES


@dataclass
class ProjectState:
    """Aggregated project state."""
    phase: str = "INITIALIZED"
    run_status: str = "IDLE"
    attention_required: bool = False
    attention_count: int = 0
    attention_scopes: list[str] = field(default_factory=list)
    active_scopes: list[str] = field(default_factory=list)
    review_scopes: list[str] = field(default_factory=list)
    next_action: str | None = None
    tasks_summary: dict[str, int] = field(default_factory=dict)


def merge_run_status(tasks: list[Task]) -> str:
    """Aggregate run status across required tasks.

    Rules:
    - If any task has terminal failure that blocks the project → BLOCKED
    - If any task is actively running → RUNNING
    - If any task is waiting for user → WAITING_USER
    - If any task is ready or failed-retryable → READY
    - If all terminal → COMPLETED
    """
    if not tasks:
        return "IDLE"

    statuses = {t.status for t in tasks}

    # Check for global blockers
    if any(t.status == TaskStatus.FAILED_TERMINAL for t in tasks):
        # Only block if it's a required task (not superseded)
        return "BLOCKED"

    # Active work
    if tasks and any(t.status in TASK_ACTIVE_STATES for t in tasks):
        return "RUNNING"

    # User attention needed
    if TaskStatus.WAITING_USER in statuses:
        return "WAITING_USER"

    # Ready to proceed
    if statuses & {TaskStatus.READY, TaskStatus.FAILED_RETRYABLE}:
        return "READY"

    # All done
    if all(t.status in TASK_TERMINAL_STATES for t in tasks):
        return "COMPLETED"

    return "READY"


def compute_project_state(
    tasks: list[Task],
    current_phase: str = "PRODUCTION",
) -> ProjectState:
    """Compute the overall project state from task states."""

    attention_required = any(t.status == TaskStatus.WAITING_USER for t in tasks)
    attention_count = sum(1 for t in tasks if t.status == TaskStatus.WAITING_USER)
    attention_scopes = [t.task_id for t in tasks if t.status == TaskStatus.WAITING_USER]

    active_scopes = [
        t.task_id for t in tasks
        if t.status in {TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.READY}
    ]

    # Build tasks summary
    summary: dict[str, int] = {}
    for t in tasks:
        summary[t.status.value] = summary.get(t.status.value, 0) + 1

    run_status = merge_run_status(tasks)

    # Determine next action
    next_action = None
    if run_status == "WAITING_USER":
        next_action = "resolve_user_attention"
    elif run_status == "READY":
        next_action = "schedule_ready_tasks"
    elif run_status == "BLOCKED":
        next_action = "resolve_terminal_failure"

    return ProjectState(
        phase=current_phase,
        run_status=run_status,
        attention_required=attention_required,
        attention_count=attention_count,
        attention_scopes=attention_scopes,
        active_scopes=active_scopes,
        review_scopes=[t.task_id for t in tasks if t.status == TaskStatus.QC_PENDING],
        next_action=next_action,
        tasks_summary=summary,
    )
