"""Tests for ModelResolver."""
from __future__ import annotations

import pytest

from lfo.config.machine_profile import ComfyUIConfig, MachineProfile
from lfo.services.model_resolver import ModelResolver, ResolvedModel


@pytest.fixture
def empty_profile():
    return MachineProfile(
        machine_id="test",
        comfyui=ComfyUIConfig(root="/nonexistent"),
    )


class TestModelResolver:
    def test_init(self, empty_profile):
        resolver = ModelResolver(empty_profile)
        assert resolver.profile == empty_profile

    def test_resolve_unknown_model(self, empty_profile):
        resolver = ModelResolver(empty_profile)
        result = resolver.resolve("totally_unknown_model")
        assert result.found is False
        assert result.resolved_path is None

    def test_resolve_nonexistent_dir(self, empty_profile):
        """When model dirs don't exist, model is not found."""
        resolver = ModelResolver(empty_profile)
        result = resolver.resolve("minimax_h3_fl2va_int8")
        assert result.found is False

    def test_resolve_with_real_model_file(self, tmp_path):
        """Create a fake model file and verify it's found."""
        models_dir = tmp_path / "models" / "unet"
        models_dir.mkdir(parents=True)
        model_file = models_dir / "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
        model_file.write_bytes(b"fake model data" * 100)

        profile = MachineProfile(
            machine_id="test",
            comfyui=ComfyUIConfig(root=str(tmp_path)),
        )
        resolver = ModelResolver(profile)
        result = resolver.resolve("minimax_h3_fl2va_int8")
        assert result.found is True
        assert result.resolved_path is not None
        assert result.verification_mode == "quick"
        assert result.size_bytes > 0

    def test_resolve_many(self, tmp_path, empty_profile):
        resolver = ModelResolver(empty_profile)
        result = resolver.resolve_many({"minimax_h3_fl2va_int8", "unknown_model"})
        assert "minimax_h3_fl2va_int8" in result
        assert "unknown_model" in result

    def test_strict_verify(self, tmp_path):
        """Strict verification computes SHA-256."""
        models_dir = tmp_path / "models" / "vae"
        models_dir.mkdir(parents=True)
        model_file = models_dir / "minimax_h3_video_vae_fp16.safetensors"
        model_file.write_bytes(b"test vae data")

        profile = MachineProfile(
            machine_id="test",
            comfyui=ComfyUIConfig(root=str(tmp_path)),
        )
        resolver = ModelResolver(profile)
        result = resolver.strict_verify("minimax_h3_video_vae_fp16")
        assert result.found is True
        assert result.verification_mode == "strict"
        assert result.sha256 is not None
        assert len(result.sha256) == 64  # SHA-256 hex

    def test_strict_verify_not_found(self, empty_profile):
        resolver = ModelResolver(empty_profile)
        result = resolver.strict_verify("minimax_h3_fl2va_int8")
        assert result.found is False
        assert result.sha256 is None


class TestResolvedModel:
    def test_defaults(self):
        rm = ResolvedModel(
            model_id="test",
            resolved_path=None,
            verification_mode="quick",
        )
        assert rm.found is False
        assert rm.size_bytes == 0
