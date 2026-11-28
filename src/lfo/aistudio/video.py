"""Execute a frozen Canvas AI Studio (Gemini Omni) video request."""

# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from lfo.aistudio.client import AIStudioClient, AIStudioConfig, ExecutorError, load_runtime_config
from lfo.aistudio.media_utils import inspect_static_image, materialize_mp4
from lfo.canvas.input_contract import validate_input_contract

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents" / "skills" / "aistudio-video-executor"
MODE_TO_VIDEO_TASK = {
    "t2v": "text_to_video",
    "i2v": "image_to_video",
    "r2v": "reference_to_video",
}


def load_capability() -> dict[str, Any]:
    return json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))


def _read_verified_image(entry: Any, label: str, inspect_fn) -> dict[str, Any]:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError(f"{label}缺少有效文件路径")
    path = Path(entry["path"]).expanduser().resolve()
    meta, mime_type = inspect_fn(path)
    raw_bytes = path.read_bytes()
    return {
        "path": path,
        "mime_type": mime_type,
        "bytes": raw_bytes,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "width": meta["width"],
        "height": meta["height"],
    }


def normalize_snapshot(
    snapshot: dict[str, Any],
    *,
    inspect_fn=inspect_static_image,
) -> dict[str, Any]:
    if snapshot.get("node_type") != "video":
        raise ValueError("AI Studio 视频执行器仅处理 video 节点")
    capability = load_capability()
    valid_models = {item["id"] for item in capability.get("models", [])}
    model = str(snapshot.get("model") or "").strip()
    if model not in valid_models:
        raise ValueError(f"不支持的 AI Studio 视频模型：{model or '<未选择>'}")
    mode = str(snapshot.get("mode") or "").strip()
    valid_modes = {item["id"] for item in capability.get("modes", [])}
    if mode not in valid_modes:
        raise ValueError(f"AI Studio 视频不支持模式 {mode or '<未选择>'}（仅支持 t2v / i2v / r2v）")

    validate_input_contract(snapshot, capability)

    prompt = str(snapshot.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("请填写视频提示词")
    request_id = str(snapshot.get("request_id") or "").strip()
    if not request_id:
        raise ValueError("执行需要画布 request_id")

    params = snapshot.get("parameters") or {}
    duration = int(params["duration"])
    if model == "gemini-omni-1.1-flash" and duration > 10:
        raise ValueError("Gemini Omni 1.1 Flash 最长仅支持 10 秒视频，请改选 Omni 1.2 Flash 或缩短时长")
    aspect_ratio = str(params["aspect_ratio"]).strip()
    resolution = str(params.get("resolution") or "1080p").strip()

    inputs = snapshot.get("inputs") or {}
    first_frame = None
    if inputs.get("first_frame") is not None:
        first_frame = _read_verified_image(inputs["first_frame"], "首帧", inspect_fn)

    references: list[dict[str, Any]] = []
    for item in inputs.get("reference_images") or []:
        references.append(_read_verified_image(item, "参考图片", inspect_fn))

    return {
        "request_id": request_id,
        "model": model,
        "mode": mode,
        "video_task": MODE_TO_VIDEO_TASK[mode],
        "prompt": prompt,
        "duration_seconds": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "first_frame": first_frame,
        "references": references,
    }


def reconcile_operation(
    operation_id: str,
    output_dir: Path,
    config: AIStudioConfig,
    *,
    request_id: str | None = None,
    client: AIStudioClient | None = None,
    materialize_fn=materialize_mp4,
) -> dict[str, Any]:
    """Query an existing AIStudio2API video operation without submitting a new job."""
    api = client or AIStudioClient(config)
    state = api.get_video_operation(operation_id)
    if state.status in {"queued", "in_progress", "processing"}:
        return {
            "status": "unknown",
            "remote_status": state.status,
            "provider_task_id": state.operation_id,
        }
    if state.status == "failed":
        if state.error_code == "video_not_found":
            return {
                "status": "unknown",
                "remote_status": "missing_history",
                "provider_task_id": state.operation_id,
                "error": state.error_message or "本地代理丢失了任务历史，远端终态未知",
            }
        detail = state.error_message or state.error_code or "远端视频生成失败"
        return {
            "status": "failed",
            "remote_status": "failed",
            "provider_task_id": state.operation_id,
            "error": detail,
            "evidence": (
                {
                    "request_id": request_id,
                    "remote_status": "failed",
                    "source": "provider_history",
                    "reason": f"AIStudio2API 原任务 {state.operation_id} 已失败：{detail}",
                }
                if request_id
                else None
            ),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".aistudio-vid-", dir=output_dir) as tmp:
        candidate = Path(tmp) / "downloaded.mp4"
        api.download_video(state.operation_id, candidate)
        output = materialize_fn(
            candidate,
            output_dir,
            extra_metadata={"model": state.model, "provider_task_id": state.operation_id},
        )
    return {
        "status": "succeeded",
        "remote_status": "succeeded",
        "provider_task_id": state.operation_id,
        "outputs": [output],
        "evidence": (
            {
                "request_id": request_id,
                "remote_status": "succeeded",
                "source": "provider_history",
                "reason": f"已从 AIStudio2API 取回原视频任务 {state.operation_id} 的已完成产物",
            }
            if request_id
            else None
        ),
    }


def execute_snapshot(
    snapshot: dict[str, Any],
    output_dir: Path,
    config: AIStudioConfig,
    *,
    emit=None,
    client: AIStudioClient | None = None,
    inspect_fn=inspect_static_image,
    materialize_fn=materialize_mp4,
) -> dict[str, Any]:
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage = "input_validation"
    operation_id: str | None = None

    try:
        emit({"stage": stage})
        normalized = normalize_snapshot(snapshot, inspect_fn=inspect_fn)

        stage = "preflight"
        emit({"stage": stage})
        api = client or AIStudioClient(config)
        catalog = api.list_models()
        model_info = catalog.get(normalized["model"])
        if model_info is None:
            raise ExecutorError(
                f"本机 AIStudio2API 当前模型目录不含 {normalized['model']}，请检查登录账户权益",
                status="failed",
                stage=stage,
            )
        options = model_info.get("capability_options") if isinstance(model_info, dict) else None
        if isinstance(options, dict):
            tasks = options.get("video_tasks")
            if isinstance(tasks, list) and tasks and normalized["video_task"] not in tasks:
                raise ExecutorError(
                    f"模型 {normalized['model']} 不支持视频任务 {normalized['video_task']}",
                    status="failed",
                    stage=stage,
                )
            ratios = options.get("video_aspect_ratios")
            if isinstance(ratios, list) and ratios and normalized["aspect_ratio"] not in ratios:
                raise ExecutorError(
                    f"模型 {normalized['model']} 不支持画幅比例 {normalized['aspect_ratio']}",
                    status="failed",
                    stage=stage,
                )
            resolutions = options.get("video_output_resolutions")
            if isinstance(resolutions, list) and resolutions and normalized["resolution"] not in resolutions:
                raise ExecutorError(
                    f"模型 {normalized['model']} 不支持输出分辨率 {normalized['resolution']}",
                    status="failed",
                    stage=stage,
                )

        output_dir.mkdir(parents=True, exist_ok=True)
        conditions = {
            "request_id": normalized["request_id"],
            "model": normalized["model"],
            "mode": normalized["mode"],
            "video_task": normalized["video_task"],
            "prompt": normalized["prompt"],
            "duration_seconds": normalized["duration_seconds"],
            "aspect_ratio": normalized["aspect_ratio"],
            "resolution": normalized["resolution"],
            "first_frame": (
                {
                    "sha256": normalized["first_frame"]["sha256"],
                    "mime_type": normalized["first_frame"]["mime_type"],
                    "width": normalized["first_frame"]["width"],
                    "height": normalized["first_frame"]["height"],
                }
                if normalized["first_frame"] is not None
                else None
            ),
            "references": [
                {
                    "index": index,
                    "sha256": item["sha256"],
                    "mime_type": item["mime_type"],
                    "width": item["width"],
                    "height": item["height"],
                }
                for index, item in enumerate(normalized["references"], 1)
            ],
        }
        (output_dir / "conditions.json").write_text(
            json.dumps(conditions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        stage = "submit"
        emit({"stage": stage})
        operation_id = api.submit_video(
            model=normalized["model"],
            prompt=normalized["prompt"],
            first_frame=(
                (normalized["first_frame"]["mime_type"], normalized["first_frame"]["bytes"])
                if normalized["first_frame"] is not None
                else None
            ),
            reference_images=[(item["mime_type"], item["bytes"]) for item in normalized["references"]],
            aspect_ratio=normalized["aspect_ratio"],
            duration_seconds=normalized["duration_seconds"],
            resolution=normalized["resolution"],
        )
        (output_dir / "submission.json").write_text(
            json.dumps(
                {"request_id": normalized["request_id"], "provider_task_id": operation_id},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        emit({"stage": "polling", "provider_task_id": operation_id})
        stage = "polling"
        api.wait_for_video(operation_id)

        stage = "collection"
        emit({"stage": stage, "provider_task_id": operation_id})
        with tempfile.TemporaryDirectory(prefix=".aistudio-vid-", dir=output_dir) as tmp:
            candidate = Path(tmp) / "downloaded.mp4"
            api.download_video(operation_id, candidate)
            emit({"stage": "media_validation", "remote_finished": True, "provider_task_id": operation_id})
            stage = "media_validation"
            output = materialize_fn(
                candidate,
                output_dir,
                extra_metadata={
                    "model": normalized["model"],
                    "requested_duration_seconds": normalized["duration_seconds"],
                    "requested_resolution": normalized["resolution"],
                    "provider_task_id": operation_id,
                },
            )

        return {
            "status": "succeeded",
            "stage": "media_validation",
            "outputs": [output],
            "provider_task_id": operation_id,
        }
    except Exception as exc:
        if not isinstance(exc, ExecutorError):
            inferred_status = (
                "unknown"
                if stage in {"submit", "polling", "collection"} and stage != "media_validation"
                else "failed"
            )
            exc = ExecutorError(str(exc), provider_task_id=operation_id, status=inferred_status)
        exc.stage = stage
        if operation_id and not exc.provider_task_id:
            exc.provider_task_id = operation_id
        raise exc


def main(argv: list[str] | None = None, *, executor=None) -> int:
    parser = argparse.ArgumentParser(description="Execute one confirmed Canvas AI Studio video request")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        config = load_runtime_config()
        result = (executor or execute_snapshot)(snapshot, args.output_dir, config)
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
