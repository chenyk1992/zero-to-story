"""Contract tests for the bundled MiniMax H3 VDN8 execution path.

These tests deliberately use a small in-process /object_info stand-in.  They
exercise the workflow that would be uploaded to ComfyUI, without starting a
generation or depending on a particular local ComfyUI installation.
"""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

import pytest

from lfo.backends.comfy_h3 import ComfyH3Config, ComfyH3VideoHandler
from lfo.comfy.cli import ComfyCliOutput, ComfyCliRunResult

REGISTRY = pathlib.Path(__file__).resolve().parents[2] / "src" / "lfo" / "registry"


class FakeVdnClient:
    """Fake client that records ordering as well as upload calls."""

    def __init__(self, object_info: dict[str, Any]) -> None:
        self.object_info = copy.deepcopy(object_info)
        self.events: list[str] = []
        self.uploaded: list[pathlib.Path] = []
        self.uploaded_files: list[pathlib.Path] = []

    def get_object_info(self) -> dict[str, Any]:
        self.events.append("object_info")
        return copy.deepcopy(self.object_info)

    def upload_image(self, path: pathlib.Path, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.events.append("upload_image")
        self.uploaded.append(pathlib.Path(path).resolve())
        return {"name": pathlib.Path(path).name, "subfolder": "lfo-input"}

    def upload_file(self, path: pathlib.Path, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.events.append("upload_file")
        self.uploaded_files.append(pathlib.Path(path).resolve())
        return {"name": pathlib.Path(path).name, "subfolder": "lfo-input"}


class FakeVdnRunner:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output
        self.submitted: dict[str, Any] | None = None

    def run_workflow(
        self,
        workflow: dict[str, Any],
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> ComfyCliRunResult:
        self.submitted = workflow
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(b"vdn8-video")
        return ComfyCliRunResult(
            prompt_id="vdn8-prompt",
            outputs=(
                ComfyCliOutput(
                    filename=self.output.name,
                    subfolder=self.output.parent.name,
                ),
            ),
        )


def _workflow(workflow_id: str) -> dict[str, Any]:
    filename = {
        "h3_standard_fl2va": "h3_standard_fl2va.json",
        "h3_standard_r2v": "h3_standard_r2v.json",
        "h3_native_fl2va": "h3_native_fl2va.json",
        "h3_native_r2v": "h3_native_r2v.json",
        "h3_presenter_r2v": "h3_presenter_r2v.json",
    }[workflow_id]
    return json.loads((REGISTRY / filename).read_text(encoding="utf-8"))


def _combo(value: object, *extra: str) -> list[Any]:
    values = [str(value), *extra]
    return [list(dict.fromkeys(values)), {}]


def _comfy_combo(value: object, *extra: str) -> list[Any]:
    """Return the COMBO shape emitted by the current ComfyUI /object_info."""
    values = [str(value), *extra]
    return [
        "COMBO",
        {
            "multiselect": False,
            "options": list(dict.fromkeys(values)),
        },
    ]


def _input_spec(class_type: str, name: str, value: object) -> list[Any]:
    """Make the smallest useful /object_info spec for a workflow input."""
    if class_type == "UNETLoader" and name == "unet_name":
        # Model discovery is part of the VDN preflight.  Keep the actual base
        # model as an explicit option instead of accepting an arbitrary file.
        return _combo(value)
    if (
        class_type == "ApplyVDNH3"
        and name not in {"model", "unet"}
        and isinstance(value, str)
    ):
        return _combo(value, "Stage-DMD", "stage_dmd", "Stage DMD")
    if class_type == "KSamplerSelect" and name == "sampler_name":
        return _comfy_combo(value, "euler", "res_multistep")
    if class_type == "BasicScheduler" and name == "scheduler":
        return _comfy_combo(value, "simple")
    if isinstance(value, bool):
        return ["BOOLEAN", {"default": value}]
    if isinstance(value, int) and not isinstance(value, bool):
        return ["INT", {"default": value}]
    if isinstance(value, float):
        return ["FLOAT", {"default": value}]
    if isinstance(value, str):
        return ["STRING", {"default": value}]
    if isinstance(value, list) and len(value) == 2:
        return ["ANY", {}]
    return ["ANY", {}]


def _object_info_for(workflow: dict[str, Any]) -> dict[str, Any]:
    """Build a permissive schema while preserving enum/model constraints."""
    object_info: dict[str, Any] = {}
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        required = {
            name: _input_spec(class_type, name, value)
            for name, value in inputs.items()
        }
        object_info[class_type] = {
            "input": {"required": required, "optional": {}},
        }

    # Dynamic reference/frame nodes are injected by the handler after the
    # static graph is loaded, so they must be present in /object_info too.
    for class_type, input_name in (
        ("LoadImage", "image"),
        ("LoadVideo", "file"),
        ("GetVideoComponents", "video"),
        ("LoadAudio", "audio"),
    ):
        object_info.setdefault(
            class_type,
            {"input": {"required": {input_name: ["ANY", {}]}, "optional": {}}},
        )
    object_info.setdefault(
        "ApplyVDNH3",
        {
            "input": {
                "required": {
                    "model": ["MODEL", {}],
                    "vdn_checkpoint": [["stage-dmd-step-250"], {}],
                    "apply_turbo_adapter": ["BOOLEAN", {"default": True}],
                    "strength": ["FLOAT", {"default": 1.0}],
                    "lora_mode": [["bypass", "merge"], {"default": "merge"}],
                    "branch_weights": [["auto", "stream", "cache_gpu"], {"default": "auto"}],
                    "retain_buffers": [["auto", "on", "off"], {"default": "auto"}],
                    "verbose": ["BOOLEAN", {"default": False}],
                    "attention_backend": [["grouped", "flex"], {"default": "grouped"}],
                },
                "optional": {},
            }
        },
    )
    object_info.setdefault(
        "MiniMaxH3SigmaShift",
        {
            "input": {
                "required": {
                    "model": ["MODEL", {}],
                    "shift_video": ["FLOAT", {"default": 12.0}],
                    "shift_audio": ["FLOAT", {"default": 3.0}],
                },
                "optional": {},
            }
        },
    )
    return object_info


def _handler(
    tmp_path: pathlib.Path,
    workflow_id: str,
    *,
    object_info: dict[str, Any] | None = None,
) -> tuple[ComfyH3VideoHandler, FakeVdnClient]:
    schema = object_info if object_info is not None else _object_info_for(_workflow(workflow_id))
    client = FakeVdnClient(schema)
    output_root = tmp_path / "output"
    output_root.mkdir()
    return (
        ComfyH3VideoHandler(
            ComfyH3Config(output_root=output_root),
            client=client,  # type: ignore[arg-type]
        ),
        client,
    )


def _nodes(workflow: dict[str, Any], class_type: str) -> list[dict[str, Any]]:
    return [
        node
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == class_type
    ]


def _node(workflow: dict[str, Any], class_type: str) -> dict[str, Any]:
    matches = _nodes(workflow, class_type)
    assert len(matches) == 1, f"expected one {class_type}, got {len(matches)}"
    return matches[0]


def _assert_vdn8_sampler(workflow: dict[str, Any]) -> None:
    apply_vdn = _node(workflow, "ApplyVDNH3")
    sigma_shift = _node(workflow, "MiniMaxH3SigmaShift")
    unet = _node(workflow, "UNETLoader")

    assert apply_vdn["inputs"]["model"] == [
        next(node_id for node_id, node in workflow.items() if node is unet),
        0,
    ]
    checkpoint = apply_vdn["inputs"].get("vdn_checkpoint")
    assert isinstance(checkpoint, str)
    assert checkpoint.lower().replace("_", "-").startswith("stage-dmd")
    assert apply_vdn["inputs"].get("apply_turbo_adapter") is True
    assert apply_vdn["inputs"].get("lora_mode") == "merge"
    assert sigma_shift["inputs"]["model"] == [
        next(node_id for node_id, node in workflow.items() if node is apply_vdn),
        0,
    ]
    assert float(sigma_shift["inputs"]["shift_video"]) == 12.0
    assert float(sigma_shift["inputs"]["shift_audio"]) == 3.0
    assert len(_nodes(workflow, "ApplyVDNH3")) == 1
    assert len(_nodes(workflow, "MiniMaxH3SigmaShift")) == 1
    assert not _nodes(workflow, "LoraLoaderModelOnly")

    sampler = _node(workflow, "KSamplerSelect")
    scheduler = _node(workflow, "BasicScheduler")
    assert sampler["inputs"]["sampler_name"] == "euler"
    assert scheduler["inputs"]["scheduler"] == "simple"
    assert scheduler["inputs"]["steps"] == 8


def _i2v_metadata(image: pathlib.Path, **extra: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "operation": "video.image_to_video",
        "prompt": "A slow cinematic camera move around the subject",
        "duration_ms": 5_000,
        "aspect_ratio": "16:9",
        "megapixels": 0.4,
        "seed": 123,
        "fps": 24,
        "resolved_references": [
            {
                "reference_id": "first-frame",
                "media_type": "image",
                "placement": "first",
                "slot": "first_frame",
                "blob_path": str(image),
            }
        ],
    }
    metadata.update(extra)
    return metadata


def _r2v_metadata(images: list[pathlib.Path], **extra: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "operation": "video.reference_to_video",
        "prompt": "A slow cinematic camera move around the references",
        "duration_ms": 5_000,
        "aspect_ratio": "9:16",
        "megapixels": 0.4,
        "seed": 456,
        "fps": 24,
        "resolved_references": [
            {
                "reference_id": f"picture-{index}",
                "media_type": "image",
                "placement": "fixed",
                "slot": f"ref_image_{index}",
                "blob_path": str(image),
            }
            for index, image in enumerate(images)
        ],
    }
    metadata.update(extra)
    return metadata


def _r2v_media_metadata(
    references: list[tuple[pathlib.Path, str]],
    **extra: Any,
) -> dict[str, Any]:
    """Build a standard R2V package for one or more typed references."""
    next_indices: dict[str, int] = {}
    resolved_references: list[dict[str, Any]] = []
    for path, media_type in references:
        index = next_indices.get(media_type, 0)
        next_indices[media_type] = index + 1
        resolved_references.append(
            {
                "reference_id": f"{media_type}-{index}",
                "media_type": media_type,
                "placement": "fixed",
                "slot": f"ref_{media_type}_{index}",
                "blob_path": str(path),
            }
        )
    metadata: dict[str, Any] = {
        "operation": "video.reference_to_video",
        "prompt": "A slow cinematic camera move around the references",
        "duration_ms": 5_000,
        "aspect_ratio": "9:16",
        "megapixels": 0.4,
        "seed": 456,
        "fps": 24,
        "resolved_references": resolved_references,
    }
    metadata.update(extra)
    return metadata


def _presenter_metadata(
    references: list[tuple[pathlib.Path, str]],
    **extra: Any,
) -> dict[str, Any]:
    """Build Presenter metadata with its required materialized typed slots."""
    next_indices: dict[str, int] = {}
    resolved_references: list[dict[str, Any]] = []
    for path, media_type in references:
        index = next_indices.get(media_type, 0)
        next_indices[media_type] = index + 1
        resolved_references.append(
            {
                "reference_id": f"{media_type}-{index}",
                "media_type": media_type,
                "placement": "fixed",
                "slot": f"ref_{media_type}_{index}",
                "blob_path": str(path),
            }
        )
    metadata: dict[str, Any] = {
        "operation": "video.virtual_presenter",
        "prompt": "The presenter speaks naturally while Audio 1 is heard",
        "duration_ms": 5_000,
        "aspect_ratio": "16:9",
        "megapixels": 0.4,
        "seed": 789,
        "fps": 24,
        "resolved_references": resolved_references,
    }
    metadata.update(extra)
    return metadata


def test_vdn8_i2v_builds_raw_unet_vdn_shift_chain_and_preserves_audio(
    tmp_path: pathlib.Path,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    handler, client = _handler(tmp_path, "h3_standard_fl2va")

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_fl2va",
        _i2v_metadata(image, duration_ms=6_000),
        output_prefix="lfo/run/task/attempt/video",
    )

    _assert_vdn8_sampler(workflow)
    assert uploaded == ["lfo-input/first.png"]
    assert client.events[0] == "object_info"
    assert client.events[1:] == ["upload_image"]
    assert client.uploaded == [image.resolve()]

    generator = _node(workflow, "MiniMaxH3ImageToVideo")
    first_frame = generator["inputs"].get("first_frame")
    assert isinstance(first_frame, list)
    assert workflow[str(first_frame[0])]["class_type"] == "LoadImage"
    assert workflow[str(first_frame[0])]["inputs"]["image"] == "lfo-input/first.png"
    length_link = generator["inputs"]["length"]
    assert isinstance(length_link, list)
    assert workflow[str(length_link[0])]["class_type"] == "ComfyMathExpression"
    assert _node(workflow, "PrimitiveFloat")["inputs"]["value"] == 6

    assert _node(workflow, "RandomNoise")["inputs"]["noise_seed"] == 123
    resolution = _node(workflow, "ResolutionSelector")["inputs"]
    assert resolution["aspect_ratio"] == "16:9 (Widescreen)"
    assert resolution["megapixels"] == 0.4
    create_video = _node(workflow, "CreateVideo")["inputs"]
    assert create_video["fps"] == 24
    assert create_video["audio"]
    assert workflow[str(create_video["audio"][0])]["class_type"] == "VAEDecodeAudio"


def test_vdn8_r2v_image_only_preserves_seed_resolution_duration_and_audio(
    tmp_path: pathlib.Path,
) -> None:
    images = [tmp_path / "picture-0.png", tmp_path / "picture-1.png"]
    for image in images:
        image.write_bytes(b"image")
    handler, client = _handler(tmp_path, "h3_standard_r2v")

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        _r2v_metadata(images, duration_ms=7_000),
        output_prefix="lfo/run/task/attempt/video",
    )

    _assert_vdn8_sampler(workflow)
    assert uploaded == ["lfo-input/picture-0.png", "lfo-input/picture-1.png"]
    assert client.events == ["object_info", "upload_image", "upload_image"]
    generator = _node(workflow, "MiniMaxH3ReferenceToVideo")
    assert generator["inputs"]["ref_images.ref_image_0"]
    assert generator["inputs"]["ref_images.ref_image_1"]
    assert "ref_images.ref_image_2" not in generator["inputs"]
    assert not _nodes(workflow, "LoadVideo")
    assert not _nodes(workflow, "GetVideoComponents")
    assert not _nodes(workflow, "LoadAudio")

    assert _node(workflow, "RandomNoise")["inputs"]["noise_seed"] == 456
    resolution = _node(workflow, "ResolutionSelector")["inputs"]
    assert resolution["aspect_ratio"] == "9:16 (Portrait Widescreen)"
    assert resolution["megapixels"] == 0.4
    assert _node(workflow, "PrimitiveFloat")["inputs"]["value"] == 7
    create_video = _node(workflow, "CreateVideo")["inputs"]
    assert create_video["audio"]
    assert workflow[str(create_video["audio"][0])]["class_type"] == "VAEDecodeAudio"


@pytest.mark.parametrize("missing_class", ["ApplyVDNH3", "MiniMaxH3SigmaShift"])
def test_vdn8_missing_required_node_fails_before_upload(
    tmp_path: pathlib.Path,
    missing_class: str,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_fl2va"))
    schema.pop(missing_class)
    handler, client = _handler(
        tmp_path,
        "h3_standard_fl2va",
        object_info=schema,
    )

    with pytest.raises(Exception, match=missing_class):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.events == ["object_info"]
    assert not client.uploaded
    assert not client.uploaded_files


def test_vdn8_missing_stage_option_fails_before_upload(tmp_path: pathlib.Path) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_fl2va"))
    stage_info = schema["ApplyVDNH3"]["input"]["required"]
    stage_name = next(name for name in stage_info if "checkpoint" in name)
    stage_info[stage_name] = [[], {}]
    handler, client = _handler(tmp_path, "h3_standard_fl2va", object_info=schema)

    with pytest.raises(Exception, match="stage|checkpoint"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.events == ["object_info"]
    assert not client.uploaded


def test_vdn8_base_unet_must_be_advertised_before_upload(tmp_path: pathlib.Path) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_fl2va"))
    schema["UNETLoader"]["input"]["required"]["unet_name"] = [
        ["some-other-model.safetensors"],
        {},
    ]
    handler, client = _handler(tmp_path, "h3_standard_fl2va", object_info=schema)

    with pytest.raises(Exception, match="UNETLoader|unet_name|model"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.events == ["object_info"]
    assert not client.uploaded


@pytest.mark.parametrize(
    ("class_type", "input_name", "replacement"),
    [
        ("MiniMaxH3SigmaShift", "shift_audio", None),
        ("KSamplerSelect", "sampler_name", [["res_multistep"], {}]),
        ("BasicScheduler", "scheduler", [["normal"], {}]),
    ],
)
def test_vdn8_static_sampler_inputs_must_be_supported_before_upload(
    tmp_path: pathlib.Path,
    class_type: str,
    input_name: str,
    replacement: list[Any] | None,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_fl2va"))
    inputs = schema[class_type]["input"]["required"]
    if replacement is None:
        inputs.pop(input_name)
    else:
        inputs[input_name] = replacement
    handler, client = _handler(tmp_path, "h3_standard_fl2va", object_info=schema)

    with pytest.raises(ValueError, match=class_type + "|" + input_name):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.events == ["object_info"]
    assert not client.uploaded


@pytest.mark.parametrize(
    ("class_type", "input_name", "replacement"),
    [
        ("KSamplerSelect", "sampler_name", ["COMBO", {}]),
        ("BasicScheduler", "scheduler", ["COMBO", {"multiselect": False}]),
        ("KSamplerSelect", "sampler_name", ["COMBO", {"options": []}]),
        ("BasicScheduler", "scheduler", ["COMBO", {"options": []}]),
    ],
)
def test_vdn8_combo_schema_requires_options_before_upload(
    tmp_path: pathlib.Path,
    class_type: str,
    input_name: str,
    replacement: list[Any],
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_fl2va"))
    schema[class_type]["input"]["required"][input_name] = replacement
    handler, client = _handler(tmp_path, "h3_standard_fl2va", object_info=schema)

    with pytest.raises(ValueError, match=class_type + "|" + input_name):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.events == ["object_info"]
    assert not client.uploaded


@pytest.mark.parametrize("steps", [1, 4, 7, 8, 9, 20])
def test_vdn8_rejects_explicit_metadata_steps_before_upload(
    tmp_path: pathlib.Path,
    steps: int,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    handler, client = _handler(tmp_path, "h3_standard_fl2va")

    with pytest.raises(Exception, match="step"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image, steps=steps),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert not client.uploaded
    assert not client.uploaded_files


def test_vdn8_registry_steps_below_floor_fail_before_upload(
    tmp_path: pathlib.Path,
) -> None:
    """A stale bundled graph cannot silently reintroduce a 4-step path."""
    workflow_dir = tmp_path / "registry"
    workflow_dir.mkdir()
    raw = _workflow("h3_standard_fl2va")
    scheduler = _node(raw, "BasicScheduler")
    scheduler["inputs"]["steps"] = 4
    (workflow_dir / "h3_standard_fl2va.json").write_text(
        json.dumps(raw), encoding="utf-8"
    )
    (workflow_dir / "h3_standard_r2v.json").write_text(
        json.dumps(_workflow("h3_standard_r2v")), encoding="utf-8"
    )
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    client = FakeVdnClient(_object_info_for(raw))
    output_root = tmp_path / "output"
    output_root.mkdir()
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root, workflow_dir=workflow_dir),
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="step|8"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image),
            output_prefix="lfo/run/task/attempt/video",
        )
    assert not client.uploaded
    assert not client.uploaded_files


def test_vdn8_execute_records_timing_workflow_hash_and_sampling_metadata(
    tmp_path: pathlib.Path,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    provider_output = output_root / "video" / "clip.mp4"
    client = FakeVdnClient(_object_info_for(_workflow("h3_standard_fl2va")))
    runner = FakeVdnRunner(provider_output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,  # type: ignore[arg-type]
        runner=runner,  # type: ignore[arg-type]
    )
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "projects" / "vdn-test"
    output_path = project_root / "outputs" / "run-1" / "clips" / "clip-1" / "generated.mp4"
    metadata = _i2v_metadata(
        image,
        run_id="run-1",
        output_path=str(output_path),
        artifact_layout={
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
        },
    )

    result = handler.execute(
        "task-1",
        "video.generate",
        "clip-1:video.generate",
        metadata,
        "attempt-1",
    )

    assert result.success is True
    assert runner.submitted is not None
    artifact = result.artifact_metadata
    assert isinstance(artifact["provider_elapsed_seconds"], (int, float))
    assert artifact["provider_elapsed_seconds"] >= 0
    assert isinstance(artifact["handler_elapsed_seconds"], (int, float))
    assert artifact["handler_elapsed_seconds"] >= artifact["provider_elapsed_seconds"]
    assert isinstance(artifact["prepared_workflow_hash"], str)
    assert len(artifact["prepared_workflow_hash"]) == 64
    sampling = artifact["sampling"]
    assert isinstance(sampling, dict)
    assert sampling["steps"] == 8
    assert sampling["sampler_profile"] == "vdn_turbo"
    assert sampling["sampler_name"] == "euler"
    assert sampling["scheduler"] == "simple"
    assert sampling["denoise"] == 1.0
    assert "vdn" in sampling
    assert "sigma_shift" in sampling


@pytest.mark.parametrize(
    ("workflow_id", "media_type", "missing_class"),
    [
        ("h3_standard_fl2va", "image", "LoadImage"),
        ("h3_standard_r2v", "video", "LoadVideo"),
        ("h3_standard_r2v", "video", "GetVideoComponents"),
        ("h3_standard_r2v", "audio", "LoadAudio"),
    ],
)
def test_required_dynamic_reference_node_fails_before_upload(
    tmp_path: pathlib.Path,
    workflow_id: str,
    media_type: str,
    missing_class: str,
) -> None:
    reference = tmp_path / f"reference.{media_type}"
    reference.write_bytes(media_type.encode("ascii"))
    schema = _object_info_for(_workflow(workflow_id))
    schema.pop(missing_class)
    handler, client = _handler(tmp_path, workflow_id, object_info=schema)
    if workflow_id == "h3_standard_fl2va":
        metadata = _i2v_metadata(reference)
    else:
        metadata = _r2v_media_metadata([(reference, media_type)])

    with pytest.raises(ValueError, match=missing_class):
        handler._prepare_workflow(
            workflow_id,
            metadata,
            output_prefix="lfo/run/task/attempt/video",
        )

    assert client.events == ["object_info"]
    assert not client.uploaded
    assert not client.uploaded_files


def test_image_only_r2v_does_not_require_unused_dynamic_media_nodes(
    tmp_path: pathlib.Path,
) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    schema = _object_info_for(_workflow("h3_standard_r2v"))
    for class_type in ("LoadVideo", "GetVideoComponents", "LoadAudio"):
        schema.pop(class_type)
    handler, client = _handler(tmp_path, "h3_standard_r2v", object_info=schema)

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        _r2v_metadata([image]),
        output_prefix="lfo/run/task/attempt/video",
    )

    _assert_vdn8_sampler(workflow)
    assert uploaded == ["lfo-input/reference.png"]
    assert client.uploaded == [image.resolve()]
    assert not client.uploaded_files


def test_audio_only_r2v_does_not_require_template_image_loader(
    tmp_path: pathlib.Path,
) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio")
    schema = _object_info_for(_workflow("h3_standard_r2v"))
    schema.pop("LoadImage")
    handler, client = _handler(tmp_path, "h3_standard_r2v", object_info=schema)

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        _r2v_media_metadata([(audio, "audio")]),
        output_prefix="lfo/run/task/attempt/video",
    )

    _assert_vdn8_sampler(workflow)
    assert uploaded == ["lfo-input/voice.wav"]
    assert not client.uploaded
    assert client.uploaded_files == [audio.resolve()]
    assert not _nodes(workflow, "LoadImage")


def test_equivalent_numeric_reference_slots_fail_before_upload(tmp_path: pathlib.Path) -> None:
    images = [tmp_path / "a.png", tmp_path / "b.png"]
    for path in images:
        path.write_bytes(b"image")
    metadata = _r2v_metadata(images)
    metadata["resolved_references"][1]["slot"] = "ref_image_00"
    handler, client = _handler(tmp_path, "h3_standard_r2v")

    with pytest.raises(ValueError, match="Duplicate"):
        handler._prepare_workflow("h3_standard_r2v", metadata, output_prefix="test/video")

    assert client.events == []
    assert client.uploaded == []


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("megapixels", 0, "megapixels"),
        ("megapixels", float("nan"), "megapixels"),
        ("megapixels", float("inf"), "megapixels"),
        ("megapixels", "not-a-number", "megapixels"),
        ("seed", 1.5, "seed"),
        ("fps", 30, "fps"),
    ],
)
def test_invalid_generation_parameter_fails_before_upload(
    tmp_path: pathlib.Path,
    field: str,
    value: object,
    error: str,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    handler, client = _handler(tmp_path, "h3_standard_fl2va")

    with pytest.raises((TypeError, ValueError), match=error):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            _i2v_metadata(image, **{field: value}),
            output_prefix="lfo/run/task/attempt/video",
        )

    assert not client.uploaded
    assert not client.uploaded_files


def test_missing_later_reference_fails_before_uploading_earlier_references(
    tmp_path: pathlib.Path,
) -> None:
    first = tmp_path / "first.png"
    missing = tmp_path / "missing.png"
    first.write_bytes(b"image")
    handler, client = _handler(tmp_path, "h3_standard_r2v")

    with pytest.raises(FileNotFoundError, match="picture-1"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            _r2v_metadata([first, missing]),
            output_prefix="lfo/run/task/attempt/video",
        )

    assert not client.uploaded
    assert not client.uploaded_files


def test_presenter_keeps_native_20_steps_and_preserves_audio_link(
    tmp_path: pathlib.Path,
) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio")
    handler, client = _handler(tmp_path, "h3_presenter_r2v")

    workflow, uploaded = handler._prepare_workflow(
        "h3_presenter_r2v",
        _presenter_metadata([(audio, "audio")]),
        output_prefix="lfo/run/task/attempt/video",
    )

    scheduler = _node(workflow, "BasicScheduler")
    sampler = _node(workflow, "KSamplerSelect")
    assert scheduler["inputs"]["steps"] == 20
    assert sampler["inputs"]["sampler_name"] == "res_multistep"
    assert not _nodes(workflow, "ApplyVDNH3")
    assert not _nodes(workflow, "MiniMaxH3SigmaShift")
    assert uploaded == ["lfo-input/voice.wav"]
    assert not client.uploaded
    assert client.uploaded_files == [audio.resolve()]

    audio_nodes = _nodes(workflow, "LoadAudio")
    assert len(audio_nodes) == 1
    audio_id = next(node_id for node_id, node in workflow.items() if node is audio_nodes[0])
    assert audio_nodes[0]["inputs"]["audio"] == "lfo-input/voice.wav"
    generator = _node(workflow, "MiniMaxH3ReferenceToVideo")
    assert generator["inputs"]["ref_audios.ref_audio_0"] == [audio_id, 0]
    create_video = _node(workflow, "CreateVideo")
    audio_link = create_video["inputs"]["audio"]
    assert isinstance(audio_link, list)
    assert workflow[str(audio_link[0])]["class_type"] == "VAEDecodeAudio"


@pytest.mark.parametrize("steps", [8, 16, 20, 37])
def test_native_fl2va_uses_explicit_steps_without_vdn_nodes(
    tmp_path: pathlib.Path,
    steps: int,
) -> None:
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    native_workflow = _workflow("h3_native_fl2va")
    object_info = _object_info_for(native_workflow)
    # A native request must not require the optional VDN node bundle.
    object_info.pop("ApplyVDNH3", None)
    object_info.pop("MiniMaxH3SigmaShift", None)
    handler, client = _handler(
        tmp_path,
        "h3_native_fl2va",
        object_info=object_info,
    )
    workflow, uploaded = handler._prepare_workflow(
        "h3_native_fl2va",
        _i2v_metadata(image, sampler_profile="native", steps=steps),
        output_prefix="lfo/run/task/attempt/video",
    )
    assert uploaded == ["lfo-input/first.png"]
    assert client.uploaded == [image.resolve()]
    assert not client.uploaded_files
    assert not _nodes(workflow, "ApplyVDNH3")
    assert not _nodes(workflow, "MiniMaxH3SigmaShift")
    assert _node(workflow, "KSamplerSelect")["inputs"]["sampler_name"] == "res_multistep"
    scheduler = _node(workflow, "BasicScheduler")
    assert scheduler["inputs"]["scheduler"] == "simple"
    assert scheduler["inputs"]["steps"] == steps
    assert scheduler["inputs"]["model"] == ["1", 0]
