"""Recovery logic — handle UNKNOWN attempts after a crash.

UNKNOWN attempts must be reconciled before creating new attempts.
Recovery never blindly re-submits; it confirms the old attempt truly
failed or has no backend record.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfo.execution.states import AttemptState


@dataclass
class AttemptRecord:
    """Lightweight attempt info for recovery decisions."""

    attempt_id: str
    task_id: str
    status: str
    provider_job_id: str | None = None


@dataclass
class BackendStatus:
    """Status of a task in the backend."""

    exists: bool  # Whether the backend has a record
    completed: bool  # Whether it completed (success or fail)
    succeeded: bool | None = None  # Whether it succeeded (if completed)


@dataclass
class RecoveryDecision:
    """Decision for an UNKNOWN attempt."""

    attempt_id: str
    action: str  # "reuse" | "retry" | "mark_failed"
    reason: str
    backend_status: BackendStatus | None = None


def reconcile_unknown_attempt(
    attempt: AttemptRecord,
    query_backend: callable,
) -> RecoveryDecision:
    """Reconcile an UNKNOWN attempt.

    Strategy:
    1. If the attempt has no provider_job_id, it was never truly submitted — safe to retry.
    2. If the backend has no record of the job, it was lost — safe to retry.
    3. If the backend shows it completed successfully, reuse the result.
    4. If the backend shows it completed with failure, mark as failed.
    5. If the backend shows it still running, wait (return "reuse" to keep monitoring).

    Args:
        attempt: The UNKNOWN attempt record.
        query_backend: Callable that takes a provider_job_id and returns BackendStatus.
            If attempt has no provider_job_id, this is not called.

    Returns:
        RecoveryDecision with the action to take.
    """
    if attempt.provider_job_id is None:
        return RecoveryDecision(
            attempt_id=attempt.attempt_id,
            action="retry",
            reason="No provider job ID — was never submitted",
        )

    try:
        status = query_backend(attempt.provider_job_id)
    except Exception as e:
        # Backend query itself failed — can't determine status
        return RecoveryDecision(
            attempt_id=attempt.attempt_id,
            action="retry",
            reason=f"Backend query failed: {e}",
            backend_status=None,
        )

    if not status.exists:
        return RecoveryDecision(
            attempt_id=attempt.attempt_id,
            action="retry",
            reason="No backend record of this job",
            backend_status=status,
        )

    if status.completed:
        if status.succeeded:
            return RecoveryDecision(
                attempt_id=attempt.attempt_id,
                action="reuse",
                reason="Backend shows completed successfully",
                backend_status=status,
            )
        else:
            return RecoveryDecision(
                attempt_id=attempt.attempt_id,
                action="mark_failed",
                reason="Backend shows completed with failure",
                backend_status=status,
            )

    # Still running according to backend
    return RecoveryDecision(
        attempt_id=attempt.attempt_id,
        action="reuse",
        reason="Backend shows still running — keep monitoring",
        backend_status=status,
    )


def find_unknown_attempts(
    attempts: list[AttemptRecord],
) -> list[AttemptRecord]:
    """Filter attempts that are in UNKNOWN state."""
    return [a for a in attempts if a.status == AttemptState.UNKNOWN.value]
