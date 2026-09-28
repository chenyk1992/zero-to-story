"""Execute one frozen Canvas Qwen3-TTS request using the shared Comfy transport."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.media._ffmpeg import probe_audio, run_command

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-tts-executor"
MODEL_DIRECTORY = "Qwen3-TTS-12Hz-1.7B-CustomVoice"
MODEL_BY_MODE = {
    "tts": ("FB_Qwen3TTSCustomVoice", "Qwen3-TTS-12Hz-1.7B-CustomVoice"),
    "design": ("FB_Qwen3TTSVoiceDesign", "Qwen3-TTS-12Hz-1.7B-VoiceDesign"),
    "clone": ("FB_Qwen3TTSVoiceClone", "Qwen3-TTS-12Hz-1.7B-Base"),
}
REQUIRED_MODEL_FILES = (
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "preprocessor_config.json",
    "speech_tokenizer/config.json",
    "speech_tokenizer/model.safetensors",
    "speech_tokenizer/preprocessor_config.json",
)


def prepare_workflow(
    snapshot: dict[str, Any], *, reference_token: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or (
        snapshot.get("node_type"),
        snapshot.get("provider"),
        snapshot.get("model"),
    ) != ("audio", "comfy-qwen-tts", "qwen3-tts-1.7b-customvoice"):
        raise ValueError("不是已选择 Qwen3-TTS 的画布音频任务")
    mode = snapshot.get("mode")
    if mode not in MODEL_BY_MODE:
        raise ValueError("不支持的 Qwen3-TTS 模式")
    for key in ("prompt", "request_id"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].strip():
            raise ValueError(f"音频任务缺少有效 {key}")
    if not isinstance(snapshot.get("parameters"), dict) or not isinstance(
        snapshot.get("inputs"), dict
    ):
        raise ValueError("音频参数与输入必须是对象")
    validate_input_contract(snapshot, capability)
    params = {
        key: value
        for key, value in snapshot["parameters"].items()
        if value is not None and value != ""
    }
    instruct = params.get("instruct", "")
    if not isinstance(instruct, str):
        raise ValueError("表演指令必须是文本")
    if mode == "design" and not instruct.strip():
        raise ValueError("声音设计需要非空声音描述")
    normalized = {
        "request_id": snapshot["request_id"],
        "mode": mode,
        "model_directory": MODEL_BY_MODE[mode][1],
        "language": params["language"],
        "tempo": params["tempo"],
        "seed": params.get("seed", secrets.randbelow(2**53)),
        "max_new_tokens": params.get("max_new_tokens", 2048),
        "temperature": params.get("temperature", 0.9),
        "instruct": instruct,
    }
    if mode == "tts":
        normalized["speaker"] = params["speaker"]
    if mode == "clone":
        if params.get("reference_verified") is not True:
            raise ValueError("参考声音须先实际听审；常规模式还须核对转写")
        for key in ("reference_source", "authorization"):
            if not isinstance(params.get(key), str) or not params[key].strip():
                raise ValueError(f"音色克隆缺少 {key}")
        x_vector_only = params.get("x_vector_only", False)
        if not isinstance(x_vector_only, bool):
            raise ValueError("x_vector_only 必须为布尔值")
        ref_text = params.get("ref_text", "")
        if not x_vector_only and (not isinstance(ref_text, str) or not ref_text.strip()):
            raise ValueError("完整参考模式需要实际参考转写 ref_text")
        references = snapshot["inputs"].get("reference_audios", [])
        if len(references) != 1 or references[0].get("kind") != "audio":
            raise ValueError("音色克隆需要一份实际参考音频")
        if not reference_token:
            raise ValueError("音色克隆需要已上传的参考音频")
        normalized.update(
            reference_path=references[0]["path"],
            reference_source=params["reference_source"],
            authorization=params["authorization"],
            reference_verified=True,
            ref_text=ref_text,
            x_vector_only=x_vector_only,
        )
    prefix = hashlib.sha256(snapshot["request_id"].encode()).hexdigest()[:24]
    voice_inputs: dict[str, Any] = {
        "model_choice": "1.7B",
        "device": "cuda",
        "precision": "bf16",
        "language": normalized["language"],
        "seed": normalized["seed"],
        "max_new_tokens": normalized["max_new_tokens"],
        "temperature": normalized["temperature"],
        "top_p": 1.0,
        "top_k": 50,
        "repetition_penalty": 1.05,
        "attention": "sdpa",
        "unload_model_after_generate": True,
    }
    if mode == "clone":
        voice_inputs.update(
            target_text=snapshot["prompt"],
            ref_audio=["3", 0],
            ref_text=normalized["ref_text"],
            x_vector_only=normalized["x_vector_only"],
        )
    else:
        voice_inputs["text"] = snapshot["prompt"]
        voice_inputs["instruct"] = instruct
        if mode == "tts":
            voice_inputs["speaker"] = normalized["speaker"]
    workflow = {
        "1": {
            "class_type": MODEL_BY_MODE[mode][0],
            "inputs": voice_inputs,
        },
        "2": {
            "class_type": "SaveAudio",
            "inputs": {
                "audio": ["1", 0],
                "filename_prefix": f"canvas/tts/{prefix}/speech",
            },
        },
    }
    if mode == "clone":
        workflow["3"] = {
            "class_type": "LoadAudio",
            "inputs": {"audio": reference_token},
        }
    return workflow, normalized


def preflight(workflow: dict[str, Any], workflow_path: Path, session) -> None:
    node_class = workflow["1"]["class_type"]
    model_directory = next(
        (directory for name, directory in MODEL_BY_MODE.values() if name == node_class),
        None,
    )
    if model_directory is None:
        raise transport.ExecutorError("不支持的 Qwen3-TTS 节点")
    files = set(transport.model_files(session, "qwen-tts"))
    missing = [name for name in REQUIRED_MODEL_FILES if f"{model_directory}/{name}" not in files]
    missing += [
        name for name in ("config.json", "model.safetensors", "preprocessor_config.json")
        if f"Qwen3-TTS-Tokenizer-12Hz/{name}" not in files
    ]
    if missing:
        raise transport.ExecutorError(
            "本机 TTS 模型文件未就绪，停止提交以避免插件自动下载：" + ", ".join(missing)
        )
    transport.preflight_workflow(workflow, workflow_path, session)


def upload_reference(path: Path, session) -> str:
    """Upload a frozen reference once and ensure the local source did not change."""
    metadata = probe_audio(path)
    if metadata["duration_ms"] <= 0:
        raise ValueError("参考音频时长无效")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    token = transport.upload_input(path, session)
    with path.open("rb") as stream:
        current = hashlib.file_digest(stream, "sha256").hexdigest()
    if current != digest:
        raise ValueError("参考音频在上传期间发生变化，停止提交")
    return token


def materialize_audio(result, output_dir: Path, config, normalized) -> dict[str, Any]:
    refs = [
        ref
        for ref in result.outputs
        if ref.file_type in {"output", "absolute"} and Path(ref.filename).suffix.lower() == ".flac"
    ]
    if len(refs) != 1:
        raise ValueError("TTS 必须返回唯一 FLAC 音频")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path, target = output_dir / "original.flac", output_dir / "speech.flac"
    with tempfile.TemporaryDirectory(prefix=".tts-", dir=output_dir) as temporary:
        raw, delivery = Path(temporary) / "original.flac", Path(temporary) / "speech.flac"
        ref = refs[0]
        shutil.copyfile(Path(ref.filename).resolve(), raw)
        original = probe_audio(raw)
        if original["codec"] != "flac":
            raise ValueError("TTS 原始输出必须是 FLAC 音频")
        # Retain the checked original even if deterministic postprocessing fails.
        raw.replace(raw_path)
        if normalized["tempo"] == 1:
            shutil.copyfile(raw_path, delivery)
            metadata = original
        else:
            run_command(
                [
                    os.environ.get("LFO_FFMPEG") or "ffmpeg",
                    "-v",
                    "error",
                    "-xerror",
                    "-n",
                    "-i",
                    str(raw_path),
                    "-map",
                    "0:a:0",
                    "-af",
                    f"atempo={normalized['tempo']}",
                    "-c:a",
                    "flac",
                    str(delivery),
                ]
            )
            metadata = probe_audio(delivery)
            expected_ms = original["duration_ms"] / normalized["tempo"]
            if abs(metadata["duration_ms"] - expected_ms) > max(150, expected_ms * 0.03):
                raise ValueError("语速处理后的音频时长异常")
        delivery.replace(target)
    metadata = {
        **metadata,
        "tempo": normalized["tempo"],
        "seed": normalized["seed"],
        "raw_duration_ms": original["duration_ms"],
    }
    return {
        "path": str(target.resolve()),
        "kind": "audio",
        "name": "语音.flac",
        "metadata": metadata,
    }


def write_delivery_manifest(
    output_dir: Path,
    normalized: dict[str, Any],
    provider_task_id: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    """Bind the actual raw and delivery bytes to one confirmed Canvas request."""
    raw_path = (output_dir / "original.flac").resolve(strict=True)
    delivery_path = Path(output["path"]).resolve(strict=True)

    def media(path: Path, duration_ms: int) -> dict[str, Any]:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return {
            "path": str(path),
            "sha256": digest,
            "duration_seconds": duration_ms / 1000,
            "sample_rate": output["metadata"]["sample_rate"],
            "channels": output["metadata"]["channels"],
        }

    receipt = {
        "kind": "qwen-tts-delivery.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "request_id": normalized["request_id"],
        "provider_task_id": provider_task_id,
        "config": normalized,
        "raw": media(raw_path, output["metadata"]["raw_duration_ms"]),
        "delivery": media(delivery_path, output["metadata"]["duration_ms"]),
        "tempo": normalized["tempo"],
        "processing_passes": 0 if normalized["tempo"] == 1 else 1,
        "listening_status": "INCONCLUSIVE",
    }
    with (output_dir / "speech.flac.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return receipt


def execute_snapshot(snapshot, output_dir: Path, config, *, emit=None):
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        emit({"stage": stage})
        clone = snapshot.get("mode") == "clone"
        workflow, normalized = prepare_workflow(
            snapshot, reference_token="pending.flac" if clone else None
        )
        from lfo.comfy.admission import VideoSubmissionGuard

        output_dir.mkdir(parents=True, exist_ok=True)
        conditions_path = output_dir / "conditions.json"
        conditions_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with VideoSubmissionGuard(config.base_url, request_id=normalized["request_id"]) as guard, transport.ready_session(config) as session:
                if clone:
                    stage = "reference_upload"
                    emit({"stage": stage})
                    workflow["3"]["inputs"]["audio"] = upload_reference(
                        Path(normalized["reference_path"]), session
                    )
                workflow_path = output_dir / "workflow.json"
                workflow_path.write_text(
                    json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                preflight(workflow, workflow_path, session)
                stage = "submit"
                emit({"stage": stage})
                result = transport.run_workflow(
                    workflow_path, output_dir, config, session, guard=guard, emit=emit
                )
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_audio(result, output_dir, config, normalized)
        write_delivery_manifest(output_dir, normalized, result.provider_task_id, output)
        conditions_path.write_text(
            json.dumps(
                {
                    **normalized,
                    "output": output,
                    "original_path": str((output_dir / "original.flac").resolve()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "status": "succeeded",
            "stage": "media_validation",
            "outputs": [output],
            "provider_task_id": result.provider_task_id,
        }
    except Exception as exc:
        if not isinstance(exc, transport.ExecutorError):
            exc = transport.ExecutorError(
                str(exc), status="unknown" if stage == "submit" and result is None else "failed"
            )
        exc.stage = stage
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Internal Canvas TTS worker adapter")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = execute_snapshot(snapshot, args.output_dir, transport.load_runtime_config())
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "status": getattr(exc, "status", "failed"),
                    "stage": getattr(exc, "stage", "input_validation"),
                    "provider_task_id": getattr(exc, "provider_task_id", None),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 1
