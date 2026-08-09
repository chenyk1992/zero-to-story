"""Layered state model for LFO v1 runtime.

Separate state machines for Run, Task, Attempt, Review, and Export.
Each has a transition matrix and a CAS (compare-and-set) transition
function that uses rowcount for safe concurrent updates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# ===========================================================================
# Run states
# ===========================================================================

class RunState(StrEnum):
    ACCEPTED = "ACCEPTED"
    IMPORTING = "IMPORTING"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_REVIEW = "WAITING_REVIEW"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


RUN_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.ACCEPTED: {RunState.IMPORTING, RunState.CANCELLED},
    RunState.IMPORTING: {RunState.PLANNING, RunState.FAILED, RunState.CANCELLED},
    RunState.PLANNING: {RunState.READY, RunState.FAILED, RunState.CANCELLED},
    RunState.READY: {RunState.RUNNING, RunState.CANCELLED, RunState.SUPERSEDED},
    RunState.RUNNING: {RunState.WAITING_REVIEW, RunState.FAILED, RunState.COMPLETED, RunState.CANCELLED},
    RunState.WAITING_REVIEW: {RunState.RUNNING, RunState.EXPORTING, RunState.FAILED, RunState.CANCELLED},
    RunState.EXPORTING: {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED},
    RunState.COMPLETED: set(),  # terminal
    RunState.FAILED: set(),  # terminal
    RunState.CANCELLED: set(),  # terminal
    RunState.SUPERSEDED: set(),  # terminal
}

RUN_TERMINAL_STATES = {
    RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED, RunState.SUPERSEDED,
}


# ===========================================================================
# Task states
# ===========================================================================

class TaskState(StrEnum):
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.BLOCKED: {TaskState.READY, TaskState.CANCELLED},
    TaskState.READY: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.STALE},
    TaskState.RUNNING: {
        TaskState.SUCCEEDED, TaskState.FAILED_RETRYABLE,
        TaskState.FAILED_TERMINAL, TaskState.CANCELLED,
    },
    TaskState.SUCCEEDED: {TaskState.STALE},  # Can become stale if upstream re-runs
    TaskState.FAILED_RETRYABLE: {TaskState.READY, TaskState.FAILED_TERMINAL, TaskState.CANCELLED},
    TaskState.FAILED_TERMINAL: set(),  # terminal
    TaskState.STALE: {TaskState.READY, TaskState.CANCELLED},
    TaskState.CANCELLED: set(),  # terminal
}

TASK_TERMINAL_STATES = {
    TaskState.SUCCEEDED, TaskState.FAILED_TERMINAL, TaskState.CANCELLED,
}


# ===========================================================================
# Attempt states
# ===========================================================================

class AttemptState(StrEnum):
    CREATED = "CREATED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


ATTEMPT_TRANSITIONS: dict[AttemptState, set[AttemptState]] = {
    AttemptState.CREATED: {AttemptState.SUBMITTING, AttemptState.CANCELLED},
    AttemptState.SUBMITTING: {AttemptState.SUBMITTED, AttemptState.FAILED, AttemptState.UNKNOWN, AttemptState.CANCELLED},
    AttemptState.SUBMITTED: {AttemptState.RUNNING, AttemptState.FAILED, AttemptState.UNKNOWN, AttemptState.CANCELLED},
    AttemptState.RUNNING: {AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.UNKNOWN, AttemptState.CANCELLED},
    AttemptState.SUCCEEDED: set(),  # terminal
    AttemptState.FAILED: {AttemptState.CREATED},  # can retry
    AttemptState.UNKNOWN: {AttemptState.RUNNING, AttemptState.FAILED, AttemptState.SUCCEEDED},
    AttemptState.CANCELLED: set(),  # terminal
}

ATTEMPT_TERMINAL_STATES = {
    AttemptState.SUCCEEDED, AttemptState.CANCELLED,
}


# ===========================================================================
# Review states
# ===========================================================================

class ReviewState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


REVIEW_TRANSITIONS: dict[ReviewState, set[ReviewState]] = {
    ReviewState.PENDING: {ReviewState.APPROVED, ReviewState.REJECTED, ReviewState.INVALIDATED},
    ReviewState.APPROVED: {ReviewState.INVALIDATED},
    ReviewState.REJECTED: {ReviewState.PENDING},  # can re-review
    ReviewState.INVALIDATED: {ReviewState.PENDING},  # can re-create after invalidation
}

REVIEW_TERMINAL_STATES: set[ReviewState] = set()  # no truly terminal states


# ===========================================================================
# Export states
# ===========================================================================

class ExportState(StrEnum):
    PENDING = "PENDING"
    ASSEMBLING = "ASSEMBLING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


EXPORT_TRANSITIONS: dict[ExportState, set[ExportState]] = {
    ExportState.PENDING: {ExportState.ASSEMBLING, ExportState.FAILED, ExportState.SUPERSEDED},
    ExportState.ASSEMBLING: {ExportState.VALIDATING, ExportState.FAILED, ExportState.SUPERSEDED},
    ExportState.VALIDATING: {ExportState.READY, ExportState.FAILED, ExportState.SUPERSEDED},
    ExportState.READY: {ExportState.SUPERSEDED},
    ExportState.FAILED: {ExportState.PENDING},  # can retry
    ExportState.SUPERSEDED: set(),  # terminal
}

EXPORT_TERMINAL_STATES = {
    ExportState.READY, ExportState.SUPERSEDED,
}


# ===========================================================================
# Validation helpers
# ===========================================================================

def is_valid_run_transition(from_state: RunState, to_state: RunState) -> bool:
    return to_state in RUN_TRANSITIONS.get(from_state, set())


def is_valid_task_transition(from_state: TaskState, to_state: TaskState) -> bool:
    return to_state in TASK_TRANSITIONS.get(from_state, set())


def is_valid_attempt_transition(from_state: AttemptState, to_state: AttemptState) -> bool:
    return to_state in ATTEMPT_TRANSITIONS.get(from_state, set())


def is_valid_review_transition(from_state: ReviewState, to_state: ReviewState) -> bool:
    return to_state in REVIEW_TRANSITIONS.get(from_state, set())


def is_valid_export_transition(from_state: ExportState, to_state: ExportState) -> bool:
    return to_state in EXPORT_TRANSITIONS.get(from_state, set())


# ===========================================================================
# CAS transition result
# ===========================================================================

@dataclass
class TransitionResult:
    """Result of a CAS state transition."""

    success: bool
    previous_state: str | None = None
    message: str = ""
