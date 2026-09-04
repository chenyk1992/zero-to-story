"""Lightweight structural checks for the public execution-package schema.

The runtime intentionally does not depend on a JSON Schema implementation.
These checks keep the machine-readable schema aligned with the Python
contract parsers and the current single-Panel/assembly boundary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "lfo"
    / "contracts"
    / "schemas"
    / "video-execution-v1.schema.json"
)


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _definition(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return schema["definitions"][name]


def test_schema_required_fields_and_defaults_match_contract() -> None:
    schema = _schema()

    # ``validate_package`` requires a non-empty clips list for production, but
    # assets and output are filled by VideoExecutionPackage.from_dict when
    # omitted. Optional nested parser fields must not become accidentally
    # required merely because they have defaults.
    assert set(schema["required"]) == {
        "schema",
        "package_id",
        "revision",
        "project",
        "clips",
    }
    assert set(_definition(schema, "AssetSpec")["required"]) == {
        "asset_key",
        "media_type",
        "source",
        "provenance",
    }
    assert _definition(schema, "AssetSpec")["properties"]["review"]["default"] == {
        "required": True
    }
    assert _definition(schema, "ReviewDeclaration")["properties"]["required"]["default"] is True

    binding = _definition(schema, "BindingPolicy")
    assert "required" not in binding
    assert binding["properties"]["required"]["default"] is True
    assert binding["properties"]["priority"]["default"] == 0
    assert binding["properties"]["placement"]["default"] == "any"
    assert binding["properties"]["on_unsupported"]["default"] == "fail"
    assert binding["properties"]["slot"]["type"] == ["string", "null"]
    assert len(binding["allOf"]) == 2
    assert binding["allOf"][0]["then"]["required"] == ["slot"]
    assert binding["allOf"][1]["then"]["properties"]["required"]["const"] is False

    generation = _definition(schema, "GenerationSpec")
    assert set(generation["required"]) == {"operation", "prompt"}
    assert "negative_prompt" not in generation["properties"]
    assert generation["properties"]["requirements"]["default"] == {}
    assert generation["properties"]["references"]["default"] == []


def test_schema_nullable_fields_and_open_maps_follow_parsers() -> None:
    schema = _schema()

    assert _definition(schema, "ProjectInfo")["properties"]["locale"]["type"] == [
        "string",
        "null",
    ]
    assert _definition(schema, "AssetSource")["properties"]["sha256"]["type"] == [
        "string",
        "null",
    ]
    assert _definition(schema, "ReferenceSpec")["properties"]["instruction"]["type"] == [
        "string",
        "null",
    ]
    assert _definition(schema, "AudioTrackSpec")["properties"]["duck_group"]["type"] == [
        "string",
        "null",
    ]
    assert _definition(schema, "AudioTrackSpec")["properties"]["offset_ms"]["minimum"] == 0
    assert _definition(schema, "AudioTrackSpec")["properties"]["fade_in_ms"]["minimum"] == 0
    assert _definition(schema, "AudioTrackSpec")["properties"]["fade_out_ms"]["minimum"] == 0
    assert _definition(schema, "SubtitleSpec")["properties"]["asset_key"]["type"] == [
        "string",
        "null",
    ]
    directory = _definition(schema, "OutputPolicy")["properties"]["directory"]
    assert directory["anyOf"][1] == {"type": "null"}
    assert directory["anyOf"][0]["$ref"] == "#/definitions/SafePathComponent"

    assert _definition(schema, "AssetSpec")["properties"]["metadata"][
        "additionalProperties"
    ]
    assert _definition(schema, "ClipSpec")["properties"]["source_context"][
        "additionalProperties"
    ]
    assert schema["properties"]["extensions"]["additionalProperties"]
    assert _definition(schema, "ClipSpec")["properties"]["extensions"][
        "additionalProperties"
    ]

    timeline = _definition(schema, "TimelineSpec")
    assert timeline["required"] == ["segments"]
    segment = _definition(schema, "TimelineSegment")["properties"]
    assert segment["source_in_ms"]["default"] == 0
    assert segment["source_out_ms"]["type"] == ["integer", "null"]
    assert segment["source_out_ms"]["default"] is None

    cue = _definition(schema, "SubtitleCue")["properties"]
    assert cue["start_ms"]["minimum"] == 0


def test_schema_models_single_panel_and_passthrough_assembly_shapes() -> None:
    schema = _schema()
    clips = schema["properties"]["clips"]

    assert clips["minItems"] == 1
    assert len(clips["oneOf"]) == 2
    assert clips["oneOf"][0]["maxItems"] == 1
    assembly = clips["oneOf"][1]
    assert assembly["minItems"] == 2
    operation = assembly["items"]["allOf"][1]["properties"]["generation"][
        "properties"
    ]["operation"]
    assert operation["const"] == "video.passthrough"


def test_schema_clip_id_is_a_single_path_component() -> None:
    schema = _schema()
    clip_id = _definition(schema, "ClipSpec")["properties"]["clip_id"]
    component = _definition(schema, "SafePathComponent")

    assert clip_id["$ref"] == "#/definitions/SafePathComponent"
    assert schema["properties"]["package_id"]["$ref"] == (
        "#/definitions/SafePathComponent"
    )
    assert _definition(schema, "ProjectInfo")["properties"]["project_id"][
        "$ref"
    ] == "#/definitions/SafePathComponent"
    assert _definition(schema, "TimelineSegment")["properties"]["clip_id"][
        "$ref"
    ] == "#/definitions/SafePathComponent"

    pattern = re.compile(component["pattern"])
    for value in ("clip-001", "故事面板", "panel.one"):
        assert pattern.fullmatch(value)
    for value in (
        "",
        " ",
        ".",
        "..",
        "nested/clip",
        "nested\\clip",
        "C:drive",
        "clip.",
        "clip ",
        "CON",
        "con.preview",
        "LPT9",
    ):
        assert pattern.fullmatch(value) is None


def test_schema_asset_uri_is_package_relative() -> None:
    schema = _schema()
    uri = _definition(schema, "AssetSource")["properties"]["uri"]
    assert uri["$ref"] == "#/definitions/PackageRelativeUri"

    pattern = re.compile(_definition(schema, "PackageRelativeUri")["pattern"])
    for value in ("assets/hero.png", "assets\\hero.png", "hero.png"):
        assert pattern.fullmatch(value)
    for value in (
        "C:/outside.png",
        "/outside.png",
        "\\\\server\\share.png",
        "https://example.com/hero.png",
        "../outside.png",
        "assets/../outside.png",
    ):
        assert pattern.fullmatch(value) is None


def test_schema_megapixels_matches_positive_numeric_contract() -> None:
    schema = _schema()
    variants = _definition(schema, "GenerationRequirements")["properties"][
        "megapixels"
    ]["anyOf"]
    number, string, nullable = variants

    assert number["exclusiveMinimum"] == 0
    assert nullable == {"type": "null"}
    pattern = re.compile(string["pattern"])
    for value in ("0.4", "1", "+1.5", "1e-3"):
        assert pattern.fullmatch(value)
    for value in ("0", "0.0", "-1", "abc", "nan", "inf"):
        assert pattern.fullmatch(value) is None


def test_schema_declares_strict_upscale_extension() -> None:
    schema = _schema()
    upscale = _definition(schema, "UpscaleOptions")

    assert upscale["additionalProperties"] is False
    assert set(upscale["properties"]) == {"enabled", "scale_multiplier", "seed"}
    assert "segment_seconds" not in upscale["properties"]
    assert upscale["properties"]["enabled"]["default"] is False
    assert upscale["properties"]["scale_multiplier"]["default"] == 2.0
    assert upscale["properties"]["seed"]["type"] == ["integer", "null"]
    assert upscale["properties"]["seed"]["minimum"] == 0
    assert upscale["properties"]["seed"]["maximum"] == 2**64 - 1

    assert "upscale" in schema["properties"]["extensions"]["properties"]
    assert "upscale" in _definition(schema, "ClipSpec")["properties"]["extensions"][
        "properties"
    ]
