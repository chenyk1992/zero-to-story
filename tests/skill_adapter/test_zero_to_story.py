"""Tests for the zero-to-story skill adapter."""
from __future__ import annotations

import pytest

from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.skill_adapter.zero_to_story import adapt


@pytest.fixture
def minimal_storyboard() -> dict:
    """A minimal legacy storyboard dict."""
    return {
        "project_id": "test-story-001",
        "project": {
            "title": "Test Story",
            "locale": "zh-CN",
            "revision": 1,
        },
        "assets": [
            {
                "asset_key": "hero.identity.front",
                "media_type": "image",
                "source": {"uri": "assets/hero.png"},
                "provenance": {
                    "source_type": "external_skill",
                    "producer": "imagegen",
                    "operation": "image.generate",
                },
                "review": {"required": True},
            },
        ],
        "shots": [
            {
                "shot_id": "shot-001",
                "duration_ms": 5000,
                "generation": {
                    "operation": "video.reference_to_video",
                    "prompt": "A hero walking in the rain",
                    "requirements": {
                        "aspect_ratio": "9:16",
                        "megapixels": 0.4,
                        "fps": 24,
                    },
                    "references": [
                        {
                            "reference_id": "ref-001",
                            "asset_key": "hero.identity.front",
                            "semantic_usage": "subject.identity",
                            "instruction": "Keep hero consistent",
                            "binding": {
                                "required": True,
                                "priority": 100,
                                "placement": "fixed",
                                "slot": "ref_image_0",
                            },
                        },
                    ],
                },
                "audio": {
                    "native_audio": "preserve",
                    "tracks": [],
                },
            },
        ],
        "output": {
            "width": 1080,
            "height": 1920,
            "fps": 24,
        },
        "approval": {
            "approved_by": "user",
            "approved_at": "2026-08-09T12:00:00Z",
        },
    }


class TestAdaptMinimal:
    def test_returns_valid_package(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        assert isinstance(pkg, VideoExecutionPackage)
        result = validate_package(pkg.to_dict())
        assert result.ok, f"Validation failed: {result.errors()}"

    def test_package_id_from_project(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        assert pkg.package_id == "test-story-001"

    def test_project_info(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        assert pkg.project.title == "Test Story"
        assert pkg.project.locale == "zh-CN"

    def test_one_clip_created(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        assert len(pkg.clips) == 1
        assert pkg.clips[0].clip_id == "clip-001"
        assert pkg.clips[0].sequence == 1
        assert pkg.clips[0].duration_ms == 5000

    def test_generation_spec(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        clip = pkg.clips[0]
        assert clip.generation.operation == "video.reference_to_video"
        assert clip.generation.prompt == "A hero walking in the rain"
        assert clip.generation.requirements.aspect_ratio == "9:16"
        assert clip.generation.requirements.megapixels == 0.4
        assert clip.generation.requirements.width is None
        assert clip.generation.requirements.height is None

    def test_references_mapped(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        refs = pkg.clips[0].generation.references
        assert len(refs) == 1
        assert refs[0].asset_key == "hero.identity.front"
        assert refs[0].binding.required is True
        assert refs[0].binding.priority == 100

    def test_assets_collected(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        assert len(pkg.assets) >= 1
        asset_keys = {a.asset_key for a in pkg.assets}
        assert "hero.identity.front" in asset_keys


class TestAdaptPanelFirst:
    def test_panel_requires_explicit_generation_operation(self) -> None:
        creative = {
            "project": {"project_id": "panel-operation-required"},
            "assets": [],
            "panels": [{"panel_id": "panel-001", "prompt_text": "Approved prompt."}],
        }
        with pytest.raises(ValueError, match="generation.operation is required"):
            adapt(creative)

    @pytest.mark.parametrize("operation", ["video.unknown", "video.not_supported"])
    def test_panel_rejects_unknown_generation_operation(self, operation: str) -> None:
        creative = {
            "project": {"project_id": "panel-unknown-operation"},
            "assets": [],
            "panels": [{
                "panel_id": "panel-001",
                "prompt_text": "Approved prompt.",
                "generation": {"operation": operation},
            }],
        }
        with pytest.raises(ValueError, match="Unsupported video operation"):
            adapt(creative)

    def test_panel_rejects_empty_r2v_references(self) -> None:
        creative = {
            "project": {"project_id": "panel-empty-r2v"},
            "assets": [],
            "panels": [{
                "panel_id": "panel-001",
                "prompt_text": "A reference-driven shot.",
                "generation": {"operation": "video.reference_to_video"},
            }],
        }
        with pytest.raises(ValueError, match="requires at least one reference"):
            adapt(creative)

    def test_approved_panel_becomes_clip(self) -> None:
        creative = {
            "project": {
                "project_id": "panel-story-001",
                "title": "Panel Story",
                "locale": "zh-CN",
                "revision": 2,
            },
            "assets": [
                {
                    "asset_key": "character.hero",
                    "asset_id": "asset-hero",
                    "media_type": "image",
                    "uri": "assets/hero.png",
                },
                {
                    "asset_key": "storyboard.panel-001",
                    "asset_id": "asset-panel-001",
                    "media_type": "image",
                    "uri": "assets/panel-001.png",
                },
            ],
            "user_constraints": {
                "aspect_ratio": "9:16",
                "delivery_width": 1080,
                "delivery_height": 1920,
                "frame_rate": 24,
            },
            "panels": [{
                "panel_id": "panel-001",
                "desired_duration_ms": 15000,
                "prompt_text": "The approved, continuous panel prompt.",
                "generation": {"operation": "video.reference_to_video"},
                "pack": {"refs": [
                    {
                        "asset_id": "asset-hero",
                        "role": "character",
                        "purpose": "Keep identity consistent.",
                        "binding": {"placement": "fixed", "slot": "ref_image_0"},
                    },
                    {
                        "asset_id": "asset-panel-001",
                        "role": "composition",
                        "purpose": "Use only for composition and motion.",
                        "binding": {"placement": "fixed", "slot": "ref_image_1"},
                    },
                ]},
                "beat_range": ["B001", "B006"],
                "setup_range": ["C001", "C002"],
            }],
            "review": {
                "status": "approved",
                "reviewer": "user",
                "approved_at": "2026-08-09T00:00:00Z",
            },
        }
        package = adapt(creative)
        assert validate_package(package.to_dict()).ok
        assert package.revision == 2
        assert package.clips[0].clip_id == "panel-001"
        assert package.clips[0].duration_ms == 15000
        assert package.clips[0].source_context["beat_range"] == ["B001", "B006"]
        assert package.clips[0].source_context["setup_range"] == ["C001", "C002"]
        assert [ref.asset_key for ref in package.clips[0].generation.references] == [
            "character.hero", "storyboard.panel-001",
        ]
        assert package.clips[0].generation.references[-1].binding.placement == "fixed"
        assert package.approval.approved_by == "user"
        requirements = package.clips[0].generation.requirements
        assert requirements.aspect_ratio == "9:16"
        assert requirements.megapixels == 0.4
        assert requirements.width is None
        assert package.output.width == 1080
        assert package.output.height == 1920

    def test_panel_preserves_explicit_frame_bindings(self) -> None:
        creative = {
            "project": {"project_id": "panel-frame-001"},
            "assets": [
                {"asset_key": "frame.first", "media_type": "image", "uri": "first.png"},
                {"asset_key": "frame.last", "media_type": "image", "uri": "last.png"},
            ],
            "panels": [{
                "panel_id": "panel-001",
                "prompt_text": "The scholar takes one deliberate step.",
                "generation": {"operation": "video.first_last_frame"},
                "references": [
                    {
                        "asset_key": "frame.first",
                        "semantic_usage": "continuity.start",
                        "binding": {"placement": "first", "priority": 9},
                    },
                    {
                        "asset_key": "frame.last",
                        "semantic_usage": "continuity.end",
                        "binding": {"placement": "last", "priority": 8},
                    },
                ],
            }],
        }

        package = adapt(creative)
        refs = package.clips[0].generation.references
        assert package.clips[0].generation.operation == "video.first_last_frame"
        assert [ref.binding.placement for ref in refs] == ["first", "last"]
        assert [ref.binding.priority for ref in refs] == [9, 8]

    @pytest.mark.parametrize(
        "claim",
        [
            {"semantic_usage": "exact_previous_last_frame"},
            {"instruction": "hard previous last frame"},
        ],
    )
    def test_panel_rejects_r2v_exact_previous_tail_claim(
        self,
        claim: dict[str, str],
    ) -> None:
        creative = {
            "project": {"project_id": "panel-r2v-fake-lock"},
            "assets": [
                {"asset_key": "tail.previous", "media_type": "image", "uri": "tail.png"},
            ],
            "panels": [
                {
                    "panel_id": "panel-002",
                    "prompt_text": "Continue from the prior panel.",
                    "generation": {"operation": "video.reference_to_video"},
                    "references": [
                        {
                            "asset_key": "tail.previous",
                            "binding": {"placement": "fixed", "slot": "ref_image_0"},
                            **claim,
                        }
                    ],
                }
            ],
        }

        with pytest.raises(ValueError, match="exact/hard first-frame continuity"):
            adapt(creative)

    def test_panel_first_does_not_create_placeholder_assets(self) -> None:
        creative = {
            "project": {"project_id": "panel-story-002", "title": "Panel Story"},
            "assets": [],
            "panels": [{
                "panel_id": "panel-001",
                "prompt_text": "Approved prompt.",
                "generation": {"operation": "video.reference_to_video"},
                "references": [{
                    "asset_key": "missing",
                    "role": "character",
                    "binding": {"placement": "fixed", "slot": "ref_image_0"},
                }],
            }],
        }
        with pytest.raises(ValueError, match="invalid VideoExecutionPackage"):
            adapt(creative)


class TestAdaptMultiShot:
    def test_multiple_ships(self) -> None:
        storyboard = {
            "project_id": "multi-001",
            "project": {"title": "Multi-Shot", "revision": 1},
            "shots": [
                {
                    "shot_id": f"shot-{i:03d}",
                    "duration_ms": 5000,
                    "generation": {
                        "operation": "video.text_to_video",
                        "prompt": f"Shot {i}",
                    },
                }
                for i in range(1, 4)
            ],
            "output": {},
        }
        pkg = adapt(storyboard)
        assert len(pkg.clips) == 3
        assert [c.clip_id for c in pkg.clips] == ["clip-001", "clip-002", "clip-003"]
        assert [c.sequence for c in pkg.clips] == [1, 2, 3]


class TestAdaptWithSubtitles:
    def test_subtitle_cues_mapped(self, minimal_storyboard: dict) -> None:
        minimal_storyboard["shots"][0]["subtitles"] = {
            "cues": [
                {"start_ms": 0, "end_ms": 2000, "text": "Hello"},
                {"start_ms": 2000, "end_ms": 4000, "text": "World"},
            ],
        }
        pkg = adapt(minimal_storyboard)
        cues = pkg.clips[0].subtitles.cues
        assert len(cues) == 2
        assert cues[0].text == "Hello"
        assert cues[1].start_ms == 2000


class TestDirectorRhythmRouting:
    @staticmethod
    def _creative_panel(
        operation: str,
        references: list[dict[str, object]],
        assets: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "project": {"project_id": f"director-{operation.rsplit('.', 1)[-1]}"},
            "assets": assets,
            "panels": [{
                "panel_id": "panel-001",
                "desired_duration_ms": 12000,
                "prompt_text": (
                    "[Shot 1] C001 holds the same setup across B001 and B002. "
                    "[Shot 2] C002 introduces one new viewpoint."
                ),
                "beat_range": ["B001", "B006"],
                "setup_range": ["C001", "C002"],
                "generation": {"operation": operation},
                "references": references,
            }],
        }

    @pytest.mark.parametrize(
        ("operation", "references", "assets"),
        [
            ("video.text_to_video", [], []),
            (
                "video.image_to_video",
                [{
                    "asset_key": "tail.previous",
                    "semantic_usage": "continuity.start",
                    "binding": {"placement": "first", "slot": "first_frame"},
                }],
                [{"asset_key": "tail.previous", "media_type": "image", "uri": "tail.png"}],
            ),
            (
                "video.first_last_frame",
                [
                    {
                        "asset_key": "frame.first",
                        "semantic_usage": "continuity.start",
                        "binding": {"placement": "first", "slot": "first_frame"},
                    },
                    {
                        "asset_key": "frame.last",
                        "semantic_usage": "continuity.end",
                        "binding": {"placement": "last", "slot": "last_frame"},
                    },
                ],
                [
                    {"asset_key": "frame.first", "media_type": "image", "uri": "first.png"},
                    {"asset_key": "frame.last", "media_type": "image", "uri": "last.png"},
                ],
            ),
            (
                "video.reference_to_video",
                [
                    {
                        "asset_key": "character.hero",
                        "semantic_usage": "subject.identity",
                        "binding": {"placement": "fixed", "slot": "ref_image_0"},
                    },
                    {
                        "asset_key": "scene.yamen",
                        "semantic_usage": "scene.layout",
                        "binding": {"placement": "fixed", "slot": "ref_image_1"},
                    },
                ],
                [
                    {"asset_key": "character.hero", "media_type": "image", "uri": "hero.png"},
                    {"asset_key": "scene.yamen", "media_type": "image", "uri": "yamen.png"},
                ],
            ),
        ],
    )
    def test_one_panel_preserves_director_setup_trace(
        self,
        operation: str,
        references: list[dict[str, object]],
        assets: list[dict[str, object]],
    ) -> None:
        package = adapt(self._creative_panel(operation, references, assets))

        assert validate_package(package.to_dict()).ok
        assert len(package.clips) == 1
        assert package.clips[0].source_context["beat_range"] == ["B001", "B006"]
        assert package.clips[0].source_context["setup_range"] == ["C001", "C002"]
        assert package.clips[0].generation.operation == operation

    def test_text_to_video_rejects_reference_instead_of_falling_back(self) -> None:
        creative = self._creative_panel(
            "video.text_to_video",
            [{
                "asset_key": "scene.yamen",
                "semantic_usage": "scene.layout",
                "binding": {"placement": "fixed", "slot": "ref_image_0"},
            }],
            [{"asset_key": "scene.yamen", "media_type": "image", "uri": "yamen.png"}],
        )

        with pytest.raises(ValueError, match="does not accept image references"):
            adapt(creative)


class TestRoundTrip:
    def test_to_dict_and_validate(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        data = pkg.to_dict()
        result = validate_package(data)
        assert result.ok
