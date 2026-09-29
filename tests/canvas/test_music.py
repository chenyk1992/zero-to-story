from __future__ import annotations

import copy
import os
from contextlib import nullcontext
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.graph import resolve_snapshot, validate_graph
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.comfy import transport
from lfo.media._ffmpeg import run_command

PROJECT = Path(__file__).resolve().parents[2]


def snapshot(mode: str = "song") -> dict:
    return {
        "node_type": "audio",
        "provider": "comfy-minimax-music",
        "model": "minimax-music-3",
        "mode": mode,
        "prompt": "温柔的中文独立流行，钢琴先进入，副歌鼓点展开。",
        "request_id": "music-request",
        "parameters": {"lyrics": "[Verse]\n雨停了。\n[Chorus]\n天亮了！", "seed": 42, "max_duration": 60},
        "inputs": {"reference_images": [], "reference_videos": [], "reference_audios": []},
    }


def test_song_keeps_caption_lyrics_and_seed_separate():
    from lfo.comfy.minimax_music import prepare_workflow

    workflow, normalized = prepare_workflow(snapshot())
    encode = workflow["4"]["inputs"]
    assert encode["caption"] == snapshot()["prompt"]
    assert encode["lyrics"] == snapshot()["parameters"]["lyrics"]
    assert encode["seed"] == workflow["7"]["inputs"]["seed"] == 42
    assert workflow["6"]["inputs"]["seconds"] == ["4", 1]
    assert workflow["4"]["inputs"]["max_duration"] == 60
    assert workflow["9"]["class_type"] == "SaveAudio"
    assert normalized["mode"] == "song"


def test_instrumental_rejects_lyrics_and_unexpected_media():
    from lfo.comfy.minimax_music import prepare_workflow

    value = snapshot("instrumental")
    with pytest.raises(ValueError):
        prepare_workflow(value)
    value["parameters"].pop("lyrics")
    workflow, _ = prepare_workflow(value)
    assert workflow["4"]["inputs"]["lyrics"] == ""
    value["inputs"]["reference_audios"] = [{"kind": "audio", "path": "song.flac"}]
    with pytest.raises(ValueError):
        prepare_workflow(value)


@pytest.mark.parametrize("patch", [
    {"prompt": " "},
    {"parameters": {"lyrics": "唱", "max_duration": float("nan")}},
    {"parameters": {"lyrics": "唱", "max_duration": 361}},
    {"parameters": {"lyrics": "唱", "seed": -1}},
    {"node_type": "video"},
])
def test_invalid_input_stops_before_io(patch):
    from lfo.comfy.minimax_music import prepare_workflow

    value = snapshot()
    value.update(copy.deepcopy(patch))
    with pytest.raises(ValueError):
        prepare_workflow(value)


def test_missing_models_prevent_submission(tmp_path, monkeypatch):
    from lfo.comfy import minimax_music as music

    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(transport, "model_files", lambda *_: [])
    monkeypatch.setattr(transport, "run_workflow", lambda *a, **k: pytest.fail("must not submit"))
    with pytest.raises(transport.ExecutorError, match="模型"):
        music.execute_snapshot(snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)


def test_unknown_music_keeps_original_task_receipt(tmp_path, monkeypatch):
    from lfo.comfy import minimax_music as music
    from lfo.comfy.admission import inspect_submission

    calls = []
    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(music, "preflight", lambda *a: None)
    seeds = iter((11, 22))
    monkeypatch.setattr(music.secrets, "randbelow", lambda _: next(seeds))
    seedless = snapshot()
    seedless["parameters"].pop("seed")

    def submit(*args, **kwargs):
        kwargs["guard"].submitted("original-task")
        calls.append(inspect_submission()["request_id"])
        raise transport.ExecutorError("connection lost", provider_task_id="original-task", status="unknown")

    monkeypatch.setattr(transport, "run_workflow", submit)
    with pytest.raises(transport.ExecutorError) as caught:
        music.execute_snapshot(seedless, tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert caught.value.status == "unknown" and caught.value.provider_task_id == "original-task"
    conditions = (tmp_path / "out" / "conditions.json").read_bytes()
    workflow = (tmp_path / "out" / "workflow.json").read_bytes()
    with pytest.raises(transport.ExecutorError):
        music.execute_snapshot(seedless, tmp_path / "out", transport.RuntimeConfig(), emit=lambda _: None)
    assert (tmp_path / "out" / "conditions.json").read_bytes() == conditions
    assert (tmp_path / "out" / "workflow.json").read_bytes() == workflow
    assert calls == ["music-request"]


def test_music_capability_queues_one_frozen_canvas_request(tmp_path, monkeypatch):
    cap = CapabilityCatalog(PROJECT).get("comfy-minimax-music")
    assert cap["execution"] == "script" and cap["resource"] == {"key": "video", "capacity": 1}
    assert not cap.get("requires_tools")
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *_args, **_kwargs: {**cap, "installed": True, "available": True})
    g = {"nodes": [{"id": "music", "type": "audio", "position": {"x": 0, "y": 0},
                    "data": {"category": "audio", "provider": "comfy-minimax-music",
                             "model": "minimax-music-3", "mode": "song", "prompt": snapshot()["prompt"],
                             "options": {"comfy-minimax-music": snapshot()["parameters"]}}}], "edges": []}
    validate_graph(g)
    resolved = resolve_snapshot({"graph": g}, "music")
    assert resolved["prompt"] == snapshot()["prompt"]
    assert resolved["parameters"]["lyrics"] == snapshot()["parameters"]["lyrics"]
    service = CanvasService(CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False)
    try:
        canvas = service.store.create_canvas("音乐", g)
        run = service.confirm(canvas["id"], "music", canvas["version"], "music-confirm")
        assert run["status"] == "queued" and run["resource_key"] == "video"
        assert run["snapshot"]["parameters"]["lyrics"] == snapshot()["parameters"]["lyrics"]
        assert service.confirm(canvas["id"], "music", canvas["version"], "music-confirm")["id"] == run["id"]
    finally:
        service.close()


def test_actual_flac_delivery_records_real_shorter_duration(tmp_path):
    from lfo.canvas.media import CanvasMedia
    from lfo.comfy.minimax_music import materialize_audio

    source = tmp_path / "remote.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=440:duration=1.25", "-c:a", "flac", str(source)])
    result = transport.ComfyResult("original-task", (transport.OutputRef(str(source)),))
    delivered = materialize_audio(result, tmp_path / "out", transport.RuntimeConfig(), {"seed": 42})
    assert delivered["kind"] == "audio" and delivered["metadata"]["codec"] == "flac"
    assert 1200 <= delivered["metadata"]["duration_ms"] <= 1300
    assert delivered["metadata"]["listening_status"] == "INCONCLUSIVE"
    assert Path(delivered["path"]).read_bytes() == source.read_bytes()
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media")
    collected = CanvasMedia(settings).collect_outputs([delivered], "canvas-1", "music-run")
    assert collected[0]["sha256"] == delivered["metadata"]["sha256"]
    assert collected[0]["metadata"]["listening_status"] == "INCONCLUSIVE"
