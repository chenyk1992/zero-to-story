"""Logical model registry — model identity declarations without machine paths."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelDeclaration:
    """A logical model identity (no machine paths)."""

    model_id: str
    model_type: str  # 'diffusion_model' | 'vae' | 'clip' | 'audio_vae' | 'llm'
    candidate_filenames: list[str] = field(default_factory=list)
    expected_size_min: int = 0  # bytes
    expected_size_max: int = 0  # bytes (0 = no limit)
    required_by: list[str] = field(default_factory=list)  # workflow_ids


# --------------------------------------------------------------------------- #
# Known models
# --------------------------------------------------------------------------- #

KNOWN_MODELS: dict[str, ModelDeclaration] = {
    "minimax_h3_fl2va_int8": ModelDeclaration(
        model_id="minimax_h3_fl2va_int8",
        model_type="diffusion_model",
        candidate_filenames=[
            "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        ],
        expected_size_min=19_000_000_000,  # ~19GB
        expected_size_max=21_000_000_000,  # ~21GB
        required_by=["h3_standard_fl2va"],
    ),
    "minimax_h3_ref2va_int8": ModelDeclaration(
        model_id="minimax_h3_ref2va_int8",
        model_type="diffusion_model",
        candidate_filenames=[
            "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        ],
        expected_size_min=19_000_000_000,
        expected_size_max=21_000_000_000,
        required_by=["h3_standard_r2v", "h3_presenter_r2v"],
    ),
    "minimax_h3_video_vae_fp16": ModelDeclaration(
        model_id="minimax_h3_video_vae_fp16",
        model_type="vae",
        candidate_filenames=[
            "minimax_h3_video_vae_fp16.safetensors",
        ],
        expected_size_min=4_500_000_000,  # ~4.5GB
        expected_size_max=5_500_000_000,  # ~5.5GB
        required_by=["h3_standard_fl2va", "h3_standard_r2v", "h3_presenter_r2v"],
    ),
    "minimax_h3_audio_vae_fp32": ModelDeclaration(
        model_id="minimax_h3_audio_vae_fp32",
        model_type="audio_vae",
        candidate_filenames=[
            "minimax_h3_audio_vae_fp32.safetensors",
        ],
        expected_size_min=500_000_000,  # ~500MB
        expected_size_max=700_000_000,  # ~700MB
        required_by=["h3_standard_fl2va", "h3_standard_r2v", "h3_presenter_r2v"],
    ),
    "qwen3vl_32b_minimax_h3_nvfp4_awq": ModelDeclaration(
        model_id="qwen3vl_32b_minimax_h3_nvfp4_awq",
        model_type="llm",
        candidate_filenames=[
            "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        ],
        expected_size_min=14_000_000_000,  # ~14GB
        expected_size_max=16_000_000_000,  # ~16GB
        required_by=["h3_standard_fl2va", "h3_standard_r2v", "h3_presenter_r2v"],
    ),
}


def get_model_declaration(model_id: str) -> ModelDeclaration | None:
    """Get a model declaration by logical ID."""
    return KNOWN_MODELS.get(model_id)


def list_models_required_by(workflow_id: str) -> list[ModelDeclaration]:
    """List all models required by a given workflow."""
    return [
        m for m in KNOWN_MODELS.values() if workflow_id in m.required_by
    ]


def list_all_models() -> list[ModelDeclaration]:
    """List all registered models."""
    return list(KNOWN_MODELS.values())
