"""Production MiniMax H3 backend for local ComfyUI workflows.

The creative boundary stops at :class:`VideoExecutionPackage`.  This module
owns the provider-specific work required to turn one ``video.generate`` task
into a durable local video artifact.
"""
from __future__ import annotations

import hashlib
import pathlib
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

H3_BACKEND_ID = "comfyui.h3"
H3_BACKEND_REVISION = "3.0.0"
H3_MAX_REFERENCE_IMAGES = 9


@dataclass(frozen=True)
class ComfyH3Config:
    """Local paths and wait policy for a ComfyUI H3 installation."""

    base_url: str = "http://127.0.0.1:8188"
    workflow_dir: pathlib.Path = pathlib.Path(__file__).resolve().parents[1] / "registry"
    output_root: pathlib.Path = pathlib.Path(
        "D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output"
    )
    poll_interval_seconds: float = 3.0
    timeout_seconds: float = 1_200.0


def build_h3_backend_registry(
    workflow_dir: pathlib.Path | str | None = None,
) -> BackendRegistry:
    """Build the default capability registry from the bundled H3 workflows."""

    root = pathlib.Path(workflow_dir) if workflow_dir is not None else ComfyH3Config().workflow_dir
    workflow_hashes: list[str] = []
    required_models: set[str] = set()
    for manifest in KNOWN_WORKFLOWS.values():
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
                "video.reference_to_video",
            ],
            accepted_media_types=["image"],
            max_references=H3_MAX_REFERENCE_IMAGES,
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
                "SaveVideo",
            ],
            output_signature={"media_type": "video", "container": "mp4", "codec": "h264"},
            extensions={"workflow_ids": sorted(KNOWN_WORKFLOWS)},
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
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={
                    "file_path": str(output),
                    "file_hash": _sha256_file(output),
                    "media_type": "video",
                    "provider_job_id": prompt_id,
                    "workflow_id": workflow_id,
                    "uploaded_references": uploaded,
                    "size": output.stat().st_size,
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
        if explicit is not None:
            if explicit not in KNOWN_WORKFLOWS:
                raise ValueError(f"Unknown H3 workflow_id: {explicit}")
            return str(explicit)

        operation = metadata.get("operation")
        if not isinstance(operation, str):
            raise ValueError("video.generate metadata.operation is required")
        suffix_by_operation = {
            "video.text_to_video": "t2v",
            "video.image_to_video": "i2v",
            "video.reference_to_video": "r2v",
        }
        suffix = suffix_by_operation.get(operation)
        if suffix is None:
            raise ValueError(f"Unsupported H3 operation: {operation!r}")

        width = metadata.get("width")
        height = metadata.get("height")
        aspect_ratio = str(metadata.get("aspect_ratio") or "")
        portrait = (
            isinstance(width, (int, float))
            and isinstance(height, (int, float))
            and height > width
        ) or aspect_ratio.startswith("9:16")
        return f"h3_{'vertical' if portrait else 'standard'}_{suffix}"

    def _prepare_workflow(
        self,
        workflow_id: str,
        metadata: dict[str, Any],
        *,
        output_prefix: str,
    ) -> tuple[dict[str, Any], list[str]]:
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
        local_paths = [_reference_path(ref) for ref in references]
        uploaded = [self._upload_reference(path) for path in local_paths]

        if manifest.workflow_mode == "i2v":
            if not uploaded:
                raise ValueError(f"{workflow_id} requires a first-frame image")
            values["first_frame"] = uploaded[0]
        elif manifest.workflow_mode == "r2v":
            if not uploaded:
                raise ValueError(f"{workflow_id} requires at least one reference image")
            if len(uploaded) > H3_MAX_REFERENCE_IMAGES:
                raise ValueError(
                    f"{workflow_id} supports at most {H3_MAX_REFERENCE_IMAGES} reference images"
                )
            # The bundled graph contains three convenience loaders.  H3 itself
            # supports a dynamic ref_images group, so bind only the declared
            # slots here and add loader nodes for reference four through nine.
            for index, value in enumerate(uploaded[:3]):
                values[f"ref_image_{index}"] = value

        resolved_values = [(bindings[key], value) for key, value in values.items() if key in bindings]
        prepared = BindingResolver(workflow).apply_values(cast(Any, resolved_values))
        if manifest.workflow_mode == "r2v":
            self._configure_r2v_reference_slots(prepared, bindings, uploaded)
            self._apply_reference_image_size(prepared, metadata.get("reference_image_size"))
        self._apply_seed(prepared, metadata.get("seed"))
        self._apply_fps(prepared, metadata.get("fps"))
        return prepared, uploaded

    @staticmethod
    def _configure_r2v_reference_slots(
        workflow: dict[str, Any],
        bindings: dict[str, Binding],
        uploaded: list[str],
    ) -> None:
        """Bind exactly the requested dynamic H3 reference-image slots."""
        prefix = "ref_images.ref_image_"
        generator_nodes: list[dict[str, Any]] = []
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if any(key.startswith(prefix) for key in inputs):
                generator_nodes.append(node)
        if len(generator_nodes) != 1:
            raise ValueError("H3 R2V workflow requires exactly one reference-image generator node")

        generator_inputs = generator_nodes[0]["inputs"]
        for key in list(generator_inputs):
            if key.startswith(prefix):
                del generator_inputs[key]

        numeric_node_ids = [int(node_id) for node_id in workflow if node_id.isdigit()]
        next_node_id = max(numeric_node_ids, default=0) + 1
        for index, value in enumerate(uploaded):
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
            generator_inputs[f"{prefix}{index}"] = [source_node_id, 0]

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

    def _upload_reference(self, path: pathlib.Path) -> str:
        response = self.client.upload_image(path)
        name = response.get("name")
        if not isinstance(name, str) or not name:
            raise LfoComfyError(f"ComfyUI upload response missing name for {path}")
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
        raise FileNotFoundError(f"Reference file not found: {path}")
    return path


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
