from __future__ import annotations

import copy
import hashlib
import json
import threading
from pathlib import Path

import pytest

from lfo.canvas.client import CanvasClient
from lfo.canvas.graph import CanvasError
from lfo.canvas.server import CanvasHTTPServer
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(CanvasSettings(Path(__file__).resolve().parents[2],
                                          tmp_path / "state", tmp_path / "media", 0), start_worker=False)
    yield instance
    instance.close()


def graph():
    return {"nodes": [{"id": "image", "type": "image", "position": {"x": 0, "y": 0},
                       "data": {"prompt": "night", "provider": "codex-imagegen",
                                "model": "image_gen", "mode": "create"}}], "edges": []}


def test_preflight_failure_prevents_request_and_readiness_is_read_only(service, monkeypatch):
    canvas = service.store.create_canvas("MV", graph())
    monkeypatch.setattr("lfo.canvas.service.inspect_mv_panel", lambda *args, **kwargs: {
        "applicable": True, "ready": False, "issues": [{"code": "text_missing", "message": "缺少歌词图"}]})
    ready = service.readiness(canvas["id"], "image")
    assert not ready["ready"] and ready["issues"][0]["code"] == "text_missing"
    with pytest.raises(CanvasError) as error:
        service.confirm(canvas["id"], "image", canvas["version"], "blocked")
    assert error.value.code == "mv_preflight_failed"
    assert service.store.list_runs(canvas["id"]) == []
    assert service.store.get_canvas(canvas["id"]) == canvas


def test_context_frozen_and_metadata_drift_invalidates_run(service, monkeypatch):
    canvas = service.store.create_canvas("MV", graph())
    context = {"declaration_fingerprint": "original", "media_versions": []}
    monkeypatch.setattr("lfo.canvas.service.inspect_mv_panel", lambda *args, **kwargs: {
        "applicable": True, "ready": True, "issues": [], "context": context})
    monkeypatch.setattr("lfo.canvas.service.mv_metadata_fingerprint", lambda *args: "original")
    run = service.confirm(canvas["id"], "image", canvas["version"], "valid")
    context["declaration_fingerprint"] = "mutated"
    assert run["snapshot"]["production_context"]["declaration_fingerprint"] == "original"
    assert service.runs(canvas["id"])[0]["matches_current"] is True
    monkeypatch.setattr("lfo.canvas.service.mv_metadata_fingerprint", lambda *args: "changed")
    assert service.runs(canvas["id"])[0]["matches_current"] is False
    assert service.store.get_run(run["id"])["snapshot"]["production_context"]["declaration_fingerprint"] == "original"


def test_metrics_paginate_events_without_writes(service, monkeypatch):
    canvas = service.store.create_canvas("MV", graph())
    events = [{"id": i} for i in range(1, 206)]
    cursors = []
    def read_events(*, after, canvas_id, limit):
        cursors.append(after)
        assert canvas_id == canvas["id"] and limit == 100
        return [event for event in events if event["id"] > after][:limit]
    monkeypatch.setattr(service.store, "list_events", read_events)
    def summarize(runs, passed_events, **kwargs):
        assert passed_events == events
        return {"events_seen": len(passed_events)}
    monkeypatch.setattr("lfo.canvas.service.summarize_production", summarize)
    assert service.production_summary(canvas["id"])["events_seen"] == 205
    assert cursors == [0, 100, 200, 205]
    assert service.store.get_canvas(canvas["id"]) == canvas


def test_metrics_cover_whole_canvas_while_scope_note_identifies_latest_plan(service, monkeypatch):
    canvas = service.store.create_canvas("MV", graph())
    runs = [
        {"id": "r1", "canvas_id": canvas["id"], "node_id": "one", "status": "running"},
        {"id": "r2", "canvas_id": canvas["id"], "node_id": "two", "status": "failed"},
    ]
    monkeypatch.setattr(service.store, "list_runs", lambda _canvas_id: runs)
    monkeypatch.setattr(service.store, "list_continuations", lambda **_kwargs: [{
        "id": "latest", "node_ids": ["one"], "state": "paused", "pause_reason": "等待确认",
        "updated_at": "2026-09-30T10:00:00Z",
    }])

    summary = service.production_summary(canvas["id"])

    assert summary["scope_node_ids"] is None
    assert summary["run_counts"]["total"]["value"] == 2
    assert summary["run_counts"]["by_status"]["running"]["value"] == 1
    assert summary["run_counts"]["by_status"]["failed"]["value"] == 1
    assert summary["continuation"]["state"] == "paused"
    assert "整张画布" in summary["scope_note"]
    assert "最近更新的计划" in summary["scope_note"]


@pytest.mark.parametrize("failure", ["outside", "hash", "invalid_json", "missing_hash", "too_large"])
def test_invalid_manifest_keeps_adoption_unknown(service, tmp_path, failure):
    canvas = service.store.create_canvas("MV", graph())
    target = (tmp_path / "external.json") if failure == "outside" else (
        service.settings.media_root / "projects" / canvas["id"] / "edit.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if failure == "invalid_json":
        content = b"broken"
    elif failure == "too_large":
        content = b" " * (4 * 1024 * 1024 + 1)
    else:
        content = json.dumps({"schema": "lfo.mv.edit.v1"}).encode("utf-8")
    target.write_bytes(content)
    updated = copy.deepcopy(canvas["graph"])
    updated["workspace"] = {"production_summary": {"edit_manifest_path": str(target)}}
    if failure == "hash":
        updated["workspace"]["production_summary"]["edit_manifest_sha256"] = "0" * 64
    elif failure != "missing_hash":
        updated["workspace"]["production_summary"]["edit_manifest_sha256"] = hashlib.sha256(content).hexdigest()
    saved = service.store.save_canvas(canvas["id"], canvas["version"], updated)
    summary = service.production_summary(canvas["id"])
    assert summary["manifest_error"]
    assert summary["production_counts"]["accepted_sources"]["state"] == "unknown"
    assert service.store.get_canvas(canvas["id"]) == saved


def test_verified_manifest_is_parsed_from_the_hashed_bytes(service):
    canvas = service.store.create_canvas("MV", graph())
    target = service.settings.media_root / "projects" / canvas["id"] / "edit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({
        "schema": "lfo.mv.edit.v1",
        "canvas_id": canvas["id"],
        "segments": [{"shot_id": "S1", "node_id": "video-1", "run_id": "r1"}],
    }).encode("utf-8")
    target.write_bytes(content)
    updated = copy.deepcopy(canvas["graph"])
    updated["workspace"] = {"production_summary": {
        "edit_manifest_path": str(target),
        "edit_manifest_sha256": hashlib.sha256(content).hexdigest(),
    }}
    service.store.save_canvas(canvas["id"], canvas["version"], updated)

    summary = service.production_summary(canvas["id"])

    assert summary["manifest_error"] is None
    assert summary["production_counts"]["segments"]["value"] == 1


def test_http_production_endpoint_is_read_only(service):
    canvas = service.store.create_canvas("MV", graph())
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = CanvasClient(service.settings, f"http://127.0.0.1:{server.server_address[1]}")
        value = client.request("GET", f"/api/canvases/{canvas['id']}/production")
        assert value["canvas_id"] == canvas["id"]
        assert value["run_counts"]["total"]["value"] == 0
        assert service.store.get_canvas(canvas["id"]) == canvas
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
