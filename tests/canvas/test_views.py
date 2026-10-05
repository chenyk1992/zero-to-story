from __future__ import annotations

import json

import pytest

from lfo.canvas.graph import CanvasError, validate_graph
from lfo.canvas.views import canvas_view, edit_receipt


def canvas(count=150):
    return {"id": "long-story", "name": "长视频", "version": 7, "graph": {
        "nodes": [{"id": f"n-{i}", "type": "video", "position": {"x": i, "y": 0}, "data": {"label": f"镜头{i}", "panel_id": f"P{i:03}", "prompt": "长提示词" * 2000, "content": "原文" * 2000, "history": [{"prompt": "old" * 2000}]}} for i in range(count)],
        "edges": [], "selection": ["n-1"], "workspace": {"story": "片名", "mv_production": {"large": "raw" * 10000}},
    }}


def test_overview_is_paged_and_omits_long_creative_and_history_data():
    original = canvas()
    page = canvas_view(original, view="overview")
    assert page["version"] == 7 and page["selection"] == ["n-1"]
    assert len(page["nodes"]) == 50
    assert page["page"] == {"offset": 0, "limit": 50, "total": 150, "next_offset": 50}
    assert "prompt" not in page["nodes"][0]["data"]
    assert page["nodes"][0]["data"]["prompt_chars"] == len(original["graph"]["nodes"][0]["data"]["prompt"])
    assert "mv_production" not in page["workspace"]
    assert len(json.dumps(page)) < len(json.dumps(original)) / 20
    assert original["graph"]["nodes"][0]["data"]["prompt"] == "长提示词" * 2000


def test_multiple_nodes_include_exact_inputs_once_without_unrelated_content():
    original = canvas(4)
    original["graph"]["edges"] = [
        {"id": "a", "source": "n-0", "target": "n-1", "targetHandle": "reference_image"},
        {"id": "b", "source": "n-0", "target": "n-2", "targetHandle": "reference_image"},
        {"id": "c", "source": "n-3", "target": "n-0", "targetHandle": "related"},
    ]
    result = canvas_view(original, node_ids=["n-1", "n-2"])
    assert [n["id"] for n in result["nodes"]] == ["n-0", "n-1", "n-2"]
    assert [e["id"] for e in result["edges"]] == ["a", "b"]
    assert result["nodes"][0]["data"] == original["graph"]["nodes"][0]["data"]
    assert canvas_view(original, node_id="n-1")["nodes"] == result["nodes"][:2]
    assert canvas_view(original, view="full") == original


def test_paging_requires_same_revision_and_exact_requested_batch():
    original = canvas()
    assert canvas_view(original, view="overview", offset=50, expected_version=7)["nodes"][0]["id"] == "n-50"
    with pytest.raises(CanvasError) as error:
        canvas_view(original, view="overview", offset=50, expected_version=6)
    assert error.value.status == 409
    for kwargs in ({"offset": 50}, {"limit": 101}, {"node_ids": ["missing"]}, {"node_ids": ["n-0"] * 21}, {"node_ids": ["n-0", "n-0"]}, {"node_id": "n-0", "node_ids": ["n-1"]}):
        with pytest.raises(ValueError):
            canvas_view(original, view="overview", **kwargs)


def test_overview_bounds_edges_and_compact_edit_receipt_has_no_graph():
    original = canvas(2)
    original["graph"]["edges"] = [{"id": f"e-{i}", "source": "n-0", "target": "n-1", "targetHandle": "related"} for i in range(250)]
    result = canvas_view(original, view="overview")
    assert len(result["edges"]) == 200 and result["edges_truncated"] is True
    receipt = edit_receipt(original, [{"op": "update_node", "node_id": "n-1", "data": {"prompt": "exact new prompt"}}])
    assert receipt["version"] == 7 and receipt["changed_node_ids"] == ["n-1"]
    assert "graph" not in receipt and "prompt" not in json.dumps(receipt)


def test_overview_projects_valid_positions_and_bounds_display_name():
    original = canvas(1)
    original["graph"]["selection"] = []
    original["name"] = "long title " * 20000
    original["graph"]["nodes"][0]["position"]["legacy_metadata"] = {
        "prompt": "legacy text " * 20000
    }
    original["graph"]["nodes"][0]["data"].pop("history")
    original["graph"] = validate_graph(original["graph"])
    result = canvas_view(original, view="overview")
    assert result["nodes"][0]["position"] == {"x": 0, "y": 0}
    assert len(result["name"]) <= 160
    assert len(json.dumps(result)) < 2500
    assert canvas_view(original)["graph"]["nodes"][0]["position"]["legacy_metadata"]


@pytest.mark.parametrize("operation, affected", [
    ({"op": "disconnect", "edge_id": "a"}, ["n-0", "n-1"]),
    ({"op": "remove_node", "node_id": "n-1"}, ["n-0", "n-1", "n-2"]),
])
def test_compact_client_receipt_includes_endpoints_of_removed_edges(tmp_path, operation, affected):
    import threading
    from pathlib import Path

    from lfo.canvas.client import CanvasClient
    from lfo.canvas.server import CanvasHTTPServer
    from lfo.canvas.service import CanvasService
    from lfo.canvas.settings import CanvasSettings

    settings = CanvasSettings(Path(__file__).resolve().parents[2], tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    graph = canvas(3)["graph"]
    for node in graph["nodes"]:
        node["data"].pop("history")
    graph["edges"] = [
        {"id": "a", "source": "n-0", "target": "n-1", "sourceHandle": "output", "targetHandle": "related"},
        {"id": "b", "source": "n-1", "target": "n-2", "sourceHandle": "output", "targetHandle": "related"},
    ]
    stored = service.store.create_canvas("connections", graph)
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = CanvasClient(settings, url=f"http://127.0.0.1:{server.server_address[1]}")
        receipt = client.edit(stored["id"], stored["version"], [operation], compact=True)
        assert receipt["changed_node_ids"] == affected
        assert receipt["changed_node_count"] == len(affected)
        assert receipt["version"] == stored["version"] + 1 and "graph" not in receipt
        assert len(service.store.get_canvas(stored["id"])["graph"]["edges"]) == (1 if operation["op"] == "disconnect" else 0)
        assert service.store.list_runs() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        service.close()
