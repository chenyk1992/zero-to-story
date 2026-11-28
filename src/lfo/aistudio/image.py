"""Execute a frozen Canvas AI Studio (Nano Banana) image request."""

# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lfo.aistudio.client import AIStudioClient, AIStudioConfig, ExecutorError, load_runtime_config
from lfo.aistudio.media_utils import inspect_static_image, materialize_png
from lfo.canvas.input_contract import validate_input_contract

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents" / "skills" / "aistudio-image-executor"


def load_capability() -> dict[str, Any]:
    return json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))


def normalize_snapshot(
    snapshot: dict[str, Any],
    *,
    inspect_fn=inspect_static_image,
) -> dict[str, Any]:
    if snapshot.get("node_type") != "image":
        raise ValueError("AI Studio 生图执行器仅处理 image 节点")
    capability = load_capability()
    valid_models = {item["id"] for item in capability.get("models", [])}
    model = str(snapshot.get("model") or "").strip()
    if model not in valid_models:
        raise ValueError(f"不支持的 AI Studio 图片模型：{model or '<未选择>'}")
    mode = str(snapshot.get("mode") or "").strip()
    valid_modes = {item["id"] for item in capability.get("modes", [])}
    if mode not in valid_modes:
        raise ValueError(f"不支持的生图模式：{mode or '<未选择>'}")

    validate_input_contract(snapshot, capability)

    prompt = str(snapshot.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("请填写图片提示词")
    request_id = str(snapshot.get("request_id") or "").strip()
    if not request_id:
        raise ValueError("执行需要画布 request_id")

    params = snapshot.get("parameters") or {}
    raw_aspect = params.get("aspect_ratio")
    aspect_ratio = str(raw_aspect).strip() if raw_aspect is not None and str(raw_aspect).strip() else None
    if mode in {"create", "reference"} and not aspect_ratio:
        aspect_ratio = "1:1"
    resolution = str(params.get("resolution") or "2K").strip()

    raw_refs = (snapshot.get("inputs") or {}).get("reference_images") or []
    references: list[dict[str, Any]] = []
    for item in raw_refs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("参考图片缺少有效文件路径")
        ref_path = Path(item["path"]).expanduser().resolve()
        meta, mime_type = inspect_fn(ref_path)
        raw_bytes = ref_path.read_bytes()
        references.append(
            {
                "path": ref_path,
                "mime_type": mime_type,
                "bytes": raw_bytes,
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "width": meta["width"],
                "height": meta["height"],
            }
        )

    return {
        "request_id": request_id,
        "model": model,
        "mode": mode,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "references": references,
    }


def execute_snapshot(
    snapshot: dict[str, Any],
    output_dir: Path,
    config: AIStudioConfig,
    *,
    emit=None,
    client: AIStudioClient | None = None,
    inspect_fn=inspect_static_image,
    materialize_fn=materialize_png,
) -> dict[str, Any]:
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage = "input_validation"
    provider_task_id: str | None = None

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
            allowed_ratios = options.get("image_aspect_ratios")
            if (
                isinstance(allowed_ratios, list)
                and allowed_ratios
                and normalized["aspect_ratio"]
                and normalized["aspect_ratio"] not in allowed_ratios
            ):
                raise ExecutorError(
                    f"模型 {normalized['model']} 不支持画幅比例 {normalized['aspect_ratio']}",
                    status="failed",
                    stage=stage,
                )
            allowed_res = options.get("image_output_resolutions")
            if (
                isinstance(allowed_res, list)
                and allowed_res
                and normalized["resolution"] not in allowed_res
            ):
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
            "prompt": normalized["prompt"],
            "aspect_ratio": normalized["aspect_ratio"],
            "resolution": normalized["resolution"],
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
        generated = api.generate_image(
            model=normalized["model"],
            prompt=normalized["prompt"],
            reference_images=[(item["mime_type"], item["bytes"]) for item in normalized["references"]],
            aspect_ratio=normalized["aspect_ratio"],
            resolution=normalized["resolution"],
        )
        provider_task_id = generated.provider_task_id

        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": provider_task_id})
        output = materialize_fn(
            generated.data,
            generated.mime_type,
            output_dir,
            extra_metadata={
                "model": normalized["model"],
                "resolution": normalized["resolution"],
                "source_mime_type": generated.mime_type,
            },
        )
        return {
            "status": "succeeded",
            "stage": "media_validation",
            "outputs": [output],
            "provider_task_id": provider_task_id,
        }
    except Exception as exc:
        if not isinstance(exc, ExecutorError):
            # After remote_finished in collection/materialization, keep status="failed" so invalid media fails cleanly.
            inferred_status = "unknown" if stage == "submit" and provider_task_id is None else "failed"
            exc = ExecutorError(str(exc), provider_task_id=provider_task_id, status=inferred_status)
        exc.stage = stage
        if provider_task_id and not exc.provider_task_id:
            exc.provider_task_id = provider_task_id
        raise exc


def main(argv: list[str] | None = None, *, executor=None) -> int:
    parser = argparse.ArgumentParser(description="Execute one confirmed Canvas AI Studio image request")
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
