"""Persistent public facade for LFO Runtime v1."""
from __future__ import annotations

import hashlib
import json
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from lfo.assets.importer import AssetImporter
from lfo.assets.store import ContentAddressedStore
from lfo.backends.comfy_seedvr2 import ComfyUpscaleVideoHandler
from lfo.backends.registry import BackendRegistry
from lfo.backends.video_router import VideoTaskRouter, build_video_backend_registry
from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.core.canonical import hash_value
from lfo.execution import ExecutionStore
from lfo.execution.dag import build_dag
from lfo.execution.handlers import HandlerRegistry
from lfo.execution.materializer import MaterializationError, MaterializedRun, materialize
from lfo.execution.runtime import PersistentRuntime
from lfo.execution.states import TaskState
from lfo.media.handlers import build_media_handler_registry
from lfo.services.artifact_layout import ArtifactLayoutError, RunArtifactLayout
from lfo.services.workspace import resolve_workspace_root


@dataclass
class ValidationResult2:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


@dataclass
class StatusResult:
    run_id: str
    status: str
    tasks: dict[str, str] = field(default_factory=dict)
    output_layout: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ReviewResult:
    review_id: str
    decision: str
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
        require_production_lock: bool = False,
    ) -> None:
        self.workspace_root = (
            pathlib.Path(workspace_root).resolve()
            if workspace_root is not None
            else resolve_workspace_root()
        )
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.db_path = pathlib.Path(db_path or self.workspace_root / "db" / "runtime-v1.sqlite3")
        self.store = ExecutionStore(self.db_path)
        self.store.init_schema()
        self.registry = registry or build_video_backend_registry()
        self.handlers = handler_registry or self._production_handlers()
        self.cas = ContentAddressedStore(self.workspace_root / "assets")
        # Keep v1 package compatibility by default.  New production callers
        # should set this flag so an unlocked creative plan cannot consume
        # assets or generation quota.
        self.require_production_lock = require_production_lock

    def _production_handlers(self) -> HandlerRegistry:
        handlers = build_media_handler_registry(self.workspace_root)
        handlers.register("video.generate", VideoTaskRouter())
        handlers.register(
            "video.upscale",
            ComfyUpscaleVideoHandler(progress_callback=self._record_task_progress),
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
            data = self._read_json(package_path)
        except Exception as exc:
            return ValidationResult2(False, [_error(str(path), str(exc), "parse_error")])
        result = validate_package(
            data,
            require_production_lock=self.require_production_lock,
        )
        errors = [error.to_dict() for error in result.errors()]
        warnings: list[str] = []
        if result.ok:
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
        return ValidationResult2(not errors, errors, warnings)

    def plan(self, path: pathlib.Path | str) -> PlanResult:
        package_path = pathlib.Path(path).resolve()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        try:
            package, package_hash = self._validated_package(package_path)
            assets = self._import_assets(package_path, package)
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

    def execute(self, path: pathlib.Path | str, approval: bool = False) -> RunResult:
        package_path = pathlib.Path(path).resolve()
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        try:
            package, package_hash = self._validated_package(package_path)
            if not approval:
                return RunResult("", "REJECTED", error="Explicit execution approval is required")
            layout = RunArtifactLayout.from_package(
                workspace_root=self.workspace_root,
                run_id=run_id,
                package=package,
            )
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
            self.store.create_snapshot(
                snapshot_id=f"snapshot-{uuid.uuid4().hex}",
                run_id=run_id,
                snapshot_hash=snapshot.materialization_hash,
                snapshot_json=json.dumps(_snapshot_dict(snapshot), sort_keys=True, ensure_ascii=False),
            )
            review_id = f"review-{uuid.uuid4().hex}"
            self.store.create_review(
                review_id=review_id,
                target_type="package",
                target_id=run_id,
                content_hash=package_hash,
                bindings={"package_id": package.package_id, "revision": package.revision},
            )
            self.store.transition_review(
                review_id,
                "PENDING",
                "APPROVED",
                package.approval.notes or "explicit runtime approval",
                decided_by=package.approval.approved_by or "runtime-user",
            )
            runtime = PersistentRuntime(self.store, self.handlers, run_id)
            runtime.load_graph(graph)
            self.store.transition_run(run_id, "ACCEPTED", "RUNNING", "execution started")
            return self._drive_runtime(runtime, len(snapshot.clips), layout.to_dict())
        except MaterializationError as exc:
            return RunResult(run_id, "FAILED", error=str(exc))
        except Exception as exc:
            run = self.store.get_run(run_id)
            if run is not None and str(run["status"]) in {"ACCEPTED", "RUNNING"}:
                self.store.transition_run(run_id, str(run["status"]), "FAILED", str(exc))
            return RunResult(run_id, "FAILED", error=str(exc))

    def status(self, run_id: str) -> StatusResult:
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

    def retry(self, run_id: str, scope: str | None = None) -> RunResult:
        run = self.store.get_run(run_id)
        if run is None:
            return RunResult(run_id, "FAILED", error="Run not found")
        runtime = PersistentRuntime(self.store, self.handlers, run_id)
        runtime.restore()
        reset = 0
        for task in runtime.tasks.values():
            if task.status != TaskState.FAILED_RETRYABLE.value:
                continue
            if scope and not (task.logical_key.startswith(f"{scope}:") or task.task_id == scope):
                continue
            if runtime.retry(task.task_id):
                reset += 1
        if reset == 0:
            return RunResult(run_id, str(run["status"]), error="No retryable tasks in scope")
        current = str(run["status"])
        self.store.transition_run(run_id, current, "RUNNING", "manual retry")
        clip_count = len({str(task["logical_key"]).split(":", 1)[0] for task in self.store.list_tasks(run_id) if ":" in str(task["logical_key"])})
        layout = json.loads(str(run.get("layout_json") or "{}"))
        return self._drive_runtime(runtime, clip_count, layout)

    def submit_prompt_revision(
        self,
        run_id: str,
        prompt: str,
        *,
        scope: str | None = None,
        plan_hash: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> RunResult:
        """Resume a blocked Clip with one prompt-only H3 revision.

        The caller (normally ``h3-prompt-writing``) supplies the revised
        prompt.  Runtime checks the immutable production-plan hash and never
        edits storyboard, timing, operation or reference fields.
        """

        run = self.store.get_run(run_id)
        if run is None:
            return RunResult(run_id, "FAILED", error="Run not found")
        runtime = PersistentRuntime(self.store, self.handlers, run_id)
        runtime.restore()
        targets = [
            task
            for task in runtime.tasks.values()
            if task.status == TaskState.WAITING_PROMPT_REVISION.value
            and (
                scope is None
                or task.logical_key.startswith(f"{scope}:")
                or task.task_id == scope
            )
        ]
        if len(targets) != 1:
            return RunResult(
                run_id,
                str(run["status"]),
                error="Expected exactly one waiting Clip for prompt revision",
            )
        target = targets[0]
        if not runtime.provide_prompt_revision(
            target.task_id,
            prompt,
            plan_hash=plan_hash,
            negative_prompt=negative_prompt,
            seed=seed,
        ):
            # A rejected hash/state leaves the run untouched.  Exhausting the
            # locked revision budget, however, transitions the waiting task
            # to terminal ``block_for_user``; keep the durable Run state in
            # sync instead of leaving it indefinitely WAITING.
            if runtime.has_failures():
                current = str(run["status"])
                if current != "FAILED":
                    self.store.transition_run(
                        run_id,
                        current,
                        "FAILED",
                        "prompt revision budget exhausted",
                    )
                return RunResult(
                    run_id,
                    "FAILED",
                    error="Prompt revision budget exhausted",
                )
            return RunResult(
                run_id,
                str(run["status"]),
                error="Prompt revision rejected: plan hash, state or revision budget is invalid",
            )
        current = str(run["status"])
        if current != "RUNNING":
            self.store.transition_run(run_id, current, "RUNNING", "prompt-only revision accepted")
        layout = json.loads(str(run.get("layout_json") or "{}"))
        clip_count = len({
            str(task["logical_key"]).split(":", 1)[0]
            for task in self.store.list_tasks(run_id)
            if ":" in str(task["logical_key"])
        })
        return self._drive_runtime(runtime, clip_count, layout)

    def cancel(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if run is None:
            return
        for task in self.store.list_tasks(run_id):
            status = str(task["status"])
            if status not in {"SUCCEEDED", "FAILED_TERMINAL", "CANCELLED"}:
                self.store.transition_task(str(task["task_id"]), status, "CANCELLED", "run cancelled")
        current = str(run["status"])
        if current != "CANCELLED":
            self.store.transition_run(run_id, current, "CANCELLED", "user cancelled")

    def review(self, run_id: str, target: str, decision: str) -> ReviewResult:
        review_id = f"review-{uuid.uuid4().hex}"
        if self.store.get_run(run_id) is None:
            return ReviewResult(review_id, decision, "Run not found")
        if decision not in {"approved", "rejected"}:
            return ReviewResult(review_id, decision, "Invalid decision")
        self.store.create_review(
            review_id=review_id,
            target_type="runtime-target",
            target_id=target,
            bindings={"run_id": run_id},
        )
        self.store.transition_review(
            review_id,
            "PENDING",
            decision.upper(),
            f"runtime review: {decision}",
            decided_by="runtime-user",
        )
        return ReviewResult(review_id, decision)

    def export(self, run_id: str) -> ExportResult2:
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
            if runtime.is_complete() or runtime.is_stalled():
                break
            runtime.tick()
        if runtime.has_failures():
            status = "FAILED"
        elif any(
            task.status == TaskState.WAITING_PROMPT_REVISION.value
            for task in runtime.tasks.values()
        ):
            status = "WAITING_PROMPT_REVISION"
        elif runtime.is_complete():
            status = "COMPLETED"
        else:
            status = "WAITING_RETRY"
        run = self.store.get_run(runtime.run_id)
        if run is not None and str(run["status"]) != status:
            self.store.transition_run(runtime.run_id, str(run["status"]), status, "scheduler stopped")
        failed = [task.error for task in runtime.tasks.values() if task.error]
        return RunResult(
            runtime.run_id,
            status,
            clip_count,
            dict(output_layout or {}),
            "; ".join(failed) or None,
        )

    def _validated_package(self, package_path: pathlib.Path) -> tuple[VideoExecutionPackage, str]:
        validation = self.validate(package_path)
        if not validation.valid:
            messages = "; ".join(str(item.get("message")) for item in validation.errors)
            raise ValueError(messages)
        package = VideoExecutionPackage.from_dict(self._read_json(package_path))
        return package, hash_value(package.to_dict())

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
    def _read_json(path: pathlib.Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(f"Package file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Package JSON must be an object")
        return data

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
