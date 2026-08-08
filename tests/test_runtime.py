"""Tests for LFO Runtime operations."""
import pytest

from lfo.core.database import Database
from lfo.core.runtime import (
    create_asset,
    create_attempt,
    create_journal_entry,
    create_task,
    get_assets_by_task,
    get_attempt,
    get_attempts_by_task,
    get_events,
    get_journal,
    get_journal_by_attempt,
    get_project_state,
    get_task,
    get_tasks_by_project,
    promote_task_to_ready,
    transition_journal,
    update_task_hashes,
    update_task_status,
)
from lfo.core.state_machine import SubmissionState, TaskStatus


@pytest.fixture
def db():
    """Create a fresh in-memory database for each test."""
    database = Database()
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def project(db):
    """Create a project with a task. Returns (project_id, task_id)."""
    pid = "proj_test_001"
    tid = create_task(db, pid, "h3_t2va")
    return pid, tid


class TestTaskOperations:
    def test_create_task(self, db):
        tid = create_task(db, "proj1", "keyframe")
        assert tid.startswith("task_")
        task = get_task(db, tid)
        assert task is not None
        assert task["project_id"] == "proj1"
        assert task["task_type"] == "keyframe"
        assert task["status"] == TaskStatus.PLANNED
        assert task["dependencies"] == []

    def test_create_task_with_deps(self, db):
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])
        task = get_task(db, t2)
        assert task["dependencies"] == [t1]

    def test_get_nonexistent_task(self, db):
        assert get_task(db, "nonexistent") is None

    def test_get_tasks_by_project(self, db):
        create_task(db, "proj1", "keyframe")
        create_task(db, "proj1", "h3_t2va")
        create_task(db, "proj2", "keyframe")
        tasks = get_tasks_by_project(db, "proj1")
        assert len(tasks) == 2
        assert all(t["project_id"] == "proj1" for t in tasks)

    def test_update_task_status(self, db):
        tid = create_task(db, "proj1", "keyframe")
        result = update_task_status(db, tid, TaskStatus.QUEUED)
        assert result is True
        task = get_task(db, tid)
        assert task["status"] == TaskStatus.QUEUED

    def test_cannot_set_ready_through_generic_status_update(self, db):
        """update_task_status() must reject READY — use promote_task_to_ready()."""
        tid = create_task(db, "proj1", "keyframe")
        with pytest.raises(ValueError, match="promote_task_to_ready"):
            update_task_status(db, tid, TaskStatus.READY)

    def test_update_task_status_with_error(self, db):
        tid = create_task(db, "proj1", "keyframe")
        update_task_status(db, tid, TaskStatus.FAILED_RETRYABLE, error="OOM")
        task = get_task(db, tid)
        assert task["status"] == TaskStatus.FAILED_RETRYABLE
        assert task["error"] == "OOM"

    def test_update_task_hashes(self, db):
        tid = create_task(db, "proj1", "keyframe")
        update_task_hashes(
            db, tid,
            content_hash="abc123",
            dependency_hash="def456",
            params_hash="ghi789",
            idempotency_key="idem_key_1",
        )
        task = get_task(db, tid)
        assert task["content_hash"] == "abc123"
        assert task["dependency_hash"] == "def456"
        assert task["params_hash"] == "ghi789"
        assert task["idempotency_key"] == "idem_key_1"

    def test_promote_to_ready_requires_all_fingerprints(self, db):
        """promote_task_to_ready must be called with all four fingerprints."""
        tid = create_task(db, "proj1", "keyframe")
        promote_task_to_ready(
            db, tid,
            content_hash="ch_1",
            dependency_hash="dh_1",
            params_hash="ph_1",
            idempotency_key="idem_1",
        )
        task = get_task(db, tid)
        assert task["status"] == TaskStatus.READY
        assert task["content_hash"] == "ch_1"
        assert task["dependency_hash"] == "dh_1"
        assert task["params_hash"] == "ph_1"
        assert task["idempotency_key"] == "idem_1"

    def test_promote_to_ready_is_atomic(self, db):
        """Promotion is all-or-nothing: fingerprints + status in one transaction."""
        tid = create_task(db, "proj1", "keyframe")
        promote_task_to_ready(
            db, tid,
            content_hash="ch_atomic",
            dependency_hash="dh_atomic",
            params_hash="ph_atomic",
            idempotency_key="idem_atomic",
        )
        task = get_task(db, tid)
        # All fingerprints must be present
        assert task["content_hash"] == "ch_atomic"
        assert task["dependency_hash"] == "dh_atomic"
        assert task["params_hash"] == "ph_atomic"
        assert task["idempotency_key"] == "idem_atomic"
        assert task["status"] == TaskStatus.READY

    def test_promote_to_ready_checks_dependencies(self, db):
        """Cannot promote if dependencies are not in terminal states."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])

        # t1 is still PLANNED, not terminal
        with pytest.raises(ValueError, match="Dependency.*not a terminal state"):
            promote_task_to_ready(
                db, t2,
                content_hash="ch_1",
                dependency_hash="dh_1",
                params_hash="ph_1",
                idempotency_key="idem_1",
            )

    def test_promote_to_ready_after_deps_complete(self, db):
        """Can promote once all dependencies are terminal."""
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_i2v", dependencies=[t1])

        # Complete t1
        update_task_status(db, t1, TaskStatus.APPROVED)

        # Now t2 can be promoted
        promote_task_to_ready(
            db, t2,
            content_hash="ch_1",
            dependency_hash="dh_1",
            params_hash="ph_1",
            idempotency_key="idem_1",
        )
        assert get_task(db, t2)["status"] == TaskStatus.READY

    def test_promote_nonexistent_task_raises(self, db):
        """promote_task_to_ready on missing task raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            promote_task_to_ready(
                db, "nonexistent",
                content_hash="ch", dependency_hash="dh",
                params_hash="ph", idempotency_key="idem",
            )

    def test_promote_from_running_with_fingerprints(self, db):
        """RUNNING can be promoted to READY when fingerprints exist (crash recovery)."""
        tid = create_task(db, "proj1", "keyframe")
        update_task_hashes(
            db, tid,
            content_hash="ch_1", dependency_hash="dh_1",
            params_hash="ph_1", idempotency_key="idem_1",
        )
        update_task_status(db, tid, TaskStatus.RUNNING)
        # Recovery scenario: task has fingerprints, can be promoted
        promote_task_to_ready(
            db, tid,
            content_hash="ch_1", dependency_hash="dh_1",
            params_hash="ph_1", idempotency_key="idem_1",
        )
        assert get_task(db, tid)["status"] == TaskStatus.READY

    def test_promote_from_approved_raises(self, db):
        """Cannot promote from APPROVED — terminal state."""
        tid = create_task(db, "proj1", "keyframe")
        update_task_status(db, tid, TaskStatus.APPROVED)
        with pytest.raises(ValueError, match="Cannot promote"):
            promote_task_to_ready(
                db, tid,
                content_hash="ch", dependency_hash="dh",
                params_hash="ph", idempotency_key="idem",
            )


class TestAttemptOperations:
    def test_create_attempt(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1",
            dependency_hash="dh_1",
            params_hash="ph_1",
            workflow_id="h3_standard_t2v",
        )
        assert aid.startswith("att_")
        attempt = get_attempt(db, aid)
        assert attempt["task_id"] == tid
        assert attempt["workflow_id"] == "h3_standard_t2v"
        assert attempt["status"] == SubmissionState.PREPARED

    def test_attempt_links_to_task(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1",
            dependency_hash="dh_1",
            params_hash="ph_1",
        )
        task = get_task(db, tid)
        assert aid in task["attempt_ids"]
        assert task["latest_attempt_id"] == aid

    def test_multiple_attempts(self, db, project):
        pid, tid = project
        aid1 = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        aid2 = create_attempt(
            db, tid,
            idempotency_key="idem_2",
            content_hash="ch_2", dependency_hash="dh_2", params_hash="ph_2",
        )
        attempts = get_attempts_by_task(db, tid)
        assert len(attempts) == 2
        task = get_task(db, tid)
        assert task["latest_attempt_id"] == aid2


class TestJournalOperations:
    def test_create_journal(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)
        assert jid.startswith("jrnl_")
        journal = get_journal(db, jid)
        assert journal["state"] == SubmissionState.PREPARED

    def test_transition_journal_success(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)

        # PREPARED -> SUBMITTING
        result = transition_journal(
            db, jid,
            from_state=SubmissionState.PREPARED,
            to_state=SubmissionState.SUBMITTING,
        )
        assert result is True
        journal = get_journal(db, jid)
        assert journal["state"] == SubmissionState.SUBMITTING

    def test_transition_journal_cas_fail(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)

        # Try PREPARED -> COMPLETED (skip steps) — should succeed as CAS doesn't care about semantics
        # but PREPARED -> SUBMITTED with wrong from_state should fail
        result = transition_journal(
            db, jid,
            from_state=SubmissionState.SUBMITTED,  # wrong from_state
            to_state=SubmissionState.COMPLETED,
        )
        assert result is False
        journal = get_journal(db, jid)
        assert journal["state"] == SubmissionState.PREPARED  # unchanged

    def test_full_journal_lifecycle(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)

        # Walk through the full lifecycle
        transitions = [
            (SubmissionState.PREPARED, SubmissionState.SUBMITTING, {}),
            (SubmissionState.SUBMITTING, SubmissionState.SUBMITTED, {"provider_job_id": "prompt_123"}),
            (SubmissionState.SUBMITTED, SubmissionState.COLLECTING, {}),
            (SubmissionState.COLLECTING, SubmissionState.COMPLETED, {}),
        ]
        for from_s, to_s, kwargs in transitions:
            result = transition_journal(db, jid, from_s, to_s, **kwargs)
            assert result is True, f"Transition {from_s} -> {to_s} failed"

        journal = get_journal(db, jid)
        assert journal["state"] == SubmissionState.COMPLETED
        assert journal["provider_job_id"] == "prompt_123"

    def test_get_journal_by_attempt(self, db, project):
        pid, tid = project
        aid = create_attempt(
            db, tid,
            idempotency_key="idem_1",
            content_hash="ch_1", dependency_hash="dh_1", params_hash="ph_1",
        )
        jid = create_journal_entry(db, aid, tid)
        journal = get_journal_by_attempt(db, aid)
        assert journal is not None
        assert journal["journal_id"] == jid


class TestAssetOperations:
    def test_create_asset(self, db, project):
        pid, tid = project
        aid = create_asset(
            db, tid,
            asset_type="video",
            file_path="lfo/proj/att001/video_00001_.mp4",
            file_hash="sha256_abc",
            file_size=1024000,
            mime_type="video/mp4",
            width=864,
            height=480,
            duration=5.0,
            frame_count=124,
        )
        assert aid.startswith("asset_")
        assets = get_assets_by_task(db, tid)
        assert len(assets) == 1
        assert assets[0]["file_hash"] == "sha256_abc"
        assert assets[0]["frame_count"] == 124

    def test_multiple_assets(self, db, project):
        pid, tid = project
        create_asset(db, tid, "image", "frame_001.png")
        create_asset(db, tid, "image", "frame_002.png")
        create_asset(db, tid, "video", "video_001.mp4")
        assets = get_assets_by_task(db, tid)
        assert len(assets) == 3


class TestProjectState:
    def test_empty_project(self, db):
        state = get_project_state(db, "nonexistent_proj")
        assert state.run_status == "IDLE"

    def test_project_with_ready_task(self, db):
        tid = create_task(db, "proj1", "keyframe")
        promote_task_to_ready(
            db, tid,
            content_hash="ch_1",
            dependency_hash="dh_1",
            params_hash="ph_1",
            idempotency_key="idem_1",
        )
        state = get_project_state(db, "proj1")
        assert state.run_status == "READY"
        assert state.next_action == "schedule_ready_tasks"

    def test_project_with_running_task(self, db):
        tid = create_task(db, "proj1", "keyframe")
        update_task_status(db, tid, TaskStatus.RUNNING)
        state = get_project_state(db, "proj1")
        assert state.run_status == "RUNNING"

    def test_project_waiting_user(self, db):
        t1 = create_task(db, "proj1", "keyframe")
        update_task_status(db, t1, TaskStatus.WAITING_USER)
        state = get_project_state(db, "proj1")
        assert state.run_status == "WAITING_USER"
        assert state.attention_required is True
        assert state.attention_count == 1

    def test_project_blocked(self, db):
        tid = create_task(db, "proj1", "keyframe")
        update_task_status(db, tid, TaskStatus.FAILED_TERMINAL)
        state = get_project_state(db, "proj1")
        assert state.run_status == "BLOCKED"

    def test_project_completed(self, db):
        t1 = create_task(db, "proj1", "keyframe")
        update_task_status(db, t1, TaskStatus.APPROVED)
        state = get_project_state(db, "proj1")
        assert state.run_status == "COMPLETED"

    def test_project_tasks_summary(self, db):
        t1 = create_task(db, "proj1", "keyframe")
        t2 = create_task(db, "proj1", "h3_t2va")
        t3 = create_task(db, "proj1", "h3_i2v")
        update_task_status(db, t1, TaskStatus.APPROVED)
        update_task_status(db, t2, TaskStatus.RUNNING)
        update_task_status(db, t3, TaskStatus.PLANNED)
        state = get_project_state(db, "proj1")
        assert state.tasks_summary.get("APPROVED") == 1
        assert state.tasks_summary.get("RUNNING") == 1
        assert state.tasks_summary.get("PLANNED") == 1


class TestEvents:
    def test_task_creation_logs_event(self, db):
        tid = create_task(db, "proj1", "keyframe")
        events = get_events(db, "proj1")
        assert len(events) >= 1
        assert events[0]["event_type"] == "task_created"
        assert events[0]["task_id"] == tid
