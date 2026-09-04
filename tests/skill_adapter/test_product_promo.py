"""Tests for the product promo skill adapter."""
from __future__ import annotations

import pytest

from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.skill_adapter.product_promo import build_package


class TestBuildPackage:
    def test_returns_valid_package(self) -> None:
        pkg = build_package(
            package_id="promo-001",
            title="Test Product",
            product_images=[
                {"asset_key": "product.front", "uri": "assets/product_front.png", "prompt": "front view"},
                {"asset_key": "product.side", "uri": "assets/product_side.png", "prompt": "side view"},
            ],
            scripts=[
                {"clip_id": "clip-001", "prompt": "Introduce the product", "duration_ms": 5000},
            ],
        )
        assert isinstance(pkg, VideoExecutionPackage)
        result = validate_package(pkg.to_dict())
        assert result.ok, f"Validation failed: {result.errors()}"

    def test_assets_from_images(self) -> None:
        pkg = build_package(
            package_id="promo-002",
            title="Test",
            product_images=[
                {"asset_key": "product.front", "uri": "assets/front.png"},
                {"asset_key": "product.side", "uri": "assets/side.png"},
            ],
            scripts=[{"prompt": "Test"}],
        )
        asset_keys = {a.asset_key for a in pkg.assets}
        assert "product.front" in asset_keys
        assert "product.side" in asset_keys

    def test_rejects_absolute_product_image_uri(self) -> None:
        with pytest.raises(ValueError, match="package-relative local URI"):
            build_package(
                package_id="promo-absolute-image",
                title="Test",
                product_images=[
                    {"asset_key": "product.front", "uri": "C:/outside/front.png"},
                ],
                scripts=[{"prompt": "Test"}],
            )

    def test_rejects_remote_dialogue_audio_uri(self) -> None:
        with pytest.raises(ValueError, match="package-relative local URI"):
            build_package(
                package_id="promo-remote-audio",
                title="Test",
                product_images=[
                    {"asset_key": "product.front", "uri": "assets/front.png"},
                ],
                scripts=[{"prompt": "Test"}],
                dialogue_audio=[
                    {"asset_key": "dialogue.001", "uri": "https://example.com/a.wav"},
                ],
            )

    def test_clips_have_references(self) -> None:
        pkg = build_package(
            package_id="promo-003",
            title="Test",
            product_images=[
                {"asset_key": "product.front", "uri": "assets/front.png"},
            ],
            scripts=[
                {"clip_id": "clip-001", "prompt": "Intro", "duration_ms": 3000},
            ],
        )
        assert len(pkg.clips) == 1
        refs = pkg.clips[0].generation.references
        assert len(refs) == 1
        assert refs[0].asset_key == "product.front"
        assert refs[0].binding.required is True

    def test_clip_count_matches_scripts(self) -> None:
        try:
            build_package(
                package_id="promo-004",
                title="Test",
                product_images=[{"asset_key": "p", "uri": "assets/p.png"}],
                scripts=[
                    {"prompt": f"Script {i}", "duration_ms": 3000}
                    for i in range(2)
                ],
            )
        except ValueError as exc:
            assert "exactly one script/clip" in str(exc)
        else:
            raise AssertionError("multi-clip product production must be rejected")

    def test_subtitle_cues(self) -> None:
        pkg = build_package(
            package_id="promo-005",
            title="Test",
            product_images=[{"asset_key": "p", "uri": "assets/p.png"}],
            scripts=[{
                "prompt": "Test",
                "cues": [
                    {"start_ms": 0, "end_ms": 1000, "text": "Buy now!"},
                ],
            }],
        )
        cues = pkg.clips[0].subtitles.cues
        assert len(cues) == 1
        assert cues[0].text == "Buy now!"

    def test_output_policy(self) -> None:
        pkg = build_package(
            package_id="promo-006",
            title="Test",
            product_images=[{"asset_key": "p", "uri": "assets/p.png"}],
            scripts=[{"prompt": "Test"}],
            width=720,
            height=1288,
            fps=30,
        )
        assert pkg.output.width == 720
        assert pkg.output.height == 1288
        assert pkg.output.fps == 30
        requirements = pkg.clips[0].generation.requirements
        assert requirements.aspect_ratio == "9:16"
        assert requirements.megapixels is None
        assert requirements.width is None

    def test_with_dialogue_audio(self) -> None:
        pkg = build_package(
            package_id="promo-007",
            title="Test",
            product_images=[{"asset_key": "p", "uri": "assets/p.png"}],
            scripts=[{"prompt": "Test", "duration_ms": 5000}],
            dialogue_audio=[
                {"asset_key": "dialogue.001", "uri": "assets/d001.wav"},
            ],
        )
        # Audio asset should be in assets
        asset_keys = {a.asset_key for a in pkg.assets}
        assert "dialogue.001" in asset_keys
        # First clip should have a track reference
        assert len(pkg.clips[0].audio.tracks) == 1
        assert pkg.clips[0].audio.tracks[0].asset_key == "dialogue.001"

    def test_rejects_duplicate_or_unused_dialogue_assets(self) -> None:
        with pytest.raises(ValueError, match="duplicate asset_key"):
            build_package(
                package_id="promo-duplicate-image",
                title="Test",
                product_images=[
                    {"asset_key": "p", "uri": "assets/front.png"},
                    {"asset_key": "p", "uri": "assets/side.png"},
                ],
                scripts=[{"prompt": "Test"}],
            )

        with pytest.raises(ValueError, match="at most one dialogue"):
            build_package(
                package_id="promo-extra-dialogue",
                title="Test",
                product_images=[{"asset_key": "p", "uri": "assets/front.png"}],
                scripts=[{"prompt": "Test"}],
                dialogue_audio=[
                    {"asset_key": "d1", "uri": "assets/d1.wav"},
                    {"asset_key": "d2", "uri": "assets/d2.wav"},
                ],
            )
