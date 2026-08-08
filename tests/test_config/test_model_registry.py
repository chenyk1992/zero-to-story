"""Tests for logical model registry."""
from __future__ import annotations

from lfo.config.model_registry import (
    KNOWN_MODELS,
    get_model_declaration,
    list_all_models,
    list_models_required_by,
)


class TestKnownModels:
    def test_five_models_registered(self):
        assert len(KNOWN_MODELS) == 5

    def test_fl2va_model(self):
        m = KNOWN_MODELS["minimax_h3_fl2va_int8"]
        assert m.model_type == "diffusion_model"
        assert m.expected_size_min > 0

    def test_ref2va_model(self):
        m = KNOWN_MODELS["minimax_h3_ref2va_int8"]
        assert m.model_type == "diffusion_model"

    def test_vae_model(self):
        m = KNOWN_MODELS["minimax_h3_video_vae_fp16"]
        assert m.model_type == "vae"

    def test_audio_vae_model(self):
        m = KNOWN_MODELS["minimax_h3_audio_vae_fp32"]
        assert m.model_type == "audio_vae"

    def test_llm_model(self):
        m = KNOWN_MODELS["qwen3vl_32b_minimax_h3_nvfp4_awq"]
        assert m.model_type == "llm"

    def test_each_model_has_required_by(self):
        for mid, decl in KNOWN_MODELS.items():
            assert len(decl.required_by) > 0, f"{mid} has no required_by"


class TestGetModelDeclaration:
    def test_existing(self):
        m = get_model_declaration("minimax_h3_fl2va_int8")
        assert m is not None
        assert m.model_id == "minimax_h3_fl2va_int8"

    def test_nonexistent(self):
        assert get_model_declaration("nonexistent") is None


class TestListModelsRequiredBy:
    def test_h3_t2v(self):
        models = list_models_required_by("h3_standard_t2v")
        assert len(models) >= 4  # fl2va + vae + audio_vae + llm

    def test_h3_r2v(self):
        models = list_models_required_by("h3_standard_r2v")
        model_ids = {m.model_id for m in models}
        assert "minimax_h3_ref2va_int8" in model_ids

    def test_unknown_workflow(self):
        assert list_models_required_by("unknown") == []

    def test_all_models(self):
        all_models = list_all_models()
        assert len(all_models) == len(KNOWN_MODELS)
