"""Canvas adapter for local MiniMax H3 Image; no implicit prompt rewriting."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import qwen_image
from lfo.comfy.qwen_image import aligned, inspect_image

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-h3-image-executor"


def normalize_snapshot(snapshot: dict[str, Any], *, inspect_fn=None) -> dict[str, Any]:
    inspect_fn = inspect_fn or inspect_image
    cap = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("图片运行快照必须是对象")
    if (snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model")) != (
        "image",
        "comfy-h3-image",
        "minimax-h3-image",
    ):
        raise ValueError("不是已选择 MiniMax H3 Image 的图片任务")
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
    params = {
        key: value
        for key, value in snapshot["parameters"].items()
        if value is not None and value != ""
    }
    refs = snapshot["inputs"].get("reference_images", [])
    if not isinstance(refs, list):
        raise ValueError("参考图片必须是有序数组")
    for marker in re.findall(r"<Picture (\d+)>", prompt):
        if not 1 <= int(marker) <= len(refs):
            raise ValueError(f"提示词中的 <Picture {marker}> 没有对应输入")
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
    pixels = params["megapixels"] * 1024 * 1024
    if snapshot["mode"] == "edit":
        left, right = infos[0]["width"], infos[0]["height"]
    else:
        left, right = map(int, params["aspect_ratio"].split(":"))
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
        "seed": int(params.get("seed", secrets.randbelow(2**53))),
        "steps": int(params.get("steps", 6)),
        "transparent": params.get("transparent", False),
        "request_id": request_id,
    }


def prepare_workflow(snapshot, *, uploader, inspect_fn=None):
    normalized = normalize_snapshot(snapshot, inspect_fn=inspect_fn)
    workflow = json.loads((SKILL_ROOT / "templates/h3_image.json").read_text(encoding="utf-8"))
    workflow["4"]["inputs"].update(
        prompt=normalized["prompt"], width=normalized["width"], height=normalized["height"]
    )
    workflow["6"]["inputs"].update(seed=normalized["seed"], steps=normalized["steps"])
    prefix = hashlib.sha256(normalized["request_id"].encode()).hexdigest()[:24]
    workflow["8"]["inputs"]["filename_prefix"] = f"canvas/h3-image/{prefix}/image"
    if not normalized["paths"]:
        workflow["4"]["inputs"]["images"] = {}
    for index, path in enumerate(normalized["paths"], 1):
        node_id = str(10 + index)
        workflow[node_id] = {"class_type": "LoadImage", "inputs": {"image": uploader(path)}}
        workflow["4"]["inputs"][f"images.image_{index}"] = [node_id, 0]
    return workflow, normalized


def execute_snapshot(snapshot, output_dir, config, *, emit=None):
    return qwen_image.execute_snapshot(
        snapshot, output_dir, config, emit=emit, prepare_fn=prepare_workflow
    )


def main(argv=None):
    return qwen_image.main(argv, executor=execute_snapshot)
