"""Execute a frozen Canvas Qwen Image 2.1 request, without an agent host."""

# ruff: noqa: RUF001 -- Chinese interface messages use Chinese punctuation.

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-image-executor"


def inspect_image(path: Path) -> dict[str, Any]:
    """Fully decode one static image; do not trust its suffix or header alone."""
    probe = subprocess.run(
        [
            os.environ.get("LFO_FFPROBE") or "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if probe.returncode:
        raise ValueError(f"图片无法读取：{path.name}")
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") not in {"png", "mjpeg", "webp", "bmp"}:
        raise ValueError("参考素材须为静态 PNG、JPEG、WebP 或 BMP 图片")
    info = streams[0]
    width, height = int(info.get("width", 0)), int(info.get("height", 0))
    if min(width, height) < 1 or width * height > 32_000_000:
        raise ValueError("图片尺寸无效或超过 3200 万像素")
    decoded = subprocess.run(
        [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "pipe:1",
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if decoded.returncode or len(decoded.stdout) != width * height * 4:
        raise ValueError(f"图片解码失败：{path.name}")
    alpha = decoded.stdout[3::4]
    alpha_format = str(info.get("pix_fmt", ""))
    has_alpha = "a" in alpha_format or alpha_format == "pal8"
    return {
        "width": width,
        "height": height,
        "codec": info["codec_name"],
        "has_alpha": has_alpha,
        "has_transparency": min(alpha) < 255,
        "has_visible_pixels": max(alpha) > 0,
        "alpha_min": min(alpha),
        "alpha_max": max(alpha),
    }


def aligned(value: float) -> int:
    return max(32, round(value / 32) * 32)


def normalize_snapshot(snapshot: dict[str, Any], *, inspect_fn=None) -> dict[str, Any]:
    inspect_fn = inspect_fn or inspect_image
    cap = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("图片运行快照必须是对象")
    if (snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model")) != (
        "image",
        "comfy-qwen-image",
        "qwen-image-2.1",
    ):
        raise ValueError("不是已选择 Qwen 2.1 的图片任务")
    if snapshot.get("mode") not in {"create", "reference", "edit"}:
        raise ValueError("请选择文生图、图片参考生成或图片编辑")
    prompt = snapshot.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("图片提示词不能为空")
    if not isinstance(snapshot.get("parameters"), dict) or not isinstance(
        snapshot.get("inputs"), dict
    ):
        raise ValueError("图片参数与输入必须是对象")
    validate_input_contract(snapshot, cap)
    params = {key: value for key, value in snapshot["parameters"].items() if value is not None and value != ""}
    refs = snapshot["inputs"].get("reference_images", [])
    if not isinstance(refs, list):
        raise ValueError("参考图片必须是有序数组")
    for marker in re.findall(r"<image(\d+)>", prompt):
        if not 1 <= int(marker) <= len(refs):
            raise ValueError(f"提示词中的 <image{marker}> 没有对应输入")
    paths, infos = [], []
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or ref.get("kind") != "image"
            or not isinstance(ref.get("path"), str)
        ):
            raise ValueError("参考素材必须是实际图片文件")
        path = Path(ref["path"]).resolve()
        if not path.is_file():
            raise ValueError(f"参考图片不存在：{path.name}")
        infos.append(inspect_fn(path))
        paths.append(path)
    resolution = int(params.get("reference_resolution", 0))
    if resolution % 32:
        raise ValueError("参考图像素预算边长必须为 32 的倍数或 0")
    if snapshot["mode"] == "edit":
        w, h = infos[0]["width"], infos[0]["height"]
        width = aligned(math.sqrt(resolution**2 * w / h)) if resolution else aligned(w)
        height = aligned(math.sqrt(resolution**2 * h / w)) if resolution else aligned(h)
    else:
        left, right = map(int, params["aspect_ratio"].split(":"))
        pixels = params["megapixels"] * 1024 * 1024
        width, height = (
            aligned(math.sqrt(pixels * left / right)),
            aligned(math.sqrt(pixels * right / left)),
        )
    request_id = snapshot.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("执行需要画布 request_id")
    return {
        "mode": snapshot["mode"],
        "prompt": prompt,
        "paths": paths,
        "width": width,
        "height": height,
        "reference_resolution": resolution,
        "seed": int(params.get("seed", secrets.randbelow(2**53))),
        "steps": int(params.get("steps", 25)),
        "transparent": params.get("transparent", False),
        "request_id": request_id,
    }


def prepare_workflow(snapshot, *, uploader, inspect_fn=None):
    normalized = normalize_snapshot(snapshot, inspect_fn=inspect_fn)
    workflow = json.loads(
        (SKILL_ROOT / "templates/qwen_image_2_1.json").read_text(encoding="utf-8")
    )
    workflow["4"]["inputs"].update(
        prompt=normalized["prompt"], resolution=normalized["reference_resolution"]
    )
    workflow["5"]["inputs"].update(width=normalized["width"], height=normalized["height"])
    workflow["6"]["inputs"].update(seed=normalized["seed"], steps=normalized["steps"])
    prefix = hashlib.sha256(normalized["request_id"].encode()).hexdigest()[:24]
    workflow["8"]["inputs"]["filename_prefix"] = f"canvas/qwen/{prefix}/image"
    if not normalized["paths"]:
        # Explicit empty V3 autogrow group also satisfies comfy-cli 1.13 validation.
        workflow["4"]["inputs"]["images"] = {}
    if normalized["paths"]:
        workflow["9"] = {
            "class_type": "QwenImage21Cache",
            "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"},
        }
        workflow["6"]["inputs"]["model"] = ["9", 0]
        workflow["4"]["inputs"]["vae"] = ["3", 0]
    for index, path in enumerate(normalized["paths"], 1):
        node_id = str(10 + index)
        workflow[node_id] = {"class_type": "LoadImage", "inputs": {"image": uploader(path)}}
        workflow["4"]["inputs"][f"images.image_{index}"] = [node_id, 0]
    if normalized["mode"] == "edit":
        workflow["6"]["inputs"]["latent_image"] = ["4", 2]
    return workflow, normalized


def materialize_image(result, output_dir, config, normalized):
    refs = [
        r
        for r in result.outputs
        if r.file_type in {"output", "absolute"} and Path(r.filename).suffix.lower() == ".png"
    ]
    if len(refs) != 1:
        raise ValueError("Qwen 必须返回唯一 PNG 图片")
    ref = refs[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "image.png"
    with tempfile.TemporaryDirectory(prefix=".image-", dir=output_dir) as temporary:
        candidate = Path(temporary) / "candidate.png"
        if ref.file_type == "absolute":
            source = Path(ref.filename).resolve()
            if source != candidate.resolve():
                shutil.copyfile(source, candidate)
        else:
            transport._download_view(config.base_url, ref, candidate, config.timeout_seconds)
        metadata = inspect_image(candidate)
        if metadata.get("codec") != "png":
            raise ValueError("实际输出不是 PNG 图片")
        if (metadata["width"], metadata["height"]) != (normalized["width"], normalized["height"]):
            raise ValueError("实际图片尺寸与本次请求不符")
        if normalized["transparent"] and not (
            metadata.get("has_alpha")
            and metadata.get("has_transparency")
            and metadata.get("has_visible_pixels")
            and metadata.get("alpha_min", 255) <= 16
            and metadata.get("alpha_max", 0) >= 239
        ):
            raise ValueError("本次要求透明背景，但结果没有可用的透明主体")
        candidate.replace(target)
    metadata.update(seed=normalized.get("seed"), steps=normalized.get("steps"))
    return {
        "path": str(target.resolve()),
        "kind": "image",
        "name": target.name,
        "metadata": metadata,
    }


def execute_snapshot(snapshot, output_dir, config, *, emit=None):
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        emit({"stage": stage})
        # Validate and preflight all nodes/models before uploading any input.
        workflow, normalized = prepare_workflow(snapshot, uploader=lambda p: p.name)
        transport.preflight_workflow(workflow, config)
        output_dir.mkdir(parents=True, exist_ok=True)
        stage = "upload"
        emit({"stage": stage})
        upload = transport._http_uploader(config.base_url, config.timeout_seconds)
        for index, path in enumerate(normalized["paths"], 1):
            workflow[str(10 + index)]["inputs"]["image"] = upload(path)
        workflow_path = output_dir / "workflow.json"
        workflow_path.write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        conditions = {key: value for key, value in normalized.items() if key != "paths"}
        conditions["references"] = [
            {"index": i, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for i, p in enumerate(normalized["paths"], 1)
        ]
        (output_dir / "conditions.json").write_text(
            json.dumps(conditions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        stage = "submit"
        emit({"stage": stage})
        result = transport.run_comfy_cli(
            workflow_path, config, emit=emit, request_id=normalized["request_id"]
        )
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_image(result, output_dir, config, normalized)
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
        if result:
            exc.provider_task_id = result.provider_task_id
        raise exc


def main(argv=None):
    parser = argparse.ArgumentParser(description="Execute one confirmed Canvas Qwen image request")
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
