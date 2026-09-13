from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest


def load_script():
    path = Path(__file__).resolve().parents[2] / "scripts/r2v_wire.py"
    spec = importlib.util.spec_from_file_location("r2v_wiring_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("conflict", [False, True])
def test_edit_preserves_unrelated_state_and_never_overwrites_conflict(tmp_path, monkeypatch, conflict):
    module = load_script()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("## P001\n```text\n<Picture 1> and <Picture 2>\n```\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["r2v_wire.py", "--canvas", "canvas", "--panel", "P001", "--refs", "b,a", "--prompt-file", str(prompt)])
    canvas = {"name": "test", "version": 2, "graph": {"nodes": [
        {"id": "video_P001", "data": {"mode": "i2v", "description": "keep"}},
        {"id": "a", "data": {}}, {"id": "b", "data": {}},
    ], "edges": [{"id": "old", "source": "a", "sourceHandle": "output", "target": "video_P001", "targetHandle": "reference_image"}],
        "viewport": {"x": 20, "y": 10, "zoom": 1.5}, "selection": ["a"], "workspace": {"story": "keep"}}}
    puts = []
    def api(method, path, body=None):
        if method == "GET":
            return copy.deepcopy(canvas)
        puts.append(copy.deepcopy(body))
        if conflict:
            canvas["graph"]["nodes"].append({"id": "concurrent", "data": {}})
            canvas["version"] += 1
            raise HTTPError(path, 409, "conflict", {}, None)
        canvas.update(body)
        canvas["version"] += 1
        return copy.deepcopy(canvas)
    monkeypatch.setattr(module, "api", api)
    if conflict:
        with pytest.raises(SystemExit, match="并发"):
            module.main()
        assert canvas["graph"]["nodes"][-1]["id"] == "concurrent"
        assert canvas["graph"]["nodes"][0]["data"]["mode"] == "i2v"
    else:
        assert module.main() == 0
        assert [edge["source"] for edge in canvas["graph"]["edges"]] == ["b", "a"]
    assert len(puts) == 1
    assert puts[0]["graph"]["workspace"] == {"story": "keep"}
    assert puts[0]["graph"]["viewport"]["zoom"] == 1.5
    assert puts[0]["graph"]["selection"] == ["a"]
    assert puts[0]["graph"]["nodes"][0]["data"]["description"] == "keep"
