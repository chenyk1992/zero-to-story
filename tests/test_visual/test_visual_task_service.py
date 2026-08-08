"""Tests for VisualTaskService — create + atomic transition."""
from __future__ import annotations

import pytest

from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.errors import IllegalStateTransitionError, VisualContractError
from lfo.visual.stages import VisualStage


def _svc(db: Database) -> VisualTaskService:
    return VisualTaskService(db)


def _setup_project(db: Database, project_id: str = "proj1") -> None:
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, 'n')", (project_id,))


def test_create_visual_task_returns_task_id():
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id="shot1",
        references=[{"asset_id": "ref1"}],
        prompt={"text": "a hero"},
    )
    assert task_id is not None
    db.close()


def test_create_visual_task_inserts_task_and_contract():
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id="shot1",
        references=[],
    )
    task = db.fetchone("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    assert task is not None
    assert task["task_type"] == "visual.generate"
    assert task["status"] == "PLANNED"

    contract = db.fetchone(
        "SELECT * FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert contract is not None
    assert contract["visual_stage"] == "UNROUTED"
    assert contract["purpose"] == "character_reference"
    assert contract["operation"] == "text_to_image"
    assert contract["compiler_identity_json"] is not None
    db.close()


def test_create_visual_task_continuity_edit():
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="continuity_edit",
        project_id="proj1",
        shot_id="shot1",
        references=[{"asset_id": "prev_frame"}],
    )
    contract = db.fetchone(
        "SELECT * FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert contract["task_type"] == "visual.edit"
    assert contract["operation"] == "image_edit"
    db.close()


def test_create_visual_task_invalid_purpose_raises():
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    with pytest.raises(VisualContractError):
        svc.create_visual_task(
            purpose="nonexistent_purpose",
            project_id="proj1",
            shot_id=None,
            references=[],
        )
    db.close()


def test_transition_success():
    """Successful CAS transition updates both task status and visual_stage."""
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="scene_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    svc.transition(
        task_id,
        expected_task_status=TaskStatus.PLANNED,
        expected_visual_stage=VisualStage.UNROUTED,
        new_task_status=TaskStatus.WAITING_ASSETS,
        new_visual_stage=VisualStage.BLOCKED,
        reason="missing refs",
    )
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "WAITING_ASSETS"
    assert contract["visual_stage"] == "BLOCKED"
    db.close()


def test_transition_cas_conflict():
    """If expected state doesn't match, transition raises."""
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="prop_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    with pytest.raises(VisualContractError, match="CAS"):
        svc.transition(
            task_id,
            expected_task_status=TaskStatus.READY,  # wrong expected
            expected_visual_stage=VisualStage.UNROUTED,
            new_task_status=TaskStatus.WAITING_ASSETS,
            new_visual_stage=VisualStage.BLOCKED,
            reason="test conflict",
        )
    db.close()


def test_transition_illegal_pair_raises():
    """Transition to an illegal (status, stage) pair is rejected."""
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    with pytest.raises(IllegalStateTransitionError):
        svc.transition(
            task_id,
            expected_task_status=TaskStatus.PLANNED,
            expected_visual_stage=VisualStage.UNROUTED,
            new_task_status=TaskStatus.SUCCEEDED,  # illegal for visual
            new_visual_stage=VisualStage.RESULT_IMPORTED,
            reason="should fail",
        )
    db.close()


def test_transition_logs_event():
    """Successful transition writes an event to the events table."""
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="scene_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    svc.transition(
        task_id,
        expected_task_status=TaskStatus.PLANNED,
        expected_visual_stage=VisualStage.UNROUTED,
        new_task_status=TaskStatus.READY,
        new_visual_stage=VisualStage.ROUTED,
        reason="routed to provider",
    )
    events = db.fetchall(
        "SELECT * FROM events WHERE task_id = ? AND event_type = 'visual_transition'",
        (task_id,),
    )
    assert len(events) == 1
    import json
    payload = json.loads(events[0]["payload"])
    assert payload["from_status"] == "PLANNED"
    assert payload["to_status"] == "READY"
    assert payload["from_stage"] == "UNROUTED"
    assert payload["to_stage"] == "ROUTED"
    assert payload["reason"] == "routed to provider"
    db.close()


def test_create_visual_task_content_hash():
    """Contract content_hash reflects the visual content fields."""
    db = Database()
    db.init_schema()
    _setup_project(db)
    svc = _svc(db)
    task_id = svc.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id="s1",
        references=[{"asset_id": "r1"}],
        prompt={"text": "hero"},
    )
    contract = db.fetchone(
        "SELECT content_hash FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert contract["content_hash"] is not None
    assert len(contract["content_hash"]) == 64
    db.close()
