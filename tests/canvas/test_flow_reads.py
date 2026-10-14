from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from lfo.canvas.continuation import build_continuation_summary
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

PROJECT = Path(__file__).resolve().parents[2]


def test_batched_read_and_continuation_reuse_one_canvas_and_run_list(tmp_path, monkeypatch):
    service = CanvasService(CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False)
    nodes = [{"id": str(i), "type": "image", "position": {"x": i, "y": 0}, "data": {
        "provider": "codex-imagegen", "model": "image_gen", "mode": "create", "prompt": "test"}}
        for i in range(10)]
    canvas = service.store.create_canvas("batch", {"nodes": nodes, "edges": []})
    get_canvas = Mock(wraps=service.store.get_canvas)
    list_runs = Mock(wraps=service.store.list_runs)
    monkeypatch.setattr(service.store, "get_canvas", get_canvas)
    monkeypatch.setattr(service.store, "list_runs", list_runs)
    try:
        packet = service.read_canvas(canvas["id"], node_ids=[n["id"] for n in nodes])
        assert all(item["readiness"]["ready"] for item in packet["production"].values())
        assert get_canvas.call_count == list_runs.call_count == 1
        get_canvas.reset_mock()
        list_runs.reset_mock()
        summary = service._continuation_summary({"id": "plan", "canvas_id": canvas["id"],
            "session_id": "session", "state": "active", "node_ids": [n["id"] for n in nodes], "units": []})
        assert len(summary["actions"]) == 10
        assert get_canvas.call_count == list_runs.call_count == 1
        # Store history is oldest-first; never hand off the first historical attempt.
        first = service.store.create_run(canvas["id"], "0", canvas["version"], "first",
                                        {"node_type": "image"}, status="failed")
        second = service.store.create_run(canvas["id"], "0", canvas["version"], "second",
                                         {"node_type": "image"}, status="failed")
        assert first["id"] != second["id"]
        assert service.read_canvas(canvas["id"], node_id="0")["production"]["0"]["latest_run"]["id"] == second["id"]
        # Edits are re-read rather than trusting an old ready flag.
        changed = service.store.get_canvas(canvas["id"])
        changed["graph"]["nodes"][0]["data"]["prompt"] = ""
        service.store.save_canvas(canvas["id"], changed["version"], changed["graph"])
        assert not service.read_canvas(canvas["id"], node_id="0")["production"]["0"]["readiness"]["ready"]
    finally:
        service.close()


@pytest.mark.parametrize(("old_status", "old_review", "replacement_review", "expected"), [
    ("succeeded", "REJECT", "ACCEPT", "complete"),
    ("succeeded", "INCONCLUSIVE", "ACCEPT", "complete"),
    ("succeeded", "REJECT", "INCONCLUSIVE", "blocked"),
    ("unknown", None, "ACCEPT", "blocked"),
    ("running", None, "ACCEPT", "waiting"),
])
def test_explicit_accepted_replacement_only_retires_resolved_old_candidates(
    old_status, old_review, replacement_review, expected,
):
    nodes = [{"id": name, "type": "video", "position": {"x": i, "y": 0},
              "data": {"superseded_by": "new"} if name == "old" else {}}
             for i, name in enumerate(("old", "new"))]
    runs = [{"id": name, "node_id": name, "status": status,
             "review": {"decision": review} if review else None}
            for name, status, review in (("old", old_status, old_review),
                                        ("new", "succeeded", replacement_review))]
    before = json.dumps(runs, sort_keys=True)
    summary = build_continuation_summary({"node_ids": ["old", "new"], "state": "active"},
        {"id": "c", "graph": {"nodes": nodes, "edges": []}}, runs, lambda _: {"ready": True})
    assert summary["nodes"][0]["state"] == expected
    assert json.dumps(runs, sort_keys=True) == before
    if expected == "complete":
        assert summary["status"] == "complete"
        assert summary["nodes"][0]["review"] == old_review
