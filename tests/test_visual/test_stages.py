"""Tests for VisualStage enum and assert_legal_pair."""
from __future__ import annotations

import pytest

from lfo.core.state_machine import TaskStatus
from lfo.visual.errors import IllegalStateTransitionError
from lfo.visual.stages import VisualStage, assert_legal_pair


def test_qc_pending_result_imported_ok():
    assert_legal_pair(TaskStatus.QC_PENDING, VisualStage.RESULT_IMPORTED)


def test_approved_pair_ok():
    assert_legal_pair(TaskStatus.APPROVED, VisualStage.APPROVED)


def test_succeeded_result_imported_illegal():
    """Visual happy path never uses SUCCEEDED — must be rejected."""
    with pytest.raises(IllegalStateTransitionError):
        assert_legal_pair(TaskStatus.SUCCEEDED, VisualStage.RESULT_IMPORTED)


def test_succeeded_any_stage_illegal():
    """SUCCEEDED + any VisualStage is illegal for visual tasks."""
    for stage in VisualStage:
        with pytest.raises(IllegalStateTransitionError):
            assert_legal_pair(TaskStatus.SUCCEEDED, stage)


def test_all_legal_pairs_from_spec_table():
    """Every row in spec §4.3 table must be a legal pair."""
    legal = [
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
    ]
    for status, stage in legal:
        assert_legal_pair(status, stage)  # must not raise


def test_illegal_pair_raises():
    """A combination not in the table must raise."""
    with pytest.raises(IllegalStateTransitionError):
        assert_legal_pair(TaskStatus.RUNNING, VisualStage.UNROUTED)


def test_blocked_disambiguated_by_status():
    """BLOCKED + WAITING_ASSETS and BLOCKED + FAILED_RETRYABLE are both legal."""
    assert_legal_pair(TaskStatus.WAITING_ASSETS, VisualStage.BLOCKED)
    assert_legal_pair(TaskStatus.FAILED_RETRYABLE, VisualStage.BLOCKED)
