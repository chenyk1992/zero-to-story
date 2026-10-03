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


def snapshot(mode="convert"):
    return {"node_type": "audio", "provider": "comfy-singing", "model": "melband-seedvc-44k",
            "mode": mode, "prompt": "authorized singing", "request_id": "singing-test",
            "parameters": {"authorization": "user supplied", "pitch_shift": -12, "seed": 42} if mode == "convert" else {},
            "inputs": {"reference_audios": [{"path": "source.flac", "kind": "audio"}]
                       + ([{"path": "target.wav", "kind": "audio"}] if mode == "convert" else [])}}


def test_reference_roles_and_timing_are_preserved():
    graph, _ = singing.prepare_workflow(snapshot(), ["source-upload.flac", "target-upload.wav"])
    inputs = graph["4"]["inputs"]
    assert graph["1"]["inputs"]["audio"] == "source-upload.flac"
    assert graph["2"]["inputs"]["audio"] == "target-upload.wav"
    assert inputs["source_audio"] == ["1", 0] and inputs["target_voice"] == ["2", 0]
    assert inputs["length_adjust"] == 1 and inputs["auto_f0_adjust"] is False
    assert inputs["pitch_shift"] == -12
    assert graph["3"]["inputs"]["download_missing"] is False


def test_separation_saves_distinct_outputs():
    graph, _ = singing.prepare_workflow(snapshot("separate"), ["source-upload.flac"])
    assert graph["4"]["inputs"]["audio"] == ["3", 0]
    assert graph["5"]["inputs"]["audio"] == ["3", 1]


@pytest.mark.parametrize("patch", [
    {"inputs": {"reference_audios": [{"path": "source.flac", "kind": "audio"}]}},
    {"parameters": {"authorization": ""}},
    {"parameters": {"authorization": "yes", "pitch_shift": 25}},
    {"parameters": {"authorization": "yes", "length_adjust": 1.2}},
])
def test_invalid_conversion_stops_before_provider(patch):
    value = snapshot()
    value.update(copy.deepcopy(patch))
    with pytest.raises(ValueError):
        singing.prepare_workflow(value, ["source.flac", "target.wav"])


def test_unknown_remote_request_is_not_retried(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(singing, "upload_reference", lambda *_: "uploaded.flac")
    monkeypatch.setattr(transport, "preflight_workflow", lambda *_: None)

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


@pytest.mark.parametrize("reference_count", [0, 1, 2, 3])
def test_canvas_conversion_requires_two_references_before_creating_run(
    tmp_path, monkeypatch, reference_count
):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    entry = copy.deepcopy(service.catalog.get("comfy-singing"))
    entry.update(installed=True, available=True)
    monkeypatch.setattr(service.catalog, "get", lambda *_args, **_kwargs: entry)
    nodes = [{
        "id": "convert", "type": "audio", "position": {"x": 300, "y": 0},
        "data": {
            "prompt": "Use the authorized target voice for the source performance.",
            "provider": "comfy-singing", "model": "melband-seedvc-44k", "mode": "convert",
            "options": {"comfy-singing": {"authorization": "User supplied test references"}},
        },
    }]
    edges = []
    for index in range(reference_count):
        source = settings.media_root / "assets" / "uploads" / f"reference-{index}.flac"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"reference-{index}".encode())
        nodes.append({
            "id": f"source-{index}", "type": "asset",
            "position": {"x": 0, "y": index * 100},
            "data": {"asset": service.media.asset(source)},
        })
        edges.append({
            "id": f"reference-{index}", "source": f"source-{index}", "target": "convert",
            "sourceHandle": "output", "targetHandle": "reference_audio",
        })
    canvas = service.store.create_canvas("Conversion input test", {"nodes": nodes, "edges": edges})
    try:
        assert service.readiness(canvas["id"], "convert")["ready"] is (reference_count == 2)
        if reference_count != 2:
            with pytest.raises(ValueError, match="参考音频"):
                service.confirm(canvas["id"], "convert", canvas["version"], "invalid-conversion")
            assert service.store.list_runs() == []
        else:
            run = service.confirm(canvas["id"], "convert", canvas["version"], "valid-conversion")
            assert run["status"] == "queued" and run["resource_key"] == "video"
            frozen = run["snapshot"]["inputs"]["reference_audios"]
            assert [Path(item["frozen_path"]).read_bytes() for item in frozen] == [
                b"reference-0", b"reference-1"
            ]
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
