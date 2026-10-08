from __future__ import annotations

import copy
import hashlib
import os
from contextlib import nullcontext
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.comfy import transport, yue2_music
from lfo.media._ffmpeg import run_command

PROJECT = Path(__file__).resolve().parents[2]


def snapshot(path="song.flac"):
    return {"node_type": "audio", "provider": "comfy-yue2-music", "model": "yue2-3b", "mode": "cover",
            "prompt": "English K-pop female group, solo lines then layered chorus",
            "request_id": "cover-request", "parameters": {"lyrics": "We are Zephyr", "seed": 42, "max_duration": 32},
            "inputs": {"reference_audios": [{"kind": "audio", "path": str(path)}]}}


def source_audio(tmp_path):
    path = tmp_path / "source.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=440:duration=1.25", "-c:a", "flac", str(path)])
    return path


def mock_session(monkeypatch):
    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(yue2_music, "upload_reference", lambda *_: "uploaded.flac")


def test_native_cover_keeps_reference_style_lyrics_and_generated_duration_separate():
    graph, conditions = yue2_music.prepare_workflow(snapshot(), reference_token="input/reference.flac")
    assert graph["1"]["inputs"]["audio"] == "input/reference.flac"
    assert graph["3"]["inputs"]["mode"] == graph["6"]["inputs"]["mode"] == "melody"
    assert graph["6"]["inputs"]["abc"] == ["4", 0]
    assert graph["6"]["inputs"]["style"] == snapshot()["prompt"]
    assert graph["6"]["inputs"]["lyrics"] == snapshot()["parameters"]["lyrics"]
    assert graph["6"]["inputs"]["seed"] == graph["9"]["inputs"]["seed"] == 42
    assert graph["8"]["inputs"]["seconds"] == ["6", 1]
    assert graph["11"]["inputs"]["format"] == "flac"
    assert not conditions["fixed_singer_identity"] and not conditions["original_accompaniment_preserved"]


@pytest.mark.parametrize("patch", [
    {"model": "minimax-music-3"}, {"mode": "song"}, {"prompt": " "},
    {"inputs": {"reference_audios": []}},
    {"inputs": {"reference_audios": [{"kind": "audio", "path": "a.flac"}] * 2}},
    {"inputs": {"reference_audios": [{"kind": "image", "path": "a.flac"}]}},
    {"inputs": {"reference_audios": [{"kind": "audio", "path": "a.flac"}], "reference_images": [{}]}},
    {"parameters": {"lyrics": " ", "max_duration": 32}},
    {"parameters": {"lyrics": 7, "max_duration": 32}},
    {"parameters": {"lyrics": "word", "max_duration": float("nan")}},
    {"parameters": {"lyrics": "word", "max_duration": 361}},
    {"parameters": {"lyrics": "word", "max_duration": 32, "voice_id": "fake"}},
])
def test_invalid_cover_stops_before_io(patch):
    value = snapshot()
    value.update(copy.deepcopy(patch))
    with pytest.raises(ValueError):
        yue2_music.prepare_workflow(value)


def test_missing_models_prevent_submit(tmp_path, monkeypatch):
    mock_session(monkeypatch)
    monkeypatch.setattr(transport, "model_files", lambda *_: [])
    monkeypatch.setattr(transport, "run_workflow", lambda *a, **k: pytest.fail("must not submit"))
    with pytest.raises(transport.ExecutorError, match="模型"):
        yue2_music.execute_snapshot(snapshot(source_audio(tmp_path)), tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)


def test_changed_reference_hash_stops_before_upload(tmp_path, monkeypatch):
    value = snapshot(source_audio(tmp_path))
    value["inputs"]["reference_audios"][0]["sha256"] = "0" * 64
    monkeypatch.setattr(yue2_music, "upload_reference", lambda *_: pytest.fail("must not upload"))
    with pytest.raises(transport.ExecutorError, match="哈希"):
        yue2_music.execute_snapshot(value, tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)


def test_unknown_cover_retains_original_task_and_frozen_seed(tmp_path, monkeypatch):
    mock_session(monkeypatch)
    monkeypatch.setattr(yue2_music, "preflight", lambda *a: None)
    calls = []

    def submit(*args, **kwargs):
        kwargs["guard"].submitted("original-cover-task")
        calls.append(1)
        raise transport.ExecutorError("lost", provider_task_id="original-cover-task", status="unknown")

    monkeypatch.setattr(transport, "run_workflow", submit)
    value = snapshot(source_audio(tmp_path))
    value["parameters"].pop("seed")
    with pytest.raises(transport.ExecutorError) as caught:
        yue2_music.execute_snapshot(value, tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert caught.value.status == "unknown" and caught.value.provider_task_id == "original-cover-task"
    frozen = (tmp_path / "out" / "conditions.json").read_bytes()
    with pytest.raises(transport.ExecutorError, match="重复"):
        yue2_music.execute_snapshot(value, tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert (tmp_path / "out" / "conditions.json").read_bytes() == frozen and calls == [1]


def test_cover_worker_submits_once_and_delivers_candidate(tmp_path, monkeypatch):
    mock_session(monkeypatch)
    monkeypatch.setattr(yue2_music, "preflight", lambda *a: None)
    source = source_audio(tmp_path)
    calls = []

    def submit(workflow_path, output_dir, config, session, **kwargs):
        calls.append(workflow_path)
        return transport.ComfyResult("cover-task", (transport.OutputRef(str(source)),))

    monkeypatch.setattr(transport, "run_workflow", submit)
    result = yue2_music.execute_snapshot(snapshot(source), tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert len(calls) == 1 and result["status"] == "succeeded"
    output = result["outputs"][0]
    assert output["metadata"]["listening_status"] == "INCONCLUSIVE"
    assert 1200 <= output["metadata"]["duration_ms"] <= 1300
    assert output["metadata"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (tmp_path / "out" / "cover.flac.json").is_file()


def test_ambiguous_audio_output_is_rejected(tmp_path):
    source = source_audio(tmp_path)
    result = transport.ComfyResult("task", (transport.OutputRef(str(source)),) * 2)
    with pytest.raises(ValueError, match="唯一"):
        yue2_music.materialize_audio(result, tmp_path / "out", {"seed": 42})


def test_canvas_cover_queues_reference_through_script_worker(tmp_path, monkeypatch):
    cap = CapabilityCatalog(PROJECT).get("comfy-yue2-music")
    assert cap["execution"] == "script" and cap["resource"] == {"key": "video", "capacity": 1}
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *_a, **_k: {**cap, "installed": True, "available": True})
    service = CanvasService(CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False)
    try:
        asset = service.media.import_file(source_audio(tmp_path))
        graph = {"nodes": [
            {"id": "source", "type": "asset", "position": {"x": 0, "y": 0}, "data": {"asset": asset}},
            {"id": "cover", "type": "audio", "position": {"x": 400, "y": 0}, "data": {
                "provider": "comfy-yue2-music", "model": "yue2-3b", "mode": "cover", "prompt": snapshot()["prompt"],
                "options": {"comfy-yue2-music": snapshot()["parameters"]}}}],
            "edges": [{"id": "reference", "source": "source", "sourceHandle": "output", "target": "cover", "targetHandle": "reference_audio"}]}
        canvas = service.store.create_canvas("cover", graph)
        run = service.confirm(canvas["id"], "cover", canvas["version"], "cover-request")
        assert run["status"] == "queued" and run["resource_key"] == "video"
        assert run["snapshot"]["inputs"]["reference_audios"][0]["sha256"] == asset["sha256"]
        assert service.confirm(canvas["id"], "cover", canvas["version"], "cover-request")["id"] == run["id"]
    finally:
        service.close()
