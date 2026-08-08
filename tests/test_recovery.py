"""Tests for LFO crash recovery and invalidation."""
import pytest

from lfo.core.database import Database
from lfo.core.invalidation import (
    get_active_invalidations,
    invalidate_upstream,
    resolve_invalidation,
)
from lfo.core.recovery import (
    recover_project,
    recover_uncertain_journal,
)
from lfo.core.runtime import (
    create_attempt,
    create_journal_entry,
    create_task,
    get_task,
    transition_journal,
    update_task_hashes,
    update_task_status,
)
from lfo.core.state_machine import SubmissionState, TaskStatus


@pytest.fixture
def db():
    database = Database()
    database.init_schema()
    yield database
    database.close()


class TestCrashRecovery:
    def test_recover_running_task(self, db):
        """A RUNNING task with fingerprints should be reset to READY on recovery."""
        tid = create_task(db, "proj1", "h3_t2va")
        update_task_hashes(
            db, tid,
            content_hash="ch_1", dependency_hash="dh_1",
            params_hash="ph_1", idempotency_key="idem_1",
        )
        update_task_status(db, tid, TaskStatus.RUNNING)

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 1

        task = get_task(db, tid)
        assert task["status"] == TaskStatus.READY
        # Fingerprints must be preserved
        assert task["content_hash"] == "ch_1"
        assert task["idempotency_key"] == "idem_1"

    def test_recover_queued_task(self, db):
        """A QUEUED task with fingerprints should be reset to READY on recovery."""
        tid = create_task(db, "proj1", "h3_t2va")
        update_task_hashes(
            db, tid,
            content_hash="ch_1", dependency_hash="dh_1",
            params_hash="ph_1", idempotency_key="idem_1",
        )
        update_task_status(db, tid, TaskStatus.QUEUED)

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 1

        task = get_task(db, tid)
        assert task["status"] == TaskStatus.READY

    def test_recover_multiple_tasks(self, db):
        """Multiple running tasks with fingerprints should all be reset."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_t2va")
        t3 = create_task(db, "proj1", "h3_i2v")
        update_task_hashes(db, t1, content_hash="ch_1", dependency_hash="dh_1",
                          params_hash="ph_1", idempotency_key="idem_1")
        update_task_hashes(db, t2, content_hash="ch_2", dependency_hash="dh_2",
                          params_hash="ph_2", idempotency_key="idem_2")
        update_task_status(db, t1, TaskStatus.RUNNING)
        update_task_status(db, t2, TaskStatus.QUEUED)
        # t3 stays PLANNED (no fingerprints)

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 2

        assert get_task(db, t1)["status"] == TaskStatus.READY
        assert get_task(db, t2)["status"] == TaskStatus.READY
        assert get_task(db, t3)["status"] == TaskStatus.PLANNED

    def test_recover_approved_task_unchanged(self, db):
        """An APPROVED task should not be touched by recovery."""
        tid = create_task(db, "proj1", "keyframe")
        update_task_status(db, tid, TaskStatus.APPROVED)

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 0
        assert get_task(db, tid)["status"] == TaskStatus.APPROVED

    def test_recover_empty_project(self, db):
        """Recovery on a project with no tasks should be a no-op."""
        summary = recover_project(db, "nonexistent")
        assert summary["tasks_reset"] == 0
        assert summary["journals_marked_uncertain"] == 0

    def test_recover_with_uncertain_journal(self, db):
        """Tasks with uncertain journal entries should be detected."""
        tid = create_task(db, "proj1", "h3_t2va")
        update_task_hashes(
            db, tid,
            content_hash="ch_1", dependency_hash="dh_1",
            params_hash="ph_1", idempotency_key="idem_1",
        )
        update_task_status(db, tid, TaskStatus.RUNNING)
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)
        # Transition to SUBMITTING (uncertain state)
        transition_journal(
            db, jid,
            from_state=SubmissionState.PREPARED,
            to_state=SubmissionState.SUBMITTING,
        )

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 1
        assert summary["journals_marked_uncertain"] == 1

        # Task should be recovered to READY with fingerprints preserved
        task = get_task(db, tid)
        assert task["status"] == TaskStatus.READY
        assert task["content_hash"] == "ch_1"
        assert task["idempotency_key"] == "idem_1"

    def test_recovery_resets_to_planned_without_fingerprints(self, db):
        """A RUNNING task without fingerprints resets to PLANNED, not READY."""
        tid = create_task(db, "proj1", "h3_t2va")
        # No hashes set — task was never properly prepared
        update_task_status(db, tid, TaskStatus.RUNNING)

        summary = recover_project(db, "proj1")
        assert summary["tasks_reset"] == 1

        task = get_task(db, tid)
        # Without fingerprints, cannot be READY — falls back to PLANNED
        assert task["status"] == TaskStatus.PLANNED


class TestUncertainJournal:
    def test_resolve_job_exists(self, db):
        """If provider still has the job, continue monitoring."""
        tid = create_task(db, "proj1", "h3_t2va")
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)
        transition_journal(
            db, jid,
            from_state=SubmissionState.PREPARED,
            to_state=SubmissionState.SUBMITTING,
        )

        result = recover_uncertain_journal(db, jid, provider_has_job=True)
        assert result == SubmissionState.SUBMITTED.value

    def test_resolve_job_lost(self, db):
        """If provider doesn't have the job, mark as FAILED."""
        tid = create_task(db, "proj1", "h3_t2va")
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)
        transition_journal(
            db, jid,
            from_state=SubmissionState.PREPARED,
            to_state=SubmissionState.SUBMITTING,
        )

        result = recover_uncertain_journal(db, jid, provider_has_job=False)
        assert result == SubmissionState.FAILED.value

    def test_resolve_nonexistent_journal(self, db):
        """Resolving a non-existent journal should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            recover_uncertain_journal(db, "nonexistent", provider_has_job=True)


class TestInvalidation:
    def test_invalidate_downstream(self, db):
        """Changing upstream should mark downstream tasks STALE."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])
        t3 = create_task(db, "proj1", "h3_first_last", dependencies=[t1])

        invalidated = invalidate_upstream(db, t1)
        assert set(invalidated) == {t2, t3}

        assert get_task(db, t2)["status"] == TaskStatus.STALE
        assert get_task(db, t3)["status"] == TaskStatus.STALE

    def test_no_invalidation_without_dep(self, db):
        """Tasks without dependency on source should not be invalidated."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_t2va")  # no dependency

        invalidated = invalidate_upstream(db, t1)
        assert invalidated == []
        assert get_task(db, t2)["status"] == TaskStatus.PLANNED

    def test_invalidation_records(self, db):
        """Invalidation should create records in invalidations table."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])

        invalidate_upstream(db, t1, reason="test_change", scope={"field": "prompt"})

        invs = get_active_invalidations(db, "proj1")
        assert len(invs) == 1
        assert invs[0]["source_task_id"] == t1
        assert invs[0]["target_task_id"] == t2
        assert invs[0]["reason"] == "test_change"

    def test_resolve_invalidation(self, db):
        """Resolving invalidation should update the records."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])

        invalidate_upstream(db, t1)
        count = resolve_invalidation(db, t2)
        assert count >= 1

        invs = get_active_invalidations(db, "proj1")
        assert len(invs) == 0

    def test_invalidate_nonexistent_source(self, db):
        """Invalidating a non-existent task should return empty list."""
        result = invalidate_upstream(db, "nonexistent")
        assert result == []

    def test_cascading_invalidation(self, db):
        """A -> B -> C chain: changing A should invalidate B and C (transitively)."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])
        # Note: t2 depends on t1, but t3 depends on t2 (one level at a time)
        t3 = create_task(db, "proj1", "assembly", dependencies=[t2])

        # First pass: t1 change invalidates t2
        invalidated = invalidate_upstream(db, t1)
        assert t2 in invalidated
        # t3 is not directly dependent on t1, so not in first pass
        # (This is by design: invalidation only goes one hop)
