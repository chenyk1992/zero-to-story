"""Tests for VisualRoutingService."""
from __future__ import annotations

from lfo.application.visual_provider_service import VisualProviderService
from lfo.application.visual_routing_service import VisualRoutingService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database


def _setup(db: Database, project_id: str = "proj1") -> None:
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, 'n')", (project_id,))


def _create_provider(
    db: Database,
    provider_id: str,
    scope_type: str,
    scope_id: str,
    caps: dict,
) -> str:
    svc = VisualProviderService(db)
    rid = svc.create_draft(
        provider_id=provider_id,
        scope_type=scope_type,
        scope_id=scope_id,
        provider_type="managed",
        adapter_name="fake",
        config={"endpoint": "http://fake"},
        capabilities=caps,
    )
    svc.activate(rid)
    return rid


def test_route_to_capable_provider():
    db = Database()
    db.init_schema()
    _setup(db)
    _create_provider(db, "p1", "global", "*", {"text_to_image": True})
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    result = rs.route(task_id)
    assert result["routed"] is True
    assert result["provider_id"] == "p1"
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "READY"
    assert contract["visual_stage"] == "ROUTED"
    db.close()


def test_route_blocked_when_no_provider():
    db = Database()
    db.init_schema()
    _setup(db)
    # No provider registered
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="continuity_edit",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    result = rs.route(task_id)
    assert result["routed"] is False
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    assert task["status"] == "WAITING_ASSETS"
    db.close()


def test_route_project_beats_global():
    db = Database()
    db.init_schema()
    _setup(db)
    _create_provider(db, "p-global", "global", "*", {"text_to_image": True})
    _create_provider(db, "p-proj", "project", "proj1", {"text_to_image": True})
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="scene_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    result = rs.route(task_id)
    assert result["provider_id"] == "p-proj"
    db.close()


def test_route_requires_matching_capability():
    db = Database()
    db.init_schema()
    _setup(db)
    # Provider only supports text_to_image, task needs image_edit
    _create_provider(db, "p1", "global", "*", {"text_to_image": True})
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="continuity_edit",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    result = rs.route(task_id)
    assert result["routed"] is False
    db.close()


def test_dry_run_does_not_modify_state():
    db = Database()
    db.init_schema()
    _setup(db)
    _create_provider(db, "p1", "global", "*", {"text_to_image": True})
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    result = rs.dry_run(
        project_id="proj1",
        purpose="character_reference",
        required_capabilities=["text_to_image"],
    )
    assert result["routed"] is True
    assert result["provider_id"] == "p1"
    # Task state should be unchanged (still PLANNED + UNROUTED)
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "PLANNED"
    assert contract["visual_stage"] == "UNROUTED"
    db.close()


def test_route_writes_snapshot():
    db = Database()
    db.init_schema()
    _setup(db)
    _create_provider(db, "p1", "global", "*", {"text_to_image": True})
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualRoutingService(db)
    rs.route(task_id)
    contract = db.fetchone(
        "SELECT routing_snapshot_json FROM visual_task_contracts WHERE task_id = ?",
        (task_id,),
    )
    assert contract["routing_snapshot_json"] is not None
    import json
    snapshot = json.loads(contract["routing_snapshot_json"])
    assert snapshot["provider_id"] == "p1"
    assert "routed_at" in snapshot
    db.close()
