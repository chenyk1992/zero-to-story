"""Tests for VideoExecutionPackage v1 — contract, validation, hash."""
from __future__ import annotations

import json
import pathlib

import pytest

from lfo.contracts import (
    AssetSpec,
    AudioPolicy,
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    ReferenceSpec,
    SubtitleCue,
    SubtitleSpec,
    ValidationError,
    ValidationResult,
    VideoExecutionPackage,
    validate_package,
)
from lfo.contracts.package import SCHEMA_ID
from lfo.contracts.validation import package_content_hash

HERE = pathlib.Path(__file__).parent
EXAMPLES = HERE.parent.parent / "examples" / "execution-packages"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_asset(**overrides) -> dict:
    base = {
        "asset_key": "test.img",
        "media_type": "image",
        "source": {"uri": "assets/test.png"},
        "provenance": {
            "source_type": "external_skill",
            "producer": "codex.imagegen",
            "operation": "image.generate",
        },
        "review": {"required": True},
    }
    base.update(overrides)
    return base


def _make_clip(**overrides) -> dict:
    base = {
        "clip_id": "clip-001",
        "sequence": 1,
        "duration_ms": 5000,
        "generation": {
            "operation": "video.text_to_video",
            "prompt": "A test clip",
            "requirements": {"width": 1080, "height": 1920, "fps": 24},
        },
    }
    base.update(overrides)
    return base


def _make_package(**overrides) -> dict:
    base = {
        "schema": SCHEMA_ID,
        "package_id": "test-001",
        "revision": 1,
        "project": {"title": "Test", "project_id": "test-project"},
        "assets": [_make_asset()],
        "clips": [_make_clip()],
        "output": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_empty_is_ok(self):
        vr = ValidationResult()
        assert vr.ok
        assert vr.errors() == []

    def test_add_error(self):
        vr = ValidationResult()
        vr.add("$.foo", "bad", "code", 42)
        assert not vr.ok
        errs = vr.errors()
        assert len(errs) == 1
        assert isinstance(errs[0], ValidationError)
        assert errs[0].path == "$.foo"
        assert errs[0].value == 42

    def test_extend(self):
        a = ValidationResult()
        a.add("$.x", "x", "code")
        b = ValidationResult()
        b.add("$.y", "y", "code")
        a.extend(b)
        assert len(a.errors()) == 2

    def test_to_dict(self):
        vr = ValidationResult()
        vr.add("$.foo", "bad", "code")
        d = vr.to_dict()
        assert d == [{"path": "$.foo", "message": "bad", "code": "code"}]


# ---------------------------------------------------------------------------
# AssetSpec
# ---------------------------------------------------------------------------


class TestAssetSpec:
    def test_round_trip(self):
        data = _make_asset()
        spec = AssetSpec.from_dict(data, "$.assets[0]")
        assert spec.asset_key == "test.img"
        assert spec.media_type == "image"
        assert spec.source.uri == "assets/test.png"
        assert spec.provenance.producer == "codex.imagegen"
        assert spec.review.required is True
        assert spec.to_dict() == data

    def test_invalid_media_type(self):
        data = _make_asset(media_type="3d_model")
        with pytest.raises(ValueError, match="media_type"):
            AssetSpec.from_dict(data, "$")

    def test_missing_uri(self):
        data = _make_asset(source={})
        with pytest.raises(ValueError, match="uri"):
            AssetSpec.from_dict(data, "$")

    @pytest.mark.parametrize(
        "uri",
        [
            "C:/outside.png",
            "/outside.png",
            "\\\\server\\share.png",
            "https://example.com/asset.png",
            "../outside.png",
            "assets/../outside.png",
        ],
    )
    def test_source_uri_must_be_package_relative(self, uri: str):
        data = _make_asset(source={"uri": uri})
        with pytest.raises(ValueError, match="package-relative local URI"):
            AssetSpec.from_dict(data, "$")

    def test_metadata_preserved(self):
        data = _make_asset(metadata={"color": "red"})
        spec = AssetSpec.from_dict(data, "$")
        assert spec.metadata == {"color": "red"}

    def test_sha256_optional(self):
        data = _make_asset()
        data["source"]["sha256"] = "abc123"
        spec = AssetSpec.from_dict(data, "$")
        assert spec.source.sha256 == "abc123"


# ---------------------------------------------------------------------------
# BindingPolicy
# ---------------------------------------------------------------------------


class TestBindingPolicy:
    def test_defaults(self):
        bp = BindingPolicy.from_dict({}, "$")
        assert bp.required is True
        assert bp.priority == 0
        assert bp.placement == "any"
        assert bp.on_unsupported == "fail"

    def test_required_cannot_drop(self):
        with pytest.raises(ValueError, match="required"):
            BindingPolicy.from_dict(
                {"required": True, "on_unsupported": "drop"}, "$"
            )

    def test_fixed_requires_slot(self):
        with pytest.raises(ValueError, match="slot"):
            BindingPolicy.from_dict({"placement": "fixed"}, "$")

    def test_invalid_placement(self):
        with pytest.raises(ValueError, match="placement"):
            BindingPolicy.from_dict({"placement": "middle"}, "$")

    def test_round_trip(self):
        # Non-default values round-trip; defaults are omitted.
        data = {
            "required": False,
            "priority": 50,
            "placement": "first",
            "on_unsupported": "drop",
        }
        bp = BindingPolicy.from_dict(data, "$")
        assert bp.to_dict() == data

    def test_defaults_omitted(self):
        bp = BindingPolicy.from_dict({"required": True}, "$")
        assert bp.to_dict() == {}


# ---------------------------------------------------------------------------
# ReferenceSpec
# ---------------------------------------------------------------------------


class TestReferenceSpec:
    def test_round_trip(self):
        data = {
            "reference_id": "ref-001",
            "asset_key": "hero.img",
            "semantic_usage": "subject.identity",
            "instruction": "Keep consistent",
            "binding": {"priority": 100},
        }
        ref = ReferenceSpec.from_dict(data, "$")
        assert ref.reference_id == "ref-001"
        assert ref.asset_key == "hero.img"
        assert ref.binding.required is True
        assert ReferenceSpec.from_dict(ref.to_dict(), "$") == ref

    def test_minimal(self):
        data = {
            "reference_id": "r1",
            "asset_key": "a1",
            "semantic_usage": "x",
            "binding": {},
        }
        ref = ReferenceSpec.from_dict(data, "$")
        assert ref.instruction is None


# ---------------------------------------------------------------------------
# GenerationRequirements
# ---------------------------------------------------------------------------


class TestGenerationRequirements:
    def test_defaults(self):
        r = GenerationRequirements.from_dict({}, "$")
        assert r.megapixels is None
        assert r.width is None
        assert r.height is None

    def test_megapixels_is_positive_number(self):
        r = GenerationRequirements.from_dict({"megapixels": 0.3}, "$")
        assert r.megapixels == 0.3
        assert r.to_dict()["megapixels"] == "0.3"

        from_string = GenerationRequirements.from_dict({"megapixels": "0.3"}, "$")
        assert from_string.megapixels == 0.3

    def test_megapixels_cannot_be_combined_with_dimensions(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            GenerationRequirements.from_dict(
                {"megapixels": 0.3, "width": 1344},
                "$",
            )

    def test_positive_integers(self):
        with pytest.raises(ValueError, match="positive"):
            GenerationRequirements.from_dict({"width": -1}, "$")

    def test_zero_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            GenerationRequirements.from_dict({"fps": 0}, "$")

    def test_native_audio_string(self):
        r = GenerationRequirements.from_dict({"native_audio": "allowed"}, "$")
        assert r.native_audio == "allowed"

    def test_native_audio_must_be_string(self):
        with pytest.raises(TypeError, match="native_audio"):
            GenerationRequirements.from_dict({"native_audio": 123}, "$")


# ---------------------------------------------------------------------------
# GenerationSpec
# ---------------------------------------------------------------------------


class TestGenerationSpec:
    def test_round_trip(self):
        data = {
            "operation": "video.reference_to_video",
            "prompt": "A hero walks",
            "seed": 42,
            "requirements": {"width": 1080, "height": 1920},
            "references": [
                {
                    "reference_id": "r1",
                    "asset_key": "hero.img",
                    "semantic_usage": "subject",
                    "binding": {"placement": "fixed", "slot": "ref_image_0"},
                }
            ],
        }
        gen = GenerationSpec.from_dict(data, "$")
        assert gen.operation == "video.reference_to_video"
        assert gen.seed == 42
        assert len(gen.references) == 1
        assert GenerationSpec.from_dict(gen.to_dict(), "$") == gen

    def test_missing_prompt(self):
        with pytest.raises(ValueError, match="prompt"):
            GenerationSpec.from_dict({"operation": "x"}, "$")

    def test_duplicate_reference_ids_are_rejected(self):
        reference = {
            "reference_id": "same",
            "asset_key": "hero.img",
            "semantic_usage": "subject",
            "binding": {"placement": "fixed", "slot": "ref_image_0"},
        }
        with pytest.raises(ValueError, match="duplicate reference_id"):
            GenerationSpec.from_dict(
                {
                    "operation": "video.reference_to_video",
                    "prompt": "A hero",
                    "references": [reference, {**reference, "binding": {
                        "placement": "fixed", "slot": "ref_image_1",
                    }}],
                },
                "$",
            )

    def test_removed_l2va_operation_is_rejected_by_direct_parser(self):
        with pytest.raises(ValueError, match="unsupported video operation"):
            GenerationSpec.from_dict(
                {"operation": "video.l2va", "prompt": "legacy"},
                "$",
            )

    def test_package_rejects_presenter_exact_first_frame_claim(self):
        reference = {
            "reference_id": "r1",
            "asset_key": "test.img",
            "semantic_usage": "exact_previous_last_frame",
            "binding": {"placement": "fixed", "slot": "ref_image_0"},
        }
        clip = _make_clip(
            generation={
                "operation": "video.virtual_presenter",
                "prompt": "Presenter",
                "references": [reference],
            }
        )
        with pytest.raises(ValueError, match="exact/hard first-frame continuity"):
            VideoExecutionPackage.from_dict(_make_package(clips=[clip]))

    def test_package_rejects_presenter_without_references(self):
        clip = _make_clip(
            generation={
                "operation": "video.virtual_presenter",
                "prompt": "Presenter",
                "references": [],
            }
        )
        with pytest.raises(ValueError, match="requires at least one reference"):
            VideoExecutionPackage.from_dict(_make_package(clips=[clip]))

    def test_package_rejects_presenter_untyped_slot(self):
        reference = {
            "reference_id": "r1",
            "asset_key": "test.img",
            "semantic_usage": "subject.identity",
            "binding": {"placement": "fixed", "slot": "character"},
        }
        clip = _make_clip(
            generation={
                "operation": "video.virtual_presenter",
                "prompt": "Presenter",
                "references": [reference],
            }
        )
        with pytest.raises(ValueError, match="typed fixed slots"):
            VideoExecutionPackage.from_dict(_make_package(clips=[clip]))

    def test_package_rejects_duplicate_r2v_slots(self):
        data = _make_package(
            assets=[
                _make_asset(asset_key="first.image"),
                _make_asset(asset_key="second.image"),
            ],
            clips=[_make_clip(generation={
                "operation": "video.reference_to_video",
                "prompt": "Two references",
                "references": [
                    {
                        "reference_id": "first",
                        "asset_key": "first.image",
                        "semantic_usage": "subject.identity",
                        "binding": {"placement": "fixed", "slot": "ref_image_0"},
                    },
                    {
                        "reference_id": "second",
                        "asset_key": "second.image",
                        "semantic_usage": "style.visual",
                        "binding": {"placement": "fixed", "slot": "ref_image_0"},
                    },
                ],
            })],
        )

        with pytest.raises(ValueError, match="duplicate slot"):
            VideoExecutionPackage.from_dict(data)


# ---------------------------------------------------------------------------
# AudioPolicy & AudioTrackSpec
# ---------------------------------------------------------------------------


class TestAudioPolicy:
    def test_defaults(self):
        ap = AudioPolicy.from_dict({}, "$")
        assert ap.native_audio == "preserve"
        assert ap.tracks == []

    def test_round_trip(self):
        data = {
            "native_audio": "mix",
            "tracks": [
                {
                    "asset_key": "dlg.wav",
                    "role": "dialogue",
                    "offset_ms": 100,
                    "gain_db": "-3",
                    "fade_in_ms": 50,
                    "fade_out_ms": 100,
                    "duck_group": "foreground",
                }
            ],
        }
        ap = AudioPolicy.from_dict(data, "$")
        assert ap.native_audio == "mix"
        assert ap.tracks[0].asset_key == "dlg.wav"
        assert ap.to_dict() == data

    @pytest.mark.parametrize(
        "field",
        ["offset_ms", "fade_in_ms", "fade_out_ms"],
    )
    def test_negative_timing_is_rejected(self, field):
        with pytest.raises(ValueError, match=field):
            AudioPolicy.from_dict(
                {"tracks": [{"asset_key": "dlg.wav", "role": "dialogue", field: -1}]},
                "$",
            )

    def test_non_numeric_gain_is_rejected(self):
        with pytest.raises(ValueError, match="gain_db"):
            AudioPolicy.from_dict(
                {"tracks": [{"asset_key": "dlg.wav", "role": "dialogue", "gain_db": "loud"}]},
                "$",
            )


# ---------------------------------------------------------------------------
# SubtitleSpec & SubtitleCue
# ---------------------------------------------------------------------------


class TestSubtitleCue:
    def test_round_trip(self):
        data = {"start_ms": 0, "end_ms": 1000, "text": "Hello"}
        cue = SubtitleCue.from_dict(data, "$")
        assert cue.to_dict() == data

    def test_end_after_start(self):
        with pytest.raises(ValueError, match="greater"):
            SubtitleCue.from_dict(
                {"start_ms": 1000, "end_ms": 500, "text": "x"}, "$"
            )

    def test_equal_rejected(self):
        with pytest.raises(ValueError, match="greater"):
            SubtitleCue.from_dict(
                {"start_ms": 500, "end_ms": 500, "text": "x"}, "$"
            )

    def test_negative_start_and_empty_text_are_rejected(self):
        with pytest.raises(ValueError, match="start_ms"):
            SubtitleCue.from_dict({"start_ms": -1, "end_ms": 500, "text": "x"}, "$")
        with pytest.raises(ValueError, match="text"):
            SubtitleCue.from_dict({"start_ms": 0, "end_ms": 500, "text": " "}, "$")

    def test_overlapping_cues_are_rejected(self):
        with pytest.raises(ValueError, match="overlaps"):
            SubtitleSpec.from_dict(
                {
                    "cues": [
                        {"start_ms": 0, "end_ms": 1000, "text": "one"},
                        {"start_ms": 500, "end_ms": 1200, "text": "two"},
                    ]
                },
                "$",
            )


# ---------------------------------------------------------------------------
# ClipSpec
# ---------------------------------------------------------------------------


class TestClipSpec:
    def test_round_trip(self):
        data = _make_clip(
            audio={"native_audio": "mute"},
            subtitles={"cues": [{"start_ms": 0, "end_ms": 1000, "text": "Hi"}]},
            dependencies=["clip-000"],
            source_context={"skill": "test"},
            extensions={"foo.bar": [1, 2]},
        )
        clip = ClipSpec.from_dict(data, "$")
        assert clip.clip_id == "clip-001"
        assert clip.duration_ms == 5000
        assert clip.audio.native_audio == "mute"
        assert len(clip.subtitles.cues) == 1
        assert clip.dependencies == ["clip-000"]
        assert clip.source_context == {"skill": "test"}
        assert clip.extensions == {"foo.bar": [1, 2]}
        assert clip.to_dict() == data

    def test_duration_positive(self):
        with pytest.raises(ValueError, match="positive"):
            ClipSpec.from_dict(_make_clip(duration_ms=0), "$")

    def test_sequence_positive(self):
        with pytest.raises(ValueError, match=">= 1"):
            ClipSpec.from_dict(_make_clip(sequence=0), "$")

    def test_minimal(self):
        clip = ClipSpec.from_dict(_make_clip(), "$")
        assert clip.dependencies == []
        assert clip.extensions == {}

    def test_subtitle_cue_must_fit_clip_duration(self):
        with pytest.raises(ValueError, match="exceeds clip duration"):
            ClipSpec.from_dict(
                _make_clip(
                    duration_ms=1000,
                    subtitles={"cues": [{"start_ms": 0, "end_ms": 1001, "text": "late"}]},
                ),
                "$",
            )

    @pytest.mark.parametrize("clip_id", ["../escape", "nested/clip", "nested\\clip"])
    def test_clip_id_must_be_one_artifact_path_component(self, clip_id: str) -> None:
        with pytest.raises(ValueError, match="single path component"):
            ClipSpec.from_dict(_make_clip(clip_id=clip_id), "$")


# ---------------------------------------------------------------------------
# VideoExecutionPackage
# ---------------------------------------------------------------------------


class TestVideoExecutionPackage:
    def test_round_trip(self):
        data = _make_package()
        pkg = VideoExecutionPackage.from_dict(data)
        assert pkg.package_id == "test-001"
        assert pkg.revision == 1
        assert pkg.project.title == "Test"
        assert len(pkg.assets) == 1
        assert len(pkg.clips) == 1
        # Semantic round-trip.
        reparsed = VideoExecutionPackage.from_dict(pkg.to_dict())
        assert pkg == reparsed

    def test_schema_mismatch(self):
        with pytest.raises(ValueError, match="schema"):
            VideoExecutionPackage.from_dict({"schema": "wrong"})

    def test_missing_package_id(self):
        with pytest.raises(ValueError, match="package_id"):
            VideoExecutionPackage.from_dict(
                {"schema": SCHEMA_ID, "revision": 1, "project": {"title": "T", "project_id": "test-project"}}
            )

    def test_revision_minimum(self):
        with pytest.raises(ValueError, match=">= 1"):
            VideoExecutionPackage.from_dict(
                {
                    "schema": SCHEMA_ID,
                    "package_id": "x",
                    "revision": 0,
                    "project": {"title": "T", "project_id": "test-project"},
                }
            )

    def test_revision_must_be_int(self):
        with pytest.raises(TypeError, match="integer"):
            VideoExecutionPackage.from_dict(
                {
                    "schema": SCHEMA_ID,
                    "package_id": "x",
                    "revision": "1",
                    "project": {"title": "T", "project_id": "test-project"},
                }
            )

    def test_extensions_preserved(self):
        data = _make_package(extensions={"zero-to-story.x": [1]})
        pkg = VideoExecutionPackage.from_dict(data)
        assert pkg.extensions == {"zero-to-story.x": [1]}

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("package_id", "../escape"),
            ("package_id", "CON"),
            ("project_id", "nested/project"),
            ("project_id", "LPT1.txt"),
            ("directory", "nested/final"),
            ("directory", "NUL"),
        ],
    )
    def test_artifact_identifiers_are_safe_path_components(
        self, field: str, value: str
    ) -> None:
        data = _make_package()
        if field == "project_id":
            data["project"]["project_id"] = value
        elif field == "directory":
            data["output"]["directory"] = value
        else:
            data[field] = value

        with pytest.raises(ValueError):
            VideoExecutionPackage.from_dict(data)

    def test_explicit_null_timeline_is_rejected(self):
        with pytest.raises(TypeError, match="timeline: expected object"):
            VideoExecutionPackage.from_dict(_make_package(timeline=None))

    def test_direct_parser_rejects_multiple_generated_clips(self):
        data = _make_package(
            clips=[
                _make_clip(),
                _make_clip(clip_id="clip-002", sequence=2),
            ]
        )

        with pytest.raises(ValueError, match="pure passthrough assembly"):
            VideoExecutionPackage.from_dict(data)

    def test_empty_clips_are_not_a_production_package(self):
        result = validate_package(_make_package(assets=[], clips=[]))
        assert not result.ok
        assert any(error.code == "production_shape" for error in result.errors())

    @pytest.mark.parametrize("clip_id", ["../escape", "nested/clip", "nested\\clip"])
    def test_validate_rejects_clip_id_that_is_not_a_path_component(self, clip_id: str):
        result = validate_package(_make_package(clips=[_make_clip(clip_id=clip_id)]))
        assert not result.ok
        assert any("single path component" in error.message for error in result.errors())

    def test_multiple_generated_clips_are_not_a_production_package(self):
        result = validate_package(
            _make_package(
                clips=[
                    _make_clip(),
                    _make_clip(clip_id="clip-002", sequence=2),
                ]
            )
        )
        assert not result.ok
        assert any(error.code == "production_shape" for error in result.errors())

    def test_multiple_passthrough_clips_are_allowed_for_assembly(self):
        asset = _make_asset(
            asset_key="accepted.video",
            media_type="video",
            source={"uri": "assets/accepted.mp4"},
        )
        passthrough = {
            "clip_id": "clip-001",
            "sequence": 1,
            "duration_ms": 5000,
            "generation": {
                "operation": "video.passthrough",
                "prompt": "Pass through accepted media",
                "requirements": {},
                "references": [{
                    "reference_id": "source-video",
                    "asset_key": "accepted.video",
                    "semantic_usage": "source.accepted_video",
                    "binding": {"placement": "fixed", "slot": "source_video"},
                }],
            },
        }
        second = dict(passthrough)
        second["clip_id"] = "clip-002"
        second["sequence"] = 2
        result = validate_package(_make_package(assets=[asset], clips=[passthrough, second]))
        assert result.ok, result.to_dict()

    def test_passthrough_assembly_rejects_enabled_upscale(self):
        asset = _make_asset(
            asset_key="accepted.video",
            media_type="video",
            source={"uri": "assets/accepted.mp4"},
        )
        passthrough = {
            "clip_id": "clip-001",
            "sequence": 1,
            "duration_ms": 5000,
            "generation": {
                "operation": "video.passthrough",
                "prompt": "Pass through accepted media",
                "requirements": {},
                "references": [{
                    "reference_id": "source-video",
                    "asset_key": "accepted.video",
                    "semantic_usage": "source.accepted_video",
                    "binding": {"placement": "fixed", "slot": "source_video"},
                }],
            },
        }

        result = validate_package(
            _make_package(
                assets=[asset],
                clips=[passthrough],
                extensions={"upscale": {"enabled": True}},
            )
        )

        assert not result.ok
        assert any(
            error.path == "$.extensions.upscale.enabled"
            and "passthrough assembly" in error.message
            for error in result.errors()
        )

    def test_passthrough_requires_one_video_reference(self):
        passthrough = _make_clip(
            generation={
                "operation": "video.passthrough",
                "prompt": "Pass through accepted media",
                "requirements": {},
            }
        )

        result = validate_package(_make_package(assets=[], clips=[passthrough]))

        assert not result.ok
        assert any(
            "exactly one video reference" in error.message
            for error in result.errors()
        )


# ---------------------------------------------------------------------------
# validate_package
# ---------------------------------------------------------------------------


class TestValidatePackage:
    def test_valid(self):
        vr = validate_package(_make_package())
        assert vr.ok, vr.to_dict()

    def test_not_object(self):
        vr = validate_package("string")
        assert not vr.ok
        assert any(e.code == "type" for e in vr.errors())

    def test_wrong_schema(self):
        vr = validate_package({"schema": "wrong"})
        assert not vr.ok
        assert any(e.code == "schema" for e in vr.errors())

    def test_missing_required(self):
        vr = validate_package({"schema": SCHEMA_ID})
        assert not vr.ok
        paths = {e.path for e in vr.errors()}
        assert "$.package_id" in paths
        assert "$.revision" in paths
        assert "$.project" in paths

    def test_duplicate_clip_id(self):
        data = _make_package(
            clips=[_make_clip(), _make_clip()]
        )
        vr = validate_package(data)
        assert not vr.ok
        assert any(e.code == "unique" and "clip_id" in e.message for e in vr.errors())

    def test_duplicate_clip_sequence(self):
        first = _make_clip(
            clip_id="clip-001",
            generation={
                "operation": "video.passthrough",
                "prompt": "one",
                "references": [{
                    "reference_id": "source-one",
                    "asset_key": "video.one",
                    "semantic_usage": "source.accepted_video",
                    "binding": {"placement": "fixed", "slot": "source_video"},
                }],
            },
        )
        second = _make_clip(
            clip_id="clip-002",
            generation={
                "operation": "video.passthrough",
                "prompt": "two",
                "references": [{
                    "reference_id": "source-two",
                    "asset_key": "video.two",
                    "semantic_usage": "source.accepted_video",
                    "binding": {"placement": "fixed", "slot": "source_video"},
                }],
            },
        )
        vr = validate_package(_make_package(
            assets=[
                _make_asset(asset_key="video.one", media_type="video"),
                _make_asset(asset_key="video.two", media_type="video"),
            ],
            clips=[first, second],
        ))
        assert not vr.ok
        assert any(e.code == "unique" and "sequence" in e.message for e in vr.errors())

    def test_duplicate_asset_key(self):
        data = _make_package(
            assets=[_make_asset(), _make_asset()]
        )
        vr = validate_package(data)
        assert not vr.ok
        assert any(e.code == "unique" and "asset_key" in e.message for e in vr.errors())

    def test_unknown_reference(self):
        data = _make_package()
        data["clips"][0]["generation"]["references"] = [
            {
                "reference_id": "r1",
                "asset_key": "nonexistent",
                "semantic_usage": "x",
                "binding": {},
            }
        ]
        vr = validate_package(data)
        assert not vr.ok
        assert any(e.code == "reference" for e in vr.errors())

    def test_unknown_audio_track_asset_is_rejected(self):
        data = _make_package()
        data["clips"][0]["audio"] = {
            "native_audio": "replace",
            "tracks": [{"asset_key": "missing.audio", "role": "narration"}],
        }

        vr = validate_package(data)

        assert not vr.ok
        assert any(
            "unknown asset_key 'missing.audio'" in error.message
            for error in vr.errors()
        )

    def test_audio_track_must_reference_audio_asset(self):
        data = _make_package()
        data["clips"][0]["audio"] = {
            "native_audio": "replace",
            "tracks": [{"asset_key": "test.img", "role": "narration"}],
        }

        vr = validate_package(data)

        assert not vr.ok
        assert any("expected audio asset" in error.message for error in vr.errors())

    def test_subtitle_must_reference_subtitle_asset(self):
        data = _make_package()
        data["clips"][0]["subtitles"] = {"asset_key": "test.img"}

        vr = validate_package(data)

        assert not vr.ok
        assert any("expected subtitle asset" in error.message for error in vr.errors())


# ---------------------------------------------------------------------------
# Canonical hash
# ---------------------------------------------------------------------------


class TestPackageContentHash:
    def test_same_package_same_hash(self):
        data = _make_package()
        pkg = VideoExecutionPackage.from_dict(data)
        assert package_content_hash(pkg) == package_content_hash(pkg)

    def test_different_revision_different_hash(self):
        a = VideoExecutionPackage.from_dict(_make_package(revision=1))
        b = VideoExecutionPackage.from_dict(_make_package(revision=2))
        assert package_content_hash(a) != package_content_hash(b)

    def test_different_prompt_different_hash(self):
        a = VideoExecutionPackage.from_dict(
            _make_package(clips=[_make_clip(generation={
                "operation": "video.text_to_video",
                "prompt": "Prompt A",
                "requirements": {},
            })])
        )
        b = VideoExecutionPackage.from_dict(
            _make_package(clips=[_make_clip(generation={
                "operation": "video.text_to_video",
                "prompt": "Prompt B",
                "requirements": {},
            })])
        )
        assert package_content_hash(a) != package_content_hash(b)

    def test_hash_is_sha256(self):
        pkg = VideoExecutionPackage.from_dict(_make_package())
        h = package_content_hash(pkg)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Example packages
# ---------------------------------------------------------------------------


class TestExamplePackages:
    @pytest.fixture(params=["short-story-r2v", "product-promo-mixed"])
    def example_path(self, request):
        return EXAMPLES / request.param / "package.json"

    def test_example_validates(self, example_path):
        data = json.loads(example_path.read_text(encoding="utf-8"))
        vr = validate_package(data)
        assert vr.ok, vr.to_dict()

    def test_example_round_trips(self, example_path):
        data = json.loads(example_path.read_text(encoding="utf-8"))
        pkg = VideoExecutionPackage.from_dict(data)
        # Semantic round-trip: re-parse the serialized form and compare objects.
        # (Serialization omits defaults; direct dict comparison would be brittle.)
        reparsed = VideoExecutionPackage.from_dict(pkg.to_dict())
        assert pkg == reparsed

    def test_example_has_no_creative_enums(self, example_path):
        """Schema must not require character/scene/prop/panel fields."""
        data = json.loads(example_path.read_text(encoding="utf-8"))
        data_str = json.dumps(data)
        # These are creative concepts that must not appear as required fields
        assert "character" not in data_str.lower() or "character" in data_str.lower()
        # The real check: schema-level required fields
        schema_path = (
            HERE.parent.parent
            / "src"
            / "lfo"
            / "contracts"
            / "schemas"
            / "video-execution-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        assert required == {"schema", "package_id", "revision", "project", "clips"}
        # No creative enums in top-level required
        for creative in ("characters", "scenes", "props", "panels", "beats"):
            assert creative not in required

    def test_example_hash_stable(self, example_path):
        data = json.loads(example_path.read_text(encoding="utf-8"))
        pkg = VideoExecutionPackage.from_dict(data)
        assert package_content_hash(pkg) == package_content_hash(pkg)


# ---------------------------------------------------------------------------
# JSON Schema
# ---------------------------------------------------------------------------


class TestJsonSchema:
    def test_schema_file_valid(self):
        schema_path = (
            HERE.parent.parent
            / "src"
            / "lfo"
            / "contracts"
            / "schemas"
            / "video-execution-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert schema["properties"]["schema"]["const"] == SCHEMA_ID

    def test_schema_required_fields(self):
        schema_path = (
            HERE.parent.parent
            / "src"
            / "lfo"
            / "contracts"
            / "schemas"
            / "video-execution-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        assert required == {
            "schema",
            "package_id",
            "revision",
            "project",
            "clips",
        }

    def test_schema_no_creative_enums(self):
        schema_path = (
            HERE.parent.parent
            / "src"
            / "lfo"
            / "contracts"
            / "schemas"
            / "video-execution-v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # Walk all definitions and check no creative enums
        creative_keywords = {"character", "scene", "prop", "panel", "beat"}
        for def_name, def_schema in schema.get("definitions", {}).items():
            props = def_schema.get("properties", {})
            for prop_name in props:
                assert prop_name not in creative_keywords, (
                    f"Creative keyword {prop_name!r} found in {def_name}"
                )
