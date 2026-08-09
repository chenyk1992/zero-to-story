"""Tests for recovery logic."""
from __future__ import annotations

from lfo.execution.recovery import (
    AttemptRecord,
    BackendStatus,
    find_unknown_attempts,
    reconcile_unknown_attempt,
)


class TestReconcileUnknownAttempt:
    def test_no_provider_job_id_retries(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id=None,
        )
        decision = reconcile_unknown_attempt(attempt, lambda _: None)
        assert decision.action == "retry"
        assert "never submitted" in decision.reason

    def test_no_backend_record_retries(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id="job-123",
        )
        decision = reconcile_unknown_attempt(
            attempt, lambda _: BackendStatus(exists=False, completed=False)
        )
        assert decision.action == "retry"

    def test_backend_completed_success_reuses(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id="job-123",
        )
        decision = reconcile_unknown_attempt(
            attempt, lambda _: BackendStatus(exists=True, completed=True, succeeded=True)
        )
        assert decision.action == "reuse"

    def test_backend_completed_failure_marks_failed(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id="job-123",
        )
        decision = reconcile_unknown_attempt(
            attempt, lambda _: BackendStatus(exists=True, completed=True, succeeded=False)
        )
        assert decision.action == "mark_failed"

    def test_backend_still_running_reuses(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id="job-123",
        )
        decision = reconcile_unknown_attempt(
            attempt, lambda _: BackendStatus(exists=True, completed=False, succeeded=None)
        )
        assert decision.action == "reuse"

    def test_backend_query_exception_keeps_attempt_unknown(self) -> None:
        attempt = AttemptRecord(
            attempt_id="att-1",
            task_id="task-1",
            status="UNKNOWN",
            provider_job_id="job-123",
        )
        def failing_query(_):
            raise ConnectionError("backend unreachable")
        decision = reconcile_unknown_attempt(attempt, failing_query)
        assert decision.action == "wait"
        assert "Backend query failed" in decision.reason


class TestFindUnknownAttempts:
    def test_filters_unknown(self) -> None:
        attempts = [
            AttemptRecord("a1", "t1", "SUCCEEDED"),
            AttemptRecord("a2", "t2", "UNKNOWN"),
            AttemptRecord("a3", "t3", "FAILED"),
            AttemptRecord("a4", "t4", "UNKNOWN"),
        ]
        result = find_unknown_attempts(attempts)
        assert len(result) == 2
        assert result[0].attempt_id == "a2"
        assert result[1].attempt_id == "a4"

    def test_no_unknown(self) -> None:
        attempts = [
            AttemptRecord("a1", "t1", "SUCCEEDED"),
            AttemptRecord("a2", "t2", "FAILED"),
        ]
        assert find_unknown_attempts(attempts) == []
