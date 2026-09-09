"""Tests for VideoRuntime facade."""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time

import pytest

import lfo.application.video_runtime as video_runtime_module
from lfo.application.video_runtime import VideoRuntime, _comfy_h3_config
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.comfy_h3 import build_h3_backend_registry
from lfo.backends.passthrough import PASSTHROUGH_BACKEND_ID, PASSTHROUGH_BACKEND_REVISION
from lfo.backends.registry import BackendRegistry
from lfo.backends.video_router import VideoTaskRouter
from lfo.config.config_resolver import ResolvedConfig
from lfo.execution.handlers import HandlerResult, TaskHandler, default_fake_registry


def _runtime(tmp_path: pathlib.Path, registry: BackendRegistry | None = None) -> VideoRuntime:
    return VideoRuntime(
        registry or _registry(),
        workspace_root=tmp_path / "workspace",
        handler_registry=default_fake_registry(),
    )


def _registry() -> BackendRegistry:
    reg = BackendRegistry()
    reg.register(CapabilityManifest(
        backend_id="comfyui.h3",
        revision="1.0.0",
        workflow_hash="wf1",
        operations=["video.text_to_video", "video.reference_to_video"],
        accepted_media_types=["image", "video"],
        max_references=9,
        duration_constraints={"min_ms": 500, "max_ms": 60000},
        resolution_constraints={"min_width": 256, "max_width": 1920},
        fps_constraints=[24.0],
        native_audio_capability="optional",
    ))
    return reg


def _package_json(
    tmp_path: pathlib.Path,
    clips: list[dict] | None = None,
    extensions: dict | None = None,
) -> pathlib.Path:
    """Write a minimal package JSON to a temp file."""
    data = {
        "schema": "lfo.video-execution.v1",
        "package_id": "test-pkg",
        "revision": 1,
        "project": {"title": "Test", "project_id": "test-project"},
        "assets": [],
        "clips": clips or [
            {
                "clip_id": "clip-001",
                "sequence": 1,
                "duration_ms": 5000,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "A beautiful sunset",
                    "requirements": {},
                },
            }
        ],
        "output": {},
        "extensions": extensions or {},
    }
    p = tmp_path / "package.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _approved(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_with_asset(
    tmp_path: pathlib.Path,
    *,
    declared_sha256: str | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    package_path = _package_json(tmp_path)
    source_path = tmp_path / "assets" / "reference.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"plan-only asset")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    source = {"uri": "assets/reference.png"}
    if declared_sha256 is not None:
        source["sha256"] = declared_sha256
    data["assets"] = [{
        "asset_key": "reference.image",
        "media_type": "image",
        "source": source,
        "provenance": {
            "source_type": "external_skill",
            "producer": "test",
            "operation": "image.generate",
        },
    }]
    data["clips"][0]["generation"]["operation"] = "video.reference_to_video"
    data["clips"][0]["generation"]["references"] = [{
        "reference_id": "reference-001",
        "asset_key": "reference.image",
        "semantic_usage": "subject.identity",
        "binding": {"required": True, "priority": 100, "placement": "fixed", "slot": "ref_image_0"},
    }]
    package_path.write_text(json.dumps(data), encoding="utf-8")
    return package_path, source_path


class TestVideoRuntime:
    @pytest.mark.parametrize(
        ("profile", "steps", "valid"),
        [("native", 16, True), ("native", 37, True), ("vdn_turbo", 8, True),
         ("vdn_turbo", 16, False), ("unknown", 8, False), ("native", None, False)],
    )
    def test_sampling_is_validated_before_generation(
        self, tmp_path: pathlib.Path, profile: str, steps: int | None, valid: bool,
    ) -> None:
        runtime = _runtime(tmp_path, build_h3_backend_registry())
        path = _package_json(tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["clips"][0]["generation"]["requirements"] = {
            "sampler_profile": profile, "steps": steps,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        assert runtime.validate(path).valid is valid
        plan = runtime.plan(path)
        assert (plan.error is None) is valid
        if valid:
            assert plan.clip_plans[0]["sampler_profile"] == profile
            assert plan.clip_plans[0]["steps"] == steps
        assert not (tmp_path / "workspace").exists()

    def test_default_production_video_registry_and_router(self, tmp_path: pathlib.Path) -> None:
        runtime = VideoRuntime(workspace_root=tmp_path / "workspace")
        assert isinstance(runtime.handlers.get("video.generate"), VideoTaskRouter)
        assert runtime.registry.get(
            PASSTHROUGH_BACKEND_ID,
            PASSTHROUGH_BACKEND_REVISION,
        ) is not None

    def test_injected_registry_keeps_builtin_passthrough_capability(
        self, tmp_path: pathlib.Path
    ) -> None:
        runtime = VideoRuntime(
            _registry(),
            workspace_root=tmp_path / "workspace",
            handler_registry=default_fake_registry(),
        )
        assert runtime.registry.get(
            PASSTHROUGH_BACKEND_ID,
            PASSTHROUGH_BACKEND_REVISION,
        ) is not None

    def test_production_handlers_include_video_upscale(self, tmp_path: pathlib.Path) -> None:
        runtime = VideoRuntime(workspace_root=tmp_path / "workspace")
        assert runtime.handlers.has_handler("video.upscale")

    def test_machine_cli_is_shared_with_upscale_handler(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            video_runtime_module,
            "resolve_config",
            lambda *, machine_id="": ResolvedConfig(
                raw={
                    "comfyui": {
                        "base_url": "http://127.0.0.1:9292",
                        "cli": "custom-comfy",
                    }
                },
                machine_id=machine_id,
                machine_profile=object(),
            ),
        )

        runtime = VideoRuntime(
            _registry(),
            workspace_root=tmp_path / "workspace",
            machine_id="custom-machine",
        )

        upscale = runtime.handlers.get("video.upscale")
        assert upscale is not None
        assert upscale.config.cli_binary == "custom-comfy"

    def test_resolved_machine_settings_map_to_comfy_cli_executor(self) -> None:
        config = _comfy_h3_config(ResolvedConfig(raw={
            "timeout_sec": 321,
            "comfyui": {
                "base_url": "http://127.0.0.1:9292",
                "cli": "custom-comfy",
            },
            "storage": {"comfy_output": "X:/Comfy/output"},
        }))

        assert config.base_url == "http://127.0.0.1:9292"
        assert config.cli_binary == "custom-comfy"
        assert config.output_root == pathlib.Path("X:/Comfy/output")
        assert config.timeout_seconds == 321

    def test_comfy_output_root_falls_back_to_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("LFO_COMFY_OUTPUT_ROOT", "Y:/Comfy/output")

        config = _comfy_h3_config(ResolvedConfig(raw={}))

        assert config.output_root == pathlib.Path("Y:/Comfy/output")

    def test_unknown_machine_profile_is_rejected(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

        with pytest.raises(ValueError, match="Machine profile not found"):
            VideoRuntime(
                workspace_root=tmp_path / "workspace",
                machine_id="missing-machine",
            )

    def test_validate_valid_package(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        result = rt.validate(p)
        assert result.valid
        assert result.package_sha256 == _approved(p)

    def test_validate_invalid_schema(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"schema": "wrong", "package_id": "x", "revision": 1}))
        rt = _runtime(tmp_path)
        result = rt.validate(p)
        assert not result.valid
        assert len(result.errors) > 0

    def test_execute_requires_exact_package_hash(self, tmp_path: pathlib.Path) -> None:
        package_path = _package_json(tmp_path)
        runtime = _runtime(tmp_path)
        rejected = runtime.execute(package_path, approved_sha256="0" * 64)
        assert rejected.status == "REJECTED"
        assert not runtime.db_path.exists()
        assert not (tmp_path / "workspace" / "assets").exists()
        accepted = runtime.execute(package_path, approved_sha256=_approved(package_path))
        assert accepted.status == "COMPLETED", accepted.error

    def test_execute_rejects_changed_bytes_before_json_parse(
        self, tmp_path: pathlib.Path
    ) -> None:
        package_path = tmp_path / "changed.json"
        package_path.write_bytes(b"not-json")
        runtime = _runtime(tmp_path)

        rejected = runtime.execute(package_path, approved_sha256="0" * 64)

        assert rejected.status == "REJECTED"
        assert rejected.error == (
            "approved_sha256 must exactly match the package file SHA-256"
        )
        assert not runtime.db_path.exists()
        assert not (tmp_path / "workspace" / "assets").exists()

    def test_constructor_validate_and_plan_do_not_initialize_persistent_services(
        self, tmp_path: pathlib.Path
    ) -> None:
        package_path = _package_json(tmp_path)
        runtime = _runtime(tmp_path)

        assert not runtime.workspace_root.exists()
        assert not runtime.db_path.exists()
        assert not (runtime.workspace_root / "assets").exists()

        validation = runtime.validate(package_path)
        assert validation.valid
        plan = runtime.plan(package_path)
        assert plan.error is None

        assert not runtime.workspace_root.exists()
        assert not runtime.db_path.exists()
        assert not (runtime.workspace_root / "assets").exists()

    def test_validate_missing_file(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        result = rt.validate("/nonexistent/path.json")
        assert not result.valid

    def test_plan_success(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        result = rt.plan(p)
        assert result.error is None
        assert len(result.clip_plans) == 1
        assert result.clip_plans[0]["backend_id"] == "comfyui.h3"

    def test_plan_resolves_assets_without_persisting_them(self, tmp_path: pathlib.Path) -> None:
        source_hash = hashlib.sha256(b"plan-only asset").hexdigest()
        package_path, _ = _package_with_asset(tmp_path, declared_sha256=source_hash)
        rt = _runtime(tmp_path)

        result = rt.plan(package_path)

        assert result.error is None, result.error
        assert not rt.db_path.exists()
        assert not (tmp_path / "workspace" / "assets").exists()

    def test_plan_rejects_declared_asset_hash_mismatch(self, tmp_path: pathlib.Path) -> None:
        package_path, _ = _package_with_asset(tmp_path, declared_sha256="0" * 64)
        rt = _runtime(tmp_path)

        result = rt.plan(package_path)

        assert result.error == "Asset hash mismatch for 'reference.image'"
        assert not rt.db_path.exists()
        assert not (tmp_path / "workspace" / "assets").exists()

    def test_plan_unsupported_operation(self, tmp_path: pathlib.Path) -> None:
        clips = [{
            "clip_id": "c1",
            "sequence": 1,
            "duration_ms": 5000,
            "generation": {
                "operation": "video.nonexistent_op",
                "prompt": "test",
                "requirements": {},
            },
        }]
        p = _package_json(tmp_path, clips=clips)
        rt = _runtime(tmp_path)
        result = rt.plan(p)
        assert result.error is not None

    def test_execute_success(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        result = rt.execute(p, approved_sha256=_approved(p))
        assert result.status == "COMPLETED"
        assert result.run_id
        assert result.clip_count == 1
        task_types = {task["task_type"] for task in rt.store.list_tasks(result.run_id)}
        assert "timeline.assemble" not in task_types
        assert "export.finalize" not in task_types

    def test_execute_with_optional_upscale_uses_fake_task_handler(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path, extensions={"upscale": {"enabled": True}})
        runtime = _runtime(tmp_path)
        result = runtime.execute(package, approved_sha256=_approved(package))
        assert result.status == "COMPLETED"
        assert any(
            task["task_type"] == "video.upscale"
            for task in runtime.store.list_tasks(result.run_id)
        )

    def test_execute_uses_project_scoped_artifact_layout(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path)
        runtime = _runtime(tmp_path)
        result = runtime.execute(package, approved_sha256=_approved(package))

        layout = result.output_layout
        assert layout["project_id"] == "test-project"
        assert pathlib.Path(layout["run_root"]).is_relative_to(
            (tmp_path / "workspace" / "projects" / "test-project").resolve()
        )
        assert pathlib.Path(layout["final_path"]).parent == (
            tmp_path / "workspace" / "projects" / "test-project" / "final" / "test-pkg"
        ).resolve()
        assert not (tmp_path / "workspace" / "runs").exists()
        assert not (tmp_path / "workspace" / "exports").exists()
        generate = next(
            task for task in runtime.store.list_tasks(result.run_id)
            if task["task_type"] == "video.generate"
        )
        assert pathlib.Path(json.loads(generate["metadata"])["output_path"]).is_relative_to(
            (tmp_path / "workspace" / "projects" / "test-project").resolve()
        )

    def test_execute_requires_approved_hash(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        result = _runtime(tmp_path).execute(p)
        assert result.status == "REJECTED"
        assert result.run_id == ""

    def test_repeated_runs_are_independent_and_durable(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        first = rt.execute(p, approved_sha256=_approved(p))
        second = rt.execute(p, approved_sha256=_approved(p))

        assert first.status == "COMPLETED", first.error
        assert second.status == "COMPLETED", second.error
        assert first.run_id != second.run_id
        first_task_ids = {str(task["task_id"]) for task in rt.store.list_tasks(first.run_id)}
        second_task_ids = {str(task["task_id"]) for task in rt.store.list_tasks(second.run_id)}
        assert first_task_ids.isdisjoint(second_task_ids)

        reopened = _runtime(tmp_path)
        assert reopened.status(first.run_id).status == "COMPLETED"
        assert reopened.status(second.run_id).status == "COMPLETED"

    def test_execute_missing_file(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        result = rt.execute("/nonexistent.json", approved_sha256="0" * 64)
        assert result.status == "FAILED"

    def test_status(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approved_sha256=_approved(p))
        status = rt.status(run_result.run_id)
        assert status.run_id == run_result.run_id
        assert status.status == "COMPLETED"
        assert len(status.tasks) > 0

    def test_status_unknown_run(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        status = rt.status("nonexistent-run")
        assert status.error is not None

    def test_cancel(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        assert rt.cancel("any-run") is False

    def test_cancel_completed_run_is_rejected_without_changing_result(
        self, tmp_path: pathlib.Path
    ) -> None:
        package_path = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run = rt.execute(package_path, approved_sha256=_approved(package_path))

        assert run.status == "COMPLETED"
        assert rt.cancel(run.run_id) is False
        assert rt.status(run.run_id).status == "COMPLETED"

    def test_cancel_active_run(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        revision_id = rt.store.create_package_revision(
            package_id="active-pkg",
            project_id="active-project",
            project_title="Active",
            revision=1,
            content_hash="active-content",
            raw_json="{}",
        )
        rt.store.create_run(
            run_id="run-active",
            package_id="active-pkg",
            revision_id=revision_id,
            status="RUNNING",
        )

        assert rt.cancel("run-active") is True
        assert rt.status("run-active").status == "CANCELLED"

    def test_cancel_during_handler_does_not_complete_run(self, tmp_path: pathlib.Path) -> None:
        started = threading.Event()
        release = threading.Event()

        class BlockingVideoHandler(TaskHandler):
            def execute(self, task_id, task_type, logical_key, metadata, attempt_id):
                started.set()
                assert release.wait(timeout=5)
                return HandlerResult(
                    success=True,
                    artifact_type="video",
                    artifact_metadata={"generation_output": True},
                    qc_passed=True,
                )

        handlers = default_fake_registry()
        handlers.register("video.generate", BlockingVideoHandler())
        execute_runtime = _runtime(tmp_path, registry=_registry())
        execute_runtime.handlers = handlers
        package_path = _package_json(tmp_path)
        result_holder: dict[str, object] = {}

        def execute() -> None:
            result_holder["result"] = execute_runtime.execute(
                package_path, approved_sha256=_approved(package_path)
            )

        worker = threading.Thread(target=execute)
        worker.start()
        assert started.wait(timeout=5)

        cancel_runtime = VideoRuntime(
            _registry(),
            workspace_root=tmp_path / "workspace",
            db_path=execute_runtime.db_path,
            handler_registry=default_fake_registry(),
        )
        run_id = ""
        for _ in range(100):
            row = cancel_runtime.store.connect().execute(
                "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row is not None:
                run_id = str(row["run_id"])
                break
            time.sleep(0.01)
        assert run_id
        assert cancel_runtime.cancel(run_id)
        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive()

        result = result_holder["result"]
        assert result.status == "CANCELLED"
        assert cancel_runtime.status(run_id).status == "CANCELLED"
        tasks = cancel_runtime.store.list_tasks(run_id)
        generation = next(task for task in tasks if task["task_type"] == "video.generate")
        assert generation["status"] == "CANCELLED"
        assert not [
            artifact for artifact in cancel_runtime.store.list_artifacts(run_id)
            if artifact["task_id"] == generation["task_id"]
        ]

    def test_export_completed_run(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approved_sha256=_approved(p))
        export = rt.export(run_result.run_id)
        assert export.status == "FAILED"
        assert "durable final artifact" in (export.error or "")

    def test_export_nonexistent_run(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        export = rt.export("nonexistent")
        assert export.error is not None

    def test_export_incomplete_run(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approved_sha256=_approved(p))
        rt.store.transition_run(run_result.run_id, "COMPLETED", "FAILED", "test")
        export = rt.export(run_result.run_id)
        assert export.error is not None
