"""Tests for the product promo skill adapter."""
from __future__ import annotations

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
                {"clip_id": "clip-002", "prompt": "Show features", "duration_ms": 4000},
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
        pkg = build_package(
            package_id="promo-004",
            title="Test",
            product_images=[{"asset_key": "p", "uri": "assets/p.png"}],
            scripts=[
                {"prompt": f"Script {i}", "duration_ms": 3000}
                for i in range(5)
            ],
        )
        assert len(pkg.clips) == 5

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
