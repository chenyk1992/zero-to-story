from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from lfo.canvas.server import CanvasHTTPServer
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

PROJECT = Path(__file__).resolve().parents[2]
INTERRUPT = PROJECT / ".agents/skills/canvas-workspace/scripts/continuation_interrupt.py"


@pytest.fixture
def continuation_server(tmp_path):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.discovery.write_text(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{server.server_address[1]}",
                "project_root": str(PROJECT),
            }
        ),
        encoding="utf-8",
    )
    try:
        yield service, settings
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        service.close()


def _interrupt(settings, event):
    result = subprocess.run(
        [sys.executable, str(INTERRUPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        cwd=PROJECT,
        env={
            **os.environ,
            "LFO_CANVAS_DATA": str(settings.data_dir),
            "LFO_WORKSPACE": str(settings.media_root),
            "PYTHONIOENCODING": "utf-8",
        },
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_project_hooks_reach_same_plan_through_real_mcp_and_interrupt(continuation_server):
    """Use configured hook inputs and real transports; never start a media worker."""
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    service, settings = continuation_server
    config = json.loads((PROJECT / ".codex/hooks.json").read_text(encoding="utf-8"))
    session_id = "integration-parent"
    agent_id = "integration-child"
    host_fields = {
        "session_id": session_id,
        "agent_id": agent_id,
        "turn_id": "integration-turn",
    }

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "lfo.canvas",
                "--project",
                str(PROJECT),
                "--data-dir",
                str(settings.data_dir),
                "--media-root",
                str(settings.media_root),
                "mcp",
            ],
            env={**os.environ, "PYTHONPATH": str(PROJECT / "src")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()

                async def call(tool, arguments):
                    response = await client.call_tool(tool, arguments)
                    assert not response.isError, response.content
                    assert response.structuredContent is not None
                    return response.structuredContent

                async def hook(event):
                    handler = config["hooks"][event][0]["hooks"][0]
                    assert handler["type"] == "mcp_tool"
                    assert handler["server"] == "story_canvas"
                    arguments = {
                        key: host_fields[value[2:-1]] if value.startswith("${") else value
                        for key, value in handler["input"].items()
                    }
                    return await call(handler["tool"], arguments)

                assert (await hook("Stop")).get("decision") != "block"
                created = await call("canvas_create", {"name": "隔离接续验证"})
                canvas = await call(
                    "canvas_edit",
                    {
                        "canvas_id": created["id"],
                        "version": created["version"],
                        "operations": [
                            {
                                "op": "add_node",
                                "node": {
                                    "id": "image-one",
                                    "type": "image",
                                    "position": {"x": 0, "y": 0},
                                    "data": {
                                        "prompt": "测试图",
                                        "provider": "codex-imagegen",
                                        "mode": "create",
                                    },
                                },
                            }
                        ],
                    },
                )
                plan = await call(
                    "canvas_continuation_configure",
                    {
                        "canvas_id": canvas["id"],
                        "canvas_version": canvas["version"],
                        "session_id": session_id,
                        "node_ids": ["image-one"],
                        "authorization": "仅测试交接状态，不生成媒体。",
                    },
                )
                plan = await call(
                    "canvas_continuation_unit",
                    {
                        "continuation_id": plan["id"],
                        "revision": plan["revision"],
                        "unit_id": "unit-one",
                        "agent_id": agent_id,
                        "turn_id": host_fields["turn_id"],
                        "node_id": "image-one",
                        "state": "dispatched",
                    },
                )
                assert (await hook("Stop"))["decision"] == "block"
                received = await hook("SubagentStop")
                assert received.get("decision") != "block"
                plans = (
                    await call(
                        "canvas_continuation_read",
                        {
                            "session_id": session_id,
                            "canvas_id": canvas["id"],
                        },
                    )
                )["plans"]
                ready = plans[0]
                assert ready["units"][0]["state"] == "result_ready"
                assert ready["summary"]["status"] == "actionable"
                assert (await hook("Stop"))["decision"] == "block"
                # A child completion must not wake a paused plan or clear the result.
                response = _interrupt(
                    settings,
                    {
                        "hook_event_name": "Interrupt",
                        "session_id": session_id,
                        "turn_id": "integration-turn",
                    },
                )
                assert response.get("decision") != "block"
                await hook("SubagentStop")
                await hook("SessionStart")
                paused = (
                    await call(
                        "canvas_continuation_read",
                        {
                            "session_id": session_id,
                        },
                    )
                )["plans"][0]
                assert paused["state"] == "paused"
                assert paused["units"][0]["state"] == "result_ready"
                assert (await hook("Stop")).get("decision") != "block"
                assert service.store.list_runs() == []

    anyio.run(exercise)


def test_interrupt_adapter_offline_is_visible_and_does_not_start_service(tmp_path):
    settings = CanvasSettings(PROJECT, tmp_path / "offline", tmp_path / "media", 0)
    result = _interrupt(
        settings,
        {
            "hook_event_name": "Interrupt",
            "session_id": "parent",
        },
    )
    assert "暂停记录未送达" in result["systemMessage"]
    assert not settings.data_dir.exists()
    assert not settings.media_root.exists()


def test_interrupt_adapter_ignores_unrelated_events_without_discovery(tmp_path):
    settings = CanvasSettings(PROJECT, tmp_path / "offline", tmp_path / "media", 0)
    assert _interrupt(settings, {"hook_event_name": "Stop", "session_id": "parent"}) == {}
    assert not settings.data_dir.exists()


def test_interrupt_adapter_refuses_external_discovery(tmp_path):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    settings.data_dir.mkdir()
    settings.discovery.write_text(
        json.dumps(
            {
                "url": "https://example.com",
                "project_root": str(PROJECT),
            }
        ),
        encoding="utf-8",
    )
    result = _interrupt(settings, {"hook_event_name": "Interrupt", "session_id": "parent"})
    assert "暂停记录未送达" in result["systemMessage"]
    assert not settings.database.exists()


def test_acceptance_does_not_clear_an_unhandled_child_result_or_rerun_an_edited_draft():
    from lfo.canvas.continuation import build_continuation_summary

    canvas = {
        "id": "canvas",
        "graph": {
            "nodes": [
                {
                    "id": "shot",
                    "type": "video",
                    "position": {"x": 0, "y": 0},
                    "data": {"prompt": "later draft"},
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": [],
        },
    }
    plan = {
        "id": "plan",
        "canvas_id": "canvas",
        "session_id": "session",
        "state": "active",
        "node_ids": ["shot"],
        "units": [
            {
                "unit_id": "child-result",
                "node_id": "shot",
                "state": "result_ready",
            }
        ],
    }
    runs = [
        {
            "id": "accepted-run",
            "node_id": "shot",
            "status": "succeeded",
            "review": {"decision": "ACCEPT"},
            "snapshot": {"prompt": "frozen prompt"},
        }
    ]

    def readiness(_):
        pytest.fail("An edited draft must not cause re-execution of an accepted shot")

    pending = build_continuation_summary(plan, canvas, runs, readiness)
    assert pending["status"] == "actionable"
    assert pending["allow_stop"] is False
    assert pending["actions"][0]["type"] == "handle_unit"
    plan["units"][0]["state"] = "handled"
    complete = build_continuation_summary(plan, canvas, runs, readiness)
    assert complete["status"] == "complete"
    assert complete["allow_stop"] is True
    assert complete["actions"] == []


def test_concurrent_plan_writes_do_not_allow_an_actionable_stop(continuation_server, monkeypatch):
    from lfo.canvas.store import ContinuationRevisionError

    service, _ = continuation_server
    canvas = service.store.create_canvas(
        "concurrency",
        {
            "nodes": [
                {
                    "id": "shot",
                    "type": "image",
                    "position": {"x": 0, "y": 0},
                    "data": {"prompt": "test"},
                }
            ],
            "edges": [],
        },
    )
    service.configure_continuation(
        canvas["id"], "session", ["shot"], "test only", canvas["version"]
    )

    def conflict(plan_id, revision, _):
        raise ContinuationRevisionError(plan_id, revision, revision + 1)

    monkeypatch.setattr(service.store, "record_continuation_stop", conflict)
    assert service.continuation_hook("session", "Stop")["decision"] == "block"
    assert service.store.list_runs() == []


def test_child_turn_is_bound_across_plans_and_units_cannot_move_backwards(continuation_server):
    from lfo.canvas.store import CanvasStoreError

    service, _ = continuation_server
    plans = []
    for name in ("first", "second"):
        canvas = service.store.create_canvas(
            name,
            {
                "nodes": [
                    {
                        "id": "shot",
                        "type": "image",
                        "position": {"x": 0, "y": 0},
                        "data": {},
                    }
                ],
                "edges": [],
            },
        )
        plan = service.configure_continuation(
            canvas["id"], "session", ["shot"], "test only", canvas["version"]
        )
        plans.append(
            service.update_continuation_unit(
                plan["id"],
                plan["revision"],
                name,
                "dispatched",
                agent_id="child",
                turn_id=name + "-turn",
                node_id="shot",
            )
        )
    service.continuation_hook("session", "SubagentStop", "child", "first-turn")
    first = service.store.get_continuation(plans[0]["id"])
    second = service.store.get_continuation(plans[1]["id"])
    assert first["units"][0]["state"] == "result_ready"
    assert second["units"][0]["state"] == "dispatched"
    with pytest.raises(CanvasStoreError, match="immutable"):
        service.update_continuation_unit(
            first["id"], first["revision"], "first", "result_ready", agent_id="another"
        )
    with pytest.raises(CanvasStoreError, match="already belongs"):
        service.update_continuation_unit(
            second["id"],
            second["revision"],
            "duplicate",
            "dispatched",
            agent_id="child",
            turn_id="first-turn",
        )
    handled = service.update_continuation_unit(first["id"], first["revision"], "first", "handled")
    with pytest.raises(CanvasStoreError, match="backwards"):
        service.update_continuation_unit(handled["id"], handled["revision"], "first", "dispatched")
    # A delayed old event cannot finish an unbound reuse of this child.
    current = service.update_continuation_unit(
        handled["id"],
        handled["revision"],
        "unbound",
        "dispatched",
        agent_id="child",
        node_id="shot",
    )
    service.continuation_hook("session", "SubagentStop", "child", "late-unseen-turn")
    assert service.store.get_continuation(current["id"])["units"][-1]["state"] == "dispatched"


def test_status_notes_do_not_reset_the_no_progress_limit(continuation_server):
    service, _ = continuation_server
    canvas = service.store.create_canvas(
        "notes",
        {
            "nodes": [
                {
                    "id": "shot",
                    "type": "image",
                    "position": {"x": 0, "y": 0},
                    "data": {},
                }
            ],
            "edges": [],
        },
    )
    plan = service.configure_continuation(
        canvas["id"], "session", ["shot"], "test only", canvas["version"]
    )
    service.update_continuation_unit(
        plan["id"], plan["revision"], "unit", "dispatched", agent_id="child", node_id="shot"
    )
    for _ in range(2):
        assert service.continuation_hook("session", "Stop")["decision"] == "block"
    current = service.store.get_continuation(plan["id"])
    service.update_continuation_unit(
        current["id"], current["revision"], "unit", "dispatched", reason="仍在等待"
    )
    assert service.continuation_hook("session", "Stop").get("decision") != "block"
    assert service.read_continuations(session_id="session")["plans"][0]["summary"]["stalled"]


def test_an_explicit_run_binding_cannot_be_replaced_by_another_runs_acceptance():
    from lfo.canvas.continuation import build_continuation_summary

    canvas = {
        "id": "canvas",
        "graph": {
            "nodes": [
                {
                    "id": "shot",
                    "type": "video",
                    "position": {"x": 0, "y": 0},
                    "data": {},
                }
            ],
            "edges": [],
        },
    }
    plan = {
        "state": "active",
        "node_ids": ["shot"],
        "units": [
            {
                "unit_id": "original",
                "node_id": "shot",
                "run_id": "original-run",
                "state": "handled",
            }
        ],
    }
    runs = [
        {"id": "original-run", "node_id": "shot", "status": "failed", "created_at": "2026-01-01"},
        {
            "id": "another-run",
            "node_id": "shot",
            "status": "succeeded",
            "review": {"decision": "ACCEPT"},
            "created_at": "2026-01-02",
        },
    ]
    summary = build_continuation_summary(plan, canvas, runs, lambda _: {"ready": True})
    assert summary["status"] == "blocked"
    assert summary["nodes"][0]["run_id"] == "original-run"
    assert summary["actions"] == []


def test_an_ordinary_last_frame_reference_does_not_invent_an_acceptance_gate():
    from lfo.canvas.continuation import build_continuation_summary

    canvas = {
        "id": "canvas",
        "graph": {
            "nodes": [
                {"id": "reference", "type": "image", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "shot", "type": "video", "position": {"x": 1, "y": 0}, "data": {}},
            ],
            "edges": [
                {
                    "id": "input",
                    "source": "reference",
                    "target": "shot",
                    "sourceHandle": "output",
                    "targetHandle": "last_frame",
                }
            ],
        },
    }
    summary = build_continuation_summary(
        {"state": "active", "node_ids": ["shot"]}, canvas, [], lambda _: {"ready": True}
    )
    assert summary["status"] == "actionable"
    assert summary["blocked_items"] == []
