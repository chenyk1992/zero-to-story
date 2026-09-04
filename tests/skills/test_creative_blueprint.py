"""Tests for the zero-to-story creative preflight contract."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_PATH = (
    Path(__file__).parents[2]
    / ".agents"
    / "skills"
    / "zero-to-story"
    / "scripts"
    / "validate_creative_blueprint.py"
)
SPEC = importlib.util.spec_from_file_location("creative_blueprint_validator", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _valid_blueprint() -> dict[str, Any]:
    return {
        "schema": "zero-to-story.creative-blueprint.v1",
        "project": {"title": "A complete scene", "scope": "episode 1", "target_duration_s": 14},
        "source": {
            "canonical": "episodes/ep001.md",
            "conflicts": [
                {
                    "id": "SRC-001",
                    "question": "Which prop is handed over?",
                    "resolution": "Use the brush from the canonical episode.",
                    "status": "resolved",
                }
            ],
        },
        "scenes": [
            {
                "id": "S001",
                "order": 1,
                "purpose": "Establish the promise.",
                "turn": "The teacher makes a decision.",
                "next_obligation": "The student must leave with the brush.",
                "location": "Study, late afternoon",
                "cast": ["teacher", "student"],
                "entry_state": {"brush": "on_desk"},
                "exit_state": {"brush": "in_teacher_hand"},
                "bridge_from_previous": None,
            },
            {
                "id": "S002",
                "order": 2,
                "purpose": "Complete the handoff.",
                "turn": "The student receives the brush.",
                "next_obligation": "The student must act on the advice.",
                "location": "Courtyard, dusk",
                "cast": ["teacher", "student"],
                "entry_state": {"brush": "in_teacher_hand"},
                "exit_state": {"brush": "in_student_hand"},
                "bridge_from_previous": {
                    "type": "causal_time",
                    "description": "The teacher walks the student into the courtyard as dusk falls.",
                },
            },
        ],
        "panels": [
            {
                "id": "P001",
                "order": 1,
                "scene_id": "S001",
                "duration_s": 8,
                "shot_ids": ["C001"],
                "coverage_ids": ["EV001"],
                "entry_state": {"brush": "on_desk"},
                "exit_state": {"brush": "in_teacher_hand"},
                "transition_to_next": {
                    "ownership": "next",
                    "bridge": "The completed brush pickup motivates the walk outside.",
                },
            },
            {
                "id": "P002",
                "order": 2,
                "scene_id": "S002",
                "duration_s": 6,
                "shot_ids": ["C002"],
                "coverage_ids": ["EV002"],
                "entry_state": {"brush": "in_teacher_hand"},
                "exit_state": {"brush": "in_student_hand"},
                "transition_to_next": None,
            },
        ],
        "coverage": [
            {
                "id": "EV001",
                "order": 1,
                "priority": "must_show",
                "source_refs": ["ep001.md:L10-L18"],
                "event": "The teacher picks up the brush.",
                "visible_proof": "The brush leaves the desk and is visibly held by the teacher.",
                "before_state": {"brush": "on_desk"},
                "after_state": {"brush": "in_teacher_hand"},
                "scene_id": "S001",
                "panel_id": "P001",
                "shot_id": "C001",
            },
            {
                "id": "EV002",
                "order": 2,
                "priority": "must_explain",
                "source_refs": ["ep001.md:L19-L28"],
                "event": "The teacher hands the brush to the student.",
                "visible_proof": "Both hands meet, the teacher releases, and the student settles the brush.",
                "before_state": {"brush": "in_teacher_hand"},
                "after_state": {"brush": "in_student_hand"},
                "scene_id": "S002",
                "panel_id": "P002",
                "shot_id": "C002",
            },
        ],
        "dialogue": [
            {
                "id": "D001",
                "order": 1,
                "speaker": "teacher",
                "text": "Take this.",
                "coverage_id": "EV001",
                "shot_id": "C001",
            },
            {
                "id": "D002",
                "order": 2,
                "speaker": "student",
                "text": "I will.",
                "coverage_id": "EV002",
                "shot_id": "C002",
            },
        ],
        "generation": {
            "limits": {
                "reference_slots": 3,
                "max_critical_characters": 2,
                "max_actions": 1,
                "max_camera_moves": 1,
                "max_dialogue_lines": 2,
            },
            "shots": [
                {
                    "id": "C001",
                    "order": 1,
                    "scene_id": "S001",
                    "panel_id": "P001",
                    "coverage_ids": ["EV001"],
                    "dialogue_ids": ["D001"],
                    "critical_characters": ["teacher"],
                    "reference_keys": ["character.teacher", "scene.S001.master"],
                    "actions": ["pick up the brush"],
                    "camera_moves": ["dolly in"],
                    "purpose": "Make the decision visible.",
                    "state_before": {"brush": "on_desk"},
                    "state_after": {"brush": "in_teacher_hand"},
                    "text_strategy": "none",
                    "post_asset": None,
                },
                {
                    "id": "C002",
                    "order": 2,
                    "scene_id": "S002",
                    "panel_id": "P002",
                    "coverage_ids": ["EV002"],
                    "dialogue_ids": ["D002"],
                    "critical_characters": ["teacher", "student"],
                    "reference_keys": ["character.teacher", "character.student", "scene.S002.master"],
                    "actions": ["hand over the brush"],
                    "camera_moves": ["fixed"],
                    "purpose": "Make the handoff undeniable.",
                    "state_before": {"brush": "in_teacher_hand"},
                    "state_after": {"brush": "in_student_hand"},
                    "text_strategy": "none",
                    "post_asset": None,
                },
            ],
        },
    }


def test_valid_blueprint_passes() -> None:
    assert MODULE.validate_blueprint(_valid_blueprint()) == []


def test_source_conflict_and_missing_mandatory_coverage_are_reported() -> None:
    blueprint = _valid_blueprint()
    blueprint["source"]["conflicts"][0]["status"] = "unresolved"
    blueprint["generation"]["shots"][0]["coverage_ids"] = []

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "source.conflicts[0].status" in messages
    assert "coverage[EV001]" in messages


def test_state_break_and_generation_budget_are_reported() -> None:
    blueprint = _valid_blueprint()
    shot = blueprint["generation"]["shots"][1]
    shot["state_before"] = {"brush": "on_desk"}
    shot["reference_keys"].append("storyboard.P002")
    shot["actions"].append("look away")
    shot["text_strategy"] = "post"
    shot.pop("post_asset")

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "generation.shots[C002].state_before" in messages
    assert "generation.shots[1].reference_keys" in messages
    assert "generation.shots[1].actions" in messages
    assert "generation.shots[1].post_asset" in messages


def test_dialogue_cannot_jump_back_to_an_earlier_shot() -> None:
    blueprint = _valid_blueprint()
    blueprint["dialogue"][0]["coverage_id"] = "EV002"
    blueprint["dialogue"][0]["shot_id"] = "C002"
    blueprint["dialogue"][1]["coverage_id"] = "EV001"
    blueprint["dialogue"][1]["shot_id"] = "C001"

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "dialogue order crosses back to an earlier shot" in messages


def test_cli_emits_json_result(tmp_path: Path, capsys: Any) -> None:
    blueprint_path = tmp_path / "creative_blueprint.json"
    blueprint_path.write_text(json.dumps(_valid_blueprint()), encoding="utf-8")

    assert MODULE.main([str(blueprint_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"ok": True, "issues": []}


def _readiness_blueprint() -> dict[str, Any]:
    blueprint = _valid_blueprint()
    blueprint["schema"] = "zero-to-story.creative-blueprint.v2"
    blueprint["generation"]["shots"][1]["reference_keys"] = ["boundary.P001.last_frame"]
    blueprint["generation"]["panel_plans"] = [
        {
            "panel_id": "P001",
            "operation": "video.reference_to_video",
            "visual_asset_policy": "scene_keyframe",
            "first_frame_source": None,
            "last_frame_source": None,
            "runtime_input_keys": ["character.teacher", "scene.S001.master"],
            "planning_only_asset_keys": [],
            "reason": "A new location and identity reference must be established together.",
        },
        {
            "panel_id": "P002",
            "operation": "video.image_to_video",
            "visual_asset_policy": "none",
            "first_frame_source": "boundary.P001.last_frame",
            "last_frame_source": None,
            "runtime_input_keys": ["boundary.P001.last_frame"],
            "planning_only_asset_keys": ["board.P002"],
            "reason": "Continue from the accepted real tail frame without generating another image.",
        },
    ]
    blueprint["production"] = {
        "profile": {
            "locale": "en-US",
            "postproduction": "none",
            "dialogue_exactness": "verbatim",
            "speech_units_per_second": 4.5,
            "punctuation_pause_ms": 120,
            "head_guard_ms": 250,
            "tail_guard_ms": 350,
            "turn_gap_ms": 180,
            "safety_margin_ratio": 0.15,
        },
        "speakers": [
            {"id": "S1", "character_id": "teacher", "gender": "male", "age": "adult"},
            {"id": "S2", "character_id": "student", "gender": "female", "age": "young adult"},
        ],
    }
    for line, speaker_id, start, end in (
        (blueprint["dialogue"][0], "S1", 900, 1800),
        (blueprint["dialogue"][1], "S2", 1000, 1700),
    ):
        line["speaker_id"] = speaker_id
        line["measured_duration_ms"] = end - start
        line["planned_start_ms"] = start
        line["planned_end_ms"] = end
        line["allow_overlap"] = False
    for shot, end_ms, action_id, action_ms in (
        (blueprint["generation"]["shots"][0], 8000, "A001", 2200),
        (blueprint["generation"]["shots"][1], 6000, "A002", 1800),
    ):
        shot["start_ms"] = 0
        shot["end_ms"] = end_ms
        shot["action_schedule"] = [
            {
                "id": action_id,
                "description": "single visible action",
                "duration_ms": action_ms,
                "serial_with_dialogue": True,
            }
        ]
    return blueprint


def test_readiness_blueprint_catches_timing_overload_before_generation() -> None:
    blueprint = _readiness_blueprint()
    assert MODULE.validate_blueprint(blueprint) == []

    blueprint["generation"]["shots"][0]["action_schedule"][0]["duration_ms"] = 9000
    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "production window is overfull" in messages


def test_readiness_requires_speaker_registry_and_planned_windows() -> None:
    blueprint = _readiness_blueprint()
    blueprint["production"]["speakers"] = []
    blueprint["dialogue"][0].pop("planned_end_ms")
    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "unknown production speaker" in messages or "production.speakers" in messages
    assert "planned_end_ms" in messages


def test_readiness_requires_one_ordered_panel_plan_per_panel() -> None:
    blueprint = _readiness_blueprint()
    blueprint["generation"]["panel_plans"].pop()

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "generation.panel_plans" in messages
    assert "exactly one plan per Panel" in messages


def test_i2v_rejects_storyboard_board_as_runtime_input() -> None:
    blueprint = _readiness_blueprint()
    blueprint["generation"]["shots"][1]["reference_keys"].append("board.P002")
    plan = blueprint["generation"]["panel_plans"][1]
    plan["runtime_input_keys"].append("board.P002")
    plan["planning_only_asset_keys"] = []

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "storyboard boards are planning assets" in messages
    assert "image-to-video accepts only its first_frame_source" in messages


def test_fl2v_requires_explicit_first_and_last_frame_sources() -> None:
    blueprint = _readiness_blueprint()
    plan = blueprint["generation"]["panel_plans"][1]
    plan["operation"] = "video.first_last_frame"
    plan["visual_asset_policy"] = "last_frame"

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "last_frame_source" in messages


def test_i2v_allows_a_planning_only_board() -> None:
    blueprint = _readiness_blueprint()
    assert MODULE.validate_blueprint(blueprint) == []


def test_panel_runtime_inputs_must_match_setup_reference_union() -> None:
    blueprint = _readiness_blueprint()
    blueprint["generation"]["panel_plans"][0]["runtime_input_keys"] = [
        "character.teacher"
    ]

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)
    assert "must exactly match the Panel's ordered Setup reference union" in messages
