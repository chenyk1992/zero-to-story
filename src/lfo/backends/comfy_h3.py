"""Production MiniMax H3 backend for local ComfyUI workflows.

The creative boundary stops at :class:`VideoExecutionPackage`.  This module
owns the provider-specific work required to turn one ``video.generate`` task
into a durable local video artifact.
"""
from __future__ import annotations

import hashlib
import math
import os
import pathlib
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, cast

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.comfy.bindings import Binding, BindingResolver
from lfo.comfy.cli import ComfyCliRunner, ComfyCliRunResult
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError
from lfo.comfy.outputs import materialize_cli_video
from lfo.comfy.validation import validate_workflow_environment
from lfo.comfy.workflow import WorkflowLoader
from lfo.contracts.operations import validate_operation_references
from lfo.core.hashing import compute_workflow_hash
from lfo.core.workflow_registry import KNOWN_WORKFLOWS, WorkflowManifest
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.services.artifact_layout import managed_path

H3_BACKEND_ID = "comfyui.h3"
H3_BACKEND_REVISION = "4.0.0"
H3_PRESENTER_BACKEND_ID = "comfyui.h3-presenter"
H3_PRESENTER_BACKEND_REVISION = "3.0.0"
H3_FL2VA_WORKFLOW_ID = "h3_standard_fl2va"
H3_R2V_WORKFLOW_ID = "h3_standard_r2v"
H3_NATIVE_FL2VA_WORKFLOW_ID = "h3_native_fl2va"
H3_NATIVE_R2V_WORKFLOW_ID = "h3_native_r2v"
H3_MAX_REFERENCE_IMAGES = 9
H3_MAX_REFERENCE_VIDEOS = 3
H3_MAX_REFERENCE_AUDIO = 3
H3_MAX_REFERENCES = (
    H3_MAX_REFERENCE_IMAGES + H3_MAX_REFERENCE_VIDEOS + H3_MAX_REFERENCE_AUDIO
)
H3_MAX_DURATION_MS = 15_000
H3_REFERENCE_NODE_CLASSES = {
    "image": {"LoadImage"},
    "video": {"LoadVideo", "GetVideoComponents"},
    "audio": {"LoadAudio"},
}
H3_RESOLUTION_ASPECTS = {
    "1:1": "1:1 (Square)",
    "2:3": "2:3 (Portrait Photo)",
    "3:2": "3:2 (Photo)",
    "3:4": "3:4 (Portrait Standard)",
    "4:3": "4:3 (Standard)",
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Widescreen)",
    "21:9": "21:9 (Ultrawide)",
}
H3_FL2VA_OPERATIONS = frozenset({
    "video.text_to_video",
    "video.image_to_video",
    "video.first_last_frame",
})


@dataclass(frozen=True)
class ComfyH3Config:
    """Local paths and wait policy for a ComfyUI H3 installation."""

    base_url: str = "http://127.0.0.1:8188"
    workflow_dir: pathlib.Path = pathlib.Path(__file__).resolve().parents[1] / "registry"
    output_root: pathlib.Path | None = field(
        default_factory=lambda: _optional_env_path("LFO_COMFY_OUTPUT_ROOT")
    )
    # ``comfy run --wait`` owns monitoring; this is its per-event silence limit.
    timeout_seconds: float = 7_200.0
    cli_binary: str = "comfy"


def build_h3_backend_registry(
    workflow_dir: pathlib.Path | str | None = None,
) -> BackendRegistry:
    """Build the default capability registry from the bundled H3 workflows."""

    root = pathlib.Path(workflow_dir) if workflow_dir is not None else ComfyH3Config().workflow_dir
    workflow_hashes: list[str] = []
    profile_models: dict[str, set[str]] = {}
    profile_nodes: dict[str, set[str]] = {}
    h3_workflow_ids: list[str] = []
    for manifest in KNOWN_WORKFLOWS.values():
        if not manifest.family.startswith("h3_") or manifest.workflow_id == "h3_presenter_r2v":
            continue
        h3_workflow_ids.append(manifest.workflow_id)
        workflow = WorkflowLoader.load(root / manifest.source_file)
        errors = WorkflowLoader.validate_workflow(workflow)
        if errors:
            raise ValueError(f"Invalid bundled workflow {manifest.source_file}: {'; '.join(errors)}")
        workflow_hashes.append(compute_workflow_hash(workflow))
        profile = manifest.sampling_profile
        if profile is None:
            raise ValueError(f"Bundled H3 workflow {manifest.workflow_id} has no sampling profile")
        profile_models.setdefault(profile, set()).update(
            dep.filename for dep in manifest.model_dependencies if dep.required
        )
        profile_nodes.setdefault(profile, set()).update(
            {node["class_type"] for node in workflow.values()}
            | set().union(*H3_REFERENCE_NODE_CLASSES.values())
        )

    # Only unconditional dependencies belong in the backend-wide manifest.
    # Profile-specific requirements remain discoverable without making a
    # native-only installation appear to require the optional VDN bundle.
    required_models = set.intersection(*profile_models.values())
    required_nodes = set.intersection(*profile_nodes.values())

    aggregate_hash = hashlib.sha256("\n".join(sorted(workflow_hashes)).encode("utf-8")).hexdigest()
    registry = BackendRegistry()
    registry.register(
        CapabilityManifest(
            backend_id=H3_BACKEND_ID,
            revision=H3_BACKEND_REVISION,
            workflow_hash=aggregate_hash,
            operations=[
                "video.text_to_video",
                "video.image_to_video",
                "video.first_last_frame",
                "video.reference_to_video",
            ],
            accepted_media_types=["image", "video", "audio"],
            max_references=H3_MAX_REFERENCES,
            duration_constraints={"min_ms": 200, "max_ms": H3_MAX_DURATION_MS},
            frame_constraints={"formula": "17k+5", "fps": 24},
            resolution_constraints={
                "min_width": 256,
                "max_width": 4096,
                "min_height": 256,
                "max_height": 4096,
                "width_multiple": 32,
                "height_multiple": 32,
            },
            fps_constraints=[24.0],
            native_audio_capability="always",
            seed_capability=True,
            reproducibility_claim="best_effort",
            required_models=sorted(required_models),
            required_nodes=sorted(required_nodes),
            output_signature={"media_type": "video", "container": "mp4", "codec": "h264"},
            extensions={
                "workflow_ids": sorted(h3_workflow_ids),
                "sampling_profiles": {
                    "native": {"min_steps": 8},
                    "vdn_turbo": {"allowed_steps": [8]},
                },
                "sampling_dependencies": {
                    profile: {
                        "required_models": sorted(profile_models[profile]),
                        "required_nodes": sorted(profile_nodes[profile]),
                    }
                    for profile in sorted(profile_models)
                },
            },
        )
    )
    presenter = KNOWN_WORKFLOWS["h3_presenter_r2v"]
    presenter_workflow = WorkflowLoader.load(root / presenter.source_file)
    presenter_errors = WorkflowLoader.validate_workflow(presenter_workflow)
    if presenter_errors:
        raise ValueError(
            f"Invalid bundled workflow {presenter.source_file}: {'; '.join(presenter_errors)}"
        )
    presenter_models = sorted(
        dependency.filename
        for dependency in presenter.model_dependencies
        if dependency.required
    )
    registry.register(
        CapabilityManifest(
            backend_id=H3_PRESENTER_BACKEND_ID,
            revision=H3_PRESENTER_BACKEND_REVISION,
            workflow_hash=compute_workflow_hash(presenter_workflow),
            operations=["video.virtual_presenter"],
            accepted_media_types=["image", "video", "audio"],
            max_references=H3_MAX_REFERENCES,
            duration_constraints={"min_ms": 4_000, "max_ms": 15_000},
            frame_constraints={"formula": "17k+5", "fps": 24},
            resolution_constraints={
                "min_width": 256,
                "max_width": 4096,
                "min_height": 256,
                "max_height": 4096,
                "width_multiple": 32,
                "height_multiple": 32,
            },
            fps_constraints=[24.0],
            native_audio_capability="always",
            seed_capability=True,
            reproducibility_claim="best_effort",
            required_models=presenter_models,
            required_nodes=sorted(
                {node["class_type"] for node in presenter_workflow.values()}
                | set().union(*H3_REFERENCE_NODE_CLASSES.values())
            ),
            output_signature={"media_type": "video", "container": "mp4", "codec": "h264"},
            extensions={
                "workflow_ids": [presenter.workflow_id],
                "sampling_profiles": {"native": {"min_steps": 8}},
            },
        )
    )
    return registry


class ComfyH3VideoHandler(TaskHandler):
    """Execute a ``video.generate`` task against local ComfyUI."""

    def __init__(
        self,
        config: ComfyH3Config | None = None,
        *,
        client: ComfyApiClient | None = None,
        runner: ComfyCliRunner | None = None,
    ) -> None:
        self.config = config or ComfyH3Config()
        self.client = client or ComfyApiClient(self.config.base_url)
        self.runner = runner or ComfyCliRunner(self.config.cli_binary)

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        if task_type != "video.generate":
            return HandlerResult(
                success=False,
                error=f"Unsupported task type: {task_type}",
                retryable=False,
                failure_class="creative_input",
                recovery_action=None,
            )

        started = time.monotonic()
        try:
            workflow_id = self._select_workflow(metadata)
            workflow, uploaded = self._prepare_workflow(
                workflow_id,
                metadata,
                output_prefix=f"lfo/{metadata.get('run_id', 'run')}/{task_id}/{attempt_id}/video",
            )
            provider_started = time.monotonic()
            cli_result = self.runner.run_workflow(
                workflow,
                base_url=self.config.base_url,
                timeout_seconds=self.config.timeout_seconds,
            )
            provider_elapsed = time.monotonic() - provider_started
            prompt_id = cli_result.prompt_id
            managed = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
            managed_hash, managed_size, provider_source = self._materialize_cli_output(
                cli_result,
                managed,
            )
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={
                    "file_path": str(managed.resolve()),
                    "file_hash": managed_hash,
                    "media_type": "video",
                    "provider_job_id": prompt_id,
                    "workflow_id": workflow_id,
                    "prepared_workflow_hash": compute_workflow_hash(workflow),
                    "sampling": self._sampling_parameters(
                        workflow,
                        sampler_profile=_effective_sampling_profile(metadata, workflow_id),
                    ),
                    "provider_elapsed_seconds": round(provider_elapsed, 3),
                    "handler_elapsed_seconds": round(time.monotonic() - started, 3),
                    "uploaded_references": uploaded,
                    "size": managed_size,
                    "provider_source_path": provider_source,
                    "provider_file_hash": managed_hash,
                },
            )
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            return HandlerResult(
                success=False,
                error=str(exc),
                retryable=False,
                failure_class="creative_input",
                recovery_action=None,
            )
        except ComfyCliTimeoutError as exc:
            self._best_effort_interrupt()
            artifact_metadata = (
                {"provider_job_id": exc.prompt_id}
                if exc.prompt_id is not None
                else {}
            )
            return HandlerResult(
                success=False,
                error=f"comfy-cli execution error: {exc}",
                retryable=False,
                artifact_metadata=artifact_metadata,
                failure_class="execution_failed",
                recovery_action=None,
            )
        except Exception as exc:  # provider extensions may raise their own exception types
            return HandlerResult(
                success=False,
                error=f"comfy-cli execution error: {exc}",
                retryable=False,
                failure_class="execution_failed",
                recovery_action=None,
            )

    def _best_effort_interrupt(self) -> None:
        """Ask ComfyUI to stop the timed-out prompt once, without masking failure."""
        with suppress(Exception):
            self.client.interrupt()

    @staticmethod
    def _select_workflow(metadata: dict[str, Any]) -> str:
        explicit = metadata.get("workflow_id")
        operation = metadata.get("operation")
        profile = _requested_sampling_profile(metadata)
        if operation == "video.virtual_presenter" and profile == "vdn_turbo":
            raise ValueError(
                "video.virtual_presenter supports only the native sampler profile"
            )
        if (
            operation == "video.virtual_presenter"
            and explicit is not None
            and str(explicit) != "h3_presenter_r2v"
        ):
            raise ValueError("video.virtual_presenter is fixed to h3_presenter_r2v")
        if explicit is not None:
            requested = str(explicit)
            manifest = KNOWN_WORKFLOWS.get(requested)
            if manifest is None or not manifest.family.startswith("h3_"):
                raise ValueError(f"Unknown H3 workflow_id: {explicit}")
            if not isinstance(operation, str) or not operation:
                raise ValueError("video.generate metadata.operation is required")
            expected = _workflow_for_operation(operation, profile)
            if requested != expected:
                raise ValueError(
                    f"H3 workflow {requested!r} does not implement operation {operation!r}; "
                    f"use {expected!r}"
                )
            return requested

        if not isinstance(operation, str):
            raise ValueError("video.generate metadata.operation is required")
        return _workflow_for_operation(operation, profile)

    def _prepare_workflow(
        self,
        workflow_id: str,
        metadata: dict[str, Any],
        *,
        output_prefix: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Validate and bind one request, then upload its references serially."""
        _reject_pixel_dimensions(metadata)
        operation = metadata.get("operation")
        if not isinstance(operation, str) or not operation:
            raise ValueError("video.generate metadata.operation is required")
        profile = _effective_sampling_profile(metadata, workflow_id)
        if _workflow_for_operation(operation, _requested_sampling_profile(metadata)) != workflow_id:
            raise ValueError(
                f"H3 workflow {workflow_id!r} does not implement operation {operation!r}"
            )
        manifest = KNOWN_WORKFLOWS[workflow_id]
        duration_ms = _validate_h3_duration(
            metadata.get("duration_ms", 5_000),
            minimum_ms=4_000 if operation == "video.virtual_presenter" else 200,
        )
        prompt = str(metadata.get("prompt") or "")
        if not prompt:
            raise ValueError("video.generate metadata.prompt is required")
        references = _validate_h3_references(operation, metadata.get("resolved_references", []))
        # Resolve every local file before performing any upload.
        reference_paths = [_reference_path(reference) for reference in references]
        media_types = [str(reference.get("media_type") or "image") for reference in references]
        workflow = WorkflowLoader.load(self.config.workflow_dir / manifest.source_file)
        bindings = self._resolve_bindings(workflow, manifest)
        values = {
            "prompt": prompt,
            "duration": duration_ms / 1_000.0,
            "filename_prefix": output_prefix.replace("\\", "/"),
        }
        prepared = BindingResolver(workflow).apply_values([
            (bindings[key], value) for key, value in values.items()
        ])
        if manifest.workflow_mode == "r2v":
            self._apply_reference_image_size(prepared, metadata.get("reference_image_size"))
            used_image_slots = {
                int(str(reference["slot"]).rsplit("_", 1)[1])
                for reference, kind in zip(references, media_types, strict=True)
                if kind == "image"
            }
            generator_inputs = self._r2v_generator_inputs(prepared)
            for binding_id, binding in bindings.items():
                if not binding_id.startswith("ref_image_"):
                    continue
                if int(binding_id.rsplit("_", 1)[1]) not in used_image_slots:
                    if binding.resolved_node_id is not None:
                        prepared.pop(binding.resolved_node_id, None)
                    generator_inputs.pop(f"ref_images.{binding_id}", None)
        self._apply_aspect_ratio(prepared, metadata.get("aspect_ratio"))
        self._apply_megapixels(prepared, metadata.get("megapixels"))
        self._apply_seed(prepared, metadata.get("seed"))
        self._apply_fps(prepared, metadata.get("fps"))
        _apply_sampling_profile(prepared, profile, metadata.get("steps"))
        self._check_workflow_environment(
            prepared,
            reference_media_types=media_types,
            sampler_profile=profile,
        )

        uploaded = [
            self._upload_reference(path, media_type)
            for path, media_type in zip(reference_paths, media_types, strict=True)
        ]
        if manifest.workflow_mode == "fl2va":
            self._configure_fl2va_frames(prepared, references, uploaded)
        else:
            grouped = {
                media_type: [
                    (reference, name)
                    for reference, name, kind in zip(references, uploaded, media_types, strict=True)
                    if kind == media_type
                ]
                for media_type in H3_REFERENCE_NODE_CLASSES
            }
            self._configure_r2v_reference_slots(
                prepared, bindings, grouped["image"], grouped["video"], grouped["audio"],
            )
        return prepared, uploaded

    @staticmethod
    def _r2v_generator_inputs(workflow: dict[str, Any]) -> dict[str, Any]:
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "MiniMaxH3ReferenceToVideo")
        if len(nodes) != 1:
            raise ValueError("H3 R2V workflow requires exactly one MiniMaxH3ReferenceToVideo node")
        return nodes[0][1]["inputs"]

    @staticmethod
    def _configure_r2v_reference_slots(
        workflow: dict[str, Any],
        bindings: dict[str, Binding],
        image_references: list[tuple[dict[str, Any], str]],
        video_references: list[tuple[dict[str, Any], str]],
        audio_references: list[tuple[dict[str, Any], str]] | None = None,
    ) -> None:
        """Bind exactly the requested H3 references without reassigning fixed slots."""
        image_prefix = "ref_images.ref_image_"
        video_prefix = "ref_videos.ref_video_"
        generator_inputs = ComfyH3VideoHandler._r2v_generator_inputs(workflow)
        for key in list(generator_inputs):
            if key.startswith(
                (
                    image_prefix,
                    video_prefix,
                    "ref_video_audios.ref_video_audio_",
                    "ref_audios.ref_audio_",
                )
            ):
                del generator_inputs[key]

        numeric_node_ids = [int(node_id) for node_id in workflow if node_id.isdigit()]
        next_node_id = max(numeric_node_ids, default=0) + 1
        image_slots = _r2v_reference_slots(image_references)
        video_slots = _r2v_reference_slots(video_references)
        audio_slots = _r2v_reference_slots(audio_references or [])

        for index, value in image_slots:
            binding = bindings.get(f"ref_image_{index}")
            if binding is not None:
                if binding.resolved_node_id is None:
                    raise ValueError(f"H3 R2V reference binding {index} was not resolved")
                source_node_id = binding.resolved_node_id
                source_node = workflow.get(source_node_id)
                if not isinstance(source_node, dict):
                    raise ValueError(f"H3 R2V reference node {source_node_id} was not found")
                source_node.setdefault("inputs", {})["image"] = value
            else:
                source_node_id = str(next_node_id)
                next_node_id += 1
                workflow[source_node_id] = {
                    "_meta": {"title": f"LFO.DynamicReference{index + 1}"},
                    "class_type": "LoadImage",
                    "inputs": {"image": value},
                }
            generator_inputs[f"{image_prefix}{index}"] = [source_node_id, 0]

        for index, value in video_slots:
            load_node_id = str(next_node_id)
            next_node_id += 1
            components_node_id = str(next_node_id)
            next_node_id += 1
            workflow[load_node_id] = {
                "_meta": {"title": f"LFO.DynamicReferenceVideo{index + 1}"},
                "class_type": "LoadVideo",
                "inputs": {"file": value},
            }
            workflow[components_node_id] = {
                "_meta": {"title": f"LFO.DynamicReferenceVideoComponents{index + 1}"},
                "class_type": "GetVideoComponents",
                "inputs": {"video": [load_node_id, 0]},
            }
            generator_inputs[f"{video_prefix}{index}"] = [components_node_id, 0]
            generator_inputs[f"ref_video_audios.ref_video_audio_{index}"] = [
                components_node_id,
                1,
            ]

        for index, value in audio_slots:
            node_id = str(next_node_id)
            next_node_id += 1
            workflow[node_id] = {
                "_meta": {"title": f"LFO.DynamicReferenceAudio{index + 1}"},
                "class_type": "LoadAudio",
                "inputs": {"audio": value},
            }
            generator_inputs[f"ref_audios.ref_audio_{index}"] = [node_id, 0]

    @staticmethod
    def _configure_fl2va_frames(
        workflow: dict[str, Any],
        image_refs: list[dict[str, Any]],
        uploaded_images: list[str],
    ) -> None:
        first, last = _fl2va_frame_uploads(image_refs, uploaded_images)
        generator_nodes = [
            node
            for node in workflow.values()
            if isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ImageToVideo"
        ]
        if len(generator_nodes) != 1:
            raise ValueError("H3 FL2VA workflow requires exactly one MiniMaxH3ImageToVideo node")
        generator_inputs = generator_nodes[0].setdefault("inputs", {})
        for key in ("first_frame", "last_frame"):
            generator_inputs.pop(key, None)
        numeric_node_ids = [int(node_id) for node_id in workflow if node_id.isdigit()]
        next_node_id = max(numeric_node_ids, default=0) + 1
        if first is not None:
            node_id = str(next_node_id)
            next_node_id += 1
            workflow[node_id] = {
                "_meta": {"title": "LFO.FirstFrame"},
                "class_type": "LoadImage",
                "inputs": {"image": first},
            }
            generator_inputs["first_frame"] = [node_id, 0]
        if last is not None:
            node_id = str(next_node_id)
            workflow[node_id] = {
                "_meta": {"title": "LFO.LastFrame"},
                "class_type": "LoadImage",
                "inputs": {"image": last},
            }
            generator_inputs["last_frame"] = [node_id, 0]

    @staticmethod
    def _resolve_bindings(
        workflow: dict[str, Any], manifest: WorkflowManifest
    ) -> dict[str, Binding]:
        resolver = BindingResolver(workflow)
        result: dict[str, Binding] = {}
        for slot in manifest.input_slots:
            binding = Binding(
                binding_id=slot.binding_id,
                selector_title=slot.selector_title,
                selector_class_type=slot.selector_class_type,
                input_name=slot.input_name,
            )
            result[slot.binding_id] = resolver.resolve_binding(binding)
        return result

    def _upload_reference(self, path: pathlib.Path, media_type: str = "image") -> str:
        response: dict[str, Any]
        if media_type in {"video", "audio"}:
            response = self.client.upload_file(path, subfolder="lfo-input")
        else:
            response = self.client.upload_image(path)
        name = response.get("name")
        if not isinstance(name, str) or not name:
            raise LfoComfyError("ComfyUI upload response missing uploaded file name")
        subfolder = response.get("subfolder")
        return f"{subfolder}/{name}" if isinstance(subfolder, str) and subfolder else name

    @staticmethod
    def _apply_seed(workflow: dict[str, Any], seed: object) -> None:
        if seed is None:
            return
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "RandomNoise")
        if len(nodes) != 1:
            raise ValueError(f"Expected one RandomNoise node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["noise_seed"] = seed

    @staticmethod
    def _apply_reference_image_size(workflow: dict[str, Any], value: object) -> None:
        if value is None:
            return
        if value not in {"match", "max"}:
            raise ValueError("H3 reference_image_size must be 'match' or 'max'")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "MiniMaxH3ReferenceToVideo")
        if len(nodes) != 1:
            raise ValueError(f"Expected one MiniMaxH3ReferenceToVideo node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["ref_image_size"] = value

    @staticmethod
    def _apply_aspect_ratio(workflow: dict[str, Any], aspect_ratio: object) -> None:
        """Override the bundled ResolutionSelector aspect combo."""
        if aspect_ratio is None:
            return
        if not isinstance(aspect_ratio, str) or not aspect_ratio.strip():
            raise TypeError("H3 aspect_ratio must be a non-empty string")
        selector_value = _resolution_selector_aspect(aspect_ratio)
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "ResolutionSelector")
        if len(nodes) != 1:
            raise ValueError(f"Expected one ResolutionSelector node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["aspect_ratio"] = selector_value

    @staticmethod
    def _apply_megapixels(workflow: dict[str, Any], megapixels: object) -> None:
        """Override the bundled resolution selector's megapixel target."""
        if megapixels is None:
            return
        if isinstance(megapixels, bool) or not isinstance(megapixels, (int, float, str)):
            raise TypeError("H3 megapixels must be numeric")
        try:
            megapixels_value = float(megapixels)
        except (TypeError, ValueError):
            raise TypeError("H3 megapixels must be numeric") from None
        if not math.isfinite(megapixels_value) or megapixels_value <= 0:
            raise ValueError("H3 megapixels must be positive and finite")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "ResolutionSelector")
        if len(nodes) != 1:
            raise ValueError(f"Expected one ResolutionSelector node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["megapixels"] = megapixels_value

    def _check_workflow_environment(
        self,
        workflow: dict[str, Any],
        *,
        reference_media_types: list[str],
        sampler_profile: str,
    ) -> None:
        """Include the loaders that this request will add after reference upload."""
        self._sampling_parameters(workflow, sampler_profile=sampler_profile)
        reference_nodes: set[str] = set().union(*(
            H3_REFERENCE_NODE_CLASSES[kind] for kind in reference_media_types
        ))
        validate_workflow_environment(
            workflow, self.client.get_object_info(), required_node_classes=reference_nodes,
        )

    @staticmethod
    def _sampling_parameters(
        workflow: dict[str, Any], *, sampler_profile: str | None = None,
    ) -> dict[str, Any]:
        """Read effective sampling settings from the graph, never override them."""
        parameters: dict[str, Any] = {}
        for class_type in ("BasicScheduler", "KSamplerSelect"):
            nodes = WorkflowLoader.find_nodes_by_class(workflow, class_type)
            if len(nodes) != 1:
                raise ValueError(f"Expected one {class_type} node, found {len(nodes)}")
            parameters.update({
                key: value for key, value in nodes[0][1]["inputs"].items()
                if not isinstance(value, list)
            })
        steps = parameters.get("steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 8:
            raise ValueError("H3 workflow steps must be an integer of at least 8")
        if sampler_profile is not None:
            parameters["sampler_profile"] = sampler_profile
        for class_type, key in (("ApplyVDNH3", "vdn"), ("MiniMaxH3SigmaShift", "sigma_shift")):
            nodes = WorkflowLoader.find_nodes_by_class(workflow, class_type)
            if nodes:
                parameters[key] = {
                    name: value for name, value in nodes[0][1]["inputs"].items()
                    if not isinstance(value, list)
                }
        return parameters

    @staticmethod
    def _apply_fps(workflow: dict[str, Any], fps: object) -> None:
        if fps is None:
            return
        if not isinstance(fps, (int, float)) or isinstance(fps, bool):
            raise TypeError("fps must be numeric")
        if float(fps) != 24.0:
            raise ValueError("Bundled H3 workflows support only 24 fps")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "CreateVideo")
        if len(nodes) == 1:
            nodes[0][1].setdefault("inputs", {})["fps"] = 24

    def _materialize_cli_output(
        self,
        result: ComfyCliRunResult,
        managed: pathlib.Path,
    ) -> tuple[str, int, str]:
        return materialize_cli_video(
            result, managed, output_root=self.config.output_root,
            client=self.client, timeout_seconds=self.config.timeout_seconds,
            base_url=self.config.base_url,
        )


def _optional_env_path(name: str) -> pathlib.Path | None:
    value = os.environ.get(name)
    return pathlib.Path(value) if value else None


def _reject_pixel_dimensions(metadata: dict[str, Any]) -> None:
    if metadata.get("width") is not None or metadata.get("height") is not None:
        raise ValueError(
            "H3 generation uses aspect_ratio and megapixels; do not pass width or height"
        )


def _requested_sampling_profile(metadata: dict[str, Any]) -> str | None:
    """Validate and return a request's explicit profile, if present."""
    profile = metadata.get("sampler_profile")
    steps = metadata.get("steps")
    if profile is None and steps is None:
        return None
    if profile is None or steps is None:
        raise ValueError("sampler_profile and steps must be provided together")
    if not isinstance(profile, str) or not profile.strip():
        raise ValueError("sampler_profile must be a non-empty string")
    if profile not in {"native", "vdn_turbo"}:
        raise ValueError(f"Unsupported H3 sampler_profile: {profile!r}")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 8:
        raise ValueError("H3 steps must be an integer of at least 8")
    if profile == "vdn_turbo" and steps != 8:
        raise ValueError("vdn_turbo supports exactly 8 steps")
    return profile


def _effective_sampling_profile(metadata: dict[str, Any], workflow_id: str) -> str:
    """Resolve explicit profile or preserve the historical graph default."""
    requested = _requested_sampling_profile(metadata)
    if requested is not None:
        return requested
    # Existing standard packages point at the bundled VDN8 graph. Presenter
    # has always been native and retains its graph's 20-step default.
    return "native" if workflow_id == "h3_presenter_r2v" else "vdn_turbo"


def _apply_sampling_profile(
    workflow: dict[str, Any],
    sampler_profile: str,
    requested_steps: object,
) -> None:
    """Apply only the explicitly supported dynamic sampling change."""
    scheduler_nodes = WorkflowLoader.find_nodes_by_class(workflow, "BasicScheduler")
    if len(scheduler_nodes) != 1:
        raise ValueError(f"Expected one BasicScheduler node, found {len(scheduler_nodes)}")
    scheduler_inputs = scheduler_nodes[0][1].setdefault("inputs", {})
    if sampler_profile == "native":
        if WorkflowLoader.find_nodes_by_class(workflow, "ApplyVDNH3"):
            raise ValueError("native sampler workflow must not contain ApplyVDNH3")
        if WorkflowLoader.find_nodes_by_class(workflow, "MiniMaxH3SigmaShift"):
            raise ValueError("native sampler workflow must not contain MiniMaxH3SigmaShift")
        sampler_nodes = WorkflowLoader.find_nodes_by_class(workflow, "KSamplerSelect")
        if len(sampler_nodes) != 1:
            raise ValueError(f"Expected one KSamplerSelect node, found {len(sampler_nodes)}")
        if sampler_nodes[0][1].setdefault("inputs", {}).get("sampler_name") != "res_multistep":
            raise ValueError("native sampler workflow must use res_multistep")
        if scheduler_inputs.get("scheduler") != "simple":
            raise ValueError("native sampler workflow must use the simple scheduler")
        if requested_steps is not None:
            if isinstance(requested_steps, bool) or not isinstance(requested_steps, int):
                raise TypeError("steps must be an integer")
            if requested_steps < 8:
                raise ValueError("native steps must be an integer of at least 8")
            scheduler_inputs["steps"] = requested_steps
        return
    if sampler_profile == "vdn_turbo":
        if requested_steps is not None and requested_steps != 8:
            raise ValueError("vdn_turbo supports exactly 8 steps")
        if not WorkflowLoader.find_nodes_by_class(workflow, "ApplyVDNH3"):
            raise ValueError("vdn_turbo workflow requires ApplyVDNH3")
        if not WorkflowLoader.find_nodes_by_class(workflow, "MiniMaxH3SigmaShift"):
            raise ValueError("vdn_turbo workflow requires MiniMaxH3SigmaShift")
        if scheduler_inputs.get("steps") != 8:
            raise ValueError("vdn_turbo workflow must use exactly 8 steps")
        return
    raise ValueError(f"Unsupported H3 sampler_profile: {sampler_profile!r}")


def _workflow_for_operation(operation: str, sampler_profile: str | None = None) -> str:
    if sampler_profile not in {None, "native", "vdn_turbo"}:
        raise ValueError(f"Unsupported H3 sampler_profile: {sampler_profile!r}")
    if operation == "video.virtual_presenter":
        if sampler_profile == "vdn_turbo":
            raise ValueError(
                "video.virtual_presenter supports only the native sampler profile"
            )
        return "h3_presenter_r2v"
    if sampler_profile == "native":
        if operation in H3_FL2VA_OPERATIONS:
            return H3_NATIVE_FL2VA_WORKFLOW_ID
        if operation == "video.reference_to_video":
            return H3_NATIVE_R2V_WORKFLOW_ID
    if operation in H3_FL2VA_OPERATIONS:
        return H3_FL2VA_WORKFLOW_ID
    if operation == "video.reference_to_video":
        return H3_R2V_WORKFLOW_ID
    raise ValueError(f"Unsupported H3 operation: {operation!r}")


def _validate_h3_duration(value: object, *, minimum_ms: int = 200) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("H3 duration_ms must be numeric")
    duration_ms = float(value)
    if not math.isfinite(duration_ms) or not minimum_ms <= duration_ms <= H3_MAX_DURATION_MS:
        raise ValueError(
            f"H3 duration_ms must be between {minimum_ms} and {H3_MAX_DURATION_MS}"
        )
    return duration_ms


def _validate_h3_references(operation: str, references: object) -> list[dict[str, Any]]:
    """Reuse public reference rules; add only H3 limits and presenter continuity."""
    validate_operation_references(operation, references)
    validated = cast(list[dict[str, Any]], references)
    if operation not in {"video.reference_to_video", "video.virtual_presenter"}:
        return validated
    limits = {
        "image": H3_MAX_REFERENCE_IMAGES,
        "video": H3_MAX_REFERENCE_VIDEOS,
        "audio": H3_MAX_REFERENCE_AUDIO,
    }
    slots: dict[str, set[int]] = {kind: set() for kind in limits}
    for reference in validated:
        media_type = str(reference.get("media_type") or "image")
        slot = str(reference["slot"])
        index = int(slot.rsplit("_", 1)[1])
        if index >= limits[media_type]:
            raise ValueError(f"{operation} slot {slot!r} is out of range")
        if index in slots[media_type]:
            raise ValueError(f"Duplicate {operation} slot {slot!r}")
        slots[media_type].add(index)
    if operation == "video.virtual_presenter":
        for media_type, indices in slots.items():
            if indices and indices != set(range(max(indices) + 1)):
                raise ValueError(f"Presenter {media_type} reference slots must be contiguous from 0")
        order = {kind: index for index, kind in enumerate(limits)}
        return sorted(validated, key=lambda reference: (
            order[str(reference.get("media_type") or "image")],
            int(str(reference["slot"]).rsplit("_", 1)[1]),
        ))
    return validated


def _r2v_reference_slots(
    references: list[tuple[dict[str, Any], str]],
) -> list[tuple[int, str]]:
    """Read already-validated explicit slots; never infer reference positions."""
    return sorted((int(str(reference["slot"]).rsplit("_", 1)[1]), name) for reference, name in references)


def _resolution_selector_aspect(aspect_ratio: str) -> str:
    trimmed = aspect_ratio.strip()
    if trimmed in H3_RESOLUTION_ASPECTS.values():
        return trimmed
    mapped = H3_RESOLUTION_ASPECTS.get(trimmed)
    if mapped is None:
        raise ValueError(
            f"Unsupported H3 aspect_ratio {aspect_ratio!r}; "
            f"expected one of {sorted(H3_RESOLUTION_ASPECTS)}"
        )
    return mapped


def _fl2va_frame_uploads(
    image_refs: list[dict[str, Any]],
    uploaded_images: list[str],
) -> tuple[str | None, str | None]:
    first: str | None = None
    last: str | None = None
    for reference, uploaded in zip(image_refs, uploaded_images, strict=True):
        placement = str(reference.get("placement") or "")
        slot = str(reference.get("slot") or "")
        if placement == "first" or slot in {"first_frame", "ref_image_first"}:
            first = uploaded
        elif placement == "last" or slot in {"last_frame", "ref_image_last"}:
            last = uploaded
    return first, last


def _reference_path(reference: object) -> pathlib.Path:
    if not isinstance(reference, dict):
        raise TypeError("Each resolved reference must be an object")
    value = reference.get("blob_path") or reference.get("file_path") or reference.get("path")
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"Reference {reference.get('reference_id', '<unknown>')} has no imported local path"
        )
    path = pathlib.Path(value).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Reference {reference.get('reference_id', '<unknown>')} file is unavailable"
        )
    return path
