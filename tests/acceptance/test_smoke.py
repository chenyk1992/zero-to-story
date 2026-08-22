"""Smoke test — full v1 end-to-end flow.

Covers: validate → plan → execute → status → export
using the VideoRuntime facade with fake backends.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from lfo.application.video_runtime import VideoRuntime
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.execution.handlers import default_fake_registry


@pytest.fixture
def h3_registry() -> BackendRegistry:
    """Registry with H3-like fake backend."""
    reg = BackendRegistry()
    reg.register(CapabilityManifest(
        backend_id="comfyui.h3",
        revision="1.0.0",
        workflow_hash="wf-h3-r2v-1",
        operations=[
            "video.text_to_video",
            "video.reference_to_video",
            "video.image_to_video",
        ],
        accepted_media_types=["image", "video"],
        max_references=9,
        duration_constraints={"min_ms": 500, "max_ms": 60000},
        frame_constraints={"formula": "17k+5"},
        resolution_constraints={
            "min_width": 256, "max_width": 1920,
            "min_height": 256, "max_height": 1920,
        },
        fps_constraints=[24.0],
        native_audio_capability="optional",
        seed_capability=True,
        reproducibility_claim="best_effort",
    ))
    return reg


def _make_package(tmp_dir: pathlib.Path) -> pathlib.Path:
    """Create a minimal 2-clip package file."""
    pkg = {
        "schema": "lfo.video-execution.v1",
        "package_id": "smoke-test-001",
        "revision": 1,
        "project": {"title": "Smoke Test", "project_id": "smoke-project", "locale": "zh-CN"},
        "assets": [
            {
                "asset_key": "hero.identity.front",
                "media_type": "image",
                "source": {"uri": "assets/hero.png"},
                "provenance": {
                    "source_type": "external_skill",
                    "producer": "imagegen",
                    "operation": "image.generate",
                },
                "review": {"required": True},
            },
        ],
        "clips": [
            {
                "clip_id": "clip-001",
                "sequence": 1,
                "duration_ms": 5000,
                "generation": {
                    "operation": "video.reference_to_video",
                    "prompt": "Hero standing in the rain",
                    "requirements": {
                        "aspect_ratio": "9:16",
                        "megapixels": 0.4,
                        "fps": 24,
                        "native_audio": "allowed",
                    },
                    "references": [
                        {
                            "reference_id": "ref-001",
                            "asset_key": "hero.identity.front",
                            "semantic_usage": "subject.identity",
                            "instruction": "Keep consistent",
                            "binding": {
                                "required": True,
                                "priority": 100,
                            },
                        },
                    ],
                },
                "audio": {"native_audio": "preserve"},
            },
            {
                "clip_id": "clip-002",
                "sequence": 2,
                "duration_ms": 4000,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "Close-up of a letter",
                    "requirements": {
                        "aspect_ratio": "9:16",
                        "megapixels": 0.4,
                        "fps": 24,
                    },
                },
                "audio": {"native_audio": "mute"},
            },
        ],
        "output": {
            "width": 1080,
            "height": 1920,
            "fps": 24,
            "sample_rate": 44100,
            "subtitles_mode": "sidecar",
            "directory": "smoke-test-001",
        },
        "approval": {
            "approved_by": "test",
            "approved_at": "2026-08-09T12:00:00Z",
        },
    }
    asset_dir = tmp_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"test-image")
    pkg_path = tmp_dir / "package.json"
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
    return pkg_path


class TestSmokeFlow:
    def test_validate(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        pkg_path = _make_package(tmp_path)
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())
        result = runtime.validate(pkg_path)
        assert result.valid, f"Validation failed: {result.errors}"

    def test_plan(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        pkg_path = _make_package(tmp_path)
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())
        result = runtime.plan(pkg_path)
        assert result.error is None, f"Plan failed: {result.error}"
        assert len(result.clip_plans) == 2

    def test_execute_completes(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        pkg_path = _make_package(tmp_path)
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())
        result = runtime.execute(pkg_path, approval=True)
        assert result.status == "COMPLETED", f"Execute failed: {result.error}"
        assert result.clip_count == 2
        assert result.run_id

    def test_full_flow(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        """Validate → plan → execute → status → export."""
        pkg_path = _make_package(tmp_path)
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())

        # Validate
        val_result = runtime.validate(pkg_path)
        assert val_result.valid

        # Plan
        plan_result = runtime.plan(pkg_path)
        assert plan_result.error is None
        assert len(plan_result.clip_plans) == 2

        # Execute
        exec_result = runtime.execute(pkg_path, approval=True)
        assert exec_result.status == "COMPLETED"
        run_id = exec_result.run_id

        # Status
        status_result = runtime.status(run_id)
        assert status_result.error is None
        assert status_result.status == "COMPLETED"
        assert len(status_result.tasks) > 0

        # Fake handlers deliberately do not claim a durable final media file.
        export_result = runtime.export(run_id)
        assert export_result.status == "FAILED"
        assert "durable final artifact" in (export_result.error or "")

    def test_invalid_package_rejected(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        """An invalid package should fail validation."""
        pkg = {"schema": "wrong-schema"}
        pkg_path = tmp_path / "bad.json"
        pkg_path.write_text(json.dumps(pkg), encoding="utf-8")
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())
        result = runtime.validate(pkg_path)
        assert not result.valid

    def test_nonexistent_file(self, h3_registry: BackendRegistry, tmp_path: pathlib.Path) -> None:
        runtime = VideoRuntime(h3_registry, workspace_root=tmp_path / "workspace", handler_registry=default_fake_registry())
        result = runtime.validate("/nonexistent/path.json")
        assert not result.valid
