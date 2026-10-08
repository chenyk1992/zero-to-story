from __future__ import annotations

import copy
from contextlib import nullcontext
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.comfy import singing, transport

PROJECT = Path(__file__).resolve().parents[2]


def snapshot(mode="separate"):
    return {"node_type": "audio", "provider": "comfy-singing", "model": "melband-seedvc-44k",
            "mode": mode, "prompt": "Separate actual song vocals", "request_id": "singing-test",
            "parameters": {},
            "inputs": {"reference_audios": [{"path": "source.flac", "kind": "audio"}]}}



def test_separation_saves_distinct_outputs():
    graph, _ = singing.prepare_workflow(snapshot("separate"), ["source-upload.flac"])
    assert graph["4"]["inputs"]["audio"] == ["3", 0]
    assert graph["5"]["inputs"]["audio"] == ["3", 1]


@pytest.mark.parametrize("mode", [None, 123, [], {}, "convert", "rvc", "soulx-svc", "synthesize"])
def test_retired_modes_stop_before_provider(tmp_path, monkeypatch, mode):
    value = snapshot(mode)
    def forbidden(*_):
        pytest.fail("Retired mode opened a provider session")
    monkeypatch.setattr(transport, "ready_session", forbidden)
    with pytest.raises(transport.ExecutorError, match="retired"):
        singing.execute_snapshot(value, tmp_path / "out", transport.RuntimeConfig())
    assert not (tmp_path / "out").exists()


def test_unknown_remote_request_is_not_retried(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(singing, "upload_reference", lambda *_: "uploaded.flac")
    monkeypatch.setattr(transport, "preflight_workflow", lambda *_: None)
    monkeypatch.setattr(transport, "model_files", lambda *_: ["MelBandRoformer_fp16.safetensors"])

    def submit(*args, **kwargs):
        calls.append(1)
        kwargs["guard"].submitted("original-task")
        raise transport.ExecutorError("lost connection", status="unknown", provider_task_id="original-task")

    monkeypatch.setattr(transport, "run_workflow", submit)
    with pytest.raises(transport.ExecutorError):
        singing.execute_snapshot(snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    with pytest.raises(Exception):
        singing.execute_snapshot(snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert len(calls) == 1


def test_singing_capability_is_discoverable():
    entry = CapabilityCatalog(PROJECT).get("comfy-singing")
    assert entry["execution"] == "script" and entry["resource"] == {"key": "video", "capacity": 1}
    assert [item["id"] for item in entry["modes"]] == ["separate"]


@pytest.mark.parametrize("reference_count", [0, 1, 2])
def test_canvas_separation_freezes_one_reference(tmp_path, monkeypatch, reference_count):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    entry = copy.deepcopy(service.catalog.get("comfy-singing"))
    entry.update(installed=True, available=True)
    monkeypatch.setattr(service.catalog, "get", lambda *_args, **_kwargs: entry)
    nodes = [{"id": "sep", "type": "audio", "position": {"x": 300, "y": 0},
              "data": {"prompt": "Separate the actual song", "provider": "comfy-singing",
                       "model": "melband-seedvc-44k", "mode": "separate"}}]
    edges = []
    for index in range(reference_count):
        source = settings.media_root / "assets" / "uploads" / f"reference-{index}.flac"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"reference-{index}".encode())
        nodes.append({"id": f"source-{index}", "type": "asset", "position": {"x": 0, "y": index * 100},
                      "data": {"asset": service.media.asset(source)}})
        edges.append({"id": f"ref-{index}", "source": f"source-{index}", "target": "sep",
                      "sourceHandle": "output", "targetHandle": "reference_audio"})
    canvas = service.store.create_canvas("Separation test", {"nodes": nodes, "edges": edges})
    try:
        assert service.readiness(canvas["id"], "sep")["ready"] is (reference_count == 1)
        if reference_count != 1:
            with pytest.raises(ValueError):
                service.confirm(canvas["id"], "sep", canvas["version"], "invalid-sep")
            assert service.store.list_runs() == []
        else:
            run = service.confirm(canvas["id"], "sep", canvas["version"], "valid-sep")
            assert run["status"] == "queued" and run["resource_key"] == "video"
            frozen = run["snapshot"]["inputs"]["reference_audios"]
            assert Path(frozen[0]["frozen_path"]).read_bytes() == b"reference-0"
    finally:
        service.close()


@pytest.mark.parametrize("mode,model", [("convert", "melband-seedvc-44k"), ("rvc", "rvc-v2"),
                                      ("soulx-svc", "soulx-singer-svc"), ("synthesize", "diffsinger-onnx")])
def test_canvas_cannot_relaunch_historical_trial(tmp_path, monkeypatch, mode, model):
    service = CanvasService(CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False)
    entry = copy.deepcopy(service.catalog.get("comfy-singing"))
    entry.update(installed=True, available=True)
    monkeypatch.setattr(service.catalog, "get", lambda *_a, **_k: entry)
    canvas = service.store.create_canvas("Historical trial", {"nodes": [
        {"id": "old", "type": "audio", "position": {"x": 0, "y": 0},
         "data": {"prompt": "Old trial", "provider": "comfy-singing", "model": model, "mode": mode}}
    ], "edges": []})
    try:
        assert service.readiness(canvas["id"], "old")["ready"] is False
        with pytest.raises(ValueError):
            service.confirm(canvas["id"], "old", canvas["version"], "retired-trial")
        assert service.store.list_runs() == []
    finally:
        service.close()


def test_flattened_output_names_use_provider_provenance(tmp_path, monkeypatch):
    first = tmp_path / "task_000.flac"
    second = tmp_path / "task_001.flac"
    first.write_bytes(b"instruments")
    second.write_bytes(b"vocals")
    monkeypatch.setattr(singing, "probe_audio", lambda _: {"codec": "flac", "duration_ms": 1200})
    normalized = {"mode": "separate", "sources": [{"path": "original.flac"}]}
    result = transport.ComfyResult("task", (
        transport.OutputRef(str(first), node_id="5"),
        transport.OutputRef(str(second), node_id="4"),
    ))
    out = tmp_path / "out"
    out.mkdir()
    outputs = singing.materialize_audio(result, out, normalized)
    assert Path(outputs[0]["path"]).read_bytes() == b"vocals"
    assert Path(outputs[1]["path"]).read_bytes() == b"instruments"
