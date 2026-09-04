"""Tests for the minimal zero-to-story creative preflight contract."""

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
        "schema": "zero-to-story.creative-blueprint.v2",
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
            "panel_plans": [
                {
                    "panel_id": "P001",
                    "operation": "video.reference_to_video",
                    "visual_asset_policy": "storyboard_board",
                    "storyboard_layout": "1x2",
                    "first_frame_source": None,
                    "last_frame_source": None,
                    "runtime_input_keys": ["character.teacher", "storyboard_board.P001"],
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
                    "planning_only_asset_keys": ["planning_note.P002"],
                    "reason": "Continue from the accepted real tail frame without generating another image.",
                },
            ],
            "shots": [
                {
                    "id": "C001",
                    "order": 1,
                    "scene_id": "S001",
                    "panel_id": "P001",
                    "coverage_ids": ["EV001"],
                    "dialogue_ids": ["D001"],
                    "critical_characters": ["teacher"],
                    "reference_keys": ["character.teacher", "storyboard_board.P001"],
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
                    "reference_keys": ["boundary.P001.last_frame"],
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


def test_valid_v2_blueprint_passes_without_production_schedule() -> None:
    blueprint = _valid_blueprint()
    assert "production" not in blueprint
    assert MODULE.validate_blueprint(blueprint) == []


def test_v1_blueprint_is_rejected_without_compatibility_path() -> None:
    blueprint = _valid_blueprint()
    blueprint["schema"] = "zero-to-story.creative-blueprint.v1"

    issues = MODULE.validate_blueprint(blueprint)

    assert any(issue.path == "$.schema" for issue in issues)


def test_source_conflict_and_missing_mandatory_coverage_are_reported() -> None:
    blueprint = _valid_blueprint()
    blueprint["source"]["conflicts"][0]["status"] = "unresolved"
    blueprint["generation"]["shots"][0]["coverage_ids"] = []

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "source.conflicts[0].status" in messages
    assert "coverage[EV001]" in messages


def test_state_and_generation_budget_are_reported() -> None:
    blueprint = _valid_blueprint()
    shot = blueprint["generation"]["shots"][1]
    shot["state_before"] = {"brush": "on_desk"}
    shot["reference_keys"].extend(
        ["reference.extra.1", "character.extra", "scene.extra"]
    )
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


def test_panel_plan_is_required_for_every_panel() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["panel_plans"].pop()

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "generation.panel_plans" in messages
    assert "exactly one plan per Panel" in messages


def test_i2v_rejects_legacy_storyboard_frame_as_runtime_input() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["shots"][1]["reference_keys"].append("storyboard_frame.P002.01")
    plan = blueprint["generation"]["panel_plans"][1]
    plan["runtime_input_keys"].append("storyboard_frame.P002.01")
    plan["planning_only_asset_keys"] = []

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "storyboard_frame.* references are not allowed" in messages
    assert "image-to-video accepts only its first_frame_source" in messages


def test_fl2v_requires_explicit_first_and_last_frame_sources() -> None:
    blueprint = _valid_blueprint()
    plan = blueprint["generation"]["panel_plans"][1]
    plan["operation"] = "video.first_last_frame"
    plan["visual_asset_policy"] = "last_frame"

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "last_frame_source" in messages


def test_i2v_allows_an_unrelated_planning_only_asset() -> None:
    assert MODULE.validate_blueprint(_valid_blueprint()) == []


def test_panel_runtime_inputs_must_match_setup_reference_union() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["panel_plans"][0]["runtime_input_keys"] = ["character.teacher"]

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must exactly match the Panel's ordered Setup reference union" in messages


def _configure_storyboard_board(
    blueprint: dict[str, Any],
    layout: str,
    *,
    board_panel_id: str = "P001",
) -> None:
    """Configure the first Panel with one fixed storyboard board reference."""

    board_key = f"storyboard_board.{board_panel_id}"
    runtime_keys = ["character.teacher", board_key]
    blueprint["generation"]["shots"][0]["reference_keys"] = runtime_keys
    plan = blueprint["generation"]["panel_plans"][0]
    plan["visual_asset_policy"] = "storyboard_board"
    plan["storyboard_layout"] = layout
    plan["runtime_input_keys"] = runtime_keys


def test_storyboard_board_accepts_supported_layouts() -> None:
    for layout in (
        "1x2",
        "2x1",
        "1x3",
        "3x1",
        "1x4",
        "2x2",
        "4x1",
        "1x5",
        "5x1",
        "1x6",
        "2x3",
        "3x2",
        "6x1",
    ):
        blueprint = _valid_blueprint()
        _configure_storyboard_board(blueprint, layout)

        assert MODULE.validate_blueprint(blueprint) == []


def test_storyboard_board_requires_layout() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["panel_plans"][0].pop("storyboard_layout")

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "storyboard_layout" in messages
    assert "is required" in messages


def test_storyboard_board_rejects_layout_outside_cell_budget() -> None:
    for layout in ("1x1", "3x3"):
        blueprint = _valid_blueprint()
        _configure_storyboard_board(blueprint, layout)

        issues = MODULE.validate_blueprint(blueprint)
        messages = "\n".join(issue.format() for issue in issues)

        assert "rows*columns must be between 2 and 6" in messages


def test_storyboard_board_rejects_noncanonical_layout_syntax() -> None:
    for layout in ("0x2", "1X2", "01x2"):
        blueprint = _valid_blueprint()
        _configure_storyboard_board(blueprint, layout)

        issues = MODULE.validate_blueprint(blueprint)
        messages = "\n".join(issue.format() for issue in issues)

        assert "must match rowsxcolumns using lowercase 'x'" in messages


def test_storyboard_board_is_only_compatible_with_r2v() -> None:
    blueprint = _valid_blueprint()
    plan = blueprint["generation"]["panel_plans"][1]
    board_key = "storyboard_board.P002"
    blueprint["generation"]["shots"][1]["reference_keys"] = [
        plan["first_frame_source"],
        board_key,
    ]
    plan["runtime_input_keys"] = [plan["first_frame_source"], board_key]
    plan["visual_asset_policy"] = "storyboard_board"
    plan["storyboard_layout"] = "1x2"

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "'storyboard_board' is only compatible with video.reference_to_video" in messages
    assert "image-to-video accepts only its first_frame_source" in messages


def test_non_board_policy_rejects_layout_and_storyboard_board_key() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["panel_plans"][0]["visual_asset_policy"] = "scene_keyframe"

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must be null or omitted unless visual_asset_policy is 'storyboard_board'" in messages
    assert "must be 'storyboard_board' when storyboard_board keys are used" in messages


def test_r2v_requires_storyboard_board_policy() -> None:
    blueprint = _valid_blueprint()
    plan = blueprint["generation"]["panel_plans"][0]
    plan["visual_asset_policy"] = "none"
    plan["storyboard_layout"] = None
    blueprint["generation"]["shots"][0]["reference_keys"] = ["character.teacher"]
    plan["runtime_input_keys"] = ["character.teacher"]

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must be 'storyboard_board' for reference-to-video" in messages


def test_r2v_requires_exactly_one_current_panel_board_key() -> None:
    blueprint = _valid_blueprint()
    plan = blueprint["generation"]["panel_plans"][0]
    plan["runtime_input_keys"] = ["character.teacher"]
    blueprint["generation"]["shots"][0]["reference_keys"] = ["character.teacher"]

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must contain exactly one current-Panel storyboard_board.P001 key" in messages


def test_storyboard_board_rejects_legacy_storyboard_frame_reference() -> None:
    blueprint = _valid_blueprint()
    blueprint["generation"]["shots"][0]["reference_keys"].append("storyboard_frame.P001.01")
    plan = blueprint["generation"]["panel_plans"][0]
    plan["runtime_input_keys"].append("storyboard_frame.P001.01")

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "storyboard_frame.* references are not allowed" in messages


def test_storyboard_board_rejects_foreign_panel_key() -> None:
    blueprint = _valid_blueprint()
    keys = ["character.teacher", "storyboard_board.P999"]
    blueprint["generation"]["shots"][0]["reference_keys"] = keys
    plan = blueprint["generation"]["panel_plans"][0]
    plan["runtime_input_keys"] = keys

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must target the current Panel 'P001'" in messages
    assert "must contain exactly one current-Panel storyboard_board.P001 key" in messages


def test_storyboard_board_rejects_multiple_board_keys() -> None:
    blueprint = _valid_blueprint()
    keys = [
        "character.teacher",
        "storyboard_board.P001",
        "storyboard_board.P002",
    ]
    blueprint["generation"]["shots"][0]["reference_keys"] = keys
    plan = blueprint["generation"]["panel_plans"][0]
    plan["runtime_input_keys"] = keys

    issues = MODULE.validate_blueprint(blueprint)
    messages = "\n".join(issue.format() for issue in issues)

    assert "must contain exactly one current-Panel storyboard_board.P001 key" in messages
