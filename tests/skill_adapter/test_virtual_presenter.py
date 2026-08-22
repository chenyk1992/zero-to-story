from __future__ import annotations

import pytest

from lfo.skill_adapter.virtual_presenter import build_assembly_package, build_shot_package


def _plan() -> dict:
    return {
        "project": {"project_id": "presenter", "title": "Presenter", "locale": "zh-CN"},
        "inputs": {
            "character_uri": "characters/hero.png",
            "panorama_uri": "environments/lobby.png",
            "voice_uri": "audio/voice.wav",
        },
        "output": {"width": 1080, "height": 1920, "fps": 24, "subtitles_mode": "both"},
        "shots": [
            {
                "shot_id": "shot-001",
                "sequence": 1,
                "duration_ms": 5000,
                "prompt": "The presenter greets the viewer",
                "environment_view_uri": "environments/lobby-front.png",
                "seed": 7,
                "subtitles": {"cues": [{"start_ms": 0, "end_ms": 1200, "text": "你好"}]},
                "continuity": {"gaze": "camera"},
            },
            {
                "shot_id": "shot-002",
                "sequence": 2,
                "duration_ms": 6000,
                "prompt": "The presenter continues",
                "environment_view_uri": "environments/lobby-side.png",
            },
        ],
        "approval": {"status": "approved", "reviewer": "user"},
    }


def test_build_shot_package_maps_fixed_and_optional_references() -> None:
    plan = _plan()
    plan["shots"][0]["include_voice_reference"] = True
    package = build_shot_package(plan, "shot-001", previous_clip_uri="accepted/shot-000.mp4")
    clip = package.clips[0]
    assert clip.generation.operation == "video.virtual_presenter"
    assert [reference.binding.slot for reference in clip.generation.references] == [
        "ref_image_0", "ref_image_1", "ref_image_2", "ref_audio_0", "ref_video_0",
    ]
    assert [reference.reference_id for reference in clip.generation.references] == [
        "character", "panorama", "direction", "voice", "previous",
    ]
    assert clip.source_context["skill"] == "virtual-presenter"
    assert clip.source_context["shot"] == "shot-001"
    assert clip.source_context["shot_contract"]["continuity"] == {"gaze": "camera"}
    assert clip.generation.requirements.aspect_ratio == "9:16"
    assert clip.generation.requirements.megapixels == 0.4
    assert clip.generation.requirements.width is None
    assert package.output.width == 1080
    assert all(not asset.source.uri.startswith(("/", "\\")) for asset in package.assets)


def test_build_shot_package_defaults_to_previous_video_audio_for_continuity() -> None:
    package = build_shot_package(
        _plan(), "shot-002", previous_clip_uri="accepted/shot-001.mp4"
    )
    assert [reference.binding.slot for reference in package.clips[0].generation.references] == [
        "ref_image_0",
        "ref_image_1",
        "ref_image_2",
        "ref_video_0",
    ]

    plan = _plan()
    plan["shots"][1]["include_voice_reference"] = True
    compared = build_shot_package(
        plan, "shot-002", previous_clip_uri="accepted/shot-001.mp4"
    )
    assert [reference.binding.slot for reference in compared.clips[0].generation.references][-2:] == [
        "ref_audio_0",
        "ref_video_0",
    ]

    no_voice_plan = _plan()
    del no_voice_plan["inputs"]["voice_uri"]
    no_voice = build_shot_package(no_voice_plan, "shot-001")
    assert "ref_audio_0" not in [
        reference.binding.slot for reference in no_voice.clips[0].generation.references
    ]


def test_build_assembly_package_maps_each_accepted_clip_to_passthrough() -> None:
    package = build_assembly_package(
        _plan(),
        [
            {"shot_id": "shot-001", "sequence": 1, "duration_ms": 5000, "uri": "accepted/001.mp4"},
            {"shot_id": "shot-002", "sequence": 2, "duration_ms": 6000, "uri": "accepted/002.mp4"},
        ],
    )
    assert [clip.generation.operation for clip in package.clips] == [
        "video.passthrough", "video.passthrough",
    ]
    assert all(
        clip.generation.references[0].binding.slot == "source_video"
        and clip.generation.references[0].reference_id == "source_video"
        for clip in package.clips
    )
    assert package.clips[0].subtitles.cues[0].text == "你好"


def test_build_assembly_package_requires_complete_matching_accepted_clips() -> None:
    with pytest.raises(ValueError, match="every planned shot"):
        build_assembly_package(
            _plan(),
            [
                {
                    "shot_id": "shot-001",
                    "sequence": 1,
                    "duration_ms": 5000,
                    "uri": "accepted/001.mp4",
                }
            ],
        )

    accepted = [
        {
            "shot_id": "shot-001",
            "sequence": 1,
            "duration_ms": 5000,
            "uri": "accepted/001.mp4",
        },
        {
            "shot_id": "shot-002",
            "sequence": 2,
            "duration_ms": 5001,
            "uri": "accepted/002.mp4",
        },
    ]
    with pytest.raises(ValueError, match="duration_ms does not match"):
        build_assembly_package(_plan(), accepted)


@pytest.mark.parametrize("bad_uri", ["C:/secret.png", "/secret.png", "https://example.invalid/a.png", "../secret.png"])
def test_adapter_rejects_absolute_or_escaping_uri(bad_uri: str) -> None:
    plan = _plan()
    plan["inputs"]["character_uri"] = bad_uri
    with pytest.raises(ValueError, match="package-relative|must not contain"):
        build_shot_package(plan, "shot-001")


def test_adapter_rejects_unapproved_duplicate_and_out_of_range_plan() -> None:
    plan = _plan()
    plan["approval"]["status"] = "pending"
    with pytest.raises(ValueError, match="approved"):
        build_shot_package(plan, "shot-001")

    plan = _plan()
    plan["shots"][1]["sequence"] = 1
    with pytest.raises(ValueError, match="duplicate sequence"):
        build_shot_package(plan, "shot-001")

    plan = _plan()
    plan["shots"][0]["duration_ms"] = 3000
    with pytest.raises(ValueError, match="between 4000ms"):
        build_shot_package(plan, "shot-001")
