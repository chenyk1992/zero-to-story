"""Tests for backend selector."""
from __future__ import annotations

import pytest

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.backends.selector import select_backend, SelectionFailure


def _h3_manifest(
    revision: str = "1.0.0",
    operations: list[str] | None = None,
    max_refs: int = 9,
    native_audio: str = "optional",
) -> CapabilityManifest:
    return CapabilityManifest(
        backend_id="comfyui.h3",
        revision=revision,
        workflow_hash=f"wf-{revision}",
        operations=operations or ["video.text_to_video", "video.reference_to_video"],
        accepted_media_types=["image", "video"],
        max_references=max_refs,
        duration_constraints={"min_ms": 500, "max_ms": 60000},
        frame_constraints={"formula": "17k+5"},
        resolution_constraints={"min_width": 256, "max_width": 1920, "min_height": 256, "max_height": 1920},
        fps_constraints=[24.0],
        native_audio_capability=native_audio,
        seed_capability=True,
        reproducibility_claim="best_effort",
    )


class TestSelectBackend:
    def test_basic_selection(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        result = select_backend("video.text_to_video", {}, reg)
        assert result.backend_id == "comfyui.h3"
        assert result.workflow_hash == "wf-1.0.0"

    def test_rejects_too_many_references(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest(max_refs=3))
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {}, reg, reference_count=5)
        assert any(r.reason == "too_many_references" for r in exc_info.value.rejections)

    def test_rejects_unsupported_media_type(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {}, reg, media_types=["audio"])
        assert any(r.reason == "unsupported_media_type" for r in exc_info.value.rejections)

    def test_rejects_duration_too_short(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {"duration_ms": 100}, reg)
        assert any(r.reason == "duration_too_short" for r in exc_info.value.rejections)

    def test_rejects_duration_too_long(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {"duration_ms": 120000}, reg)
        assert any(r.reason == "duration_too_long" for r in exc_info.value.rejections)

    def test_rejects_unsupported_fps(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {"fps": 30}, reg)
        assert any(r.reason == "unsupported_fps" for r in exc_info.value.rejections)

    def test_rejects_native_audio_required_when_unsupported(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest(native_audio="none"))
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {"native_audio": "required"}, reg)
        assert any(r.reason == "native_audio_unsupported" for r in exc_info.value.rejections)

    def test_no_candidates_raises(self) -> None:
        reg = BackendRegistry()
        with pytest.raises(SelectionFailure):
            select_backend("video.text_to_video", {}, reg)

    def test_prefers_listed_backend(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest(revision="1.0.0"))
        reg.register(_h3_manifest(revision="2.0.0"))
        result = select_backend(
            "video.text_to_video", {}, reg,
            preferred_backends=[("comfyui.h3", "2.0.0")],
        )
        assert result.revision == "2.0.0"

    def test_rejection_reasons_collected(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest(max_refs=2))
        reg.register(_h3_manifest(revision="2.0.0", max_refs=1))
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {}, reg, reference_count=5)
        # Both candidates should be rejected
        assert len(exc_info.value.rejections) == 2

    def test_resolution_constraints(self) -> None:
        reg = BackendRegistry()
        reg.register(_h3_manifest())
        with pytest.raises(SelectionFailure) as exc_info:
            select_backend("video.text_to_video", {"width": 100}, reg)
        assert any(r.reason == "width_too_small" for r in exc_info.value.rejections)

    def test_selection_result_includes_rejections(self) -> None:
        """When one candidate passes, rejections from others are still reported."""
        reg = BackendRegistry()
        reg.register(_h3_manifest(revision="1.0.0", max_refs=9))
        reg.register(_h3_manifest(revision="2.0.0", max_refs=0))
        result = select_backend("video.text_to_video", {}, reg, reference_count=2)
        assert result.backend_id == "comfyui.h3"
        # rev 2.0.0 should be rejected for too_many_references
        assert any(r.backend_id == "comfyui.h3" and r.revision == "2.0.0" for r in result.rejections)
