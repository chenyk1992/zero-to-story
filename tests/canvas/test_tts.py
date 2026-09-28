from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
from contextlib import nullcontext
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.graph import GraphValidationError, resolve_snapshot, validate_graph
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.comfy import transport

PROJECT = Path(__file__).resolve().parents[2]


def snapshot():
    return {
        "node_type": "audio",
        "provider": "comfy-qwen-tts",
        "model": "qwen3-tts-1.7b-customvoice",
        "mode": "tts",
        "prompt": "你今天下午有空没得？\n莫着急。",
        "request_id": "tts-request",
        "parameters": {"speaker": "Eric", "language": "Chinese", "tempo": 1.2},
        "inputs": {"reference_images": [], "reference_videos": [], "reference_audios": []},
    }


def graph():
    s = snapshot()
    return {
        "nodes": [
            {
                "id": "voice",
                "type": "audio",
                "position": {"x": 0, "y": 0},
                "data": {
                    "category": "audio",
                    "prompt": s["prompt"],
                    "provider": s["provider"],
                    "model": s["model"],
                    "mode": s["mode"],
                    "options": {s["provider"]: s["parameters"]},
                },
            }
        ],
        "edges": [],
    }


def test_audio_snapshot_and_video_reference_preserve_current_delivery():
    g = graph()
    validate_graph(g)
    s = resolve_snapshot({"graph": g}, "voice")
    assert s["node_type"] == "audio" and s["prompt"] == snapshot()["prompt"]
    g["nodes"].append(
        {
            "id": "video",
            "type": "video",
            "position": {"x": 0, "y": 0},
            "data": {"provider": "comfy", "model": "h3", "mode": "r2v", "prompt": "口播"},
        }
    )
    g["edges"].append(
        {
            "id": "audio-ref",
            "source": "voice",
            "target": "video",
            "sourceHandle": "output",
            "targetHandle": "reference_audio",
        }
    )
    runs = [
        {
            "id": "r",
            "node_id": "voice",
            "status": "succeeded",
            "outputs": [{"kind": "audio", "path": "speech.flac"}],
        }
    ]
    s = resolve_snapshot({"graph": g}, "video", runs)
    assert s["inputs"]["reference_audios"] == [{"kind": "audio", "path": "speech.flac"}]
    g["nodes"][1]["type"] = "image"
    with pytest.raises(GraphValidationError):
        validate_graph(g)
    g["nodes"][1]["type"] = "video"
    g["edges"][0]["targetHandle"] = "first_frame"
    with pytest.raises(GraphValidationError):
        validate_graph(g)
    g["edges"][0].update(source="video", target="voice", targetHandle="reference_audio")
    with pytest.raises(GraphValidationError):
        validate_graph(g)


@pytest.fixture
def tts():
    return importlib.import_module("lfo.comfy.qwen_tts")


def test_workflow_uses_exact_text_and_keeps_tempo_out_of_generation(tts):
    value = snapshot()
    value["parameters"].update(seed=42, instruct="自然地说", temperature=0.8)
    workflow, normalized = tts.prepare_workflow(value)
    voice = workflow["1"]["inputs"]
    assert voice["text"] == value["prompt"]
    assert voice["speaker"] == "Eric" and voice["instruct"] == "自然地说"
    assert voice["seed"] == 42 and voice["temperature"] == 0.8
    assert voice["model_choice"] == "1.7B" and voice["attention"] == "sdpa"
    assert "tempo" not in voice and normalized["tempo"] == 1.2
    assert workflow["2"]["inputs"]["audio"] == ["1", 0]
    assert "tts-request" not in workflow["2"]["inputs"]["filename_prefix"]
    value["request_id"] = "other"
    other, _ = tts.prepare_workflow(value)
    assert other["2"]["inputs"]["filename_prefix"] != workflow["2"]["inputs"]["filename_prefix"]


def test_voice_design_uses_description_and_its_own_model(tts):
    value = snapshot()
    value["mode"] = "design"
    value["parameters"] = {"language": "Chinese", "tempo": 1.2, "instruct": "温暖的成年女性声音"}
    workflow, normalized = tts.prepare_workflow(value)
    voice = workflow["1"]
    assert voice["class_type"] == "FB_Qwen3TTSVoiceDesign"
    assert voice["inputs"]["text"] == value["prompt"]
    assert voice["inputs"]["instruct"] == "温暖的成年女性声音"
    assert "speaker" not in voice["inputs"]
    assert normalized["model_directory"].endswith("VoiceDesign")
    value["parameters"]["instruct"] = ""
    with pytest.raises(ValueError, match="声音描述"):
        tts.prepare_workflow(value)


def test_clone_keeps_target_and_reference_transcript_separate(tts, tmp_path):
    reference = tmp_path / "reference.flac"
    reference.write_bytes(b"frozen-test-reference")
    value = snapshot()
    value["mode"] = "clone"
    value["parameters"] = {
        "language": "Chinese",
        "tempo": 1.2,
        "ref_text": "参考声音说过的原句。",
        "reference_source": "本次合成角色",
        "authorization": "用户授权用于这次合成测试",
        "reference_verified": True,
    }
    value["inputs"]["reference_audios"] = [{"kind": "audio", "path": str(reference)}]
    workflow, normalized = tts.prepare_workflow(value, reference_token="uploaded.flac")
    assert workflow["1"]["class_type"] == "FB_Qwen3TTSVoiceClone"
    assert workflow["1"]["inputs"]["target_text"] == value["prompt"]
    assert workflow["1"]["inputs"]["ref_text"] == value["parameters"]["ref_text"]
    assert workflow["1"]["inputs"]["x_vector_only"] is False
    assert workflow["1"]["inputs"]["ref_audio"] == ["3", 0]
    assert workflow["3"]["inputs"]["audio"] == "uploaded.flac"
    assert normalized["model_directory"].endswith("Base")
    value["parameters"]["reference_verified"] = False
    with pytest.raises(ValueError, match="听审"):
        tts.prepare_workflow(value, reference_token="uploaded.flac")


def test_clone_reference_can_connect_from_audio_node():
    g = graph()
    g["nodes"].append({
        "id": "clone", "type": "audio", "position": {"x": 200, "y": 0},
        "data": {
            "category": "audio", "prompt": "新台词", "provider": "comfy-qwen-tts",
            "model": "qwen3-tts-1.7b-customvoice", "mode": "clone",
            "options": {"comfy-qwen-tts": {}},
        },
    })
    g["edges"].append({
        "id": "reference", "source": "voice", "target": "clone",
        "sourceHandle": "output", "targetHandle": "reference_audio",
    })
    validate_graph(g)
    runs = [{"id": "accepted", "node_id": "voice", "status": "succeeded",
             "outputs": [{"kind": "audio", "path": "speech.flac"}]}]
    resolved = resolve_snapshot({"graph": g}, "clone", runs)
    assert resolved["inputs"]["reference_audios"] == [{"kind": "audio", "path": "speech.flac"}]


@pytest.mark.parametrize(
    "patch",
    [
        {"prompt": " "},
        {"request_id": ""},
        {"mode": "clone"},
        {"node_type": "video"},
        {"parameters": {"speaker": "not-a-voice", "language": "Chinese", "tempo": 1.2}},
        {"parameters": {"speaker": "Eric", "language": "Chinese", "tempo": float("nan")}},
        {
            "parameters": {
                "speaker": "Eric",
                "language": "Chinese",
                "tempo": 1.2,
                "aspect_ratio": "16:9",
            }
        },
        {"parameters": {"speaker": "Eric", "language": "Chinese", "tempo": 1.2, "instruct": 123}},
        {"inputs": {"reference_audios": [{"path": "clone.wav", "kind": "audio"}]}},
    ],
)
def test_invalid_tts_inputs_are_rejected_before_io(tts, patch):
    value = snapshot()
    value.update(patch)
    with pytest.raises(ValueError):
        tts.prepare_workflow(value)


def test_missing_models_stop_before_submission(tts, tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: None)
    monkeypatch.setattr(transport, "model_files", lambda *a: [])
    monkeypatch.setattr(transport, "run_workflow", lambda *a, **k: pytest.fail("must not submit"))
    with pytest.raises(transport.ExecutorError, match="模型"):
        tts.execute_snapshot(
            snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda e: None
        )


def test_unknown_tts_is_submitted_once_and_keeps_task_id(tts, tmp_path, monkeypatch):
    from lfo.comfy.admission import inspect_submission

    calls = []
    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(tts, "preflight", lambda *a: None)

    def submit(*a, **kw):
        kw["guard"].submitted("remote")
        calls.append(inspect_submission()["request_id"])
        raise transport.ExecutorError(
            "connection lost", provider_task_id="remote", status="unknown"
        )

    monkeypatch.setattr(transport, "run_workflow", submit)
    with pytest.raises(transport.ExecutorError) as caught:
        tts.execute_snapshot(
            snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda e: None
        )
    assert calls == ["tts-request"]
    assert caught.value.status == "unknown" and caught.value.provider_task_id == "remote"
    assert inspect_submission()["provider_task_id"] == "remote"
    with pytest.raises(transport.ExecutorError, match="原 Comfy"):
        tts.execute_snapshot(
            snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=lambda e: None
        )
    assert calls == ["tts-request"]


@pytest.mark.parametrize(
    "metadata",
    [
        {"has_audio": False},
        {"duration_ms": 0},
        {"width": 64},
        {"sample_rate": 0},
    ],
)
def test_audio_probe_rejects_non_audio_or_invalid_metadata(tmp_path, monkeypatch, metadata):
    from lfo.media import _ffmpeg

    value = {
        "duration_ms": 2000,
        "has_audio": True,
        "audio_codec": "flac",
        "width": None,
        "sample_rate": 24000,
        "channels": 1,
        **metadata,
    }
    monkeypatch.setattr(_ffmpeg, "probe", lambda *a: value)
    monkeypatch.setattr(_ffmpeg, "run_command", lambda *a: pytest.fail("invalid header must stop"))
    with pytest.raises(_ffmpeg.MediaCommandError):
        _ffmpeg.probe_audio(tmp_path / "audio.flac")


def test_audio_probe_does_not_trust_header_when_decode_fails(tmp_path, monkeypatch):
    from lfo.media import _ffmpeg

    monkeypatch.setattr(
        _ffmpeg,
        "probe",
        lambda *a: {
            "duration_ms": 2000,
            "has_audio": True,
            "audio_codec": "flac",
            "width": None,
            "sample_rate": 24000,
            "channels": 1,
        },
    )

    def corrupt(command):
        assert "-xerror" in command
        raise _ffmpeg.MediaCommandError("corrupt audio")

    monkeypatch.setattr(_ffmpeg, "run_command", corrupt)
    with pytest.raises(_ffmpeg.MediaCommandError, match="corrupt"):
        _ffmpeg.probe_audio(tmp_path / "audio.flac")


def test_completed_generation_with_failed_audio_validation_is_terminal(tts, tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(tts, "preflight", lambda *a: None)
    monkeypatch.setattr(
        transport, "run_workflow", lambda *a, **k: transport.ComfyResult("done", ())
    )
    events = []
    with pytest.raises(transport.ExecutorError) as caught:
        tts.execute_snapshot(
            snapshot(), tmp_path / "out", transport.RuntimeConfig(), emit=events.append
        )
    assert caught.value.status == "failed" and caught.value.provider_task_id == "done"
    assert any(e.get("remote_finished") for e in events)


def test_audio_confirm_freezes_options_and_shares_gpu_slot(tts, tmp_path, monkeypatch):
    cap = json.loads((tts.SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    cap.update(installed=True, available=True)
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *a, **k: cap)
    service = CanvasService(
        CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False
    )
    try:
        canvas = service.store.create_canvas("语音", graph())
        run = service.confirm(canvas["id"], "voice", canvas["version"], "tts-confirm")
        assert run["status"] == "queued" and run["resource_key"] == "video"
        assert run["resource_capacity"] == 1
        assert (
            service.confirm(canvas["id"], "voice", canvas["version"], "tts-confirm")["id"]
            == run["id"]
        )
        changed = copy.deepcopy(canvas["graph"])
        changed["nodes"][0]["data"]["options"]["comfy-qwen-tts"]["speaker"] = "Dylan"
        service.store.save_canvas(canvas["id"], canvas["version"], changed)
        assert service.store.get_run(run["id"])["snapshot"]["parameters"]["speaker"] == "Eric"
        assert service.runs(canvas["id"])[0]["matches_current"] is False
    finally:
        service.close()


def test_model_manifest_requires_real_files_not_download_cache(tts, monkeypatch):
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: None)
    files = [f"Qwen3-TTS-12Hz-1.7B-CustomVoice/{p}" for p in tts.REQUIRED_MODEL_FILES]
    files += [f"Qwen3-TTS-Tokenizer-12Hz/{p}" for p in ("config.json", "model.safetensors", "preprocessor_config.json")]
    monkeypatch.setattr(transport, "model_files", lambda *a: files)
    workflow, _ = tts.prepare_workflow(snapshot())
    tts.preflight(workflow, Path("workflow.json"), object())
    files[:] = [
        p.replace("/model.safetensors", "/.cache/download/model.safetensors.metadata")
        for p in files
    ]
    with pytest.raises(transport.ExecutorError, match="模型"):
        tts.preflight(workflow, Path("workflow.json"), object())


@pytest.mark.parametrize(
    "mode,parameters,directory",
    [
        ("design", {"language": "Chinese", "tempo": 1.2, "instruct": "温暖女声"},
         "Qwen3-TTS-12Hz-1.7B-VoiceDesign"),
        ("clone", {"language": "Chinese", "tempo": 1.2, "reference_source": "synthetic",
                   "authorization": "test", "reference_verified": True, "ref_text": "参考句。"},
         "Qwen3-TTS-12Hz-1.7B-Base"),
    ],
)
def test_preflight_checks_selected_model_family(tts, monkeypatch, mode, parameters, directory):
    value = snapshot()
    value["mode"] = mode
    value["parameters"] = parameters
    if mode == "clone":
        value["inputs"]["reference_audios"] = [{"kind": "audio", "path": "reference.flac"}]
    workflow, _ = tts.prepare_workflow(
        value, reference_token="uploaded.flac" if mode == "clone" else None
    )
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: None)
    files = [f"{directory}/{name}" for name in tts.REQUIRED_MODEL_FILES]
    files += [f"Qwen3-TTS-Tokenizer-12Hz/{p}" for p in ("config.json", "model.safetensors", "preprocessor_config.json")]
    monkeypatch.setattr(transport, "model_files", lambda *a: files)
    tts.preflight(workflow, Path("workflow.json"), object())
    files.pop()
    with pytest.raises(transport.ExecutorError, match="模型"):
        tts.preflight(workflow, Path("workflow.json"), object())


def test_clone_reference_upload_requires_receipt_and_unchanged_source(tts, monkeypatch, tmp_path):
    reference = tmp_path / "reference.flac"
    reference.write_bytes(b"frozen bytes")
    monkeypatch.setattr(tts, "probe_audio", lambda path: {"duration_ms": 1000})
    monkeypatch.setattr(transport, "upload_input", lambda *a: "uploaded.flac")
    assert tts.upload_reference(reference, object()) == "uploaded.flac"

    def mutate(_path, _session):
        reference.write_bytes(b"changed bytes")
        return "uploaded.flac"

    monkeypatch.setattr(transport, "upload_input", mutate)
    with pytest.raises(ValueError, match="变化"):
        tts.upload_reference(reference, object())


def test_tokenizer_is_checked_by_mcp_filename_only(tts, monkeypatch):
    workflow, _ = tts.prepare_workflow(snapshot())
    files = [f"{tts.MODEL_DIRECTORY}/{name}" for name in tts.REQUIRED_MODEL_FILES]
    monkeypatch.setattr(transport, "model_files", lambda *a: files)
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: None)
    with pytest.raises(transport.ExecutorError, match="模型"):
        tts.preflight(workflow, Path("workflow.json"), object())
    files += [f"Qwen3-TTS-Tokenizer-12Hz/{p}" for p in ("config.json", "model.safetensors", "preprocessor_config.json")]
    tts.preflight(workflow, Path("workflow.json"), object())


def test_service_rejects_corrupt_audio_even_when_adapter_claims_success(tmp_path, monkeypatch):
    import lfo.canvas.service as service_module

    service = CanvasService(
        CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False
    )
    path = tmp_path / "fake.flac"
    path.write_bytes(b"corrupt")

    def invalid(*a):
        raise ValueError("cannot decode")

    monkeypatch.setattr(service_module, "probe_audio", invalid, raising=False)
    try:
        with pytest.raises(ValueError, match="cannot decode"):
            service._validate_output_payload(
                [{"kind": "audio", "path": str(path), "metadata": {"duration_ms": 3000}}], "audio"
            )
    finally:
        service.close()


def test_audio_delivery_preserves_original_and_only_returns_processed_audio(
    tts, tmp_path, monkeypatch
):
    raw = tmp_path / "provider.flac"
    raw.write_bytes(b"raw audio")
    result = transport.ComfyResult("done", (transport.OutputRef(str(raw), file_type="absolute"),))
    calls = []

    def process(command):
        calls.append(command)
        Path(command[-1]).write_bytes(b"processed audio")

    monkeypatch.setattr(tts, "run_command", process)
    monkeypatch.setattr(
        tts,
        "probe_audio",
        lambda p: {
            "codec": "flac",
            "duration_ms": 2400 if p.name == "original.flac" else 2000,
            "sample_rate": 24000,
            "channels": 1,
        },
    )
    out = tts.materialize_audio(
        result, tmp_path / "out", transport.RuntimeConfig(), {"tempo": 1.2, "seed": 42}
    )
    assert Path(out["path"]).read_bytes() == b"processed audio"
    assert (tmp_path / "out/original.flac").read_bytes() == b"raw audio"
    assert raw.read_bytes() == b"raw audio"
    assert calls[0][calls[0].index("-af") + 1] == "atempo=1.2"
    assert out["kind"] == "audio" and out["metadata"]["duration_ms"] == 2000
    assert out["metadata"]["raw_duration_ms"] == 2400


def test_delivery_manifest_binds_actual_audio_and_provider_task(tts, tmp_path, monkeypatch):
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    (output_dir / "original.flac").write_bytes(b"raw bytes")
    (output_dir / "speech.flac").write_bytes(b"delivery bytes")
    monkeypatch.setattr(tts, "probe_audio", lambda path: {
        "codec": "flac", "duration_ms": 2400, "sample_rate": 24000, "channels": 1
    })
    output = {
        "path": str(output_dir / "speech.flac"),
        "kind": "audio",
        "metadata": {"duration_ms": 2000, "sample_rate": 24000, "channels": 1,
                     "raw_duration_ms": 2400, "tempo": 1.2},
    }
    receipt = tts.write_delivery_manifest(
        output_dir, {"request_id": "confirmed-run", "mode": "design", "tempo": 1.2},
        "comfy-task", output
    )
    assert receipt["kind"] == "qwen-tts-delivery.v1"
    assert receipt["request_id"] == "confirmed-run"
    assert receipt["provider_task_id"] == "comfy-task"
    assert receipt["delivery"]["sha256"] != receipt["raw"]["sha256"]
    assert receipt["listening_status"] == "INCONCLUSIVE"
    assert json.loads((output_dir / "speech.flac.json").read_text(encoding="utf-8")) == receipt


def test_original_speed_never_applies_atempo(tts, tmp_path, monkeypatch):
    raw = tmp_path / "provider.flac"
    raw.write_bytes(b"raw audio")
    result = transport.ComfyResult("done", (transport.OutputRef(str(raw), file_type="absolute"),))
    monkeypatch.setattr(tts, "probe_audio", lambda p: {"codec": "flac", "duration_ms": 2000})
    monkeypatch.setattr(tts, "run_command", lambda *a: pytest.fail("must not change tempo"))
    out = tts.materialize_audio(
        result, tmp_path / "out", transport.RuntimeConfig(), {"tempo": 1, "seed": 1}
    )
    assert Path(out["path"]).read_bytes() == raw.read_bytes()


@pytest.mark.skipif(
    not shutil.which(os.environ.get("LFO_FFMPEG") or "ffmpeg")
    or not shutil.which(os.environ.get("LFO_FFPROBE") or "ffprobe"),
    reason="FFmpeg and FFprobe are required for the real audio pipeline",
)
def test_real_audio_tempo_delivery(tts, tmp_path):
    source = tmp_path / "test-tone.flac"
    tts.run_command(
        [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2.4:sample_rate=24000",
            "-c:a",
            "flac",
            str(source),
        ]
    )
    result = transport.ComfyResult(
        "synthetic-test", (transport.OutputRef(str(source), file_type="absolute"),)
    )
    output = tts.materialize_audio(
        result, tmp_path / "out", transport.RuntimeConfig(), {"tempo": 1.2, "seed": 1}
    )
    assert (tmp_path / "out/original.flac").read_bytes() == source.read_bytes()
    assert output["metadata"]["raw_duration_ms"] == 2400
    assert 1900 <= output["metadata"]["duration_ms"] <= 2100
    assert output["metadata"]["sample_rate"] == 24000
    assert output["metadata"]["channels"] == 1
    assert tts.probe_audio(Path(output["path"]))["codec"] == "flac"


def test_canvas_worker_collects_verified_audio_and_resolves_delivery(tts, tmp_path, monkeypatch):
    import lfo.canvas.service as service_module

    skill = tmp_path / "fake-adapter"
    skill.mkdir()
    (skill / "execute.py").write_text(
        "import argparse,json,pathlib\n"
        "p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output-dir');a=p.parse_args()\n"
        "s=json.loads(pathlib.Path(a.input).read_text(encoding='utf-8'))\n"
        "d=pathlib.Path(a.output_dir);(d/'original.flac').write_bytes(b'original')\n"
        "o=d/'speech.flac';o.write_text(s['prompt'],encoding='utf-8')\n"
        "print(json.dumps({'stage':'collection','remote_finished':True,'provider_task_id':s['request_id']}),flush=True)\n"
        "print(json.dumps({'outputs':[{'path':str(o),'kind':'audio','metadata':{'duration_ms':99999,'tempo':1.2,'raw_duration_ms':2400}}]}))\n",
        encoding="utf-8",
    )
    cap = json.loads((tts.SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    cap.update(installed=True, available=True, _skill_dir=str(skill), entrypoint="execute.py")
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *a, **k: cap)
    checked = []

    def verify(path):
        checked.append(path)
        assert path.read_text(encoding="utf-8") == snapshot()["prompt"]
        return {"duration_ms": 2000, "sample_rate": 24000, "channels": 1, "codec": "flac"}

    monkeypatch.setattr(service_module, "probe_audio", verify)
    service = CanvasService(
        CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"), start_worker=False
    )
    try:
        canvas = service.store.create_canvas("voice", graph())
        run = service.confirm(canvas["id"], "voice", canvas["version"], "worker-tts")
        assert run["status"] == "queued"
        service._execute(service.store.claim_run(run["id"]))
        result = service.store.get_run(run["id"])
        assert result["status"] == "succeeded", result["error"]
        assert result["provider_task_id"] == "worker-tts"
        assert len(checked) == 1 and len(result["outputs"]) == 1
        delivery = result["outputs"][0]
        assert delivery["metadata"]["duration_ms"] == 2000
        assert delivery["metadata"]["tempo"] == 1.2
        assert delivery["metadata"]["raw_duration_ms"] == 2400
        assert Path(delivery["path"]).name == "speech.flac"
        assert (Path(delivery["path"]).parent / "original.flac").read_bytes() == b"original"
        g = graph()
        g["nodes"].append(
            {
                "id": "video",
                "type": "video",
                "position": {"x": 1, "y": 0},
                "data": {"provider": "comfy", "model": "h3", "mode": "r2v", "prompt": "口播"},
            }
        )
        g["edges"].append(
            {
                "id": "ref",
                "source": "voice",
                "target": "video",
                "sourceHandle": "output",
                "targetHandle": "reference_audio",
            }
        )
        resolved = resolve_snapshot({"graph": g}, "video", [result])
        assert resolved["inputs"]["reference_audios"] == [delivery]
    finally:
        service.close()
