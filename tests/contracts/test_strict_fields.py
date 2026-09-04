"""Unknown-field rejection for VideoExecutionPackage contract objects."""
from __future__ import annotations

import re

import pytest

from lfo.contracts import (
    ApprovalDeclaration,
    AssetSource,
    AssetSpec,
    AudioPolicy,
    AudioTrackSpec,
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    OutputPolicy,
    ProjectInfo,
    ProvenanceSpec,
    ReferenceSpec,
    ReviewDeclaration,
    SubtitleCue,
    SubtitleSpec,
    TimelineSegment,
    TimelineSpec,
    VideoExecutionPackage,
    validate_package,
)
from lfo.contracts.package import SCHEMA_ID


def _asset() -> dict:
    return {
        "asset_key": "image",
        "media_type": "image",
        "source": {"uri": "assets/image.png"},
        "provenance": {
            "source_type": "external_skill",
            "producer": "test",
            "operation": "image.generate",
        },
        "review": {},
    }


def _clip() -> dict:
    return {
        "clip_id": "clip-001",
        "sequence": 1,
        "duration_ms": 1000,
        "generation": {
            "operation": "video.text_to_video",
            "prompt": "A test clip",
            "requirements": {},
        },
    }


def _package() -> dict:
    return {
        "schema": SCHEMA_ID,
        "package_id": "package-001",
        "revision": 1,
        "project": {"title": "Test", "project_id": "project-001"},
        "assets": [_asset()],
        "clips": [_clip()],
        "output": {},
    }


@pytest.mark.parametrize(
    ("parser", "data", "path"),
    [
        (ProjectInfo.from_dict, {"title": "T", "project_id": "p", "titel": "typo"}, "$.titel"),
        (AssetSource.from_dict, {"uri": "x", "urii": "typo"}, "$.urii"),
        (AssetSpec.from_dict, {**_asset(), "medai_type": "image"}, "$.medai_type"),
        (
            ProvenanceSpec.from_dict,
            {"source_type": "skill", "producer": "test", "operation": "generate", "operatoin": "typo"},
            "$.operatoin",
        ),
        (ReviewDeclaration.from_dict, {"requred": True}, "$.requred"),
        (
            lambda value, path: AssetSpec.from_dict(value, path),
            {**_asset(), "source": {"uri": "x", "urii": "typo"}},
            "$.source.urii",
        ),
        (
            lambda value, path: GenerationSpec.from_dict(value, path),
            {"operation": "video.text_to_video", "prompt": "x", "requirements": {}, "promtp": "typo"},
            "$.promtp",
        ),
        (
            lambda value, path: GenerationSpec.from_dict(value, path),
            {"operation": "video.text_to_video", "prompt": "x", "requirements": {}, "negative_prompt": "typo"},
            "$.negative_prompt",
        ),
        (ClipSpec.from_dict, {**_clip(), "durtion_ms": 1000}, "$.durtion_ms"),
        (BindingPolicy.from_dict, {"placment": "any"}, "$.placment"),
        (
            ReferenceSpec.from_dict,
            {
                "reference_id": "r",
                "asset_key": "image",
                "semantic_usage": "subject",
                "binding": {},
                "bindnig": {},
            },
            "$.bindnig",
        ),
        (GenerationRequirements.from_dict, {"widht": 1920}, "$.widht"),
        (AudioPolicy.from_dict, {"native_audio": "preserve", "trakcs": []}, "$.trakcs"),
        (
            AudioTrackSpec.from_dict,
            {"asset_key": "audio", "role": "voice", "gain_dbb": "0"},
            "$.gain_dbb",
        ),
        (SubtitleCue.from_dict, {"start_ms": 0, "end_ms": 1, "text": "x", "txt": "typo"}, "$.txt"),
        (SubtitleSpec.from_dict, {"asset_ky": "subtitles"}, "$.asset_ky"),
        (OutputPolicy.from_dict, {"subtitles_mode": "none", "subtitles_mdoe": "none"}, "$.subtitles_mdoe"),
        (ApprovalDeclaration.from_dict, {"approved_byy": "user"}, "$.approved_byy"),
        (TimelineSegment.from_dict, {"clip_id": "clip", "clipid": "typo"}, "$.clipid"),
        (TimelineSpec.from_dict, {"segments": [], "segmnts": []}, "$.segmnts"),
    ],
)
def test_public_object_parsers_reject_unknown_fields(parser, data, path) -> None:
    with pytest.raises(ValueError, match=re.escape(f"{path}: unknown field")):
        parser(data, "$")


def test_nested_clip_typo_has_full_field_path() -> None:
    data = _package()
    data["clips"][0]["generation"]["requirements"]["widht"] = 1920

    with pytest.raises(ValueError, match=r"\$\.clips\[0\]\.generation\.requirements\.widht"):
        VideoExecutionPackage.from_dict(data)


def test_validate_package_reports_unknown_field_path() -> None:
    data = _package()
    data["project"]["project_idd"] = data["project"].pop("project_id")

    result = validate_package(data)

    assert not result.ok
    assert any(error.path == "$.project.project_idd" for error in result.errors())


def test_open_metadata_and_extension_maps_remain_opaque() -> None:
    data = _package()
    data["assets"][0]["metadata"] = {"arbitrary": {"nested": True}}
    data["clips"][0]["source_context"] = {"arbitrary": {"nested": True}}
    data["clips"][0]["extensions"] = {"arbitrary.namespace": {"nested": True}}
    data["extensions"] = {"arbitrary.namespace": {"nested": True}}

    package = VideoExecutionPackage.from_dict(data)

    assert package.assets[0].metadata["arbitrary"]["nested"] is True
    assert package.clips[0].source_context["arbitrary"]["nested"] is True
