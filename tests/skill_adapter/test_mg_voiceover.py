"""Tests for the MG voiceover animation Skill adapter."""

from __future__ import annotations

from typing import Any

import pytest

from lfo.contracts.package import validate_package
from lfo.skill_adapter.mg_voiceover import build_package


def _reference(
    asset_key: str = "product.hero",
    *,
    media_type: str = "image",
    placement: str = "any",
) -> dict[str, Any]:
    return {
        "asset_key": asset_key,
        "uri": f"assets/{asset_key}.png",
        "media_type": media_type,
        "semantic_usage": "product.hero",
        "instruction": "Keep the approved garment appearance exact",
        "required": True,
        "priority": 100,
        "placement": placement,
        "on_unsupported": "fail",
        "producer": "imagegen",
        "operation": "image.generate",
        "prompt_hash": "prompt-hash",
    }


def _build(**overrides: Any):
    values: dict[str, Any] = {
        "package_id": "summer-fashion-mg-001",
        "title": "Summer Fashion",
        "prompt": "A continuous vertical MG product voiceover animation",
        "duration_ms": 15_000,
        "approved_by": "user",
    }
    values.update(overrides)
    return build_package(**values)


@pytest.mark.parametrize(
    ("references", "operation"),
    [
        ([], "video.text_to_video"),
        ([_reference()], "video.image_to_video"),
        ([_reference("front"), _reference("detail")], "video.reference_to_video"),
        ([_reference("motion", media_type="video")], "video.reference_to_video"),
    ],
)
def test_routes_by_visual_reference_shape(references: list[dict[str, Any]], operation: str) -> None:
    package = _build(reference_assets=references)

    assert package.clips[0].generation.operation == operation
    assert validate_package(package.to_dict()).ok


def test_single_image_is_bound_to_first_frame() -> None:
    package = _build(reference_assets=[_reference(placement="any")])

    binding = package.clips[0].generation.references[0].binding
    assert package.clips[0].generation.requirements.reference_image_size == "match"
    assert binding.placement == "first"
    assert binding.required is True
    assert binding.priority == 100
    assert binding.on_unsupported == "fail"


def test_pixel_ratio_maps_without_generation_dimensions() -> None:
    package = _build(pixel_ratio="0.4")
    requirements = package.clips[0].generation.requirements

    assert requirements.megapixels == 0.4
    assert requirements.width is None
    assert requirements.height is None
    assert package.output.width == 1080
    assert package.output.height == 1920
    assert package.output.fps == 24


def test_dimensions_are_generation_requirements_without_pixel_ratio() -> None:
    package = _build(width=720, height=1280, fps=30)
    requirements = package.clips[0].generation.requirements

    assert requirements.megapixels is None
    assert requirements.width == 720
    assert requirements.height == 1280
    assert requirements.fps == 30


def test_default_project_id_is_non_empty_package_id() -> None:
    package = _build()

    assert package.project.project_id == package.package_id


def test_explicit_project_id_is_preserved() -> None:
    package = _build(project_id="summer-fashion")

    assert package.project.project_id == "summer-fashion"


def test_blank_project_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="project_id"):
        _build(project_id="   ")


def test_native_voiceover_and_ordinary_subtitles_are_explicit() -> None:
    package = _build()
    clip = package.clips[0]

    assert len(package.clips) == 1
    assert clip.duration_ms == 15_000
    assert clip.generation.requirements.native_audio == "allowed"
    assert clip.audio.native_audio == "preserve"
    assert clip.audio.tracks == []
    assert clip.subtitles.cues == []
    assert package.output.subtitles_mode == "none"


def test_external_voiceover_replaces_native_audio() -> None:
    package = _build(
        voiceover_audio={
            "asset_key": "voiceover.zh",
            "uri": "assets/voiceover.wav",
            "producer": "tts",
        }
    )
    clip = package.clips[0]
    audio_asset = next(asset for asset in package.assets if asset.asset_key == "voiceover.zh")

    assert clip.generation.requirements.native_audio == "none"
    assert clip.audio.native_audio == "replace"
    assert len(clip.audio.tracks) == 1
    assert clip.audio.tracks[0].asset_key == "voiceover.zh"
    assert clip.audio.tracks[0].role == "narration"
    assert audio_asset.provenance.operation == "audio.synthesize"


def test_approval_source_context_review_provenance_and_binding() -> None:
    package = _build(
        reference_assets=[_reference()],
        approved_at="2026-08-18T10:00:00+08:00",
        approval_notes="Prompt and product image approved",
        output_directory="summer-fashion-final",
    )
    clip = package.clips[0]
    asset = package.assets[0]
    reference = clip.generation.references[0]

    assert package.approval.approved_by == "user"
    assert package.approval.approved_at == "2026-08-18T10:00:00+08:00"
    assert package.approval.notes == "Prompt and product image approved"
    assert package.output.directory == "summer-fashion-final"
    assert clip.source_context["skill"] == "mg-voiceover-animation-generator"
    assert clip.source_context["continuous_clip"] is True
    assert asset.review.required is True
    assert asset.provenance.producer == "imagegen"
    assert asset.provenance.operation == "image.generate"
    assert reference.asset_key == asset.asset_key
    assert reference.semantic_usage == "product.hero"
    assert reference.instruction


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"duration_ms": 0}, ValueError),
        ({"approved_by": ""}, ValueError),
        ({"pixel_ratio": 0}, ValueError),
        ({"pixel_ratio": "not-a-number"}, TypeError),
        ({"reference_assets": "invalid"}, TypeError),
        ({"reference_assets": ["invalid"]}, TypeError),
        ({"reference_assets": [{"asset_key": "missing-fields"}]}, ValueError),
        ({"width": True}, TypeError),
    ],
)
def test_invalid_parameters(overrides: dict[str, Any], error: type[Exception]) -> None:
    with pytest.raises(error):
        _build(**overrides)


def test_duplicate_asset_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate asset_key"):
        _build(reference_assets=[_reference("same"), _reference("same")])


def test_required_reference_cannot_be_dropped() -> None:
    reference = _reference()
    reference["on_unsupported"] = "drop"

    with pytest.raises(ValueError, match="required reference"):
        _build(reference_assets=[reference])
