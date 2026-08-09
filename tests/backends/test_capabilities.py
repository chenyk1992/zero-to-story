"""Tests for CapabilityManifest."""
from __future__ import annotations

import pytest

from lfo.backends.capabilities import CapabilityManifest


class TestCapabilityManifest:
    def test_minimal_manifest(self) -> None:
        m = CapabilityManifest(
            backend_id="comfyui.h3",
            revision="1.0.0",
            workflow_hash="abc123",
            operations=["video.text_to_video"],
        )
        assert m.backend_id == "comfyui.h3"
        assert m.supports_operation("video.text_to_video")
        assert not m.supports_operation("video.image_to_video")

    def test_accepts_media_type(self) -> None:
        m = CapabilityManifest(
            backend_id="test",
            revision="1",
            workflow_hash="h",
            accepted_media_types=["image", "video"],
        )
        assert m.accepts_media_type("image")
        assert not m.accepts_media_type("audio")

    def test_round_trip_dict(self) -> None:
        m = CapabilityManifest(
            backend_id="comfyui.h3",
            revision="1.0.0",
            workflow_hash="abc123",
            operations=["video.text_to_video", "video.image_to_video"],
            accepted_media_types=["image"],
            max_references=9,
            duration_constraints={"min_ms": 1000, "max_ms": 30000},
            frame_constraints={"formula": "17k+5", "min": 22, "max": 1000},
            resolution_constraints={"min_width": 256, "max_width": 1920},
            fps_constraints=[24.0, 30.0],
            native_audio_capability="optional",
            seed_capability=True,
            reproducibility_claim="best_effort",
            required_models=["minimax_h3_fl2va.safetensors"],
            output_signature={"container": "mp4", "has_audio": True},
        )
        d = m.to_dict()
        m2 = CapabilityManifest.from_dict(d)
        assert m2.backend_id == m.backend_id
        assert m2.operations == m.operations
        assert m2.max_references == 9
        assert m2.native_audio_capability == "optional"
        assert m2.fps_constraints == [24.0, 30.0]

    def test_from_dict_missing_backend_id(self) -> None:
        with pytest.raises(ValueError, match="backend_id"):
            CapabilityManifest.from_dict({"revision": "1", "workflow_hash": "h"})

    def test_from_dict_invalid_native_audio(self) -> None:
        with pytest.raises(ValueError, match="native_audio_capability"):
            CapabilityManifest.from_dict({
                "backend_id": "x",
                "revision": "1",
                "workflow_hash": "h",
                "native_audio_capability": "invalid",
            })

    def test_from_dict_invalid_reproducibility(self) -> None:
        with pytest.raises(ValueError, match="reproducibility_claim"):
            CapabilityManifest.from_dict({
                "backend_id": "x",
                "revision": "1",
                "workflow_hash": "h",
                "reproducibility_claim": "maybe",
            })

    def test_from_dict_negative_max_references(self) -> None:
        with pytest.raises(ValueError, match="max_references"):
            CapabilityManifest.from_dict({
                "backend_id": "x",
                "revision": "1",
                "workflow_hash": "h",
                "max_references": -1,
            })
