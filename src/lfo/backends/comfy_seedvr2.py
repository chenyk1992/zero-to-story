"""SeedVR2 video-upscale handler for local ComfyUI."""
from __future__ import annotations

import os
import pathlib
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from lfo.comfy.bindings import Binding, BindingResolver
from lfo.comfy.cli import ComfyCliRunner
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError
from lfo.comfy.outputs import materialize_cli_video
from lfo.comfy.workflow import WorkflowLoader
from lfo.contracts.upscale import UpscaleOptions, resolve_upscale_options
from lfo.core.workflow_registry import KNOWN_WORKFLOWS, WorkflowManifest
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.services.artifact_layout import managed_path

SEEDVR2_UPSCALE_WORKFLOW_ID = "seedvr2_upscale"


@dataclass(frozen=True)
class ComfyUpscaleConfig:
    """Local paths and wait policy for the bundled SeedVR2 workflow."""

    base_url: str = "http://127.0.0.1:8188"
    workflow_dir: pathlib.Path = pathlib.Path(__file__).resolve().parents[1] / "registry"
    output_root: pathlib.Path | None = field(
        default_factory=lambda: (
            pathlib.Path(value)
            if (value := os.environ.get("LFO_COMFY_OUTPUT_ROOT"))
            else None
        )
    )
    cli_binary: str = "comfy"
    timeout_seconds: float = 7_200.0


class ComfyUpscaleVideoHandler(TaskHandler):
    """Execute one ``video.upscale`` task with the SeedVR2 ComfyUI workflow."""

    def __init__(
        self,
        config: ComfyUpscaleConfig | None = None,
        *,
        client: ComfyApiClient | None = None,
        cli_runner: ComfyCliRunner | None = None,
    ) -> None:
        self.config = config or ComfyUpscaleConfig()
        self.client = client or ComfyApiClient(self.config.base_url)
        self.cli_runner = cli_runner or ComfyCliRunner(self.config.cli_binary)

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        if task_type != "video.upscale":
            return HandlerResult(
                success=False,
                error=f"Unsupported task type: {task_type}",
                retryable=False,
                failure_class="creative_input",
                recovery_action=None,
            )

        try:
            source_video = self._source_video_path(metadata)
            return self._execute_single(
                task_id,
                logical_key,
                metadata,
                attempt_id,
                source_video,
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
            return HandlerResult(
                success=False, error=str(exc), retryable=False,
                artifact_metadata={"provider_job_id": exc.prompt_id} if exc.prompt_id else {},
                failure_class="execution_transient",
            )
        except LfoComfyError as exc:
            return HandlerResult(
                success=False,
                error=str(exc),
                retryable=False,
                failure_class="execution_transient",
                recovery_action=None,
            )
        except Exception as exc:  # provider extensions may raise their own exception types
            return HandlerResult(
                success=False,
                error=f"ComfyUI execution error: {exc}",
                retryable=False,
                failure_class="execution_transient",
                recovery_action=None,
            )

    def _execute_single(
        self,
        task_id: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
        source_video: pathlib.Path,
    ) -> HandlerResult:
        """Upscale one video file through one ComfyUI prompt."""
        # Validate all local prerequisites before spending provider resources.
        managed = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
        options = self._upscale_options(metadata)
        # H3 and SeedVR2 are both large GPU models.  Release H3's cached
        # weights before loading SeedVR2 on single-GPU workstations.
        self.client.free_memory()
        upload = self.client.upload_file(source_video, subfolder="lfo-input")
        uploaded_name = self._uploaded_name(upload)
        output_prefix = (
            f"lfo/{metadata.get('run_id', 'run')}/{task_id}/{attempt_id}/upscaled"
        )
        workflow, scale_multiplier = self._prepare_workflow(
            metadata,
            uploaded_name,
            output_prefix=output_prefix,
            options=options,
        )
        # Use the workflow's native adaptive temporal chunking on the first
        # and only submission.  An OOM is terminal; LFO never submits a hidden
        # fallback attempt.
        self._enable_temporal_chunking(workflow)
        result = self.cli_runner.run_workflow(
            workflow, base_url=self.config.base_url,
            timeout_seconds=self.config.timeout_seconds,
        )
        managed_hash, managed_size, provider_source = materialize_cli_video(
            result, managed, output_root=self.config.output_root,
            client=self.client, timeout_seconds=self.config.timeout_seconds,
            base_url=self.config.base_url,
        )
        artifact_metadata = {
            "file_path": str(managed.resolve()),
            "file_hash": managed_hash,
            "media_type": "video",
            "provider_job_id": result.prompt_id,
            "workflow_id": SEEDVR2_UPSCALE_WORKFLOW_ID,
            "source_video_path": str(source_video),
            "uploaded_source": uploaded_name,
            "scale_multiplier": scale_multiplier,
            "size": managed_size,
            "provider_source_path": provider_source,
            "provider_file_hash": managed_hash,
        }
        return HandlerResult(
            success=True,
            artifact_type="video",
            artifact_metadata=artifact_metadata,
        )

    def _best_effort_interrupt(self) -> None:
        """Ask ComfyUI to stop the timed-out prompt once, without masking failure."""
        with suppress(Exception):
            self.client.interrupt()

    @staticmethod
    def _enable_temporal_chunking(workflow: dict[str, Any]) -> None:
        """Switch a bundled direct workflow to ComfyUI's adaptive chunk mode."""
        for node_id in ("11", "15"):
            workflow[node_id]["inputs"]["switch"] = True
        chunk_inputs = workflow["8"]["inputs"]
        chunk_inputs["chunking_mode"] = "auto"
        chunk_inputs.pop("chunking_mode.frames_per_chunk", None)

    def _prepare_workflow(
        self,
        metadata: dict[str, Any],
        uploaded_name: str,
        *,
        output_prefix: str,
        options: UpscaleOptions | None = None,
    ) -> tuple[dict[str, Any], float]:
        if options is None:
            options = self._upscale_options(metadata)

        manifest = KNOWN_WORKFLOWS[SEEDVR2_UPSCALE_WORKFLOW_ID]
        workflow = WorkflowLoader.load(self.config.workflow_dir / manifest.source_file)
        bindings = self._resolve_bindings(workflow, manifest)
        values: dict[str, Any] = {
            "input_video": uploaded_name,
            "scale_multiplier": options.scale_multiplier,
            "filename_prefix": output_prefix.replace("\\", "/"),
        }
        if options.seed is not None:
            values["seed"] = options.seed
        resolved_values = [
            (bindings[key], value) for key, value in values.items() if key in bindings
        ]
        return BindingResolver(workflow).apply_values(resolved_values), options.scale_multiplier

    @staticmethod
    def _upscale_options(metadata: dict[str, Any]) -> UpscaleOptions:
        config = metadata.get("upscale", {})
        options = resolve_upscale_options({"upscale": config}, {})
        if not options.enabled:
            raise ValueError("video.upscale metadata.upscale.enabled must be true")
        return options

    @staticmethod
    def _resolve_bindings(
        workflow: dict[str, Any],
        manifest: WorkflowManifest,
    ) -> dict[str, Binding]:
        resolver = BindingResolver(workflow)
        resolved: dict[str, Binding] = {}
        for slot in manifest.input_slots:
            binding = Binding(
                binding_id=slot.binding_id,
                selector_title=slot.selector_title,
                selector_class_type=slot.selector_class_type,
                input_name=slot.input_name,
            )
            resolved[slot.binding_id] = resolver.resolve_binding(binding)
        return resolved

    @staticmethod
    def _source_video_path(metadata: dict[str, Any]) -> pathlib.Path:
        input_artifacts = metadata.get("input_artifacts")
        if not isinstance(input_artifacts, dict) or not input_artifacts:
            raise ValueError("video.upscale requires one upstream video artifact")
        input_task_ids = metadata.get("input_task_ids")
        artifact_ids = input_task_ids if isinstance(input_task_ids, list) else list(input_artifacts)
        candidates: list[pathlib.Path] = []
        for source_task_id in artifact_ids:
            artifact = input_artifacts.get(source_task_id)
            if not isinstance(artifact, dict):
                continue
            file_path = artifact.get("file_path")
            if isinstance(file_path, str) and file_path:
                candidates.append(pathlib.Path(file_path).resolve())
        if len(candidates) != 1:
            raise ValueError("video.upscale requires exactly one upstream video artifact")
        source = candidates[0]
        if not source.is_file():
            raise FileNotFoundError(f"Upstream video artifact not found: {source}")
        return source

    @staticmethod
    def _uploaded_name(upload: object) -> str:
        if not isinstance(upload, dict):
            raise TypeError("ComfyUI upload response must be an object")
        name = upload.get("name")
        subfolder = upload.get("subfolder", "")
        if not isinstance(name, str) or not name:
            raise ValueError("ComfyUI upload response did not include a file name")
        if not isinstance(subfolder, str):
            raise TypeError("ComfyUI upload response subfolder must be a string")
        return f"{subfolder.rstrip('/')}/{name}" if subfolder else name
