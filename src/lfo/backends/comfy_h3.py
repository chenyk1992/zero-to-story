"""Production MiniMax H3 backend for local ComfyUI workflows.

The creative boundary stops at :class:`VideoExecutionPackage`.  This module
owns the provider-specific work required to turn one ``video.generate`` task
into a durable local video artifact.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import uuid
from dataclasses import dataclass
from typing import Any, cast

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.comfy.bindings import Binding, BindingResolver
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import ComfyUnreachableError, LfoComfyError
from lfo.comfy.monitor import ComfyMonitor
from lfo.comfy.workflow import WorkflowLoader
from lfo.core.hashing import compute_workflow_hash
from lfo.core.workflow_registry import KNOWN_WORKFLOWS, WorkflowManifest
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.services.artifact_layout import atomic_copy_verified, managed_path

H3_BACKEND_ID = "comfyui.h3"
H3_BACKEND_REVISION = "3.0.0"
H3_PRESENTER_BACKEND_ID = "comfyui.h3-presenter"
H3_PRESENTER_BACKEND_REVISION = "3.0.0"
H3_FL2VA_WORKFLOW_ID = "h3_standard_fl2va"
H3_R2V_WORKFLOW_ID = "h3_standard_r2v"
H3_MAX_REFERENCE_IMAGES = 9
H3_MAX_REFERENCE_VIDEOS = 3
H3_MAX_REFERENCE_AUDIO = 3
H3_MAX_REFERENCES = (
    H3_MAX_REFERENCE_IMAGES + H3_MAX_REFERENCE_VIDEOS + H3_MAX_REFERENCE_AUDIO
)
H3_PRESENTER_MAX_REFERENCES = 15
H3_PRESENTER_MAX_REFERENCE_IMAGES = 9
H3_PRESENTER_MAX_REFERENCE_VIDEOS = 3
H3_PRESENTER_MAX_REFERENCE_AUDIO = 3
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
    output_root: pathlib.Path = pathlib.Path(
        "D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output"
    )
    poll_interval_seconds: float = 3.0
    # H3 768P clips with long reference videos can exceed the generic
    # twenty-minute provider wait; keep the worker alive while ComfyUI
    # continues sampling instead of orphaning a valid prompt.
    timeout_seconds: float = 7_200.0
    # Match the H3 turbo 8-step distillation lora (minimax_h3_fl2v_turbo_8step_v1.0).
    # 20 steps defeats the purpose of the lora and adds unnecessary forward overhead.
    # Override per task via metadata.steps when a higher-quality pass is required.
    steps: int = 8


def build_h3_backend_registry(
    workflow_dir: pathlib.Path | str | None = None,
) -> BackendRegistry:
    """Build the default capability registry from the bundled H3 workflows."""

    root = pathlib.Path(workflow_dir) if workflow_dir is not None else ComfyH3Config().workflow_dir
    workflow_hashes: list[str] = []
    required_models: set[str] = set()
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
        required_models.update(dep.filename for dep in manifest.model_dependencies if dep.required)

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
            duration_constraints={"min_ms": 200, "max_ms": 150_000},
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
            required_nodes=[
                "MiniMaxH3ImageToVideo",
                "MiniMaxH3ReferenceToVideo",
                "LoadImage",
                "LoadVideo",
                "GetVideoComponents",
                "LoadAudio",
                "SaveVideo",
            ],
            output_signature={"media_type": "video", "container": "mp4", "codec": "h264"},
            extensions={"workflow_ids": sorted(h3_workflow_ids)},
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
            max_references=H3_PRESENTER_MAX_REFERENCES,
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
            required_nodes=[
                "MiniMaxH3ReferenceToVideo",
                "LoadImage",
                "LoadVideo",
                "GetVideoComponents",
                "LoadAudio",
                "VAEDecode",
                "VAEDecodeAudio",
                "CreateVideo",
                "SaveVideo",
            ],
            output_signature={"media_type": "video", "container": "mp4", "codec": "h264"},
            extensions={"workflow_ids": [presenter.workflow_id]},
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
        monitor: ComfyMonitor | None = None,
    ) -> None:
        self.config = config or ComfyH3Config()
        self.client = client or ComfyApiClient(self.config.base_url)
        self.monitor = monitor or ComfyMonitor(self.client)

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        if task_type != "video.generate":
            return HandlerResult(success=False, error=f"Unsupported task type: {task_type}", retryable=False)

        try:
            workflow_id = self._select_workflow(metadata)
            workflow, uploaded = self._prepare_workflow(
                workflow_id,
                metadata,
                output_prefix=f"lfo/{metadata.get('run_id', 'run')}/{task_id}/{attempt_id}/video",
            )
            client_id = f"lfo-{uuid.uuid4().hex}"
            submitted = self.client.submit_prompt(workflow, client_id=client_id)
            prompt_id = submitted.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise LfoComfyError("ComfyUI response did not include prompt_id")

            status = self.monitor.poll_until_done(
                prompt_id,
                interval=self.config.poll_interval_seconds,
                timeout=self.config.timeout_seconds,
            )
            if status.get("status") == "timeout":
                return HandlerResult(
                    success=False,
                    error=f"ComfyUI prompt {prompt_id} timed out",
                    retryable=True,
                    artifact_metadata={"provider_job_id": prompt_id},
                )
            if not status.get("completed"):
                return HandlerResult(
                    success=False,
                    error=f"ComfyUI prompt {prompt_id} failed: {status.get('error') or status.get('status')}",
                    retryable=False,
                    artifact_metadata={"provider_job_id": prompt_id},
                )

            output = self._find_output(prompt_id, status)
            managed = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
            managed_hash, managed_size = atomic_copy_verified(output, managed)
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={
                    "file_path": str(managed.resolve()),
                    "file_hash": managed_hash,
                    "media_type": "video",
                    "provider_job_id": prompt_id,
                    "workflow_id": workflow_id,
                    "uploaded_references": uploaded,
                    "size": managed_size,
                    "provider_source_path": str(output),
                    "provider_file_hash": _sha256_file(output),
                },
            )
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            return HandlerResult(success=False, error=str(exc), retryable=False)
        except ComfyUnreachableError as exc:
            return HandlerResult(success=False, error=str(exc), retryable=True)
        except Exception as exc:  # provider extensions may raise their own exception types
            return HandlerResult(success=False, error=f"ComfyUI execution error: {exc}", retryable=True)

    @staticmethod
    def _select_workflow(metadata: dict[str, Any]) -> str:
        explicit = metadata.get("workflow_id")
        operation = metadata.get("operation")
        if operation == "video.virtual_presenter":
            if explicit is not None and str(explicit) != "h3_presenter_r2v":
                raise ValueError(
                    "video.virtual_presenter is fixed to h3_presenter_r2v"
                )
            return "h3_presenter_r2v"
        if explicit is not None:
            requested = str(explicit)
            manifest = KNOWN_WORKFLOWS.get(requested)
            if manifest is None or not manifest.family.startswith("h3_"):
                raise ValueError(f"Unknown H3 workflow_id: {explicit}")
            return requested

        if not isinstance(operation, str):
            raise ValueError("video.generate metadata.operation is required")
        if operation in H3_FL2VA_OPERATIONS:
            return H3_FL2VA_WORKFLOW_ID
        if operation == "video.reference_to_video":
            return H3_R2V_WORKFLOW_ID
        raise ValueError(f"Unsupported H3 operation: {operation!r}")

    def _prepare_workflow(
        self,
        workflow_id: str,
        metadata: dict[str, Any],
        *,
        output_prefix: str,
    ) -> tuple[dict[str, Any], list[str]]:
        if workflow_id == "h3_presenter_r2v":
            return self._prepare_presenter_workflow(metadata, output_prefix=output_prefix)
        _reject_pixel_dimensions(metadata)
        manifest = KNOWN_WORKFLOWS[workflow_id]
        workflow = WorkflowLoader.load(self.config.workflow_dir / manifest.source_file)
        bindings = self._resolve_bindings(workflow, manifest)
        values: dict[str, str | float] = {
            "prompt": str(metadata.get("prompt") or ""),
            "duration": max(0.2, float(metadata.get("duration_ms", 5_000)) / 1_000.0),
            "filename_prefix": output_prefix.replace("\\", "/"),
        }
        if not values["prompt"]:
            raise ValueError("video.generate metadata.prompt is required")

        references = metadata.get("resolved_references", [])
        if not isinstance(references, list):
            raise TypeError("resolved_references must be a list")
        uploaded: list[str] = []
        uploaded_images: list[str] = []
        uploaded_videos: list[str] = []
        uploaded_audios: list[str] = []
        image_refs: list[dict[str, Any]] = []
        allowed_media = (
            {"image", "video", "audio"}
            if manifest.workflow_mode == "r2v"
            else {"image"}
        )
        for ref in references:
            if not isinstance(ref, dict):
                raise TypeError("Each resolved reference must be an object")
            media_type = str(ref.get("media_type") or "image")
            if media_type not in allowed_media:
                raise ValueError(f"H3 references do not support media type {media_type!r}")
            uploaded_name = self._upload_reference(_reference_path(ref), media_type)
            uploaded.append(uploaded_name)
            if media_type == "video":
                uploaded_videos.append(uploaded_name)
            elif media_type == "audio":
                uploaded_audios.append(uploaded_name)
            else:
                uploaded_images.append(uploaded_name)
                image_refs.append(ref)

        if manifest.workflow_mode == "fl2va":
            self._require_fl2va_frames(
                str(metadata.get("operation") or ""),
                workflow_id,
                image_refs,
                uploaded_images,
            )
        elif manifest.workflow_mode == "r2v":
            if not uploaded_images and not uploaded_videos and not uploaded_audios:
                raise ValueError(
                    f"{workflow_id} requires at least one reference image, video or audio"
                )
            if len(uploaded_images) > H3_MAX_REFERENCE_IMAGES:
                raise ValueError(
                    f"{workflow_id} supports at most {H3_MAX_REFERENCE_IMAGES} image references"
                )
            if len(uploaded_videos) > H3_MAX_REFERENCE_VIDEOS:
                raise ValueError(
                    f"{workflow_id} supports at most {H3_MAX_REFERENCE_VIDEOS} reference videos"
                )
            if len(uploaded_audios) > H3_MAX_REFERENCE_AUDIO:
                raise ValueError(
                    f"{workflow_id} supports at most {H3_MAX_REFERENCE_AUDIO} standalone audio references"
                )
            for index, value in enumerate(uploaded_images[:3]):
                values[f"ref_image_{index}"] = value

        resolved_values = [(bindings[key], value) for key, value in values.items() if key in bindings]
        prepared = BindingResolver(workflow).apply_values(cast(Any, resolved_values))
        if manifest.workflow_mode == "fl2va":
            self._configure_fl2va_frames(
                prepared,
                str(metadata.get("operation") or ""),
                image_refs,
                uploaded_images,
            )
        elif manifest.workflow_mode == "r2v":
            self._configure_r2v_reference_slots(
                prepared,
                bindings,
                uploaded_images,
                uploaded_videos,
                uploaded_audios,
            )
            self._apply_reference_image_size(prepared, metadata.get("reference_image_size"))
        self._apply_aspect_ratio(prepared, metadata.get("aspect_ratio"))
        self._apply_megapixels(prepared, metadata.get("megapixels"))
        self._apply_steps(prepared, metadata.get("steps", self.config.steps))
        self._apply_seed(prepared, metadata.get("seed"))
        self._apply_fps(prepared, metadata.get("fps"))
        return prepared, uploaded

    def _prepare_presenter_workflow(
        self,
        metadata: dict[str, Any],
        *,
        output_prefix: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Prepare Presenter R2V using explicit materialized reference slots.

        Presenter references are not positional.  The materializer supplies a
        ``ref_image_N``, ``ref_video_N`` or ``ref_audio_N`` slot and the slot
        determines both the ComfyUI input and the prompt-facing Picture/Video/
        Audio N+1 identity.
        """
        _reject_pixel_dimensions(metadata)
        manifest = KNOWN_WORKFLOWS["h3_presenter_r2v"]
        workflow = WorkflowLoader.load(self.config.workflow_dir / manifest.source_file)
        bindings = self._resolve_bindings(workflow, manifest)
        prompt = str(metadata.get("prompt") or "")
        if not prompt:
            raise ValueError("video.generate metadata.prompt is required")
        values: dict[str, str | float] = {
            "prompt": prompt,
            "duration": max(0.2, float(metadata.get("duration_ms", 5_000)) / 1_000.0),
            "filename_prefix": output_prefix.replace("\\", "/"),
        }

        references = self._validate_presenter_references(metadata.get("resolved_references", []))
        uploaded: list[str] = []
        prepared_references: list[tuple[str, str, str]] = []
        for reference in references:
            path = _reference_path(reference)
            media_type = str(reference["media_type"])
            uploaded_name = self._upload_reference(path, media_type)
            uploaded.append(uploaded_name)
            prepared_references.append((str(reference["slot"]), media_type, uploaded_name))

        resolved_values = [
            (bindings[key], value) for key, value in values.items() if key in bindings
        ]
        prepared = BindingResolver(workflow).apply_values(cast(Any, resolved_values))
        self._configure_presenter_reference_slots(prepared, prepared_references)
        self._apply_reference_image_size(prepared, metadata.get("reference_image_size"))
        self._apply_aspect_ratio(prepared, metadata.get("aspect_ratio"))
        self._apply_megapixels(prepared, metadata.get("megapixels"))
        self._apply_steps(prepared, metadata.get("steps", self.config.steps))
        self._apply_seed(prepared, metadata.get("seed"))
        self._apply_fps(prepared, metadata.get("fps"))
        return prepared, uploaded

    @staticmethod
    def _validate_presenter_references(references: object) -> list[dict[str, Any]]:
        """Validate Presenter slots without inferring them from array order."""
        if not isinstance(references, list):
            raise TypeError("resolved_references must be a list")
        if len(references) > H3_PRESENTER_MAX_REFERENCES:
            raise ValueError(
                f"h3_presenter_r2v supports at most {H3_PRESENTER_MAX_REFERENCES} references"
            )

        validated: list[dict[str, Any]] = []
        seen_slots: set[str] = set()
        max_indices = {
            "image": H3_PRESENTER_MAX_REFERENCE_IMAGES - 1,
            "video": H3_PRESENTER_MAX_REFERENCE_VIDEOS - 1,
            "audio": H3_PRESENTER_MAX_REFERENCE_AUDIO - 1,
        }
        slots_by_type: dict[str, list[int]] = {"image": [], "video": [], "audio": []}
        for reference in references:
            if not isinstance(reference, dict):
                raise TypeError("Each resolved reference must be an object")
            media_type = reference.get("media_type")
            if media_type not in max_indices:
                raise ValueError(
                    f"h3_presenter_r2v does not support reference media type {media_type!r}"
                )
            slot = reference.get("slot")
            if not isinstance(slot, str):
                raise ValueError("Presenter references require materialized ref.slot")
            match = re.fullmatch(r"ref_(image|video|audio)_([0-9]+)", slot)
            if match is None:
                raise ValueError(
                    f"Invalid Presenter reference slot {slot!r}; expected ref_image_N, "
                    "ref_video_N or ref_audio_N"
                )
            slot_type, raw_index = match.groups()
            index = int(raw_index)
            if slot_type != media_type:
                raise ValueError(
                    f"Presenter slot {slot!r} does not match media type {media_type!r}"
                )
            if index > max_indices[slot_type]:
                raise ValueError(f"Presenter reference slot {slot!r} is out of range")
            if slot in seen_slots:
                raise ValueError(f"Duplicate Presenter reference slot {slot!r}")
            seen_slots.add(slot)
            slots_by_type[slot_type].append(index)
            validated.append(reference)

        if not validated:
            raise ValueError("h3_presenter_r2v requires at least one reference")
        for slot_type, indices in slots_by_type.items():
            if indices:
                expected = list(range(max(indices) + 1))
                if sorted(indices) != expected:
                    raise ValueError(
                        f"Presenter {slot_type} reference slots must be contiguous from 0"
                    )
        order = {"image": 0, "video": 1, "audio": 2}
        return sorted(
            validated,
            key=lambda reference: (
                order[str(reference["media_type"])],
                int(str(reference["slot"]).rsplit("_", 1)[1]),
            ),
        )

    @staticmethod
    def _configure_presenter_reference_slots(
        workflow: dict[str, Any],
        references: list[tuple[str, str, str]],
    ) -> None:
        """Inject Presenter Load* nodes and wire each declared materialized slot."""
        generator_nodes = [
            (node_id, node)
            for node_id, node in workflow.items()
            if isinstance(node, dict)
            and node.get("class_type") == "MiniMaxH3ReferenceToVideo"
            and isinstance(node.get("_meta"), dict)
            and node["_meta"].get("title") == "LFO.MainGenerator"
        ]
        if len(generator_nodes) != 1:
            raise ValueError("Presenter workflow requires exactly one titled H3 R2V generator")
        generator_inputs = generator_nodes[0][1].setdefault("inputs", {})
        for key in list(generator_inputs):
            if key.startswith(("ref_images.", "ref_videos.", "ref_video_audios.", "ref_audios.")):
                del generator_inputs[key]

        numeric_node_ids = [int(node_id) for node_id in workflow if node_id.isdigit()]
        next_node_id = max(numeric_node_ids, default=0) + 1
        for slot, media_type, uploaded_name in references:
            index = int(slot.rsplit("_", 1)[1])
            node_id = str(next_node_id)
            next_node_id += 1
            if media_type == "image":
                workflow[node_id] = {
                    "_meta": {"title": f"LFO.PresenterPicture{index + 1}"},
                    "class_type": "LoadImage",
                    "inputs": {"image": uploaded_name},
                }
                generator_inputs[f"ref_images.ref_image_{index}"] = [node_id, 0]
            elif media_type == "video":
                components_node_id = str(next_node_id)
                next_node_id += 1
                workflow[node_id] = {
                    "_meta": {"title": f"LFO.PresenterVideo{index + 1}"},
                    "class_type": "LoadVideo",
                    "inputs": {"file": uploaded_name},
                }
                workflow[components_node_id] = {
                    "_meta": {"title": f"LFO.PresenterVideoComponents{index + 1}"},
                    "class_type": "GetVideoComponents",
                    "inputs": {"video": [node_id, 0]},
                }
                generator_inputs[f"ref_videos.ref_video_{index}"] = [components_node_id, 0]
                generator_inputs[f"ref_video_audios.ref_video_audio_{index}"] = [
                    components_node_id,
                    1,
                ]
            else:
                workflow[node_id] = {
                    "_meta": {"title": f"LFO.PresenterAudio{index + 1}"},
                    "class_type": "LoadAudio",
                    "inputs": {"audio": uploaded_name},
                }
                generator_inputs[f"ref_audios.ref_audio_{index}"] = [node_id, 0]

    @staticmethod
    def _configure_r2v_reference_slots(
        workflow: dict[str, Any],
        bindings: dict[str, Binding],
        uploaded_images: list[str],
        uploaded_videos: list[str],
        uploaded_audios: list[str] | None = None,
    ) -> None:
        """Bind exactly the requested H3 image and video reference slots."""
        image_prefix = "ref_images.ref_image_"
        video_prefix = "ref_videos.ref_video_"
        generator_nodes: list[dict[str, Any]] = []
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if any(key.startswith(image_prefix) for key in inputs):
                generator_nodes.append(node)
        if len(generator_nodes) != 1:
            raise ValueError("H3 R2V workflow requires exactly one reference-image generator node")

        generator_inputs = generator_nodes[0]["inputs"]
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
        for index, value in enumerate(uploaded_images):
            if index < 3:
                binding = bindings[f"ref_image_{index}"]
                if binding.resolved_node_id is None:
                    raise ValueError(f"H3 R2V reference binding {index} was not resolved")
                source_node_id = binding.resolved_node_id
            else:
                source_node_id = str(next_node_id)
                next_node_id += 1
                workflow[source_node_id] = {
                    "_meta": {"title": f"LFO.DynamicReference{index + 1}"},
                    "class_type": "LoadImage",
                    "inputs": {"image": value},
                }
            generator_inputs[f"{image_prefix}{index}"] = [source_node_id, 0]

        for index, value in enumerate(uploaded_videos):
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

        for index, value in enumerate(uploaded_audios or []):
            node_id = str(next_node_id)
            next_node_id += 1
            workflow[node_id] = {
                "_meta": {"title": f"LFO.DynamicReferenceAudio{index + 1}"},
                "class_type": "LoadAudio",
                "inputs": {"audio": value},
            }
            generator_inputs[f"ref_audios.ref_audio_{index}"] = [node_id, 0]

    @staticmethod
    def _require_fl2va_frames(
        operation: str,
        workflow_id: str,
        image_refs: list[dict[str, Any]],
        uploaded_images: list[str],
    ) -> None:
        first, last = _fl2va_frame_uploads(operation, image_refs, uploaded_images)
        if operation == "video.image_to_video" and first is None:
            raise ValueError(f"{workflow_id} requires a first-frame image")
        if operation == "video.first_last_frame" and (first is None or last is None):
            raise ValueError(f"{workflow_id} requires first-frame and last-frame images")
        if operation == "video.text_to_video" and uploaded_images:
            raise ValueError(
                "video.text_to_video does not accept image references; "
                "use video.image_to_video, video.first_last_frame or video.reference_to_video"
            )

    @staticmethod
    def _configure_fl2va_frames(
        workflow: dict[str, Any],
        operation: str,
        image_refs: list[dict[str, Any]],
        uploaded_images: list[str],
    ) -> None:
        first, last = _fl2va_frame_uploads(operation, image_refs, uploaded_images)
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
            result[slot.binding_id] = resolver.resolve_binding(binding, mode="strict")
        return result

    def _upload_reference(self, path: pathlib.Path, media_type: str = "image") -> str:
        response: dict[str, Any]
        if media_type in {"video", "audio"}:
            upload_file = getattr(self.client, "upload_file", None)
            if not callable(upload_file):
                raise LfoComfyError("ComfyUI client does not support generic file upload")
            response = cast(dict[str, Any], upload_file(path, subfolder="lfo-input"))
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
        if megapixels_value <= 0:
            raise ValueError("H3 megapixels must be positive")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "ResolutionSelector")
        if len(nodes) != 1:
            raise ValueError(f"Expected one ResolutionSelector node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["megapixels"] = megapixels_value

    @staticmethod
    def _apply_steps(workflow: dict[str, Any], steps: object) -> None:
        """Set the H3 sampler step count used by the local resource profile."""
        if not isinstance(steps, int) or isinstance(steps, bool):
            raise TypeError("H3 steps must be an integer")
        if steps < 1 or steps > 100:
            raise ValueError("H3 steps must be between 1 and 100")
        nodes = WorkflowLoader.find_nodes_by_class(workflow, "BasicScheduler")
        if len(nodes) != 1:
            raise ValueError(f"Expected one BasicScheduler node, found {len(nodes)}")
        nodes[0][1].setdefault("inputs", {})["steps"] = steps

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

    def _find_output(self, prompt_id: str, status: dict[str, Any]) -> pathlib.Path:
        outputs = status.get("outputs")
        if not isinstance(outputs, dict) or not outputs:
            history = self.client.get_history(prompt_id)
            entry = history.get(prompt_id, {})
            outputs = entry.get("outputs", {}) if isinstance(entry, dict) else {}

        candidates: list[pathlib.Path] = []
        for node_output in outputs.values() if isinstance(outputs, dict) else []:
            if not isinstance(node_output, dict):
                continue
            for collection in ("video", "videos", "images", "gifs"):
                items = node_output.get(collection, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not isinstance(filename, str) or not filename:
                        continue
                    subfolder = item.get("subfolder", "")
                    path = self.config.output_root / str(subfolder) / filename
                    if path.is_file():
                        candidates.append(path.resolve())
        if not candidates:
            raise FileNotFoundError(f"No local output found for ComfyUI prompt {prompt_id}")
        videos = [p for p in candidates if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]
        return max(videos or candidates, key=lambda p: p.stat().st_mtime_ns)


def _reject_pixel_dimensions(metadata: dict[str, Any]) -> None:
    if metadata.get("width") is not None or metadata.get("height") is not None:
        raise ValueError(
            "H3 generation uses aspect_ratio and megapixels; do not pass width or height"
        )


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
    operation: str,
    image_refs: list[dict[str, Any]],
    uploaded_images: list[str],
) -> tuple[str | None, str | None]:
    if operation == "video.text_to_video" or not uploaded_images:
        return None, None
    first: str | None = None
    last: str | None = None
    for reference, uploaded in zip(image_refs, uploaded_images, strict=False):
        placement = str(reference.get("placement") or "")
        slot = str(reference.get("slot") or "")
        if placement == "first" or slot in {"first_frame", "ref_image_first"}:
            first = uploaded
        elif placement == "last" or slot in {"last_frame", "ref_image_last"}:
            last = uploaded
    if first is None:
        first = uploaded_images[0]
    if last is None and operation == "video.first_last_frame" and len(uploaded_images) >= 2:
        last = uploaded_images[1]
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


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
