"""Tests for hard beat density enforcement in StoryboardDecomposer."""
from __future__ import annotations

import json

import pytest

from lfo.storyboard.decompose import DecomposeError, StoryboardDecomposer
from lfo.storyboard.intake import (
    Intake,
    IntakeConstraints,
    InputSourceType,
)
from lfo.storyboard.storyboard import ProjectInfo, Story


class FakeLLMClient:
    def __init__(self, response: str = ""):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


def _make_intake(**constraint_kw) -> Intake:
    intake = Intake(
        project_id="density_test",
        constraints=IntakeConstraints(**constraint_kw),
    )
    intake.add_source(InputSourceType.STORY_SYNOPSIS, "测试故事")
    return intake


def _minimal_shot(shot_id: str, scene_id: str = "scene_test") -> dict:
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "description": "medium shot, 陈默站在超市中央(中景偏左)，面对镜头",
        "desired_duration_ms": 2000,
        "camera": {"shot_size": "medium", "angle": "eye_level", "movement": "static"},
        "characters": [],
        "action_beats": [],
        "narration": "",
        "continuity": {
            "previous_shot_id": None,
            "next_shot_id": None,
            "start_frame_needed": False,
        },
        "generation_hint": {"preferred_family": "h3_fl2va", "preferred_mode": "t2va"},
    }


def _shots_payload(count: int) -> str:
    shots = [
        _minimal_shot(f"shot_{i:03d}_beat")
        for i in range(1, count + 1)
    ]
    return json.dumps({"scenes": [], "props": [], "shots": shots})


class TestBeatCountTargetFromIntake:
    def test_shot_count_target_alias(self):
        c = IntakeConstraints(custom={"shot_count_target": 22})
        assert c.beat_count_target() == 22

    def test_derives_from_duration_when_no_custom(self):
        c = IntakeConstraints(target_duration_ms=30_000)
        assert c.beat_count_target() == 15

    def test_beat_count_target_field(self):
        c = IntakeConstraints(custom={"beat_count_target": 10})
        assert c.beat_count_target() == 10


class TestDecomposePromptDensity:
    def test_prompt_contains_hard_beat_count(self):
        llm = FakeLLMClient(response='{"shots": []}')
        decomposer = StoryboardDecomposer(llm=llm, project=ProjectInfo(project_id="p"))
        intake = _make_intake(target_duration_ms=30_000, custom={"shot_count_target": 15})
        with pytest.raises(DecomposeError):
            decomposer.decompose(intake)
        prompt = llm.calls[0][1]
        assert "BEAT COUNT (HARD CONSTRAINT)" in prompt
        assert "exactly 15 beats" in prompt
        assert "Do NOT emit per-beat preferred_mode" in prompt
        assert "start_frame_needed" in prompt
        assert "Usually 3-6" not in prompt

    def test_prompt_uses_duration_derived_target(self):
        llm = FakeLLMClient(response='{"shots": []}')
        decomposer = StoryboardDecomposer(llm=llm, project=ProjectInfo(project_id="p"))
        intake = _make_intake(target_duration_ms=15_000)
        with pytest.raises(DecomposeError):
            decomposer.decompose(intake)
        prompt = llm.calls[0][1]
        assert "exactly 8 beats" in prompt


class TestDecomposeBeatCountEnforcement:
    def test_fails_when_beat_count_mismatch(self):
        llm = FakeLLMClient(response=_shots_payload(3))
        decomposer = StoryboardDecomposer(llm=llm, project=ProjectInfo(project_id="p"))
        intake = _make_intake(custom={"shot_count_target": 5})
        with pytest.raises(DecomposeError, match="beat_count_target"):
            decomposer.decompose(intake)

    def test_passes_when_beat_count_matches(self):
        llm = FakeLLMClient(response=_shots_payload(5))
        decomposer = StoryboardDecomposer(llm=llm, project=ProjectInfo(project_id="p"))
        intake = _make_intake(custom={"shot_count_target": 5})
        sb = decomposer.decompose(intake)
        assert len(sb.beats) == 5
        assert len(sb.panels) == 1
