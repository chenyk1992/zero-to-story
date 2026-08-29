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
