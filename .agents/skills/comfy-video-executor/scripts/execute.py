"""Execute one confirmed canvas video snapshot through local ComfyUI.

The adapter uses the project's Comfy MCP transport and media-probe helpers.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from lfo.comfy.exceptions import LfoComfyError
from lfo.comfy.transport import (
    ComfyResult,
    ExecutorError,
    OutputRef,
    RuntimeConfig,
    load_runtime_config,
    preflight_workflow,
    ready_session,
    run_workflow,
    upload_input,
)

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
    {
        "sampler_profile",
        "steps",
        "seed",
        "fps",
        "reference_image_size",
        "frame_zero_video_guide",
        "vdn_checkpoint",
        "vdn_branch_weights",
        "vdn_retain_buffers",
        "video_decode",
    }
)


try:
    from lfo.media._ffmpeg import probe as _project_probe
except ImportError:  # pragma: no cover - direct standalone invocation fallback
    _project_probe = None


Uploader = Callable[[pathlib.Path], str]


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
    for key in ("vdn_checkpoint", "vdn_branch_weights", "vdn_retain_buffers", "video_decode"):
        if provider.get(key) is None or provider.get(key) == "":
            provider.pop(key, None)
        elif key.startswith("vdn_") and profile != "vdn_turbo":
            raise ExecutorError(f"parameters.{key} is supported only by vdn_turbo")
    checkpoint = provider.get("vdn_checkpoint")
    if checkpoint is not None:
        if not isinstance(checkpoint, str):
            raise ExecutorError("parameters.vdn_checkpoint must be a relative checkpoint name")
        checkpoint = checkpoint.strip()
        parts = checkpoint.replace("\\", "/").split("/")
        if any(part in {"", ".", ".."} for part in parts) or ":" in checkpoint or "\0" in checkpoint:
            raise ExecutorError("parameters.vdn_checkpoint must stay within models/vdn")
        provider["vdn_checkpoint"] = checkpoint
    for key, choices in (
        ("vdn_branch_weights", {"auto", "stream", "cache_gpu"}),
        ("vdn_retain_buffers", {"auto", "on", "off"}),
        ("video_decode", {"full", "tiled"}),
    ):
        if key in provider and (not isinstance(provider[key], str) or provider[key] not in choices):
            raise ExecutorError(f"parameters.{key} must be one of {', '.join(sorted(choices))}")
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
    frame_zero_video_guide = provider.get("frame_zero_video_guide", False)
    if not isinstance(frame_zero_video_guide, bool):
        raise ExecutorError("parameters.frame_zero_video_guide must be a boolean")
    if frame_zero_video_guide and mode != "r2v":
        raise ExecutorError("frame_zero_video_guide is supported only by r2v")

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
        if last_asset is not None:
            raise ExecutorError("r2v does not support a last_frame input")
        if not (images or videos or audios):
            raise ExecutorError("r2v requires at least one reference asset")
        if frame_zero_video_guide and not videos:
            raise ExecutorError(
                "frame_zero_video_guide requires at least one reference video"
            )
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
    if comfy["sampler_profile"] == "vdn_turbo":
        acceleration = _one_node(workflow, "ApplyVDNH3").setdefault("inputs", {})
        acceleration["vdn_checkpoint"] = comfy.get("vdn_checkpoint", "stage-dmd-step-250")
        acceleration["branch_weights"] = comfy.get("vdn_branch_weights", "auto")
        acceleration["retain_buffers"] = comfy.get("vdn_retain_buffers", "auto")
    if comfy.get("video_decode") == "tiled":
        decoder = _one_node(workflow, "VAEDecode")
        decoder["class_type"] = "VAEDecodeTiled"
        decoder["inputs"].update(tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
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
        frame_zero_video_guide = normalized["comfy"].get("frame_zero_video_guide", False)
        guided_video_components_id: str | None = None
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
                {"_meta": {"title": f"Canvas.ReferenceVideo{index + 1}"}, "class_type": "LoadVideo", "inputs": {"file": token}},
            )
            components_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceVideoComponents{index + 1}"}, "class_type": "GetVideoComponents", "inputs": {"video": [load_id, 0]}},
            )
            if frame_zero_video_guide and index == 0:
                # The first video is a short temporal prefix, not an additional
                # semantic <Video N> reference. Its frames and soundtrack are
                # attached to AddGuide below, matching Comfy's multiframe
                # workflow and avoiding a second, competing video reference.
                guided_video_components_id = components_id
            else:
                generator_inputs[f"ref_videos.ref_video_{index}"] = [components_id, 0]
                generator_inputs[f"ref_video_audios.ref_video_audio_{index}"] = [components_id, 1]
        for index, asset in enumerate(normalized["reference_audios"]):
            token = uploader(asset["path"])
            load_id = _add_node(
                workflow,
                {"_meta": {"title": f"Canvas.ReferenceAudio{index + 1}"}, "class_type": "LoadAudio", "inputs": {"audio": token}},
            )
            generator_inputs[f"ref_audios.ref_audio_{index}"] = [load_id, 0]
        if frame_zero_video_guide:
            if guided_video_components_id is None:
                raise ExecutorError(
                    "frame_zero_video_guide could not prepare its reference video"
                )
            # Anchor the short, frame-valid (22, 39, ...) continuation prefix
            # together with its original soundtrack at output frame zero.
            # Panel adoption requires trimming before review or a legal derived
            # review; final-assembly trimming preserves the accepted source.
            generator_id = next(key for key, node in workflow.items() if node is generator)
            guide_id = _add_node(workflow, {
                "_meta": {"title": "Canvas.FrameZeroVideoGuide"},
                "class_type": "MiniMaxH3AddGuide",
                "inputs": {
                    "positive": [generator_id, 0],
                    "latent": [generator_id, 1],
                    "vae": generator_inputs["vae"],
                    "audio_vae": generator_inputs["audio_vae"],
                    "image": [guided_video_components_id, 0],
                    "audio": [guided_video_components_id, 1],
                    "frame_idx": 0,
                },
            })
            _one_node(workflow, "BasicGuider")["inputs"]["conditioning"] = [guide_id, 0]
        elif normalized["first_frame"] is not None:
            # Timed image conditioning is separate from identity/voice references.
            # Keep the R2V latent and reference slots, then anchor frame zero with
            # the same AddGuide route used by Comfy's multiframe workflow.
            generator_id = next(key for key, node in workflow.items() if node is generator)
            load_id = _add_node(workflow, {
                "_meta": {"title": "Canvas.first_frame"},
                "class_type": "LoadImage",
                "inputs": {"image": uploader(normalized["first_frame"]["path"])},
            })
            guide_id = _add_node(workflow, {
                "_meta": {"title": "Canvas.FrameZeroGuide"},
                "class_type": "MiniMaxH3AddGuide",
                "inputs": {
                    "positive": [generator_id, 0],
                    "latent": [generator_id, 1],
                    "vae": generator_inputs["vae"],
                    "image": [load_id, 0],
                    "frame_idx": 0,
                },
            })
            _one_node(workflow, "BasicGuider")["inputs"]["conditioning"] = [guide_id, 0]
    return workflow, normalized


def _video_refs(result: ComfyResult) -> list[OutputRef]:
    # LoadVideo exposes its source file as an intermediate ``type=input``
    # output when a temporal guide is present. Only SaveVideo/output (or an
    # explicitly resolved absolute path) is a generated result.
    refs = [
        reference
        for reference in result.outputs
        if reference.file_type in {"output", "absolute"}
        and pathlib.Path(reference.filename).suffix.lower() in VIDEO_EXTENSIONS
    ]
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
    result: ComfyResult,
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
    if not source.is_file():
        raise ExecutorError(
            "Comfy MCP returned an output path that does not exist",
            provider_task_id=result.provider_task_id,
        )
    shutil.copy2(source, target)
    try:
        metadata = validate_video_output(target, probe_fn=probe_fn)
    except ExecutorError as exc:
        exc.stage = "media_validation"
        target.unlink(missing_ok=True)
        raise
    return {"path": str(target), "kind": "video", "name": target.name, "metadata": metadata}


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
    result: ComfyResult | None = None
    started_at = time.perf_counter()
    try:
        from lfo.comfy.admission import VideoSubmissionGuard

        emit({"stage": stage})
        normalize_snapshot(snapshot)
        validated_at = time.perf_counter()
        request_id = snapshot.get("request_id") if isinstance(snapshot, dict) else None
        with VideoSubmissionGuard(config.base_url, request_id=request_id) as guard, ready_session(config) as session:
                ready_at = time.perf_counter()
                upload = uploader or (lambda path: upload_input(path, session))
                with tempfile.TemporaryDirectory(prefix="canvas-comfy-") as temp_dir:
                    stage = "upload"
                    emit({"stage": stage})
                    workflow, _normalized = prepare_workflow(snapshot, uploader=upload)
                    prepared_at = time.perf_counter()
                    stage = "input_validation"
                    emit({"stage": stage})
                    workflow_path = pathlib.Path(temp_dir) / "workflow.json"
                    workflow_path.write_text(
                        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
                    )
                    preflight_workflow(workflow, workflow_path, session)
                    preflight_at = time.perf_counter()
                    stage = "submit"
                    emit({"stage": stage})
                    result = run_workflow(
                        workflow_path, output_dir, config, session, guard=guard, emit=emit
                    )
        stage = "collection"
        collection_at = time.perf_counter()
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_video(result, output_dir, config)
        finished_at = time.perf_counter()
        # Keep diagnostics beside the actual run media. Canvas re-probes media
        # metadata, so attaching timings to ffprobe fields would discard them.
        vdn_nodes = [node for node in workflow.values() if node.get("class_type") == "ApplyVDNH3"]
        report = {
            "schema": "comfy-video-execution.v1",
            "recorded_at": datetime.now(UTC).isoformat(),
            "request_id": _normalized["request_id"],
            "provider_task_id": result.provider_task_id,
            "sampler_profile": _normalized["comfy"]["sampler_profile"],
            "parameters": {**_normalized["parameters"], "steps": _normalized["comfy"]["steps"],
                           "seed": _one_node(workflow, "RandomNoise")["inputs"]["noise_seed"]},
            "models": {
                "diffusion": _one_node(workflow, "UNETLoader")["inputs"]["unet_name"],
                "text_encoder": _one_node(workflow, "CLIPLoader")["inputs"]["clip_name"],
                "vaes": [node["inputs"]["vae_name"] for node in workflow.values() if node.get("class_type") == "VAELoader"],
            },
            "vdn": {key: value for key, value in vdn_nodes[0]["inputs"].items() if key != "model"} if vdn_nodes else None,
            "video_decode": _normalized["comfy"].get("video_decode", "full"),
            "timings_seconds": {
                "input_validation": validated_at - started_at,
                "resource_and_startup": ready_at - validated_at,
                "prepare_and_upload": prepared_at - ready_at,
                "preflight": preflight_at - prepared_at,
                **result.timings_seconds,
                "collection_and_validation": finished_at - collection_at,
                "total": finished_at - started_at,
            },
            "provider_stage_timings_seconds": None,
            "peak_vram_bytes": None,
            "resolved_vdn_memory_policy": None,
        }
        (output_dir / "execution-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return {"status": "succeeded", "stage": "media_validation", "outputs": [output], "provider_task_id": result.provider_task_id}
    except (OSError, ExecutorError, LfoComfyError) as exc:
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        config = load_runtime_config()
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
