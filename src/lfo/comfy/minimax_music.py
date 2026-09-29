"""Execute one frozen Canvas MiniMax Music 3 request via the shared Comfy transport."""

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
from lfo.media._ffmpeg import probe_audio

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-music-executor"
DEFAULT_MODELS = {
    "unet_name": "minimax_music3_dit_fp16.safetensors",
    "clip_name": "minimax_music3_text_encoder_pruned_int8_convrot.safetensors",
    "vae_name": "minimax_music3_dav.safetensors",
}


def prepare_workflow(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or (
        snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model")
    ) != ("audio", "comfy-minimax-music", "minimax-music-3"):
        raise ValueError("不是已选择 Music 3 的画布音频任务")
    mode = snapshot.get("mode")
    if mode not in {"song", "instrumental"}:
        raise ValueError("不支持的 Music 3 模式")
    for key in ("prompt", "request_id"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].strip():
            raise ValueError(f"音乐任务缺少有效 {key}")
    if not isinstance(snapshot.get("parameters"), dict) or not isinstance(snapshot.get("inputs"), dict):
        raise ValueError("音乐参数与输入必须是对象")
    validate_input_contract(snapshot, capability)
    params = {key: value for key, value in snapshot["parameters"].items() if value is not None and value != ""}
    lyrics = params.get("lyrics", "")
    if not isinstance(lyrics, str):
        raise ValueError("歌词必须是文本")
    if mode == "song" and not lyrics.strip():
        raise ValueError("歌曲需要非空歌词")
    if mode == "instrumental" and lyrics.strip():
        raise ValueError("纯器乐模式不能包含歌词")
    defaults = {field["key"]: field["default"] for field in capability["fields"] if "default" in field}
    values = {**defaults, **params}
    seed = values["seed"] if "seed" in values else secrets.randbelow(2**53)
    models = {key: values[key] for key in DEFAULT_MODELS}
    normalized = {
        "request_id": snapshot["request_id"], "mode": mode, "caption": snapshot["prompt"],
        "lyrics": lyrics, "max_duration": values["max_duration"], "seed": seed,
        "steps": values["steps"], "cfg": values["cfg"], "text_cfg": values["text_cfg"],
        "top_k": values["top_k"], "tiled_decode": values["tiled_decode"], **models,
    }
    prefix = hashlib.sha256(snapshot["request_id"].encode()).hexdigest()[:24]
    decode_type = "VAEDecodeAudioTiled" if normalized["tiled_decode"] else "VAEDecodeAudio"
    decode_inputs: dict[str, Any] = {"samples": ["7", 0], "vae": ["3", 0]}
    if normalized["tiled_decode"]:
        decode_inputs.update(tile_size=1536, overlap=64)
    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": models["unet_name"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": models["clip_name"], "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": models["vae_name"]}},
        "4": {"class_type": "MiniMaxMusic3TextEncode", "inputs": {
            "clip": ["2", 0], "caption": snapshot["prompt"], "lyrics": lyrics, "seed": seed,
            "max_duration": values["max_duration"], "cfg_scale": values["text_cfg"], "top_k": values["top_k"],
        }},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyMiniMaxMusic3LatentAudio", "inputs": {"seconds": ["4", 1], "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["6", 0], "seed": seed, "steps": values["steps"],
            "cfg": values["cfg"], "sampler_name": "euler", "scheduler": "simple", "denoise": 1,
        }},
        "8": {"class_type": decode_type, "inputs": decode_inputs},
        "9": {"class_type": "SaveAudio", "inputs": {
            "audio": ["8", 0], "filename_prefix": f"canvas/music/{prefix}/music",
        }},
    }
    return workflow, normalized


def preflight(workflow: dict[str, Any], workflow_path: Path, session) -> None:
    for folder, key in (("diffusion_models", "unet_name"), ("text_encoders", "clip_name"), ("vae", "vae_name")):
        chosen = workflow[{"unet_name": "1", "clip_name": "2", "vae_name": "3"}[key]]["inputs"][key]
        if chosen not in set(transport.model_files(session, folder)):
            raise transport.ExecutorError(f"本机 Music 3 模型文件未就绪：{folder}/{chosen}")
    transport.preflight_workflow(workflow, workflow_path, session)


def materialize_audio(result, output_dir: Path, _config, normalized: dict[str, Any]) -> dict[str, Any]:
    refs = [ref for ref in result.outputs
            if ref.file_type in {"output", "absolute"} and Path(ref.filename).suffix.lower() == ".flac"]
    if len(refs) != 1:
        raise ValueError("Music 3 必须返回唯一 FLAC 音频")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "music.flac"
    if target.exists():
        raise ValueError("目标音乐文件已存在，停止覆盖")
    with tempfile.TemporaryDirectory(prefix=".music-", dir=output_dir) as temporary:
        candidate = Path(temporary) / "music.flac"
        shutil.copyfile(Path(refs[0].filename).resolve(strict=True), candidate)
        metadata = probe_audio(candidate)
        if metadata["codec"] != "flac" or metadata["duration_ms"] <= 0:
            raise ValueError("Music 3 输出不是有效 FLAC")
        candidate.replace(target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(target.resolve()), "kind": "audio", "name": "音乐.flac",
            "metadata": {**metadata, "sha256": digest, "seed": normalized["seed"],
                         "listening_status": "INCONCLUSIVE"}}


def execute_snapshot(snapshot, output_dir: Path, config, *, emit=None) -> dict[str, Any]:
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        emit({"stage": stage})
        workflow, normalized = prepare_workflow(snapshot)
        from lfo.comfy.admission import VideoSubmissionGuard

        output_dir.mkdir(parents=True, exist_ok=True)
        with VideoSubmissionGuard(config.base_url, request_id=normalized["request_id"]) as guard, transport.ready_session(config) as session:
            workflow_path = output_dir / "workflow.json"
            if (output_dir / "conditions.json").exists() or workflow_path.exists():
                raise ValueError("音乐请求已有冻结输入或工作流，停止覆盖和重复提交")
            with (output_dir / "conditions.json").open("x", encoding="utf-8") as stream:
                json.dump(normalized, stream, ensure_ascii=False, indent=2)
            with workflow_path.open("x", encoding="utf-8") as stream:
                json.dump(workflow, stream, ensure_ascii=False, indent=2)
            preflight(workflow, workflow_path, session)
            stage = "submit"
            emit({"stage": stage})
            result = transport.run_workflow(workflow_path, output_dir, config, session, guard=guard, emit=emit)
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_audio(result, output_dir, config, normalized)
        receipt = {
            "kind": "minimax-music-delivery.v1", "created_at": datetime.now(UTC).isoformat(),
            "request_id": normalized["request_id"], "provider_task_id": result.provider_task_id,
            "config": normalized, "output": output, "listening_status": "INCONCLUSIVE",
        }
        with (output_dir / "music.flac.json").open("x", encoding="utf-8") as stream:
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
    parser = argparse.ArgumentParser(description="Internal Canvas Music 3 worker adapter")
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
