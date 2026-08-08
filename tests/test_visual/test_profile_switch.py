"""Tests for profile switch + invalidation (Task 11).

On profile activate: unstarted visual tasks (UNROUTED/BLOCKED/ROUTED) →
STALE. Running (SUBMITTED/AWAITING_RESULT) keep old profile. Terminal
(RESULT_IMPORT/AWAITING_REVIEW/APPROVED/REJECTED) untouched.
"""
from __future__ import annotations

from lfo.application.visual_profile_service import VisualProfileService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.stages import VisualStage


def _fresh_db() -> Database:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    return db


def _create_profile(db: Database, policy: str = "allow_t2va_fallback") -> str:
    svc = VisualProfileService(db)
    rid = svc.create_draft("proj1", {"visual_input_policy": policy})
    svc.activate(rid)
    return rid


def _make_task(db: Database, stage: VisualStage) -> str:
    """Create a visual task and transition it to the given stage."""
    ts = VisualTaskService(db)
    tid = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    if stage == VisualStage.UNROUTED:
        return tid
    # UNROUTED → BLOCKED
    ts.transition(
        tid,
        expected_task_status=TaskStatus.PLANNED,
        expected_visual_stage=VisualStage.UNROUTED,
        new_task_status=TaskStatus.WAITING_ASSETS,
        new_visual_stage=VisualStage.BLOCKED,
        reason="test",
    )
    if stage == VisualStage.BLOCKED:
        return tid
    # BLOCKED → ROUTED
    ts.transition(
        tid,
        expected_task_status=TaskStatus.WAITING_ASSETS,
        expected_visual_stage=VisualStage.BLOCKED,
        new_task_status=TaskStatus.READY,
        new_visual_stage=VisualStage.ROUTED,
        reason="test",
    )
    if stage == VisualStage.ROUTED:
        return tid
    # ROUTED → SUBMITTED
    ts.transition(
        tid,
        expected_task_status=TaskStatus.READY,
        expected_visual_stage=VisualStage.ROUTED,
        new_task_status=TaskStatus.QUEUED,
        new_visual_stage=VisualStage.SUBMITTED,
        reason="test",
    )
    if stage == VisualStage.SUBMITTED:
        return tid
    # SUBMITTED → AWAITING_RESULT
    ts.transition(
        tid,
        expected_task_status=TaskStatus.QUEUED,
        expected_visual_stage=VisualStage.SUBMITTED,
        new_task_status=TaskStatus.WAITING_USER,
        new_visual_stage=VisualStage.AWAITING_RESULT,
        reason="test",
    )
    return tid


def _task_status(db: Database, tid: str) -> str:
    row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (tid,))
    return row["status"]


def _visual_stage(db: Database, tid: str) -> str:
    row = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?",
        (tid,),
    )
    return row["visual_stage"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_activate_stales_unrouted_tasks():
    db = _fresh_db()
    _create_profile(db)

    tid = _make_task(db, VisualStage.UNROUTED)

    # Activate a new profile
    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    assert _task_status(db, tid) == TaskStatus.STALE.value
    assert _visual_stage(db, tid) == VisualStage.STALE.value
    db.close()


def test_activate_stales_blocked_tasks():
    db = _fresh_db()
    _create_profile(db)

    tid = _make_task(db, VisualStage.BLOCKED)

    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    assert _task_status(db, tid) == TaskStatus.STALE.value
    assert _visual_stage(db, tid) == VisualStage.STALE.value
    db.close()


def test_activate_stales_routed_tasks():
    db = _fresh_db()
    _create_profile(db)

    tid = _make_task(db, VisualStage.ROUTED)

    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    assert _task_status(db, tid) == TaskStatus.STALE.value
    assert _visual_stage(db, tid) == VisualStage.STALE.value
    db.close()


def test_activate_does_not_stale_submitted_tasks():
    db = _fresh_db()
    _create_profile(db)

    tid = _make_task(db, VisualStage.SUBMITTED)

    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    # Running tasks keep old status
    assert _task_status(db, tid) == TaskStatus.QUEUED.value
    assert _visual_stage(db, tid) == VisualStage.SUBMITTED.value
    db.close()


def test_activate_does_not_stale_awaiting_result_tasks():
    db = _fresh_db()
    _create_profile(db)

    tid = _make_task(db, VisualStage.AWAITING_RESULT)

    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    assert _task_status(db, tid) == TaskStatus.WAITING_USER.value
    assert _visual_stage(db, tid) == VisualStage.AWAITING_RESULT.value
    db.close()


def test_activate_only_affects_target_project():
    """Profile switch on proj1 should not stale tasks in proj2."""
    db = _fresh_db()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj2', 'n')")

    _create_profile(db)

    # Task in proj1
    tid1 = _make_task(db, VisualStage.UNROUTED)

    # Task in proj2 (manually inserted)
    ts = VisualTaskService(db)
    tid2 = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj2",
        shot_id=None,
        references=[],
    )

    # Activate new profile for proj1 only
    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    assert _task_status(db, tid1) == TaskStatus.STALE.value
    assert _task_status(db, tid2) == TaskStatus.PLANNED.value  # untouched
    db.close()


def test_activate_stales_multiple_tasks():
    db = _fresh_db()
    _create_profile(db)

    t1 = _make_task(db, VisualStage.UNROUTED)
    t2 = _make_task(db, VisualStage.BLOCKED)
    t3 = _make_task(db, VisualStage.ROUTED)

    svc = VisualProfileService(db)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)

    for tid in (t1, t2, t3):
        assert _task_status(db, tid) == TaskStatus.STALE.value
        assert _visual_stage(db, tid) == VisualStage.STALE.value
    db.close()
