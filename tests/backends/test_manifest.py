"""Tests for BackendManifest and validate_manifest."""
from __future__ import annotations

import json
import pathlib

import pytest

from lfo.backends.manifest import BackendManifest, validate_manifest


class TestValidateManifest:
    def test_valid_manifest(self) -> None:
        data = {
            "capability": {
                "backend_id": "comfyui.h3",
                "revision": "1.0.0",
                "workflow_hash": "abc123",
                "operations": ["video.text_to_video"],
                "accepted_media_types": ["image"],
                "max_references": 9,
                "duration_constraints": {"min_ms": 1000},
                "frame_constraints": {"formula": "17k+5"},
                "resolution_constraints": {"min_width": 256},
                "fps_constraints": [24.0],
                "native_audio_capability": "optional",
                "reproducibility_claim": "best_effort",
                "seed_capability": True,
            }
        }
        errors = validate_manifest(data)
        assert errors == []

    def test_missing_capability(self) -> None:
        errors = validate_manifest({})
        assert any("capability" in e for e in errors)

    def test_missing_required_fields(self) -> None:
        data = {"capability": {}}
        errors = validate_manifest(data)
        assert any("backend_id" in e for e in errors)
        assert any("revision" in e for e in errors)
        assert any("workflow_hash" in e for e in errors)

    def test_invalid_operations_type(self) -> None:
        data = {"capability": {
            "backend_id": "x", "revision": "1", "workflow_hash": "h",
            "operations": "not-a-list",
        }}
        errors = validate_manifest(data)
        assert any("operations" in e for e in errors)

    def test_invalid_native_audio(self) -> None:
        data = {"capability": {
            "backend_id": "x", "revision": "1", "workflow_hash": "h",
            "native_audio_capability": "sometimes",
        }}
        errors = validate_manifest(data)
        assert any("native_audio_capability" in e for e in errors)

    def test_not_a_dict(self) -> None:
        errors = validate_manifest("not a dict")  # type: ignore
        assert len(errors) == 1


class TestBackendManifest:
    def test_from_dict_round_trip(self, tmp_path: pathlib.Path) -> None:
        data = {
            "name": "ComfyUI H3 R2V",
            "description": "Reference-to-video via ComfyUI",
            "version": "1.0.0",
            "authors": ["LFO"],
            "capability": {
                "backend_id": "comfyui.h3",
                "revision": "1.0.0",
                "workflow_hash": "abc123",
                "operations": ["video.reference_to_video"],
                "accepted_media_types": ["image"],
                "max_references": 9,
                "duration_constraints": {},
                "frame_constraints": {},
                "resolution_constraints": {},
                "fps_constraints": [24.0],
                "seed_capability": True,
            },
        }
        m = BackendManifest.from_dict(data)
        assert m.name == "ComfyUI H3 R2V"
        assert m.capability.backend_id == "comfyui.h3"
        assert m.to_dict()["name"] == "ComfyUI H3 R2V"

    def test_from_json(self, tmp_path: pathlib.Path) -> None:
        data = {
            "name": "Test",
            "capability": {
                "backend_id": "test",
                "revision": "1",
                "workflow_hash": "h",
                "operations": ["video.text_to_video"],
                "accepted_media_types": [],
                "max_references": 0,
                "duration_constraints": {},
                "frame_constraints": {},
                "resolution_constraints": {},
                "fps_constraints": [],
            },
        }
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        m = BackendManifest.from_json(p)
        assert m.capability.backend_id == "test"
