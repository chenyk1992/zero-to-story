"""VisualStage enum and legal (TaskStatus, VisualStage) combinations.

The visual happy path never uses TaskStatus.SUCCEEDED — terminal success
for visual tasks is APPROVED + APPROVED. This avoids conflict with
TASK_TERMINAL_STATES and premature dependency satisfaction.

Legal combinations encode spec §4.3. BLOCKED is disambiguated by
TaskStatus (WAITING_ASSETS vs FAILED_RETRYABLE).
"""
from __future__ import annotations

from enum import Enum

from lfo.core.state_machine import TaskStatus


class VisualStage(str, Enum):
    """Persisted visual-domain stage for a visual task.

    EXPORTED is intentionally absent — export atomically transitions
    to AWAITING_RESULT, so it is a transient action, not a persisted stage.
    """
    UNROUTED = "UNROUTED"
    BLOCKED = "BLOCKED"
    ROUTED = "ROUTED"
    SUBMITTED = "SUBMITTED"
    AWAITING_RESULT = "AWAITING_RESULT"
    RESULT_IMPORTED = "RESULT_IMPORTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


# Legal (TaskStatus, VisualStage) combinations from spec §4.3.
# Visual happy path never lands on SUCCEEDED, so SUCCEEDED + anything is illegal.
_LEGAL_PAIRS: frozenset[tuple[TaskStatus, VisualStage]] = frozenset({
    (TaskStatus.PLANNED, VisualStage.UNROUTED),
    (TaskStatus.WAITING_ASSETS, VisualStage.BLOCKED),
    (TaskStatus.READY, VisualStage.ROUTED),
    (TaskStatus.WAITING_USER, VisualStage.AWAITING_RESULT),
    (TaskStatus.QUEUED, VisualStage.SUBMITTED),
    (TaskStatus.RUNNING, VisualStage.SUBMITTED),
    (TaskStatus.QC_PENDING, VisualStage.RESULT_IMPORTED),
    (TaskStatus.WAITING_USER, VisualStage.AWAITING_REVIEW),
    (TaskStatus.APPROVED, VisualStage.APPROVED),
    (TaskStatus.FAILED_RETRYABLE, VisualStage.BLOCKED),
    (TaskStatus.FAILED_TERMINAL, VisualStage.REJECTED),
    (TaskStatus.STALE, VisualStage.STALE),
    (TaskStatus.NEEDS_REMATERIALIZATION, VisualStage.STALE),
    (TaskStatus.SUPERSEDED, VisualStage.SUPERSEDED),
    (TaskStatus.CANCELLED, VisualStage.CANCELLED),
})


def assert_legal_pair(status: TaskStatus, stage: VisualStage) -> None:
    """Assert that (status, stage) is a legal combination.

    Args:
        status: The task status.
        stage: The visual stage.

    Raises:
        IllegalStateTransitionError: If the combination is illegal,
            including the visual happy-path rule that SUCCEEDED is
            never a valid visual status.
    """
    from lfo.visual.errors import IllegalStateTransitionError

    if (status, stage) not in _LEGAL_PAIRS:
        raise IllegalStateTransitionError(status=status, stage=stage)
