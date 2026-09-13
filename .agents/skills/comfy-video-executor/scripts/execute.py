"""Execute one confirmed canvas video snapshot through local ComfyUI.

The adapter keeps a narrow provider boundary: local ComfyUI HTTP, the official
``comfy run`` CLI, and the project's shared admission and media-probe helpers.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import pathlib
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "templates"
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})
MODES = frozenset({"t2v", "i2v", "fl2v", "r2v"})
PROFILES = frozenset({"native", "vdn_turbo"})
ASPECT_LABELS = {
    "1:1": "1:1 (Square)",
    "2:3": "2:3 (Portrait Photo)",
    "3:2": "3:2 (Photo)",
    "3:4": "3:4 (Portrait Standard)",
    "4:3": "4:3 (Standard)",
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Widescreen)",
    "21:9": "21:9 (Ultrawide)",
}
REFERENCE_LIMITS = {"image": 9, "video": 3, "audio": 3}
ADVANCED_KEYS = frozenset(
    {"sampler_profile", "steps", "seed", "fps", "reference_image_size"}
)
PROCESS_EXIT_GRACE_SECONDS = 300.0
DYNAMIC_MEDIA_INPUTS = {
    "LoadImage": frozenset({"image"}),
    "LoadVideo": frozenset({"video"}),
    "LoadAudio": frozenset({"audio"}),
}


try:
    from lfo.media._ffmpeg import probe as _project_probe
except ImportError:  # pragma: no cover - direct standalone invocation fallback
    _project_probe = None


class ExecutorError(RuntimeError):
    """A terminal, non-retryable adapter error."""

    def __init__(
        self,
        message: str,
        *,
        provider_task_id: str | None = None,
        status: str = "failed",
    ) -> None:
        super().__init__(message)
        self.provider_task_id = provider_task_id
        if status not in {"failed", "unknown"}:
            raise ValueError(f"unsupported executor error status: {status}")
        self.status = status


@dataclass(frozen=True)
class RuntimeConfig:
    base_url: str = "http://127.0.0.1:8188"
    cli_binary: str = "comfy"
    timeout_seconds: float = 7_200.0
    output_root: pathlib.Path | None = None


@dataclass(frozen=True)
class OutputRef:
    filename: str
    subfolder: str = ""
    file_type: str = "output"
    url: str | None = None


@dataclass(frozen=True)
class CliResult:
    provider_task_id: str
    outputs: tuple[OutputRef, ...]
    events: tuple[dict[str, Any], ...]


Uploader = Callable[[pathlib.Path], str]


def _read_json(path: pathlib.Path, *, explicit: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if explicit:
            raise ExecutorError(f"Comfy config file does not exist: {path}")
        return None
    if not path.is_file():
        raise ExecutorError(f"Comfy config path is not a file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"Could not read Comfy config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExecutorError(f"Comfy config must be a JSON object: {path}")
    return value


def _safe_config_values(value: dict[str, Any]) -> dict[str, Any]:
    """Keep only provider connection fields; never expose unrelated settings."""
    comfy = value.get("comfyui")
    comfy = comfy if isinstance(comfy, dict) else {}
    storage = value.get("storage")
    storage = storage if isinstance(storage, dict) else {}
    result: dict[str, Any] = {}
    for key in ("base_url", "cli"):
        candidate = comfy.get(key, value.get(key))
        if candidate is not None:
            result[key] = candidate
    timeout = comfy.get(
        "timeout_seconds",
        comfy.get("timeout_sec", value.get("timeout_seconds", value.get("timeout_sec"))),
    )
    if timeout is not None:
        result["timeout_seconds"] = timeout
    output_root = (
        comfy.get("output_root")
        or storage.get("comfy_output")
        or value.get("output_root")
    )
    if output_root is not None:
        result["output_root"] = output_root
    return result


def _merge_runtime_values(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in _safe_config_values(source).items():
        target[key] = value


def load_runtime_config(
    *,
    config_path: pathlib.Path | None = None,
    machine_id: str | None = None,
    base_url: str | None = None,
    cli_binary: str | None = None,
    timeout_seconds: float | None = None,
) -> RuntimeConfig:
    """Resolve only safe Comfy connection settings.

    Existing LFO config is read opportunistically but no LFO module is
    imported.  Explicit command-line values have the final say.
    """
    values: dict[str, Any] = {}
    appdata = os.environ.get("APPDATA")
    if appdata:
        global_path = pathlib.Path(appdata) / "LFO" / "config.json"
        global_config = _read_json(global_path)
        if global_config is not None:
            _merge_runtime_values(values, global_config)
        selected_machine = machine_id or os.environ.get("LFO_MACHINE_ID")
        if selected_machine:
            machine_path = pathlib.Path(appdata) / "LFO" / "machines" / f"{selected_machine}.json"
            machine_config = _read_json(machine_path)
            if machine_config is not None:
                _merge_runtime_values(values, machine_config)
    if config_path is not None:
        explicit_config = _read_json(config_path, explicit=True)
        assert explicit_config is not None
        _merge_runtime_values(values, explicit_config)

    env_values = {
        "base_url": os.environ.get("LFO_COMFY_BASE_URL"),
        "cli": os.environ.get("LFO_COMFY_CLI"),
        "timeout_seconds": os.environ.get("LFO_COMFY_TIMEOUT"),
        "output_root": os.environ.get("LFO_COMFY_OUTPUT_ROOT"),
    }
    for key, value in env_values.items():
        if value:
            values[key] = value
    if base_url is not None:
        values["base_url"] = base_url
    if cli_binary is not None:
        values["cli"] = cli_binary
    if timeout_seconds is not None:
        values["timeout_seconds"] = timeout_seconds

    resolved_url = str(values.get("base_url") or "http://127.0.0.1:8188")
    resolved_cli = str(values.get("cli") or "comfy")
    raw_timeout = values.get("timeout_seconds", 7_200.0)
    try:
        resolved_timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ExecutorError("Comfy timeout must be a positive finite number") from exc
    if not math.isfinite(resolved_timeout) or resolved_timeout <= 0:
        raise ExecutorError("Comfy timeout must be a positive finite number")
    output_value = values.get("output_root")
    return RuntimeConfig(
        base_url=resolved_url,
        cli_binary=resolved_cli,
        timeout_seconds=resolved_timeout,
        output_root=pathlib.Path(str(output_value)).expanduser() if output_value else None,
    )


def _number(value: object, *, field: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutorError(f"parameters.{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        suffix = f" >= {minimum:g}" if minimum is not None else " and finite"
        raise ExecutorError(f"parameters.{field} must be a finite number{suffix}")
    return result


def _integer(value: object, *, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExecutorError(f"parameters.{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ExecutorError(f"parameters.{field} must be >= {minimum}")
    return value


def _provider_parameters(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten provider options while rejecting conflicting duplicate values."""
    merged: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    for key in ("comfy", "comfy_options"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, dict):
                raise ExecutorError(f"parameters.{key} must be an object")
            sources.append(value)
    options = raw.get("options")
    if options is not None:
        if not isinstance(options, dict):
            raise ExecutorError("parameters.options must be an object")
        comfy = options.get("comfy")
        if comfy is not None:
            if not isinstance(comfy, dict):
                raise ExecutorError("parameters.options.comfy must be an object")
            sources.append(comfy)
    for source in sources:
        for key, value in source.items():
            if key in merged and merged[key] != value:
                raise ExecutorError(f"Conflicting Comfy values for parameters.{key}")
            merged[key] = value
    for key in ADVANCED_KEYS:
        if key in raw:
            if key in merged and merged[key] != raw[key]:
                raise ExecutorError(f"Conflicting Comfy values for parameters.{key}")
            merged[key] = raw[key]
    return merged


def _asset(value: object, *, field: str, expected_kind: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExecutorError(f"inputs.{field} must be an asset object")
    raw_path = value.get("path")
    kind = value.get("kind")
    if not isinstance(raw_path, str) or not raw_path:
        raise ExecutorError(f"inputs.{field}.path is required")
    if not isinstance(kind, str) or not kind:
        raise ExecutorError(f"inputs.{field}.kind is required")
    if expected_kind is not None and kind != expected_kind:
        raise ExecutorError(f"inputs.{field}.kind must be {expected_kind!r}")
    path = pathlib.Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise ExecutorError(f"inputs.{field} file is unavailable: {path}")
    return {"path": path, "kind": kind}


def _asset_list(value: object, *, field: str, kind: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ExecutorError(f"inputs.{field} must be an array")
    if len(value) > REFERENCE_LIMITS[kind]:
        raise ExecutorError(
            f"inputs.{field} supports at most {REFERENCE_LIMITS[kind]} {kind} references"
        )
    return [_asset(item, field=f"{field}[{index}]", expected_kind=kind) for index, item in enumerate(value)]


def normalize_snapshot(snapshot: object) -> dict[str, Any]:
    """Validate and normalize a confirmed video snapshot without side effects."""
    if not isinstance(snapshot, dict):
        raise ExecutorError("snapshot must be a JSON object")
    for key in ("node_id", "node_type", "provider", "model", "mode", "prompt", "parameters", "inputs"):
        if key not in snapshot:
            raise ExecutorError(f"snapshot.{key} is required")
    node_id = snapshot["node_id"]
    if not isinstance(node_id, str) or not node_id.strip():
        raise ExecutorError("snapshot.node_id must be a non-empty string")
    if snapshot["node_type"] != "video":
        raise ExecutorError("snapshot.node_type must be 'video'")
    if snapshot["provider"] != "comfy":
        raise ExecutorError("snapshot.provider must be 'comfy'")
    if snapshot["model"] != "h3":
        raise ExecutorError("Comfy executor supports model 'h3' only")
    mode = snapshot["mode"]
    if mode not in MODES:
        raise ExecutorError(f"Unsupported Comfy video mode: {mode!r}")
    prompt = snapshot["prompt"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise ExecutorError("snapshot.prompt must be a non-empty string")
    parameters = snapshot["parameters"]
    inputs = snapshot["inputs"]
    if not isinstance(parameters, dict):
        raise ExecutorError("snapshot.parameters must be an object")
    if not isinstance(inputs, dict):
        raise ExecutorError("snapshot.inputs must be an object")
    request_id = snapshot.get("request_id")
    if request_id is not None and (
        not isinstance(request_id, str) or not request_id.strip()
    ):
        raise ExecutorError("snapshot.request_id must be a non-empty string")

    provider = _provider_parameters(parameters)
    common: dict[str, Any] = {}
    duration = _number(parameters.get("duration"), field="duration", minimum=0.2)
    if duration > 15:
        raise ExecutorError("parameters.duration must be <= 15 seconds for H3")
    common["duration"] = duration
    aspect = parameters.get("aspect_ratio")
    if not isinstance(aspect, str) or aspect not in ASPECT_LABELS:
        raise ExecutorError(
            "parameters.aspect_ratio must be one of " + ", ".join(ASPECT_LABELS)
        )
    common["aspect_ratio"] = aspect
    common["megapixels"] = _number(parameters.get("megapixels"), field="megapixels", minimum=0.000001)

    profile = provider.get("sampler_profile")
    if profile not in PROFILES:
        raise ExecutorError("parameters.sampler_profile must be 'native' or 'vdn_turbo'")
    steps = _integer(provider.get("steps"), field="steps", minimum=8)
    if profile == "vdn_turbo" and steps != 8:
        raise ExecutorError("vdn_turbo requires exactly 8 sampling steps")
    provider["sampler_profile"] = profile
    provider["steps"] = steps
    if "seed" in provider and provider["seed"] is not None:
        provider["seed"] = _integer(provider["seed"], field="seed")
    if "fps" in provider and provider["fps"] is not None:
        fps = _number(provider["fps"], field="fps")
        if fps != 24:
            raise ExecutorError("H3 Comfy workflows currently support only 24 fps")
        provider["fps"] = 24
    image_size = provider.get("reference_image_size")
    if image_size is not None and image_size not in {"match", "max"}:
        raise ExecutorError("parameters.reference_image_size must be 'match' or 'max'")
    if image_size is not None and mode != "r2v":
        raise ExecutorError("reference_image_size is supported only by r2v")

    first = inputs.get("first_frame")
    last = inputs.get("last_frame")
    first_asset = _asset(first, field="first_frame", expected_kind="image") if first is not None else None
    last_asset = _asset(last, field="last_frame", expected_kind="image") if last is not None else None
    images = _asset_list(inputs.get("reference_images"), field="reference_images", kind="image")
    videos = _asset_list(inputs.get("reference_videos"), field="reference_videos", kind="video")
    audios = _asset_list(inputs.get("reference_audios"), field="reference_audios", kind="audio")
    if mode == "t2v":
        if any((first_asset, last_asset, images, videos, audios)):
            raise ExecutorError("t2v does not accept media inputs")
    elif mode == "i2v":
        if first_asset is None or last_asset is not None or images or videos or audios:
            raise ExecutorError("i2v requires exactly one first_frame and no other media")
    elif mode == "fl2v":
        if first_asset is None or last_asset is None or images or videos or audios:
            raise ExecutorError("fl2v requires exactly one first_frame and last_frame")
    elif mode == "r2v":
        if first_asset is not None or last_asset is not None:
            raise ExecutorError("r2v uses reference lists instead of first/last frame inputs")
        if not (images or videos or audios):
            raise ExecutorError("r2v requires at least one reference asset")
    from lfo.canvas.input_contract import validate_input_contract

    capability = json.loads((pathlib.Path(__file__).resolve().parents[1] / "capability.json").read_text(encoding="utf-8"))
    try:
        validate_input_contract({**snapshot, "parameters": {**common, **provider}}, capability)
    except ValueError as exc:
        raise ExecutorError(str(exc)) from exc
    return {
        "node_id": node_id,
        "request_id": request_id,
        "mode": mode,
        "prompt": prompt,
        "parameters": common,
        "comfy": provider,
        "first_frame": first_asset,
        "last_frame": last_asset,
        "reference_images": images,
        "reference_videos": videos,
        "reference_audios": audios,
    }


def _one_node(workflow: dict[str, Any], class_type: str) -> dict[str, Any]:
    found = [node for node in workflow.values() if isinstance(node, dict) and node.get("class_type") == class_type]
    if len(found) != 1:
        raise ExecutorError(f"H3 template requires exactly one {class_type} node; found {len(found)}")
    return found[0]


def _next_node_id(workflow: dict[str, Any]) -> str:
    ids = [int(key) for key in workflow if isinstance(key, str) and key.isdigit()]
    return str(max(ids, default=0) + 1)


def _add_node(workflow: dict[str, Any], node: dict[str, Any]) -> str:
    node_id = _next_node_id(workflow)
    workflow[node_id] = node
    return node_id


def _load_template(mode: str, profile: str) -> dict[str, Any]:
    family = "r2v" if mode == "r2v" else "fl2va"
    path = TEMPLATE_ROOT / f"h3_{'native' if profile == 'native' else 'standard'}_{family}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"Could not load Comfy H3 template {path.name}: {exc}") from exc
    if not isinstance(value, dict) or not value:
        raise ExecutorError(f"Comfy H3 template {path.name} must be a non-empty object")
    return copy.deepcopy(value)


def _prefix_for(node_id: str, request_id: str) -> str:
    safe_node = "".join(char if char.isalnum() or char in "-_" else "_" for char in node_id)
    safe_request = "".join(
        char if char.isalnum() or char in "-_" else "_" for char in request_id
    )
    return f"canvas/{safe_node[:80] or 'node'}/{safe_request[:80] or 'request'}/video"


def prepare_workflow(
    snapshot: object,
    *,
    uploader: Uploader | None = None,
    request_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one temporary API workflow and return it with normalized inputs."""
    normalized = normalize_snapshot(snapshot)
    comfy = normalized["comfy"]
    workflow = _load_template(normalized["mode"], comfy["sampler_profile"])
    request_id = request_id or normalized["request_id"] or uuid.uuid4().hex
    normalized["request_id"] = request_id

    generator_type = "MiniMaxH3ReferenceToVideo" if normalized["mode"] == "r2v" else "MiniMaxH3ImageToVideo"
    generator = _one_node(workflow, generator_type)
    generator_inputs = generator.setdefault("inputs", {})
    if normalized["mode"] != "r2v":
        generator_inputs["prompt"] = normalized["prompt"]
    duration = _one_node(workflow, "PrimitiveFloat").setdefault("inputs", {})
    duration["value"] = normalized["parameters"]["duration"]
    resolution = _one_node(workflow, "ResolutionSelector").setdefault("inputs", {})
    resolution["aspect_ratio"] = ASPECT_LABELS[normalized["parameters"]["aspect_ratio"]]
    resolution["megapixels"] = normalized["parameters"]["megapixels"]
    scheduler = _one_node(workflow, "BasicScheduler").setdefault("inputs", {})
    scheduler["steps"] = comfy["steps"]
    if "seed" in comfy and comfy["seed"] is not None:
        noise = _one_node(workflow, "RandomNoise").setdefault("inputs", {})
        noise["noise_seed"] = comfy["seed"]
    if "fps" in comfy and comfy["fps"] is not None:
        _one_node(workflow, "CreateVideo").setdefault("inputs", {})["fps"] = comfy["fps"]
    if normalized["mode"] == "r2v":
        if comfy.get("reference_image_size") is not None:
            generator_inputs["ref_image_size"] = comfy["reference_image_size"]
        prompt_nodes = [
            node
            for node in workflow.values()
            if isinstance(node, dict) and node.get("class_type") == "PrimitiveStringMultiline"
        ]
        if prompt_nodes:
            prompt_nodes[0].setdefault("inputs", {})["value"] = normalized["prompt"]
        else:
            generator_inputs["prompt"] = normalized["prompt"]

    save_video = _one_node(workflow, "SaveVideo")
    save_video.setdefault("inputs", {})["filename_prefix"] = _prefix_for(
        normalized["node_id"], request_id
    )

    if uploader is None and any(
        normalized[key] is not None or normalized[key]
        for key in ("first_frame", "last_frame", "reference_images", "reference_videos", "reference_audios")
    ):
        raise ExecutorError("A Comfy uploader is required for media inputs")
    if normalized["mode"] in {"i2v", "fl2v"}:
        assert uploader is not None
        for key in ("first_frame", "last_frame"):
            asset = normalized[key]
            if asset is None:
                continue
            token = uploader(asset["path"])
            load_id = _add_node(
                workflow,
                {
                    "_meta": {"title": f"Canvas.{key}"},
                    "class_type": "LoadImage",
                    "inputs": {"image": token},
                },
            )
            generator_inputs[key] = [load_id, 0]
    elif normalized["mode"] == "r2v":
        assert uploader is not None
        for key in list(generator_inputs):
            if key.startswith(("ref_images.", "ref_videos.", "ref_video_audios.", "ref_audios.")):
                generator_inputs.pop(key, None)
        for node_id, node in list(workflow.items()):
            if not isinstance(node, dict):
                continue
            title = node.get("_meta", {}).get("title") if isinstance(node.get("_meta"), dict) else None
            if node.get("class_type") == "LoadImage" and str(title or "").startswith("LFO.Reference"):
                workflow.pop(node_id, None)
        for index, asset in enumerate(normalized["reference_images"]):
            token = uploader(asset["path"])
            load_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceImage{index + 1}"}, "class_type": "LoadImage", "inputs": {"image": token}},
            )
            generator_inputs[f"ref_images.ref_image_{index}"] = [load_id, 0]
        for index, asset in enumerate(normalized["reference_videos"]):
            token = uploader(asset["path"])
            load_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceVideo{index + 1}"}, "class_type": "LoadVideo", "inputs": {"video": token}},
            )
            components_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceVideoComponents{index + 1}"}, "class_type": "GetVideoComponents", "inputs": {"video": [load_id, 0]}},
            )
            generator_inputs[f"ref_videos.ref_video_{index}"] = [components_id, 0]
            generator_inputs[f"ref_video_audios.ref_video_audio_{index}"] = [components_id, 1]
        for index, asset in enumerate(normalized["reference_audios"]):
            token = uploader(asset["path"])
            load_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceAudio{index + 1}"}, "class_type": "LoadAudio", "inputs": {"audio": token}},
            )
            generator_inputs[f"ref_audios.ref_audio_{index}"] = [load_id, 0]
    return workflow, normalized


def _parse_base_url(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url if "://" in base_url else f"http://{base_url}")
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ExecutorError("local Comfy URL must be an HTTP host without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ExecutorError("local Comfy URL cannot contain a path, query, or fragment")
    try:
        port = parsed.port or 8188
    except ValueError as exc:
        raise ExecutorError("local Comfy URL has an invalid port") from exc
    return parsed.hostname, port


def _http_uploader(base_url: str, timeout: float) -> Uploader:
    def upload(path: pathlib.Path) -> str:
        boundary = f"----canvas-comfy-{uuid.uuid4().hex}"
        upload_name = f"canvas-{uuid.uuid4().hex}-{path.name}"
        content = path.read_bytes()
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{upload_name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\ninput\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\nfalse\r\n--{boundary}--\r\n".encode(),
        ]
        request = Request(
            base_url.rstrip("/") + "/upload/image",
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
            raise ExecutorError(f"Could not upload Comfy input {path.name}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not payload["name"]:
            raise ExecutorError(f"Comfy upload response for {path.name} has no file name")
        if payload.get("type") != "input":
            raise ExecutorError(f"Comfy upload response for {path.name} has an unexpected file type")
        subfolder = payload.get("subfolder")
        if subfolder is not None and not isinstance(subfolder, str):
            raise ExecutorError(f"Comfy upload response for {path.name} has an invalid subfolder")
        return f"{subfolder}/{payload['name']}" if isinstance(subfolder, str) and subfolder else payload["name"]

    return upload


def _fetch_object_info(base_url: str, timeout: float) -> dict[str, Any]:
    request = Request(base_url.rstrip("/") + "/object_info", method="GET")
    try:
        with urlopen(request, timeout=min(timeout, 30.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"Comfy preflight could not read /object_info: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutorError("Comfy /object_info returned a non-object payload")
    return payload


def _input_specs(node_info: object) -> dict[str, Any]:
    if not isinstance(node_info, dict):
        return {}
    inputs = node_info.get("input")
    if not isinstance(inputs, dict):
        return {}
    result: dict[str, Any] = {}
    for section in ("required", "optional"):
        values = inputs.get(section)
        if isinstance(values, dict):
            result.update(values)
    return result


def _choice_values(spec: object) -> list[object] | None:
    if isinstance(spec, dict):
        for key in ("enum", "choices", "options"):
            values = spec.get(key)
            if isinstance(values, list):
                return values
        return None
    if isinstance(spec, (list, tuple)) and spec:
        first = spec[0]
        if isinstance(first, (list, tuple, set)):
            return list(first)
    return None


def preflight_workflow(
    workflow: dict[str, Any],
    config: RuntimeConfig,
    *,
    object_info: dict[str, Any] | None = None,
) -> None:
    """Check node classes and server-advertised enum/model values before submit."""
    info = object_info if object_info is not None else _fetch_object_info(config.base_url, config.timeout_seconds)
    missing: list[str] = []
    invalid: list[str] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            invalid.append(f"node {node_id} is not an object")
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            invalid.append(f"node {node_id} has no class_type")
            continue
        node_info = info.get(class_type)
        if not isinstance(node_info, dict):
            missing.append(f"{class_type} (node {node_id})")
            continue
        values = node.get("inputs")
        if not isinstance(values, dict):
            invalid.append(f"node {node_id} has no inputs object")
            continue
        specs = _input_specs(node_info)
        for input_name, value in values.items():
            if isinstance(value, list):
                continue
            if input_name in DYNAMIC_MEDIA_INPUTS.get(class_type, frozenset()):
                # These choices are the server's current file listing.  The
                # adapter uploads confirmed media immediately before this
                # preflight, so they are not model/enum constraints.
                continue
            spec = specs.get(input_name)
            choices = _choice_values(spec)
            if choices is not None and value not in choices:
                invalid.append(f"{class_type}.{input_name}={value!r}")
    if missing:
        raise ExecutorError("Comfy preflight missing node classes: " + ", ".join(missing))
    if invalid:
        raise ExecutorError("Comfy preflight rejected workflow inputs: " + ", ".join(invalid))


def _parse_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, line in enumerate(stdout.splitlines(), 1):
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ExecutorError(f"comfy-cli returned invalid JSON on stdout line {number}") from exc
        if not isinstance(event, dict):
            raise ExecutorError(f"comfy-cli returned a non-object event on stdout line {number}")
        events.append(event)
    return events


def _output_ref(value: object) -> OutputRef | None:
    if isinstance(value, str):
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            query = parse_qs(parsed.query)
            filename = query.get("filename", [""])[0]
            if filename:
                return OutputRef(
                    filename=filename,
                    subfolder=query.get("subfolder", [""])[0],
                    file_type=query.get("type", ["output"])[0],
                    url=value,
                )
        return OutputRef(filename=value, file_type="absolute" if pathlib.Path(value).is_absolute() else "output")
    if not isinstance(value, dict):
        return None
    filename = value.get("filename")
    if not isinstance(filename, str) or not filename:
        return None
    url = value.get("url")
    file_type = str(value.get("type") or "output")
    if pathlib.Path(filename).is_absolute():
        file_type = "absolute"
    return OutputRef(
        filename=filename,
        subfolder=str(value.get("subfolder") or ""),
        file_type=file_type,
        url=url if isinstance(url, str) else None,
    )


def _collect_outputs(events: list[dict[str, Any]], prompt_id: str) -> tuple[OutputRef, ...]:
    values: list[object] = []
    envelope = next((event for event in reversed(events) if event.get("type") == "envelope"), None)
    has_envelope_outputs = False
    if isinstance(envelope, dict):
        data = envelope.get("data")
        if isinstance(data, dict) and isinstance(data.get("outputs"), list):
            values.extend(data["outputs"])
            has_envelope_outputs = bool(data["outputs"])
    if not has_envelope_outputs:
        for event in events:
            if event.get("type") == "executed" and event.get("prompt_id") == prompt_id:
                if isinstance(event.get("outputs"), list):
                    values.extend(event["outputs"])
    result: list[OutputRef] = []
    seen: set[tuple[str, str, str]] = set()
    for value in values:
        reference = _output_ref(value)
        if reference is None:
            continue
        key = (reference.filename, reference.subfolder, reference.file_type)
        if key not in seen:
            result.append(reference)
            seen.add(key)
    return tuple(result)


_STREAM_END = object()


def _read_process_stream(stream: Any, target: queue.Queue[object]) -> None:
    try:
        for line in stream:
            target.put(line)
    finally:
        target.put(_STREAM_END)


def _progress_event(
    event: dict[str, Any], provider_task_id: str | None,
) -> dict[str, Any] | None:
    """Translate official comfy-cli events to the small canvas event contract."""
    event_type = event.get("type")
    if event_type not in {"queued", "progress", "executed"}:
        return None
    event_id = event.get("prompt_id")
    if not isinstance(event_id, str) or not event_id:
        event_id = provider_task_id
    payload: dict[str, Any] = {
        "event": str(event_type),
        "status": "queued" if event_type == "queued" else "running",
        "stage": "generation",
    }
    if event_id:
        payload["provider_task_id"] = event_id
    if event_type == "progress":
        for key in ("value", "max", "node"):
            if key in event:
                payload[key] = event[key]
    return payload


def _emit_progress(
    event: dict[str, Any], provider_task_id: str | None,
    emit: Callable[[dict[str, Any]], None] | None,
) -> None:
    if emit is None:
        return
    payload = _progress_event(event, provider_task_id)
    if payload is not None:
        emit(payload)


def run_comfy_cli(
    workflow_path: pathlib.Path,
    config: RuntimeConfig,
    *,
    emit: Callable[[dict[str, Any]], None] | None = None,
    request_id: str | None = None,
) -> CliResult:
    from lfo.comfy.admission import VideoSubmissionGuard
    from lfo.comfy.exceptions import LfoComfyError

    try:
        with VideoSubmissionGuard(config.base_url, request_id=request_id) as guard:
            guard.submitted()
            def progress(event: dict[str, Any]) -> None:
                if event.get("provider_task_id"):
                    guard.submitted(str(event["provider_task_id"]))
                if event.get("remote_finished") is True:
                    guard.finished()
                if emit is not None:
                    emit(event)
            try:
                result = _run_comfy_cli(workflow_path, config, emit=progress)
            except ExecutorError as exc:
                if exc.status == "failed":
                    guard.finished()
                elif exc.provider_task_id:
                    guard.submitted(exc.provider_task_id)
                raise
            guard.finished()
            return result
    except LfoComfyError as exc:
        raise ExecutorError(str(exc)) from exc


def _run_comfy_cli(
    workflow_path: pathlib.Path,
    config: RuntimeConfig,
    *,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> CliResult:
    """Run the official CLI and forward NDJSON events while it is running."""
    host, port = _parse_base_url(config.base_url)
    command = [
        config.cli_binary,
        "--skip-prompt",
        "--where",
        "local",
        "run",
        "--workflow",
        str(workflow_path),
        "--wait",
        "--host",
        host,
        "--port",
        str(port),
        "--timeout",
        str(max(1, int(config.timeout_seconds))),
        "--no-notify",
        "--json",
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ExecutorError("comfy-cli executable was not found") from exc
    except OSError as exc:
        raise ExecutorError(f"could not start comfy-cli: {exc}") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_queue: queue.Queue[object] = queue.Queue()
    stderr_queue: queue.Queue[object] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_read_process_stream, args=(process.stdout, stdout_queue), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_read_process_stream, args=(process.stderr, stderr_queue), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    events: list[dict[str, Any]] = []
    stderr_lines: list[str] = []
    stdout_done = False
    deadline = time.monotonic() + config.timeout_seconds + PROCESS_EXIT_GRACE_SECONDS
    provider_task_id: str | None = None
    parse_error: ExecutorError | None = None
    try:
        while not stdout_done or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise ExecutorError(
                    "comfy-cli exceeded its wall-clock timeout",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
            try:
                line = stdout_queue.get(timeout=min(0.2, remaining))
            except queue.Empty:
                continue
            if line is _STREAM_END:
                stdout_done = True
                continue
            if not isinstance(line, str) or not line.strip():
                continue
            try:
                event = json.loads(line.lstrip("\ufeff"))
            except json.JSONDecodeError:
                parse_error = ExecutorError(
                    "comfy-cli returned invalid JSON while execution status was uncertain",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
                # Keep draining the process so it can be terminated cleanly and
                # so a later queued event can still supply the provider ID.
                continue
            if not isinstance(event, dict):
                parse_error = ExecutorError(
                    "comfy-cli returned a non-object event while execution status was uncertain",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
                continue
            events.append(event)
            event_id = event.get("prompt_id")
            if isinstance(event_id, str) and event_id:
                provider_task_id = event_id
            _emit_progress(event, provider_task_id, emit)
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise ExecutorError(
                "comfy-cli exceeded its wall-clock timeout",
                provider_task_id=provider_task_id,
                status="unknown",
            ) from exc
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        while True:
            try:
                line = stderr_queue.get_nowait()
            except queue.Empty:
                break
            if line is not _STREAM_END and isinstance(line, str):
                stderr_lines.append(line)

    if parse_error is not None:
        raise parse_error
    envelope = next((event for event in reversed(events) if event.get("type") == "envelope"), None)
    if envelope is None:
        detail = " ".join(stderr_lines).strip() or "missing terminal JSON envelope"
        raise ExecutorError(
            f"comfy-cli did not return a terminal result: {detail}",
            provider_task_id=provider_task_id,
            status="unknown",
        )
    prompt_id: str | None = envelope.get("prompt_id") if isinstance(envelope.get("prompt_id"), str) else provider_task_id
    data = envelope.get("data")
    if isinstance(data, dict) and isinstance(data.get("prompt_id"), str):
        prompt_id = data["prompt_id"]
    if isinstance(data, dict) and data.get("status") in {"timeout", "timed_out"}:
        raise ExecutorError("comfy-cli workflow timed out", provider_task_id=prompt_id, status="unknown")
    error = envelope.get("error")
    if envelope.get("ok") is not True:
        message = error.get("message") if isinstance(error, dict) else None
        code = str(error.get("code") or "") if isinstance(error, dict) else ""
        if "timeout" in code.lower() or "timed out" in str(message or "").lower():
            raise ExecutorError(
                str(message or "comfy-cli workflow timed out"),
                provider_task_id=prompt_id,
                status="unknown",
            )
        raise ExecutorError(
            str(message or "comfy-cli reported a provider failure"),
            provider_task_id=prompt_id,
            status="failed",
        )
    if process.returncode != 0:
        raise ExecutorError(
            f"comfy-cli exited with code {process.returncode} after submission",
            provider_task_id=prompt_id,
            status="unknown",
        )
    if not isinstance(data, dict) or data.get("status") != "completed":
        status = "failed" if isinstance(data, dict) and data.get("status") in {"failed", "error"} else "unknown"
        raise ExecutorError(
            "comfy-cli returned without a completed workflow",
            provider_task_id=prompt_id,
            status=status,
        )
    if not prompt_id:
        raise ExecutorError("comfy-cli result did not include prompt_id", status="unknown")
    if emit is not None:
        emit({"stage": "collection", "remote_finished": True, "provider_task_id": prompt_id})
    outputs = _collect_outputs(events, prompt_id)
    if not outputs:
        raise ExecutorError(
            f"comfy-cli prompt {prompt_id} completed without file output",
            provider_task_id=prompt_id,
            status="failed",
        )
    return CliResult(prompt_id, outputs, tuple(events))


def _video_refs(result: CliResult) -> list[OutputRef]:
    refs = [reference for reference in result.outputs if pathlib.Path(reference.filename).suffix.lower() in VIDEO_EXTENSIONS]
    if not refs:
        raise ExecutorError(f"Comfy prompt {result.provider_task_id} did not report a video output", provider_task_id=result.provider_task_id)
    if len(refs) > 1:
        raise ExecutorError(f"Comfy prompt {result.provider_task_id} reported multiple video outputs", provider_task_id=result.provider_task_id)
    return refs


def _fallback_probe(path: pathlib.Path) -> dict[str, Any]:
    """Use ffprobe directly only when the project media helper is unavailable."""
    try:
        completed = subprocess.run(
            [
                os.environ.get("LFO_FFPROBE", "ffprobe"),
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutorError(f"ffprobe could not inspect generated video: {exc}") from exc
    if completed.returncode != 0:
        raise ExecutorError("ffprobe could not decode generated video")
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    duration = float(payload.get("format", {}).get("duration") or 0)
    return {
        "duration_ms": round(duration * 1000),
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "codec": video.get("codec_name") if video else None,
    }


def validate_video_output(
    path: pathlib.Path,
    *,
    probe_fn: Callable[[pathlib.Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Require an actual ffprobe-readable video with dimensions and duration."""
    if not path.is_file() or path.stat().st_size <= 0:
        raise ExecutorError("Comfy output is missing or empty")
    inspector = probe_fn or _project_probe or _fallback_probe
    try:
        metadata = inspector(path)
    except Exception as exc:
        raise ExecutorError(f"Comfy output is not a readable video: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ExecutorError("Comfy output probe returned no media metadata")
    width = metadata.get("width")
    height = metadata.get("height")
    codec = metadata.get("codec")
    duration = metadata.get("duration_ms")
    if not (
        isinstance(width, int)
        and width > 0
        and isinstance(height, int)
        and height > 0
        and isinstance(codec, str)
        and bool(codec)
        and isinstance(duration, (int, float))
        and not isinstance(duration, bool)
        and duration > 0
    ):
        raise ExecutorError(
            "Comfy output is not a usable video stream: "
            f"width={width!r}, height={height!r}, codec={codec!r}, duration_ms={duration!r}"
        )
    return metadata


def materialize_video(
    result: CliResult,
    output_dir: pathlib.Path,
    config: RuntimeConfig,
    *,
    probe_fn: Callable[[pathlib.Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Copy or download exactly one provider video into the run directory."""
    reference = _video_refs(result)[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    name = pathlib.Path(reference.filename).name or "video.mp4"
    target = (output_dir / name).resolve()
    if not target.is_relative_to(output_dir.resolve()):
        raise ExecutorError("Comfy output filename escaped the output directory", provider_task_id=result.provider_task_id)
    source = pathlib.Path(reference.filename).expanduser()
    if reference.file_type == "absolute":
        if not source.is_file():
            raise ExecutorError(
                "Comfy reported an absolute output path that does not exist",
                provider_task_id=result.provider_task_id,
            )
        shutil.copy2(source, target)
    else:
        if config.output_root is not None and reference.file_type == "output":
            local = (config.output_root / reference.subfolder / reference.filename).resolve()
            if local.is_file():
                shutil.copy2(local, target)
            else:
                _download_view(config.base_url, reference, target, config.timeout_seconds)
        else:
            _download_view(config.base_url, reference, target, config.timeout_seconds)
    try:
        metadata = validate_video_output(target, probe_fn=probe_fn)
    except ExecutorError as exc:
        exc.stage = "media_validation"
        target.unlink(missing_ok=True)
        raise
    return {"path": str(target), "kind": "video", "name": target.name, "metadata": metadata}


def _download_view(base_url: str, reference: OutputRef, target: pathlib.Path, timeout: float) -> None:
    query = urlencode({"filename": reference.filename, "subfolder": reference.subfolder, "type": reference.file_type})
    request = Request(base_url.rstrip("/") + "/view?" + query, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response, target.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    except (OSError, HTTPError, URLError) as exc:
        raise ExecutorError(f"Could not download Comfy output {reference.filename}: {exc}") from exc


def execute_snapshot(
    snapshot: object,
    output_dir: pathlib.Path,
    config: RuntimeConfig,
    *,
    uploader: Uploader | None = None,
) -> dict[str, Any]:
    """Execute one snapshot exactly once and return the final result object."""
    def emit(event: dict[str, Any]) -> None:
        nonlocal stage
        stage = event.get("stage", stage)
        print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)

    stage = "input_validation"
    result: CliResult | None = None
    try:
        emit({"stage": stage})
        normalize_snapshot(snapshot)
        uploader = uploader or _http_uploader(config.base_url, config.timeout_seconds)
        with tempfile.TemporaryDirectory(prefix="canvas-comfy-") as temp_dir:
            stage = "upload"
            emit({"stage": stage})
            workflow, normalized = prepare_workflow(snapshot, uploader=uploader)
            stage = "input_validation"
            emit({"stage": stage})
            preflight_workflow(workflow, config)
            workflow_path = pathlib.Path(temp_dir) / "workflow.json"
            workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            stage = "submit"
            emit({"stage": stage})
            result = run_comfy_cli(
                workflow_path,
                config,
                emit=emit,
                request_id=normalized["request_id"],
            )
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_video(result, output_dir, config)
        return {"status": "succeeded", "stage": "media_validation", "outputs": [output], "provider_task_id": result.provider_task_id}
    except (OSError, ExecutorError) as exc:
        if not isinstance(exc, ExecutorError):
            exc = ExecutorError(str(exc), status="unknown" if stage in {"submit", "generation"} else "failed")
        exc.stage = getattr(exc, "stage", stage)
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute one confirmed ComfyUI H3 canvas video node")
    parser.add_argument("--input", required=True, type=pathlib.Path, help="confirmed snapshot JSON")
    parser.add_argument("--output-dir", required=True, type=pathlib.Path, help="existing run output directory")
    parser.add_argument("--comfy-url", type=str, default=None)
    parser.add_argument("--comfy-executable", type=str, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--config", type=pathlib.Path, default=None)
    parser.add_argument("--machine-id", type=str, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        config = load_runtime_config(
            config_path=args.config,
            machine_id=args.machine_id,
            base_url=args.comfy_url,
            cli_binary=args.comfy_executable,
            timeout_seconds=args.timeout,
        )
        result = execute_snapshot(snapshot, args.output_dir, config)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
        return 0
    except (OSError, json.JSONDecodeError, ExecutorError) as exc:
        payload: dict[str, Any] = {
            "event": "failed" if getattr(exc, "status", "failed") == "failed" else "unknown",
            "status": getattr(exc, "status", "failed"),
            "error": str(exc),
            "stage": getattr(exc, "stage", "input_validation"),
        }
        if isinstance(exc, ExecutorError) and exc.provider_task_id:
            payload["provider_task_id"] = exc.provider_task_id
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
