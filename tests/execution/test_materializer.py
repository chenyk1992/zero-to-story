"""Tests for Materializer."""
from __future__ import annotations

import pytest

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.contracts.assets import (
    AssetSource,
    AssetSpec,
    ProvenanceSpec,
)
from lfo.contracts.clips import BindingPolicy, ClipSpec, GenerationSpec, ReferenceSpec
from lfo.contracts.package import ProjectInfo, VideoExecutionPackage
from lfo.execution.materializer import MaterializationError, materialize


def _h3_registry() -> BackendRegistry:
    reg = BackendRegistry()
    reg.register(CapabilityManifest(
        backend_id="comfyui.h3",
        revision="1.0.0",
        workflow_hash="wf-r2v-1",
        operations=["video.text_to_video", "video.reference_to_video"],
        accepted_media_types=["image", "video"],
        max_references=9,
        duration_constraints={"min_ms": 500, "max_ms": 60000},
        resolution_constraints={"min_width": 256, "max_width": 1920},
        fps_constraints=[24.0],
        native_audio_capability="optional",
        seed_capability=True,
        reproducibility_claim="best_effort",
    ))
    return reg


def _make_clip(
    clip_id: str = "clip-001",
    operation: str = "video.text_to_video",
    references: list[ReferenceSpec] | None = None,
) -> ClipSpec:
    gen = GenerationSpec(
        operation=operation,
        prompt=f"Prompt for {clip_id}",
        references=references or [],
    )
    return ClipSpec(
        clip_id=clip_id,
        sequence=1,
        duration_ms=5000,
        generation=gen,
    )


def _make_package(clips: list[ClipSpec] | None = None) -> VideoExecutionPackage:
    return VideoExecutionPackage(
        package_id="pkg-test",
        revision=1,
        project=ProjectInfo(title="Test Project"),
        assets=[],
        clips=clips or [_make_clip()],
    )


class TestMaterialize:
    def test_basic_materialization(self) -> None:
        pkg = _make_package()
        result = materialize("run-1", pkg, "pkghash", _h3_registry())
        assert result.run_id == "run-1"
        assert result.package_id == "pkg-test"
        assert len(result.clips) == 1
        assert result.clips[0].backend_id == "comfyui.h3"

    def test_deterministic_hash(self) -> None:
        """Same inputs produce same materialization hash."""
        pkg = _make_package()
        r1 = materialize("run-1", pkg, "pkghash", _h3_registry())
        r2 = materialize("run-1", pkg, "pkghash", _h3_registry())
        assert r1.materialization_hash == r2.materialization_hash

    def test_different_prompt_changes_hash(self) -> None:
        """Changing the prompt changes the materialization hash."""
        clip_a = _make_clip("clip-001")
        clip_b = _make_clip("clip-001")
        clip_b.generation.prompt = "Different prompt"
        pkg_a = VideoExecutionPackage(
            package_id="pkg", revision=1,
            project=ProjectInfo(title="T"),
            clips=[clip_a],
        )
        pkg_b = VideoExecutionPackage(
            package_id="pkg", revision=1,
            project=ProjectInfo(title="T"),
            clips=[clip_b],
        )
        r_a = materialize("r", pkg_a, "h", _h3_registry())
        r_b = materialize("r", pkg_b, "h", _h3_registry())
        assert r_a.materialization_hash != r_b.materialization_hash

    def test_different_backend_changes_hash(self) -> None:
        """Different backend selection changes the hash."""
        pkg = _make_package()
        reg1 = _h3_registry()
        reg2 = BackendRegistry()
        reg2.register(CapabilityManifest(
            backend_id="other.backend",
            revision="1",
            workflow_hash="other-wf",
            operations=["video.text_to_video"],
            accepted_media_types=["image"],
            max_references=9,
            duration_constraints={"min_ms": 500, "max_ms": 60000},
            resolution_constraints={"min_width": 256, "max_width": 1920},
            fps_constraints=[24.0],
        ))
        r1 = materialize("r", pkg, "h", reg1)
        r2 = materialize("r", pkg, "h", reg2)
        assert r1.materialization_hash != r2.materialization_hash

    def test_unsupported_operation_raises(self) -> None:
        pkg = _make_package([_make_clip("c1", operation="video.nonexistent")])
        with pytest.raises(MaterializationError):
            materialize("r", pkg, "h", _h3_registry())

    def test_too_many_references_raises(self) -> None:
        refs = [
            ReferenceSpec(
                reference_id=f"ref-{i}",
                asset_key=f"asset-{i}",
                semantic_usage="subject.identity",
                binding=BindingPolicy(required=True, priority=i),
            )
            for i in range(15)
        ]
        pkg = _make_package([_make_clip("c1", references=refs)])
        with pytest.raises(MaterializationError):
            materialize("r", pkg, "h", _h3_registry())

    def test_asset_resolutions_passed_through(self) -> None:
        refs = [
            ReferenceSpec(
                reference_id="ref-1",
                asset_key="hero.png",
                semantic_usage="subject.identity",
                binding=BindingPolicy(required=True),
            )
        ]
        assets = [
            AssetSpec(
                asset_key="hero.png",
                media_type="image",
                source=AssetSource(uri="assets/hero.png"),
                provenance=ProvenanceSpec(
                    source_type="skill",
                    producer="codex",
                    operation="image.generate",
                ),
            )
        ]
        pkg = VideoExecutionPackage(
            package_id="pkg", revision=1,
            project=ProjectInfo(title="T"),
            assets=assets,
            clips=[_make_clip("c1", references=refs)],
        )
        resolutions = {"hero.png": "asset-rev-abc"}
        result = materialize("r", pkg, "h", _h3_registry(), asset_resolutions=resolutions)
        assert result.asset_resolutions == resolutions
        # Check the reference was resolved
        mat_clip = result.clips[0]
        assert mat_clip.resolved_references[0]["asset_revision_id"] == "asset-rev-abc"

    def test_required_reference_without_imported_revision_fails(self) -> None:
        ref = ReferenceSpec(
            reference_id="hero", asset_key="hero.png", semantic_usage="subject.identity",
            binding=BindingPolicy(required=True),
        )
        asset = AssetSpec(
            asset_key="hero.png", media_type="image", source=AssetSource(uri="hero.png"),
            provenance=ProvenanceSpec(source_type="skill", producer="test", operation="image.generate"),
        )
        package = _make_package([_make_clip("c1", references=[ref])])
        package.assets = [asset]
        with pytest.raises(MaterializationError) as error:
            materialize("run", package, "hash", _h3_registry())
        assert "no imported revision" in error.value.details[0]

    def test_optional_reference_is_dropped_by_priority_when_backend_is_full(self) -> None:
        registry = BackendRegistry()
        registry.register(CapabilityManifest(
            backend_id="small", revision="1", workflow_hash="small-wf",
            operations=["video.reference_to_video"], accepted_media_types=["image"], max_references=1,
        ))
        refs = [
            ReferenceSpec("required", "required.png", "subject.identity", BindingPolicy(required=True, priority=10)),
            ReferenceSpec("optional", "optional.png", "style", BindingPolicy(required=False, priority=0, on_unsupported="drop")),
        ]
        assets = [
            AssetSpec(asset_key=key, media_type="image", source=AssetSource(uri=key),
                      provenance=ProvenanceSpec(source_type="skill", producer="test", operation="image.generate"))
            for key in ("required.png", "optional.png")
        ]
        package = VideoExecutionPackage(package_id="pkg", revision=1, project=ProjectInfo(title="T"), assets=assets,
                                        clips=[_make_clip("c1", operation="video.reference_to_video", references=refs)])
        result = materialize("run", package, "hash", registry, {
            "required.png": {"asset_revision_id": "r1", "file_path": "C:/required.png"},
            "optional.png": {"asset_revision_id": "r2", "file_path": "C:/optional.png"},
        })
        assert [ref["reference_id"] for ref in result.clips[0].resolved_references] == ["required"]
        assert result.clips[0].dropped_references[0]["reference_id"] == "optional"

    def test_output_policy_captured(self) -> None:
        from lfo.contracts.timeline import OutputPolicy
        pkg = _make_package()
        pkg.output = OutputPolicy(container="mkv", video_encoder="h265")
        result = materialize("r", pkg, "hash", _h3_registry())
        assert result.output_policy["container"] == "mkv"
        assert result.output_policy["video_encoder"] == "h265"
