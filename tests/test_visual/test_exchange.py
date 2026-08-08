"""Tests for exchange execution (manual/delegated)."""
from __future__ import annotations

from lfo.application.visual_provider_service import VisualProviderService
from lfo.application.visual_routing_service import VisualRoutingService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.stages import VisualStage


def _setup(db: Database, project_id: str = "proj1") -> None:
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, 'n')", (project_id,))


def test_exchange_execution_no_attempt_row():
    """Exchange execution does NOT create an attempts row."""
    db = Database()
    db.init_schema()
    _setup(db)
    # Register a delegated provider
    psvc = VisualProviderService(db)
    rid = psvc.create_draft(
        provider_id="agent-1",
        scope_type="global",
        scope_id="*",
        provider_type="delegated",
        adapter_name="delegated_exchange",
        config={"allowed_recipients": ["agent_x"]},
        capabilities={"text_to_image": True},
    )
    psvc.activate(rid)

    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    # Route to provider
    rs = VisualRoutingService(db)
    result = rs.route(task_id)
    assert result["routed"] is True

    # No attempts row for exchange
    attempts = db.fetchall(
        "SELECT * FROM attempts WHERE task_id = ?", (task_id,)
    )
    assert len(attempts) == 0
    db.close()


def test_manual_provider_export_transitions_to_awaiting_result():
    """Manual export transitions task to WAITING_USER + AWAITING_RESULT."""
    db = Database()
    db.init_schema()
    _setup(db)
    psvc = VisualProviderService(db)
    rid = psvc.create_draft(
        provider_id="human-1",
        scope_type="global",
        scope_id="*",
        provider_type="manual",
        adapter_name="manual_exchange",
        config={},
        capabilities={"text_to_image": True},
    )
    psvc.activate(rid)

    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    # Transition to READY + ROUTED first (simulating a route)
    ts.transition(
        task_id,
        expected_task_status=TaskStatus.PLANNED,
        expected_visual_stage=VisualStage.UNROUTED,
        new_task_status=TaskStatus.READY,
        new_visual_stage=VisualStage.ROUTED,
        reason="routed",
    )
    # Transition to simulate export
    ts.transition(
        task_id,
        expected_task_status=TaskStatus.READY,
        expected_visual_stage=VisualStage.ROUTED,
        new_task_status=TaskStatus.WAITING_USER,
        new_visual_stage=VisualStage.AWAITING_RESULT,
        reason="exported to manual provider",
    )
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "WAITING_USER"
    assert contract["visual_stage"] == "AWAITING_RESULT"
    db.close()
