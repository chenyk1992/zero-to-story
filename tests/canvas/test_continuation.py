"""Bounded persistence and inspection checks for canvas continuations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import (
    CanvasStore,
    ContinuationRevisionError,
    ContinuationRevisionRequiredError,
)

PROJECT = Path(__file__).resolve().parents[2]


def _node(node_id: str, node_type: str = "image", *, panel_id: str | None = None) -> dict:
    data = {"prompt": f"prompt-{node_id}", "provider": "test", "mode": "create"}
    if panel_id is not None:
        data["panel_id"] = panel_id
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": 0, "y": 0},
        "data": data,
    }


def _graph(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    return {
        "nodes": nodes,
        "edges": edges or [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }


@pytest.fixture
def service(tmp_path: Path):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    instance = CanvasService(settings, start_worker=False)
    yield instance
    instance.close()


def _ready(instance: CanvasService) -> None:
    # The continuation check is meant to reuse the existing read-only
    # readiness result; these tests focus on the continuation state machine.
    instance.readiness = lambda _canvas_id, _node_id: {"ready": True}  # type: ignore[method-assign]


def _configure(
    instance: CanvasService, canvas: dict, nodes: list[str], session: str = "sess"
) -> dict:
    _ready(instance)
    return instance.configure_continuation(
        canvas["id"], session, nodes, "用户明确授权当前范围", canvas["version"]
    )


def test_configuration_is_opt_in_persistent_and_revision_cas(tmp_path: Path) -> None:
    db_path = tmp_path / "canvas.sqlite3"
    with CanvasStore(db_path) as store:
        canvas = store.create_canvas("demo", _graph([_node("a"), _node("b")]))
        first = store.configure_continuation(
            canvas["id"], "host-session", ["a"], "原始授权文本", canvas["version"]
        )
        assert first["revision"] == 1
        assert first["state"] == "active"
        assert store.list_continuations("other-session") == []

        identical = store.configure_continuation(
            canvas["id"], "host-session", ["a"], "原始授权文本", canvas["version"]
        )
        assert identical["id"] == first["id"]
        assert identical["revision"] == first["revision"]

        with pytest.raises(ContinuationRevisionRequiredError):
            store.configure_continuation(
                canvas["id"], "host-session", ["a", "b"], "原始授权文本", canvas["version"]
            )
        changed = store.configure_continuation(
            canvas["id"],
            "host-session",
            ["a", "b"],
            "更新后的授权文本",
            canvas["version"],
            revision=first["revision"],
        )
        assert changed["revision"] == 2
        with pytest.raises(ContinuationRevisionError):
            store.update_continuation_state(changed["id"], first["revision"], "paused", "暂停")

    with CanvasStore(db_path) as reopened:
        restored = reopened.get_continuation(first["id"])
        assert restored["node_ids"] == ["a", "b"]
        assert restored["authorization"] == "更新后的授权文本"
        assert restored["revision"] == 2
        assert restored["units"] == []


def test_read_summary_keeps_independent_ready_node_actionable(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("ready"), _node("blocked")]))
    plan = _configure(service, canvas, ["ready", "blocked"])
    failed = service.store.create_run(
        canvas["id"],
        "blocked",
        canvas["version"],
        "failed-request",
        {"node_id": "blocked", "node_type": "image"},
    )
    service.store.update_run(failed["id"], status="failed", error="provider failed")
    read = service.read_continuations(session_id="sess")["plans"][0]
    summary = read["summary"]
    assert summary["status"] == "actionable"
    assert summary["allow_stop"] is False
    assert any(
        action["type"] == "execute_after_authorization_check" and action["node_id"] == "ready"
        for action in summary["actions"]
    )
    assert any(item["node_id"] == "blocked" for item in summary["blocked_items"])
    assert plan["id"] == read["id"]


def test_waiting_precedes_local_blocked_item(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("running"), _node("failed")]))
    _configure(service, canvas, ["running", "failed"])
    running = service.store.create_run(
        canvas["id"],
        "running",
        canvas["version"],
        "running-request",
        {"node_id": "running", "node_type": "image"},
        status="running",
    )
    failed = service.store.create_run(
        canvas["id"],
        "failed",
        canvas["version"],
        "failed-request",
        {"node_id": "failed", "node_type": "image"},
        status="failed",
    )
    assert running["status"] == "running"
    assert failed["status"] == "failed"
    summary = service.read_continuations(session_id="sess")["plans"][0]["summary"]
    assert summary["status"] == "waiting"
    assert summary["allow_stop"] is False
    assert "heartbeat" in summary["reason"]


def test_pending_agent_is_actionable_claim_step(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("pending")]))
    _configure(service, canvas, ["pending"])
    run = service.store.create_run(
        canvas["id"],
        "pending",
        canvas["version"],
        "pending-request",
        {"node_id": "pending", "node_type": "image"},
        status="pending_agent",
    )
    summary = service.read_continuations(session_id="sess")["plans"][0]["summary"]
    assert summary["status"] == "actionable"
    assert summary["allow_stop"] is False
    assert summary["actions"] == [
        {
            "type": "claim_agent",
            "node_id": "pending",
            "run_id": run["id"],
            "reason": "等待具备当前能力的宿主领取 pending_agent 单元",
        }
    ]


def test_result_ready_is_first_action_and_subagent_stop_is_bound(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("a")]))
    plan = _configure(service, canvas, ["a"])
    dispatched = service.update_continuation_unit(
        plan["id"],
        plan["revision"],
        "unit-a",
        "dispatched",
        agent_id="agent-a",
        node_id="a",
        turn_id="turn-1",
    )
    assert dispatched["revision"] == 2
    before = service.store.get_continuation(plan["id"])
    assert service.continuation_hook("sess", "SubagentStop") == {}
    assert service.store.get_continuation(plan["id"])["revision"] == before["revision"]
    assert service.store.get_continuation(plan["id"])["units"][0]["state"] == "dispatched"

    assert service.continuation_hook("sess", "SubagentStop", "agent-a", "turn-1") == {}
    ready = service.read_continuations(session_id="sess")["plans"][0]
    assert ready["units"][0]["state"] == "result_ready"
    assert ready["summary"]["status"] == "actionable"
    assert ready["summary"]["actions"][0]["type"] == "handle_unit"

    handled = service.update_continuation_unit(ready["id"], ready["revision"], "unit-a", "handled")
    second = service.update_continuation_unit(
        handled["id"],
        handled["revision"],
        "unit-b",
        "dispatched",
        agent_id="agent-a",
        node_id="a",
        turn_id="turn-2",
    )
    # A lifecycle event without its turn binding is only a hint.  It must not
    # advance even the unique dispatched unit or erase the stop ledger.
    service.continuation_hook("sess", "SubagentStop", "agent-a")
    assert service.store.get_continuation(plan["id"])["units"][-1]["state"] == "dispatched"
    # Replaying the old turn must not finish the newly dispatched unit.
    service.continuation_hook("sess", "SubagentStop", "agent-a", "turn-1")
    assert service.store.get_continuation(plan["id"])["units"][-1]["state"] == "dispatched"
    service.continuation_hook("sess", "SubagentStop", "agent-a", "turn-2")
    assert service.store.get_continuation(plan["id"])["units"][-1]["state"] == "result_ready"

    # Two outstanding units with one agent are ambiguous without a turn; no
    # unit is guessed or advanced.
    current = service.store.get_continuation(plan["id"])
    third = service.update_continuation_unit(
        current["id"], current["revision"], "unit-c", "dispatched", agent_id="agent-a", node_id="a"
    )
    fourth = service.update_continuation_unit(
        third["id"], third["revision"], "unit-d", "dispatched", agent_id="agent-a", node_id="a"
    )
    service.continuation_hook("sess", "SubagentStop", "agent-a")
    assert all(
        unit["state"] == "dispatched"
        for unit in service.store.get_continuation(plan["id"])["units"][-2:]
    )
    assert fourth["revision"] == service.store.get_continuation(plan["id"])["revision"]


def test_explicit_block_prevents_review_but_accept_remains_complete(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("a")]))
    plan = _configure(service, canvas, ["a"])
    succeeded = service.store.create_run(
        canvas["id"],
        "a",
        canvas["version"],
        "accepted-request",
        {"node_id": "a", "node_type": "image"},
        status="succeeded",
    )
    blocked = service.update_continuation_unit(
        plan["id"],
        plan["revision"],
        "review-tool",
        "blocked",
        node_id="a",
        reason="审片工具不可用",
    )
    blocked_summary = service.read_continuations(session_id="sess")["plans"][0]["summary"]
    assert blocked_summary["status"] == "blocked"
    assert blocked_summary["nodes"][0]["state"] == "blocked"
    assert not any(
        action.get("node_id") == "a"
        and action.get("type") in {"review", "prepare", "execute_after_authorization_check"}
        for action in blocked_summary["actions"]
    )

    review_owner = service.store.claim_review(succeeded["id"])
    accepted = service.store.review_run(
        succeeded["id"],
        {
            "decision": "ACCEPT",
            "output_path": "accepted.png",
            "output_sha256": "a" * 64,
            "evidence": ["checked"],
            "end_state": {},
            "unverified": [],
        },
        owner_token=review_owner,
    )
    assert accepted["status"] == "succeeded"
    accepted_summary = service.read_continuations(session_id="sess")["plans"][0]["summary"]
    node = next(item for item in accepted_summary["nodes"] if item["node_id"] == "a")
    assert node["state"] == "complete"
    assert any(item.get("unit_id") == "review-tool" for item in accepted_summary["blocked_items"])


def test_continuation_scope_rejects_non_media_nodes(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("doc", "document")]))
    from lfo.canvas.store import CanvasStoreError

    with pytest.raises(CanvasStoreError, match="only image or video"):
        service.configure_continuation(
            canvas["id"], "sess", ["doc"], "用户明确授权当前范围", canvas["version"]
        )


def test_tail_acceptance_dependency_uses_explicit_panel_id(service: CanvasService) -> None:
    source = _node("source-node", "video", panel_id="P001")
    target = _node("target-node", "video")
    target["data"]["planned_inputs"] = {"first_frame": "tail:P001"}
    board = _node("board-node", "image", panel_id="P001")
    canvas = service.store.create_canvas("demo", _graph([source, target, board]))
    plan = _configure(service, canvas, ["target-node"])
    summary = plan["summary"]
    assert summary["status"] == "blocked"
    assert summary["blocked_items"][0]["source_node_id"] == "source-node"
    assert "ACCEPT" in summary["blocked_items"][0]["reason"]


def test_interrupt_pauses_and_session_start_is_minimal(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("a")]))
    plan = _configure(service, canvas, ["a"])
    context = service.continuation_hook("sess", "SessionStart")
    text = context["hookSpecificOutput"]["additionalContext"]
    decoded = json.loads(text)
    assert decoded["session_id"] == "sess"
    assert decoded["plans"] == [{"id": plan["id"], "state": "active"}]
    assert "用户明确授权当前范围" not in text
    assert service.continuation_hook("unbound", "Interrupt") == {}
    paused = service.continuation_hook("sess", "Interrupt")
    assert "systemMessage" in paused
    current = service.read_continuations(session_id="sess")["plans"][0]
    assert current["state"] == "paused"
    assert current["summary"]["status"] == "paused"
    assert current["summary"]["allow_stop"] is True


def test_stop_is_bounded_and_get_does_not_increment(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("a")]))
    plan = _configure(service, canvas, ["a"])
    first = service.continuation_hook("sess", "Stop")
    assert first["decision"] == "block"
    after_first = service.store.get_continuation(plan["id"])
    read = service.read_continuations(session_id="sess")["plans"][0]
    assert read["summary"]["stop_attempts"] == 1
    assert service.store.get_continuation(plan["id"])["revision"] == after_first["revision"]
    second = service.continuation_hook("sess", "Stop")
    assert second["decision"] == "block"
    third = service.continuation_hook("sess", "Stop")
    assert "systemMessage" in third
    stalled = service.read_continuations(session_id="sess")["plans"][0]
    assert stalled["summary"]["stalled"] is True
    assert stalled["summary"]["stop_attempts"] == 3
    assert service.store.list_runs(canvas["id"]) == []


def test_failed_existing_run_is_not_retried_by_continuation(service: CanvasService) -> None:
    canvas = service.store.create_canvas("demo", _graph([_node("a")]))
    _configure(service, canvas, ["a"])
    run = service.store.create_run(
        canvas["id"],
        "a",
        canvas["version"],
        "failed-request",
        {"node_id": "a", "node_type": "image"},
        status="failed",
    )
    summary = service.read_continuations(session_id="sess")["plans"][0]["summary"]
    assert summary["status"] == "blocked"
    assert not any(
        action["type"] == "execute_after_authorization_check" for action in summary["actions"]
    )
    assert service.store.get_run(run["id"])["status"] == "failed"
