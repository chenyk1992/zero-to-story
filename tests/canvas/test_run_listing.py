from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path
from time import perf_counter

from lfo.canvas.graph import resolve_snapshot
from lfo.canvas.media import creative_snapshot
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


def test_large_history_resolves_once_per_node_and_checks_each_file(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    service = CanvasService(CanvasSettings(root, tmp_path / "state", tmp_path / "media"), start_worker=False)
    try:
        nodes = [{"id": f"image-{i}", "type": "image", "position": {"x": i, "y": 0},
                  "data": {"prompt": f"scene {i}", "provider": "codex-imagegen", "model": "image_gen", "mode": "create"}} for i in range(100)]
        canvas = service.store.create_canvas("benchmark", {"nodes": nodes, "edges": []})
        snapshots = {node["id"]: resolve_snapshot(canvas, node["id"], []) for node in nodes}
        runs = [{"id": str(i), "canvas_id": canvas["id"], "node_id": f"image-{i % 100}", "status": "succeeded", "outputs": [],
                 "snapshot": copy.deepcopy(snapshots[f"image-{i % 100}"])} for i in range(1000)]
        # A historical creative edit must remain different despite shared resolution.
        runs[0]["snapshot"]["prompt"] = "old prompt"
        monkeypatch.setattr(service.store, "list_runs", lambda *args: copy.deepcopy(runs))
        counts = Counter()
        def counted(canvas, node_id, runs):
            counts[node_id] += 1
            return resolve_snapshot(canvas, node_id, runs)
        monkeypatch.setattr("lfo.canvas.service.resolve_snapshot", counted)
        checked = []
        monkeypatch.setattr(service.media, "inputs_unchanged", lambda snapshot: checked.append(snapshot) or True)
        start = perf_counter()
        baseline = [creative_snapshot(resolve_snapshot(canvas, run["node_id"], runs)) == creative_snapshot(run["snapshot"]) for run in runs]
        baseline_time = perf_counter() - start
        start = perf_counter()
        actual = service.runs(canvas["id"])
        optimized_time = perf_counter() - start
        assert [item["matches_current"] for item in actual] == baseline
        assert counts == Counter({node["id"]: 1 for node in nodes})
        assert len(checked) == 999
        print(f"100 nodes / 1000 runs: baseline={baseline_time:.3f}s optimized={optimized_time:.3f}s; resolution calls 1000 -> 100")
    finally:
        service.close()
