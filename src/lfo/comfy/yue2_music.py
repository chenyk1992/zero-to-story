"""Execute one frozen Canvas YuE2 melody-cover request through official Comfy MCP."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.comfy.qwen_tts import upload_reference
from lfo.media._ffmpeg import probe_audio

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-yue2-executor"
CHECKPOINT = "yue2_3b_int8_convrot.safetensors"
AUDIO_ENCODER = "sheetsage2_bf16.safetensors"


def prepare_workflow(snapshot: dict[str, Any], *, reference_token: str = "pending.flac"):
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or (
        snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model"), snapshot.get("mode")
    ) != ("audio", "comfy-yue2-music", "yue2-3b", "cover"):
        raise ValueError("不是已选择 YuE2 旋律翻唱的画布音频任务")
    for key in ("prompt", "request_id"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].strip():
            raise ValueError(f"翻唱任务缺少有效 {key}")
    if not isinstance(snapshot.get("parameters"), dict) or not isinstance(snapshot.get("inputs"), dict):
        raise ValueError("翻唱参数与输入必须是对象")
    validate_input_contract(snapshot, capability)
    reference = snapshot["inputs"]["reference_audios"][0]
    if not isinstance(reference, dict) or reference.get("kind") != "audio" or not isinstance(reference.get("path"), str) or not reference["path"].strip():
        raise ValueError("翻唱需要一份实际参考音频")
    params = {key: value for key, value in snapshot["parameters"].items() if value is not None and value != ""}
    if not isinstance(params.get("lyrics"), str) or not params["lyrics"].strip():
        raise ValueError("翻唱需要与参考对应的非空歌词")
    values = {field["key"]: field["default"] for field in capability["fields"] if "default" in field}
    values.update(params)
    seed = values["seed"] if "seed" in values else secrets.randbelow(2**53)
    normalized = {
        **values, "seed": seed, "request_id": snapshot["request_id"], "mode": "melody",
        "style": snapshot["prompt"], "reference_path": reference["path"],
        "reference_sha256": reference.get("sha256"), "checkpoint": CHECKPOINT,
        "audio_encoder": AUDIO_ENCODER, "abc_source": "automatic_sheetsage2",
        "fixed_singer_identity": False, "original_accompaniment_preserved": False,
    }
    prefix = hashlib.sha256(snapshot["request_id"].encode()).hexdigest()[:24]
    workflow = {
        "1": {"class_type": "LoadAudio", "inputs": {"audio": reference_token}},
        "2": {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": AUDIO_ENCODER}},
        "3": {"class_type": "SheetSage2AudioToABC", "inputs": {"audio_encoder": ["2", 0], "audio": ["1", 0], "mode": "melody"}},
        "4": {"class_type": "PreviewAny", "inputs": {"source": ["3", 0]}},
        "5": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "6": {"class_type": "YuE2GenerateMusic", "inputs": {
            "clip": ["5", 1], "style": snapshot["prompt"], "lyrics": values["lyrics"],
            "abc": ["4", 0], "mode": "melody", "seed": seed, **{key: values[key] for key in (
                "max_duration", "temperature", "top_p", "top_k", "repetition_penalty", "cfg_scale")},
        }},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {"class_type": "EmptyYuE2LatentAudio", "inputs": {"seconds": ["6", 1], "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {
            "model": ["5", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["8", 0], "seed": seed, "steps": values["steps"],
            "cfg": 1.0, "sampler_name": "dpm_2", "scheduler": "sgm_uniform", "denoise": 1.0,
        }},
        "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["9", 0], "vae": ["5", 2]}},
        "11": {"class_type": "SaveAudioAdvanced", "inputs": {
            "audio": ["10", 0], "filename_prefix": f"canvas/yue2/{prefix}/cover", "format": "flac",
        }},
    }
    return workflow, normalized


def preflight(workflow: dict[str, Any], workflow_path: Path, session) -> None:
    for folder, model in (("checkpoints", CHECKPOINT), ("audio_encoders", AUDIO_ENCODER)):
        if model not in set(transport.model_files(session, folder)):
            raise transport.ExecutorError(f"本机 YuE2 模型文件未就绪：{folder}/{model}")
    transport.preflight_workflow(workflow, workflow_path, session)


def materialize_audio(result, output_dir: Path, normalized: dict[str, Any]) -> dict[str, Any]:
    refs = [ref for ref in result.outputs if ref.file_type in {"output", "absolute"}
            and Path(ref.filename).suffix.lower() == ".flac"]
    if len(refs) != 1:
        raise ValueError("YuE2 必须返回唯一 FLAC 音频")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "cover.flac"
    if target.exists():
        raise ValueError("目标翻唱音频已存在，停止覆盖")
    with tempfile.TemporaryDirectory(prefix=".yue2-", dir=output_dir) as folder:
        candidate = Path(folder) / "cover.flac"
        shutil.copyfile(Path(refs[0].filename).resolve(strict=True), candidate)
        metadata = probe_audio(candidate)
        if metadata["codec"] != "flac" or metadata["duration_ms"] <= 0:
            raise ValueError("YuE2 输出不是有效 FLAC")
        candidate.replace(target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(target.resolve()), "kind": "audio", "name": "YuE2 翻唱.flac",
            "metadata": {**metadata, "sha256": digest, "seed": normalized["seed"],
                         "listening_status": "INCONCLUSIVE", "fixed_singer_identity": False}}


def execute_snapshot(snapshot, output_dir: Path, config, *, emit=None):
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        emit({"stage": stage})
        workflow, normalized = prepare_workflow(snapshot)
        from lfo.comfy.admission import VideoSubmissionGuard

        output_dir.mkdir(parents=True, exist_ok=True)
        conditions_path, workflow_path = output_dir / "conditions.json", output_dir / "workflow.json"
        if conditions_path.exists() or workflow_path.exists():
            raise ValueError("翻唱请求已有冻结输入或工作流，停止重复提交")
        reference = Path(normalized["reference_path"]).resolve(strict=True)
        metadata = probe_audio(reference)
        if metadata["duration_ms"] <= 0:
            raise ValueError("参考音频时长无效")
        with reference.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if normalized["reference_sha256"] and normalized["reference_sha256"] != digest:
            raise ValueError("参考音频与画布冻结哈希不同")
        normalized.update(reference_sha256=digest, reference_duration_ms=metadata["duration_ms"])
        with VideoSubmissionGuard(config.base_url, request_id=normalized["request_id"]) as guard, transport.ready_session(config) as session:
            with conditions_path.open("x", encoding="utf-8") as stream:
                json.dump(normalized, stream, ensure_ascii=False, indent=2)
            stage = "reference_upload"
            emit({"stage": stage})
            workflow["1"]["inputs"]["audio"] = upload_reference(reference, session)
            with reference.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("参考音频在冻结后发生变化")
            with workflow_path.open("x", encoding="utf-8") as stream:
                json.dump(workflow, stream, ensure_ascii=False, indent=2)
            stage = "preflight"
            emit({"stage": stage})
            preflight(workflow, workflow_path, session)
            stage = "submit"
            emit({"stage": stage})
            result = transport.run_workflow(workflow_path, output_dir, config, session, guard=guard, emit=emit)
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_audio(result, output_dir, normalized)
        receipt = {"kind": "yue2-cover-delivery.v1", "created_at": datetime.now(UTC).isoformat(),
                   "request_id": normalized["request_id"], "provider_task_id": result.provider_task_id,
                   "config": normalized, "output": output, "timings_seconds": result.timings_seconds,
                   "listening_status": "INCONCLUSIVE"}
        with (output_dir / "cover.flac.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        return {"status": "succeeded", "stage": "media_validation", "outputs": [output],
                "provider_task_id": result.provider_task_id}
    except Exception as exc:
        if not isinstance(exc, transport.ExecutorError):
            exc = transport.ExecutorError(str(exc), status="unknown" if stage == "submit" and result is None else "failed")
        exc.stage = stage
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Internal Canvas YuE2 cover worker adapter")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = execute_snapshot(snapshot, args.output_dir, transport.load_runtime_config())
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "status": getattr(exc, "status", "failed"),
                          "stage": getattr(exc, "stage", "input_validation"),
                          "provider_task_id": getattr(exc, "provider_task_id", None)}, ensure_ascii=False), flush=True)
        return 1
