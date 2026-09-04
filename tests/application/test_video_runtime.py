"""Tests for VideoRuntime facade."""
from __future__ import annotations

import json
import pathlib

from lfo.application.video_runtime import VideoRuntime
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.passthrough import PASSTHROUGH_BACKEND_ID, PASSTHROUGH_BACKEND_REVISION
from lfo.backends.registry import BackendRegistry
from lfo.backends.video_router import VideoTaskRouter
from lfo.contracts import with_production_lock
from lfo.execution.handlers import default_fake_registry


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


class TestVideoRuntime:
    def test_default_production_video_registry_and_router(self, tmp_path: pathlib.Path) -> None:
        runtime = VideoRuntime(workspace_root=tmp_path / "workspace")
        assert isinstance(runtime.handlers.get("video.generate"), VideoTaskRouter)
        assert runtime.registry.get(
            PASSTHROUGH_BACKEND_ID,
            PASSTHROUGH_BACKEND_REVISION,
        ) is not None

    def test_production_handlers_include_video_upscale(self, tmp_path: pathlib.Path) -> None:
        runtime = VideoRuntime(workspace_root=tmp_path / "workspace")
        assert runtime.handlers.has_handler("video.upscale")

    def test_validate_valid_package(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        result = rt.validate(p)
        assert result.valid

    def test_validate_invalid_schema(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"schema": "wrong", "package_id": "x", "revision": 1}))
        rt = _runtime(tmp_path)
        result = rt.validate(p)
        assert not result.valid
        assert len(result.errors) > 0

    def test_strict_runtime_requires_and_accepts_production_lock(self, tmp_path: pathlib.Path) -> None:
        package_path = _package_json(tmp_path)
        strict = VideoRuntime(
            _registry(),
            workspace_root=tmp_path / "strict-workspace",
            handler_registry=default_fake_registry(),
            require_production_lock=True,
        )
        rejected = strict.validate(package_path)
        assert not rejected.valid
        assert any(error["code"] == "production_lock_required" for error in rejected.errors)

        package = json.loads(package_path.read_text(encoding="utf-8"))
        package_path.write_text(json.dumps(with_production_lock(package)), encoding="utf-8")
        accepted = strict.validate(package_path)
        assert accepted.valid, accepted.errors

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
        result = rt.execute(p, approval=True)
        assert result.status == "COMPLETED"
        assert result.run_id
        assert result.clip_count == 1

    def test_execute_with_optional_upscale_uses_fake_task_handler(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path, extensions={"upscale": {"enabled": True}})
        runtime = _runtime(tmp_path)
        result = runtime.execute(package, approval=True)
        assert result.status == "COMPLETED"
        assert any(
            task["task_type"] == "video.upscale"
            for task in runtime.store.list_tasks(result.run_id)
        )

    def test_execute_uses_project_scoped_artifact_layout(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path)
        runtime = _runtime(tmp_path)
        result = runtime.execute(package, approval=True)

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

    def test_execute_requires_explicit_approval(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        result = _runtime(tmp_path).execute(p)
        assert result.status == "REJECTED"
        assert result.run_id == ""

    def test_repeated_runs_are_independent_and_durable(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        first = rt.execute(p, approval=True)
        second = rt.execute(p, approval=True)

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
        result = rt.execute("/nonexistent.json", approval=True)
        assert result.status == "FAILED"

    def test_status(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approval=True)
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
        rt.cancel("any-run")  # should not raise

    def test_review(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run = rt.execute(package, approval=True)
        result = rt.review(run.run_id, "clip-001", "approved")
        assert result.decision == "approved"

    def test_review_invalid_decision(self, tmp_path: pathlib.Path) -> None:
        package = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run = rt.execute(package, approval=True)
        result = rt.review(run.run_id, "c1", "maybe")
        assert result.error is not None

    def test_export_completed_run(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approval=True)
        final_path = tmp_path / "final.mp4"
        final_path.write_bytes(b"durable-test-artifact")
        final_task = next(
            task for task in rt.store.list_tasks(run_result.run_id)
            if task["task_type"] == "export.finalize"
        )
        rt.store.record_artifact(
            artifact_id="artifact-final-test",
            task_id=str(final_task["task_id"]),
            artifact_type="final_video",
            file_path=str(final_path),
            file_hash="test-hash",
            media_type="video",
        )
        export = rt.export(run_result.run_id)
        assert export.status == "READY"
        assert export.file_path is not None

    def test_export_nonexistent_run(self, tmp_path: pathlib.Path) -> None:
        rt = _runtime(tmp_path)
        export = rt.export("nonexistent")
        assert export.error is not None

    def test_export_incomplete_run(self, tmp_path: pathlib.Path) -> None:
        p = _package_json(tmp_path)
        rt = _runtime(tmp_path)
        run_result = rt.execute(p, approval=True)
        rt.store.transition_run(run_result.run_id, "COMPLETED", "FAILED", "test")
        export = rt.export(run_result.run_id)
        assert export.error is not None
