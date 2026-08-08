"""Tests for the decompose output schema validation.

These tests cover the LLM output validator independently of any LLM call.
The validator must catch every category of malformed response.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.storyboard.decompose_schema import (
    CAMERA_ANGLES,
    CAMERA_MOVEMENTS,
    CAMERA_SHOT_SIZES,
    DecomposeSchemaError,
    collect_warnings,
    parse_llm_output,
    validate_llm_payload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "decompose_responses"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _valid_minimal_shot(shot_id: str = "shot_001_t2v", scene_id: str = "scene_supermarket") -> dict:
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "description": "陈默踹翻洗发水货架",
        "desired_duration_ms": 5000,
        "camera": {"shot_size": "wide", "angle": "eye_level", "movement": "static"},
        "characters": [],
        "action_beats": [],
        "continuity": {
            "previous_shot_id": None,
            "next_shot_id": None,
            "start_frame_needed": False,
        },
        "generation_hint": {"preferred_family": "h3_fl2va", "preferred_mode": "t2va"},
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestValidPayloads:
    def test_chenmo_3shot_fixture(self):
        """A full 2-shot payload with continuity must validate."""
        data = _load("chenmo_3shot.json")
        payload = validate_llm_payload(data)
        assert len(payload.new_scenes) == 1
        assert len(payload.new_props) == 1
        assert len(payload.new_shots) == 2
        assert payload.new_shots[0]["shot_id"] == "shot_001_t2v"
        assert payload.new_shots[1]["shot_id"] == "shot_002_i2v"

    def test_minimal_single_shot(self):
        """One-shot minimal payload with just the required fields."""
        data = {"shots": [_valid_minimal_shot()]}
        payload = validate_llm_payload(data)
        assert len(payload.new_shots) == 1
        assert payload.new_scenes == []
        assert payload.new_props == []

    def test_samurai_short_payload(self):
        """A 1-shot payload (no continuity chain) is valid."""
        data = _load("samurai_3shot.json")
        payload = validate_llm_payload(data)
        assert len(payload.new_shots) == 1
        assert payload.new_shots[0]["continuity"]["next_shot_id"] is None


# ---------------------------------------------------------------------------
# Top-level structural errors
# ---------------------------------------------------------------------------


class TestTopLevelErrors:
    def test_not_a_dict(self):
        with pytest.raises(DecomposeSchemaError, match="must be a JSON object"):
            validate_llm_payload([1, 2, 3])

    def test_missing_shots(self):
        with pytest.raises(DecomposeSchemaError, match="missing required field: shots"):
            validate_llm_payload({"scenes": []})

    def test_empty_shots(self):
        with pytest.raises(DecomposeSchemaError, match="empty shots"):
            validate_llm_payload({"shots": []})

    def test_shots_not_a_list(self):
        with pytest.raises(DecomposeSchemaError, match="/shots"):
            validate_llm_payload({"shots": "not a list"})

    def test_scenes_not_a_list(self):
        with pytest.raises(DecomposeSchemaError, match="/scenes"):
            validate_llm_payload({"scenes": "oops", "shots": [_valid_minimal_shot()]})


# ---------------------------------------------------------------------------
# Shot field errors
# ---------------------------------------------------------------------------


class TestShotErrors:
    def test_missing_shot_id(self):
        shot = _valid_minimal_shot()
        del shot["shot_id"]
        with pytest.raises(DecomposeSchemaError, match="shot_id"):
            validate_llm_payload({"shots": [shot]})

    def test_bad_shot_id_format(self):
        shot = _valid_minimal_shot(shot_id="123 bad id with spaces")
        with pytest.raises(DecomposeSchemaError, match="shot_id"):
            validate_llm_payload({"shots": [shot]})

    def test_missing_description(self):
        shot = _valid_minimal_shot()
        del shot["description"]
        with pytest.raises(DecomposeSchemaError, match="description"):
            validate_llm_payload({"shots": [shot]})

    def test_empty_description(self):
        shot = _valid_minimal_shot()
        shot["description"] = ""
        with pytest.raises(DecomposeSchemaError, match="description"):
            validate_llm_payload({"shots": [shot]})

    def test_missing_duration(self):
        shot = _valid_minimal_shot()
        del shot["desired_duration_ms"]
        with pytest.raises(DecomposeSchemaError, match="desired_duration_ms"):
            validate_llm_payload({"shots": [shot]})

    def test_negative_duration(self):
        shot = _valid_minimal_shot()
        shot["desired_duration_ms"] = -1
        with pytest.raises(DecomposeSchemaError, match="desired_duration_ms"):
            validate_llm_payload({"shots": [shot]})

    def test_non_int_duration(self):
        shot = _valid_minimal_shot()
        shot["desired_duration_ms"] = "5000"
        with pytest.raises(DecomposeSchemaError, match="desired_duration_ms"):
            validate_llm_payload({"shots": [shot]})


# ---------------------------------------------------------------------------
# Camera errors
# ---------------------------------------------------------------------------


class TestCameraErrors:
    def test_bad_shot_size(self):
        shot = _valid_minimal_shot()
        shot["camera"]["shot_size"] = "tiny"
        with pytest.raises(DecomposeSchemaError, match="shot_size"):
            validate_llm_payload({"shots": [shot]})

    def test_bad_angle(self):
        shot = _valid_minimal_shot()
        shot["camera"]["angle"] = "sideways"
        with pytest.raises(DecomposeSchemaError, match="angle"):
            validate_llm_payload({"shots": [shot]})

    def test_bad_movement(self):
        shot = _valid_minimal_shot()
        shot["camera"]["movement"] = "drone"
        with pytest.raises(DecomposeSchemaError, match="movement"):
            validate_llm_payload({"shots": [shot]})


# ---------------------------------------------------------------------------
# Continuity / cross-shot errors
# ---------------------------------------------------------------------------


class TestContinuityErrors:
    def test_first_shot_cannot_need_start_frame(self):
        # Two-shot setup so previous_shot_id lookup passes; only the "first
        # shot cannot have start_frame_needed" rule should fire.
        s1 = _valid_minimal_shot("shot_001_t2v")
        s1["continuity"]["previous_shot_id"] = "shot_002_i2v"  # points to s2; passes lookup
        s1["continuity"]["start_frame_needed"] = True  # but first shot — invalid
        s2 = _valid_minimal_shot("shot_002_i2v")
        s2["continuity"]["previous_shot_id"] = "shot_001_t2v"
        s2["continuity"]["start_frame_needed"] = False
        with pytest.raises(DecomposeSchemaError, match="first shot cannot"):
            validate_llm_payload({"shots": [s1, s2]})

    def test_start_frame_needed_requires_previous(self):
        s1 = _valid_minimal_shot("shot_001_t2v")
        s2 = _valid_minimal_shot("shot_002_i2v")
        s2["continuity"]["start_frame_needed"] = True
        # Intentionally omit previous_shot_id
        s2["continuity"].pop("previous_shot_id", None)
        with pytest.raises(DecomposeSchemaError, match="requires previous_shot_id"):
            validate_llm_payload({"shots": [s1, s2]})

    def test_duplicate_shot_ids(self):
        s1 = _valid_minimal_shot("shot_001_t2v")
        s2 = _valid_minimal_shot("shot_001_t2v")  # same id!
        s2["scene_id"] = "scene_other"
        with pytest.raises(DecomposeSchemaError, match="duplicate shot_ids"):
            validate_llm_payload({"shots": [s1, s2]})

    def test_previous_shot_id_not_in_payload(self):
        s1 = _valid_minimal_shot("shot_001_t2v")
        s2 = _valid_minimal_shot("shot_002_i2v")
        s2["continuity"]["previous_shot_id"] = "shot_999_t2v"  # doesn't exist
        s2["continuity"]["start_frame_needed"] = False
        with pytest.raises(DecomposeSchemaError, match="not in this payload"):
            validate_llm_payload({"shots": [s1, s2]})


# ---------------------------------------------------------------------------
# parse_llm_output
# ---------------------------------------------------------------------------


class TestParseOutput:
    def test_plain_json(self):
        data = parse_llm_output('{"shots": []}')
        assert data == {"shots": []}

    def test_json_with_markdown_fence(self):
        text = '```json\n{"shots": []}\n```'
        data = parse_llm_output(text)
        assert data == {"shots": []}

    def test_json_with_preamble(self):
        text = 'Here is my response:\n{"shots": []}\nDone.'
        data = parse_llm_output(text)
        assert data == {"shots": []}

    def test_no_json_object_raises(self):
        with pytest.raises(DecomposeSchemaError, match="no JSON object"):
            parse_llm_output("Sorry I cannot help with that.")

    def test_invalid_json_raises(self):
        # Balanced braces but malformed content
        with pytest.raises(DecomposeSchemaError, match="not valid JSON"):
            parse_llm_output('{"key": , "broken": true}')

    def test_empty_string_raises(self):
        with pytest.raises(DecomposeSchemaError, match="no JSON object"):
            parse_llm_output("")


# ---------------------------------------------------------------------------
# Allowed values surface (sanity check)
# ---------------------------------------------------------------------------


class TestAllowedValues:
    def test_camera_movements_contains_expected(self):
        assert "slow_push_in" in CAMERA_MOVEMENTS
        assert "slow_pull_out" in CAMERA_MOVEMENTS
        assert "static" in CAMERA_MOVEMENTS

    def test_camera_angles_contains_expected(self):
        assert "eye_level" in CAMERA_ANGLES
        assert "low" in CAMERA_ANGLES
        assert "high" in CAMERA_ANGLES

    def test_camera_sizes_contains_expected(self):
        assert "extreme_wide" in CAMERA_SHOT_SIZES
        assert "extreme_close_up" in CAMERA_SHOT_SIZES


# ---------------------------------------------------------------------------
# Spatial relationship soft validation (warnings, not errors)
# ---------------------------------------------------------------------------


class TestSpatialWarnings:
    """collect_warnings() flags shots missing spatial relationship keywords."""

    def test_spatial_description_no_warning(self):
        """Description with spatial keywords → no warning."""
        data = {
            "shots": [
                {
                    "shot_id": "shot_001_t2v",
                    "scene_id": "scene_test",
                    "description": "陈默站在超市中央货架旁(中景偏左)，面对镜头",
                    "desired_duration_ms": 5000,
                    "continuity": {"start_frame_needed": False},
                }
            ]
        }
        warnings = collect_warnings(data)
        assert warnings == []

    def test_missing_spatial_description_warns(self):
        """Description without spatial keywords → warning."""
        data = {
            "shots": [
                {
                    "shot_id": "shot_001_t2v",
                    "scene_id": "scene_test",
                    "description": "陈默在超市里",
                    "desired_duration_ms": 5000,
                    "continuity": {"start_frame_needed": False},
                }
            ]
        }
        warnings = collect_warnings(data)
        assert len(warnings) == 1
        assert "no spatial relationship keywords" in warnings[0]

    def test_multiple_shots_mixed(self):
        """Only shots missing spatial keywords get warned."""
        data = {
            "shots": [
                {
                    "shot_id": "shot_001_t2v",
                    "scene_id": "scene_test",
                    "description": "陈默站在超市中央货架旁(中景偏左)",
                    "desired_duration_ms": 5000,
                    "continuity": {"start_frame_needed": False},
                },
                {
                    "shot_id": "shot_002_i2v",
                    "scene_id": "scene_test",
                    "description": "丧尸倒地",  # no spatial keywords
                    "desired_duration_ms": 3000,
                    "continuity": {
                        "start_frame_needed": True,
                        "previous_shot_id": "shot_001_t2v",
                    },
                },
            ]
        }
        warnings = collect_warnings(data)
        assert len(warnings) == 1
        assert "/shots/1/description" in warnings[0]

    def test_empty_description_no_warning(self):
        """Empty description → no spatial warning (the field is required elsewhere)."""
        data = {
            "shots": [
                {
                    "shot_id": "shot_001_t2v",
                    "scene_id": "scene_test",
                    "description": "",
                    "desired_duration_ms": 5000,
                    "continuity": {"start_frame_needed": False},
                }
            ]
        }
        warnings = collect_warnings(data)
        assert warnings == []

    def test_non_dict_input_no_crash(self):
        """Non-dict input returns empty warnings, no crash."""
        assert collect_warnings(None) == []
        assert collect_warnings("string") == []
        assert collect_warnings([1, 2, 3]) == []

    def test_chinese_spatial_keywords_recognized(self):
        """Chinese spatial keywords are recognized."""
        for kw in ["前景", "中景", "远景", "左", "右", "中央", "旁", "远", "近"]:
            data = {
                "shots": [
                    {
                        "shot_id": "shot_001_t2v",
                        "scene_id": "scene_test",
                        "description": f"画面{kw}角",
                        "desired_duration_ms": 5000,
                        "continuity": {"start_frame_needed": False},
                    }
                ]
            }
            assert collect_warnings(data) == [], f"Keyword '{kw}' should be recognized"
