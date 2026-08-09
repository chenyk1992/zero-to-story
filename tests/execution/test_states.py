"""Tests for state transition matrices."""
from __future__ import annotations

from lfo.execution.states import (
    AttemptState,
    ExportState,
    ReviewState,
    RunState,
    TaskState,
    is_valid_attempt_transition,
    is_valid_export_transition,
    is_valid_review_transition,
    is_valid_run_transition,
    is_valid_task_transition,
)


class TestRunTransitions:
    def test_accepted_to_importing(self) -> None:
        assert is_valid_run_transition(RunState.ACCEPTED, RunState.IMPORTING)

    def test_importing_to_planning(self) -> None:
        assert is_valid_run_transition(RunState.IMPORTING, RunState.PLANNING)

    def test_running_to_completed(self) -> None:
        assert is_valid_run_transition(RunState.RUNNING, RunState.COMPLETED)

    def test_illegal_jump(self) -> None:
        assert not is_valid_run_transition(RunState.ACCEPTED, RunState.RUNNING)

    def test_terminal_no_exit(self) -> None:
        assert not is_valid_run_transition(RunState.COMPLETED, RunState.RUNNING)
        assert not is_valid_run_transition(RunState.FAILED, RunState.RUNNING)


class TestTaskTransitions:
    def test_blocked_to_ready(self) -> None:
        assert is_valid_task_transition(TaskState.BLOCKED, TaskState.READY)

    def test_ready_to_running(self) -> None:
        assert is_valid_task_transition(TaskState.READY, TaskState.RUNNING)

    def test_running_to_succeeded(self) -> None:
        assert is_valid_task_transition(TaskState.RUNNING, TaskState.SUCCEEDED)

    def test_running_to_failed_retryable(self) -> None:
        assert is_valid_task_transition(TaskState.RUNNING, TaskState.FAILED_RETRYABLE)

    def test_failed_retryable_to_ready(self) -> None:
        assert is_valid_task_transition(TaskState.FAILED_RETRYABLE, TaskState.READY)

    def test_succeeded_can_go_stale(self) -> None:
        assert is_valid_task_transition(TaskState.SUCCEEDED, TaskState.STALE)

    def test_illegal(self) -> None:
        assert not is_valid_task_transition(TaskState.READY, TaskState.SUCCEEDED)


class TestAttemptTransitions:
    def test_created_to_submitting(self) -> None:
        assert is_valid_attempt_transition(AttemptState.CREATED, AttemptState.SUBMITTING)

    def test_submitting_to_submitted(self) -> None:
        assert is_valid_attempt_transition(AttemptState.SUBMITTING, AttemptState.SUBMITTED)

    def test_submitted_to_running(self) -> None:
        assert is_valid_attempt_transition(AttemptState.SUBMITTED, AttemptState.RUNNING)

    def test_running_to_succeeded(self) -> None:
        assert is_valid_attempt_transition(AttemptState.RUNNING, AttemptState.SUCCEEDED)

    def test_failed_to_created_retry(self) -> None:
        assert is_valid_attempt_transition(AttemptState.FAILED, AttemptState.CREATED)

    def test_unknown_reconciliation(self) -> None:
        assert is_valid_attempt_transition(AttemptState.UNKNOWN, AttemptState.FAILED)
        assert is_valid_attempt_transition(AttemptState.UNKNOWN, AttemptState.SUCCEEDED)
        assert is_valid_attempt_transition(AttemptState.UNKNOWN, AttemptState.RUNNING)

    def test_illegal(self) -> None:
        assert not is_valid_attempt_transition(AttemptState.SUCCEEDED, AttemptState.FAILED)
        assert not is_valid_attempt_transition(AttemptState.CANCELLED, AttemptState.CREATED)


class TestReviewTransitions:
    def test_pending_to_approved(self) -> None:
        assert is_valid_review_transition(ReviewState.PENDING, ReviewState.APPROVED)

    def test_approved_can_be_invalidated(self) -> None:
        assert is_valid_review_transition(ReviewState.APPROVED, ReviewState.INVALIDATED)

    def test_invalidated_to_pending(self) -> None:
        assert is_valid_review_transition(ReviewState.INVALIDATED, ReviewState.PENDING)


class TestExportTransitions:
    def test_full_flow(self) -> None:
        assert is_valid_export_transition(ExportState.PENDING, ExportState.ASSEMBLING)
        assert is_valid_export_transition(ExportState.ASSEMBLING, ExportState.VALIDATING)
        assert is_valid_export_transition(ExportState.VALIDATING, ExportState.READY)

    def test_failed_can_retry(self) -> None:
        assert is_valid_export_transition(ExportState.FAILED, ExportState.PENDING)

    def test_illegal(self) -> None:
        assert not is_valid_export_transition(ExportState.READY, ExportState.PENDING)
