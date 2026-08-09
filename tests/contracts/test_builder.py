"""Tests for the public VideoPackageBuilder SDK."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.contracts import (
    AssetSource,
    AssetSpec,
    BindingPolicy,
    ClipSpec,
    GenerationSpec,
    OutputPolicy,
    ProvenanceSpec,
    ReferenceSpec,
    VideoPackageBuilder,
    validate_package,
)


def _asset() -> AssetSpec:
    return AssetSpec(
        asset_key="subject.hero",
        media_type="image",
        source=AssetSource(uri="assets/hero.png"),
        provenance=ProvenanceSpec(
            source_type="external_skill",
            producer="imagegen",
            operation="image.generate",
        ),
    )


def _clip() -> ClipSpec:
    return ClipSpec(
        clip_id="clip-001",
        sequence=1,
        duration_ms=5000,
        generation=GenerationSpec(
            operation="video.reference_to_video",
            prompt="A hero walks through rain.",
            references=[ReferenceSpec(
                reference_id="hero",
                asset_key="subject.hero",
                semantic_usage="subject.identity",
                binding=BindingPolicy(required=True, priority=100),
            )],
        ),
    )


def test_builder_builds_a_valid_package() -> None:
    package = (
        VideoPackageBuilder("pkg-001", "A test", locale="zh-CN")
        .add_asset(_asset())
        .add_clip(_clip())
        .output(OutputPolicy(width=1080, height=1920, fps=24))
        .approval(approved_by="user", approved_at="2026-08-09T00:00:00Z")
        .build()
    )
    assert validate_package(package.to_dict()).ok
    assert package.project.locale == "zh-CN"


def test_builder_writes_stable_valid_json(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "execution-package.json"
    builder = VideoPackageBuilder("pkg-001", "A test").add_asset(_asset()).add_clip(_clip())
    assert builder.write(destination) == destination
    data = json.loads(destination.read_text(encoding="utf-8"))
    assert validate_package(data).ok


def test_builder_rejects_invalid_references() -> None:
    bad_clip = ClipSpec(
        clip_id="clip-001",
        sequence=1,
        duration_ms=1000,
        generation=GenerationSpec(
            operation="video.reference_to_video",
            prompt="A test",
            references=[ReferenceSpec(
                reference_id="missing",
                asset_key="missing.asset",
                semantic_usage="subject.identity",
                binding=BindingPolicy(),
            )],
        ),
    )
    with pytest.raises(ValueError, match="invalid VideoExecutionPackage"):
        VideoPackageBuilder("pkg-001", "A test").add_clip(bad_clip).build()


def test_builder_convenience_fields_round_trip(tmp_path: Path) -> None:
    destination = tmp_path / "execution-package.json"
    builder = VideoPackageBuilder("pkg-fields", "Fields")
    builder.add_asset(
        asset_key="hero",
        media_type="image",
        uri="assets/hero.png",
        producer="imagegen",
        operation="image.generate",
    )
    builder.add_clip(
        clip_id="clip-001",
        sequence=1,
        duration_ms=5_000,
        operation="video.reference_to_video",
        prompt="Hero walks through rain",
        references=[
            {
                "reference_id": "hero-ref",
                "asset_key": "hero",
                "semantic_usage": "subject.identity",
                "binding": {"required": True, "priority": 100},
            }
        ],
    )
    builder.write(destination)
    data = json.loads(destination.read_text(encoding="utf-8"))
    assert data["assets"][0]["asset_key"] == "hero"
    assert data["clips"][0]["generation"]["references"][0]["asset_key"] == "hero"
