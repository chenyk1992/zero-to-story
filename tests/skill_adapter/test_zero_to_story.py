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
                        "width": 1080,
                        "height": 1920,
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
        assert clip.generation.requirements.width == 1080

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


class TestRoundTrip:
    def test_to_dict_and_validate(self, minimal_storyboard: dict) -> None:
        pkg = adapt(minimal_storyboard)
        data = pkg.to_dict()
        result = validate_package(data)
        assert result.ok
