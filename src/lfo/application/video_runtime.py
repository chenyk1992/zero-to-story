"""Persistent public facade for LFO Runtime v1."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import string
import uuid
from dataclasses import dataclass, field
from typing import Any

from lfo.assets.importer import AssetImporter
from lfo.assets.store import ContentAddressedStore
from lfo.backends.comfy_h3 import ComfyH3Config, ComfyH3VideoHandler
from lfo.backends.comfy_seedvr2 import ComfyUpscaleConfig, ComfyUpscaleVideoHandler
from lfo.backends.passthrough import (
    PASSTHROUGH_BACKEND_ID,
    PASSTHROUGH_BACKEND_REVISION,
    build_passthrough_capability,
)
from lfo.backends.registry import BackendRegistry
from lfo.backends.video_router import VideoTaskRouter, build_video_backend_registry
from lfo.config.config_resolver import ResolvedConfig, resolve_config
from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.execution import ExecutionStore
from lfo.execution.dag import build_dag
from lfo.execution.handlers import HandlerRegistry
from lfo.execution.materializer import MaterializationError, MaterializedRun, materialize
from lfo.execution.runtime import PersistentRuntime
from lfo.execution.states import RunState, is_valid_run_transition
from lfo.media.handlers import build_media_handler_registry
from lfo.services.artifact_layout import ArtifactLayoutError, RunArtifactLayout
from lfo.services.workspace import resolve_workspace_root


@dataclass
class ValidationResult2:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    package_sha256: str | None = None


@dataclass
class PlanResult:
    plan_id: str
    clip_plans: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backend_summary: list[dict[str, str]] = field(default_factory=list)
    output_layout: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class RunResult:
    run_id: str
    status: str
    clip_count: int = 0
    output_layout: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    file_path: str | None = None


@dataclass
class StatusResult:
    run_id: str
    status: str
    tasks: dict[str, str] = field(default_factory=dict)
    output_layout: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ExportResult2:
    export_id: str
    status: str
    file_path: str | None = None
    error: str | None = None


class VideoRuntime:
    """Validate, plan and execute immutable video packages with durable state."""

    def __init__(
        self,
        registry: BackendRegistry | None = None,
        *,
        db_path: str | pathlib.Path | None = None,
        workspace_root: str | pathlib.Path | None = None,
        handler_registry: HandlerRegistry | None = None,
        machine_id: str = "",
    ) -> None:
        self.workspace_root = (
            pathlib.Path(workspace_root).resolve()
            if workspace_root is not None
            else resolve_workspace_root()
        )
        self.db_path = pathlib.Path(db_path or self.workspace_root / "db" / "runtime-v1.sqlite3")
        self.store = ExecutionStore(self.db_path)
        self.config = resolve_config(machine_id=machine_id)
        if machine_id and self.config.machine_profile is None:
            raise ValueError(f"Machine profile not found: {machine_id}")
        self.registry = registry or build_video_backend_registry()
        # Passthrough is an LFO-owned execution primitive, not an optional
        # provider capability.  Keep it available even when a caller injects
        # a reduced provider registry for tests or a machine-specific setup.
        if self.registry.get(PASSTHROUGH_BACKEND_ID, PASSTHROUGH_BACKEND_REVISION) is None:
            self.registry.register(build_passthrough_capability())
        self.handlers = handler_registry or self._production_handlers()
        self.cas = ContentAddressedStore(self.workspace_root / "assets")

    def _production_handlers(self) -> HandlerRegistry:
        handlers = build_media_handler_registry(self.workspace_root)
        comfy_config = _comfy_h3_config(self.config)
        handlers.register(
            "video.generate",
            VideoTaskRouter(comfy_h3_handler=ComfyH3VideoHandler(comfy_config)),
        )
        handlers.register(
            "video.upscale",
            ComfyUpscaleVideoHandler(
                ComfyUpscaleConfig(
                    base_url=comfy_config.base_url,
                    output_root=comfy_config.output_root,
                    cli_binary=comfy_config.cli_binary,
                    timeout_seconds=comfy_config.timeout_seconds,
                ),
            ),
        )
        return handlers

    def _record_task_progress(self, event: dict[str, Any]) -> None:
        """Persist live handler progress without changing task state."""
        task_id = event.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return
        task = self.store.get_task(task_id)
        if task is None:
            return
        metadata = json.loads(str(task.get("metadata") or "{}"))
        metadata["progress"] = dict(event)
        self.store.update_task_metadata(task_id, metadata)

    def validate(self, path: pathlib.Path | str) -> ValidationResult2:
        package_path = pathlib.Path(path).resolve()
        try:
            raw, package_sha256 = _read_package_bytes(package_path)
            data = _parse_package_bytes(raw)
        except Exception as exc:
            return ValidationResult2(False, [_error(str(path), str(exc), "parse_error")])
        result = self._validate_package_data(package_path, data)
        result.package_sha256 = package_sha256
        return result

    def _validate_package_data(
        self,
        package_path: pathlib.Path,
        data: Any,
    ) -> ValidationResult2:
        """Validate already-read package data without reopening its file."""

        result = validate_package(data)
        errors = [error.to_dict() for error in result.errors()]
        warnings: list[str] = []
        if result.ok:
            try:
                package = VideoExecutionPackage.from_dict(data)
                errors.extend(self._validate_asset_sources(package_path, package))
                try:
                    RunArtifactLayout.from_package(
                        workspace_root=self.workspace_root,
                        run_id="run-validation",
                        package=package,
                    )
                except ArtifactLayoutError as exc:
                    errors.append(_error("$.project.project_id", str(exc), "project_layout"))
            except (TypeError, ValueError) as exc:
                errors.append(_error("$", str(exc), "parse"))
        return ValidationResult2(not errors, errors, warnings)

    def plan(self, path: pathlib.Path | str) -> PlanResult:
        package_path = pathlib.Path(path).resolve()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        try:
            package, package_hash = self._validated_package(package_path)
            # Planning is deliberately read-only.  Execution imports assets
            # into CAS and records durable revisions, but a diagnostic plan
            # must only resolve the original package-relative source paths.
            assets = self._plan_asset_resolutions(package_path, package)
            layout = RunArtifactLayout.from_package(
                workspace_root=self.workspace_root,
                run_id=plan_id,
                package=package,
            )
            snapshot = materialize(
                run_id=plan_id,
                package=package,
                package_hash=package_hash,
                registry=self.registry,
                asset_resolutions=assets,
                artifact_layout=layout.to_dict(),
            )
        except MaterializationError as exc:
            return PlanResult(plan_id, error=exc.message, warnings=exc.details)
        except Exception as exc:
            return PlanResult(plan_id, error=str(exc))
        return self._plan_result(plan_id, snapshot)

    def execute(
        self,
        path: pathlib.Path | str,
        approved_sha256: str | None = None,
    ) -> RunResult:
        package_path = pathlib.Path(path).resolve()
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        run_created = False
        try:
            raw, actual_hash = _read_package_bytes(package_path)
            if not _matches_sha256(approved_sha256, actual_hash):
                return RunResult(
                    "",
                    "REJECTED",
                    error="approved_sha256 must exactly match the package file SHA-256",
                )
            package_data = _parse_package_bytes(raw)
            package, package_hash = self._validated_package(
                package_path,
                package_data=package_data,
                expected_hash=actual_hash,
            )
            layout = RunArtifactLayout.from_package(
                workspace_root=self.workspace_root,
                run_id=run_id,
                package=package,
            )
            # Durable services are initialized only after the exact package
            # hash and all public package/layout validation have passed.
            self.store.init_schema()
            assets = self._import_assets(package_path, package)
            revision_id = self.store.create_package_revision(
                package_id=package.package_id,
                project_id=package.project.project_id,
                project_title=package.project.title,
                locale=package.project.locale,
                revision=package.revision,
                content_hash=package_hash,
                raw_json=json.dumps(package.to_dict(), sort_keys=True, ensure_ascii=False),
            )
            snapshot = materialize(
                run_id=run_id,
                package=package,
                package_hash=package_hash,
                registry=self.registry,
                asset_resolutions=assets,
                artifact_layout=layout.to_dict(),
            )
            graph = build_dag(snapshot)
            layout.prepare()
            self.store.create_run(
                run_id=run_id,
                package_id=package.package_id,
                revision_id=revision_id,
                layout_json=json.dumps(layout.to_dict(), sort_keys=True, ensure_ascii=False),
                status="ACCEPTED",
            )
            run_created = True
            self.store.create_snapshot(
                snapshot_id=f"snapshot-{uuid.uuid4().hex}",
                run_id=run_id,
                snapshot_hash=snapshot.materialization_hash,
                snapshot_json=json.dumps(_snapshot_dict(snapshot), sort_keys=True, ensure_ascii=False),
            )
            runtime = PersistentRuntime(self.store, self.handlers, run_id)
            runtime.load_graph(graph)
            self.store.transition_run(run_id, "ACCEPTED", "RUNNING", "execution started")
            return self._drive_runtime(runtime, len(snapshot.clips), layout.to_dict())
        except MaterializationError as exc:
            return RunResult(run_id, "FAILED", error=str(exc))
        except Exception as exc:
            if run_created:
                run = self.store.get_run(run_id)
                if run is not None and str(run["status"]) in {"ACCEPTED", "RUNNING"}:
                    self.store.transition_run(run_id, str(run["status"]), "FAILED", str(exc))
            return RunResult(run_id, "FAILED", error=str(exc))

    def status(self, run_id: str) -> StatusResult:
        self.store.init_schema()
        run = self.store.get_run(run_id)
        if run is None:
            return StatusResult(run_id, "UNKNOWN", error="Run not found")
        tasks = {
            str(task["logical_key"]): str(task["status"])
            for task in self.store.list_tasks(run_id)
        }
        progress: dict[str, dict[str, Any]] = {}
        for task in self.store.list_tasks(run_id):
            metadata = json.loads(str(task.get("metadata") or "{}"))
            task_progress = metadata.get("progress")
            if isinstance(task_progress, dict):
                progress[str(task["logical_key"])] = task_progress
        layout = json.loads(str(run.get("layout_json") or "{}"))
        return StatusResult(run_id, str(run["status"]), tasks, layout, progress)

    def cancel(self, run_id: str) -> bool:
        self.store.init_schema()
        run = self.store.get_run(run_id)
        if run is None:
            return False
        current = str(run["status"])
        if current == RunState.CANCELLED.value:
            return True
        try:
            current_state = RunState(current)
        except ValueError:
            return False
        if not is_valid_run_transition(current_state, RunState.CANCELLED):
            return False
        for task in self.store.list_tasks(run_id):
            status = str(task["status"])
            if status not in {"SUCCEEDED", "FAILED_TERMINAL", "CANCELLED"}:
                self.store.transition_task(str(task["task_id"]), status, "CANCELLED", "run cancelled")
        return self.store.transition_run(
            run_id,
            current,
            RunState.CANCELLED.value,
            "user cancelled",
        )

    def export(self, run_id: str) -> ExportResult2:
        self.store.init_schema()
        run = self.store.get_run(run_id)
        if run is None:
            return ExportResult2("", "FAILED", error="Run not found")
        if str(run["status"]) != "COMPLETED":
            return ExportResult2("", "FAILED", error=f"Run is {run['status']}")
        final = None
        for artifact in reversed(self.store.list_artifacts(run_id)):
            if artifact["artifact_type"] == "final_video":
                final = artifact
                break
        if final is None or not isinstance(final.get("file_path"), str):
            return ExportResult2("", "FAILED", error="Completed run has no durable final artifact")
        file_path = pathlib.Path(str(final["file_path"]))
        if not file_path.is_file():
            return ExportResult2("", "FAILED", error=f"Final artifact is missing: {file_path}")
        existing = self.store.latest_export(run_id)
        if existing is not None:
            return ExportResult2(str(existing["export_id"]), str(existing["status"]), str(existing["file_path"]))
        metadata = json.loads(str(final.get("metadata") or "{}"))
        export_id = f"export-{uuid.uuid4().hex}"
        self.store.create_export(
            export_id=export_id,
            run_id=run_id,
            status="READY",
            file_path=str(file_path),
            file_hash=str(final.get("file_hash") or ""),
            manifest_path=metadata.get("manifest_path"),
            subtitles_path=metadata.get("subtitles_path"),
        )
        return ExportResult2(export_id, "READY", str(file_path))

    def _drive_runtime(
        self,
        runtime: PersistentRuntime,
        clip_count: int,
        output_layout: dict[str, Any] | None = None,
    ) -> RunResult:
        for _ in range(max(50, len(runtime.tasks) * 5)):
            persisted_run = self.store.get_run(runtime.run_id)
            if (
                persisted_run is not None
                and str(persisted_run["status"]) == RunState.CANCELLED.value
            ):
                break
            if runtime.is_complete() or runtime.is_stalled():
                break
            tick = runtime.tick()
            if tick.tasks_failed or runtime.has_failures():
                break
        if runtime.has_failures():
            status = "FAILED"
        elif runtime.is_complete():
            status = "COMPLETED"
        else:
            # A production run has no retry/review/prompt-wait state.  Any
            # scheduler stall is terminal and must be re-submitted as a new
            # package with a new exact approval hash.
            status = "FAILED"
        run = self.store.get_run(runtime.run_id)
        if run is not None and str(run["status"]) == RunState.CANCELLED.value:
            # Cancellation may race a handler that was already in flight.  A
            # late handler result must never turn the public result into
            # COMPLETED or overwrite the durable CANCELLED state.
            status = RunState.CANCELLED.value
        elif run is not None and str(run["status"]) != status:
            self.store.transition_run(runtime.run_id, str(run["status"]), status, "scheduler stopped")
            latest = self.store.get_run(runtime.run_id)
            if latest is not None and str(latest["status"]) == RunState.CANCELLED.value:
                status = RunState.CANCELLED.value
        failed = [task.error for task in runtime.tasks.values() if task.error]
        file_path = _current_video_path(runtime) if status == "COMPLETED" else None
        return RunResult(
            runtime.run_id,
            status,
            clip_count,
            dict(output_layout or {}),
            "; ".join(failed) or None,
            file_path,
        )

    def _validated_package(
        self,
        package_path: pathlib.Path,
        *,
        package_data: Any | None = None,
        expected_hash: str | None = None,
    ) -> tuple[VideoExecutionPackage, str]:
        if package_data is None:
            raw, package_hash = _read_package_bytes(package_path)
            data = _parse_package_bytes(raw)
        else:
            data = package_data
            package_hash = (
                expected_hash
                if expected_hash is not None
                else _sha256_file(package_path)
            )
        validation = self._validate_package_data(package_path, data)
        if not validation.valid:
            messages = "; ".join(str(item.get("message")) for item in validation.errors)
            raise ValueError(messages)
        package = VideoExecutionPackage.from_dict(data)
        return package, package_hash

    def _import_assets(
        self, package_path: pathlib.Path, package: VideoExecutionPackage
    ) -> dict[str, dict[str, str]]:
        importer = AssetImporter(self.cas)
        resolutions: dict[str, dict[str, str]] = {}
        for asset in package.assets:
            imported = importer.import_asset(
                asset.asset_key,
                asset.source.uri,
                package_path.parent,
                asset.media_type,
            )
            if asset.source.sha256 and imported.blob_ref.blob_hash.lower() != asset.source.sha256.lower():
                raise ValueError(f"Asset hash mismatch for {asset.asset_key!r}")
            asset_id = "asset-" + hashlib.sha256(
                f"{package.package_id}\0{asset.asset_key}".encode()
            ).hexdigest()[:24]
            revision_id = self.store.record_asset_revision(
                asset_id=asset_id,
                asset_key=asset.asset_key,
                media_type=asset.media_type,
                blob_hash=imported.blob_ref.blob_hash,
                blob_size=imported.blob_ref.size,
                blob_path=str(imported.blob_ref.path),
                file_hash=imported.blob_ref.blob_hash,
                probe_result=imported.probe.to_dict(),
                source_uri=asset.source.uri,
                original_filename=imported.original_filename,
                provenance=asset.provenance.to_dict(),
                review_required=asset.review.required,
                metadata=asset.metadata,
            )
            resolutions[asset.asset_key] = {
                "asset_revision_id": revision_id,
                "blob_path": str(imported.blob_ref.path.resolve()),
                "file_path": str(imported.blob_ref.path.resolve()),
                "file_hash": imported.blob_ref.blob_hash,
            }
        return resolutions

    def _plan_asset_resolutions(
        self, package_path: pathlib.Path, package: VideoExecutionPackage
    ) -> dict[str, dict[str, str]]:
        """Resolve package assets for planning without importing or recording them.

        Materialization needs a revision-like identifier and a usable file
        path, even though no durable asset revision exists during planning.
        The identifier is intentionally temporary and deterministic; the path
        remains the original package-relative source resolved inside the
        package directory.  Hashing the source here also makes a declared
        ``source.sha256`` meaningful for a plan without writing to CAS.
        """
        from lfo.assets.paths import resolve_package_uri, validate_readable_file

        resolutions: dict[str, dict[str, str]] = {}
        for asset in package.assets:
            source = resolve_package_uri(asset.source.uri, package_path.parent)
            validate_readable_file(source)
            file_hash = _sha256_file(source)
            if asset.source.sha256 and file_hash.lower() != asset.source.sha256.lower():
                raise ValueError(f"Asset hash mismatch for {asset.asset_key!r}")
            temporary_revision = "plan-asset-" + hashlib.sha256(
                f"{package.package_id}\0{asset.asset_key}".encode()
            ).hexdigest()[:24]
            source_path = str(source.resolve())
            resolutions[asset.asset_key] = {
                "asset_revision_id": temporary_revision,
                "blob_path": source_path,
                "file_path": source_path,
                "file_hash": file_hash,
            }
        return resolutions

    def _validate_asset_sources(
        self, package_path: pathlib.Path, package: VideoExecutionPackage
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        from lfo.assets.paths import resolve_package_uri

        for index, asset in enumerate(package.assets):
            try:
                source = resolve_package_uri(asset.source.uri, package_path.parent)
                if not source.is_file():
                    raise FileNotFoundError(f"Asset source does not exist: {source}")
            except Exception as exc:
                errors.append(_error(f"$.assets[{index}].source.uri", str(exc), "asset_path"))
        return errors

    @staticmethod
    def _plan_result(plan_id: str, snapshot: MaterializedRun) -> PlanResult:
        clips = [
            {
                "clip_id": clip.clip_id,
                "operation": clip.operation,
                "backend_id": clip.backend_id,
                "backend_revision": clip.backend_revision,
                "workflow_hash": clip.workflow_hash,
                "duration_ms": clip.duration_ms,
                "reference_count": len(clip.resolved_references),
                "megapixels": clip.megapixels,
                "width": clip.width,
                "height": clip.height,
                "dropped_references": clip.dropped_references,
            }
            for clip in snapshot.clips
        ]
        backends = sorted(
            {
                (clip.backend_id, clip.backend_revision)
                for clip in snapshot.clips
            }
        )
        return PlanResult(
            plan_id=plan_id,
            clip_plans=clips,
            warnings=snapshot.warnings,
            backend_summary=[
                {"backend_id": backend_id, "revision": revision}
                for backend_id, revision in backends
            ],
            output_layout=dict(snapshot.artifact_layout),
        )


def _snapshot_dict(snapshot: MaterializedRun) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(snapshot)


def _error(path: str, message: str, code: str) -> dict[str, Any]:
    return {"path": path, "message": message, "code": code}


def _current_video_path(runtime: PersistentRuntime) -> str | None:
    """Return the latest successful video artifact for the run."""

    preferred_types = (
        "export.finalize",
        "timeline.assemble",
        "media.qc",
        "video.upscale",
        "video.generate",
    )
    for task_type in preferred_types:
        for task in reversed(list(runtime.tasks.values())):
            if task.task_type != task_type:
                continue
            artifact = runtime.artifacts_by_task.get(task.task_id, {})
            path = artifact.get("file_path")
            if isinstance(path, str) and path:
                return path
    return None


def _sha256_file(path: pathlib.Path) -> str:
    """Return the SHA-256 digest of the exact package bytes on disk."""

    if not path.is_file():
        raise FileNotFoundError(f"Package file not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_package_bytes(path: pathlib.Path) -> tuple[bytes, str]:
    """Read and hash one immutable package byte sequence."""

    if not path.is_file():
        raise FileNotFoundError(f"Package file not found: {path}")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, digest


def _parse_package_bytes(raw: bytes) -> Any:
    """Decode package JSON only after any required approval check."""

    return json.loads(raw.decode("utf-8"))


def _matches_sha256(approved: str | None, actual: str) -> bool:
    """Require an explicit, well-formed digest with no implicit approval."""

    return (
        isinstance(approved, str)
        and len(approved) == 64
        and all(character in string.hexdigits for character in approved)
        and approved.lower() == actual
    )


def _comfy_h3_config(config: ResolvedConfig) -> ComfyH3Config:
    """Map the resolved machine/global configuration to the H3 executor."""

    output_value = config.get("storage.comfy_output")
    if not isinstance(output_value, str) or not output_value.strip():
        output_value = os.environ.get("LFO_COMFY_OUTPUT_ROOT")
    output_root = (
        pathlib.Path(output_value)
        if isinstance(output_value, str) and output_value.strip()
        else None
    )
    timeout_value = config.get("timeout_sec", 7_200)
    if isinstance(timeout_value, bool) or not isinstance(timeout_value, (int, float)):
        raise ValueError("timeout_sec must be numeric")
    cli_value = config.get("comfyui.cli", "comfy")
    if not isinstance(cli_value, str) or not cli_value.strip():
        raise ValueError("comfyui.cli must be a non-empty string")
    base_url = config.get("comfyui.base_url", "http://127.0.0.1:8188")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("comfyui.base_url must be a non-empty string")
    return ComfyH3Config(
        base_url=base_url,
        output_root=output_root,
        timeout_seconds=float(timeout_value),
        cli_binary=cli_value,
    )
