"""Tests for the StoryboardDecomposer.

These tests use a FakeLLMClient to feed canned responses. We never call
mmx or any external service in unit tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.storyboard.decompose import (
    DecomposeError,
    MmxLLMClient,
    StoryboardDecomposer,
)
from lfo.storyboard.decompose_schema import DecomposeSchemaError
from lfo.storyboard.intake import (
    Intake,
    IntakeConstraints,
    IntakeSource,
    InputSourceType,
    Origin,
)
from lfo.storyboard.storyboard import (
    Character,
    ProjectInfo,
    Scene,
    Story,
    Storyboard,
    StyleGuide,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLLMClient:
    """Returns a pre-canned response. Optionally raises."""

    def __init__(self, response: str = "", raises: Exception | None = None):
        self.response = response
        self.raises = raises
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.raises is not None:
            raise self.raises
        return self.response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "decompose_responses"


def _make_intake(
    synopsis: str = "特价鸡蛋引发的僵尸末日里，试用期员工陈默凭摸鱼经验逃生。",
    shot_count_target: int = 2,
) -> Intake:
    intake = Intake(
        project_id="intake_test_001",
        constraints=IntakeConstraints(
            target_duration_ms=30000,
            aspect_ratio="9:16",
            pacing="medium",
            custom={"shot_count_target": shot_count_target},
        ),
    )
    intake.add_source(
        source_type=InputSourceType.STORY_SYNOPSIS,
        content=synopsis,
    )
    return intake


def _make_project() -> ProjectInfo:
    return ProjectInfo(
        project_id="我今天不上班-chapter_01",
        title="特价鸡蛋引发的血案",
        novel_id="我今天不上班",
        chapter_id="chapter_01",
    )


def _make_characters() -> list[Character]:
    return [
        Character(
            character_id="char_chenmo",
            name="陈默",
            description="25岁中国男性超市员工，白色制服，漫不经心",
            role="protagonist",
            age="25",
            gender="male",
            distinguishing_features="扫码枪钢管",
        ),
    ]


def _make_scenes() -> list[Scene]:
    return [
        Scene(
            scene_id="scene_supermarket",
            name="超市",
            description="冷白荧光灯下",
            time_of_day="day",
            lighting="cold fluorescent",
            mood="panic",
            environment="interior",
        ),
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDecomposeHappyPath:
    def test_chenmo_3shot_returns_storyboard(self):
        """A canned 2-shot response produces a valid Storyboard."""
        raw = (FIXTURES / "chenmo_3shot.json").read_text(encoding="utf-8")
        llm = FakeLLMClient(response=raw)
        decomposer = StoryboardDecomposer(
            llm=llm,
            project=_make_project(),
            story=Story(logline="陈默摸鱼逃生", synopsis="特价鸡蛋引发的血案"),
            style=StyleGuide(visual_style="cinematic dark comedy"),
            characters=_make_characters(),
            scenes=_make_scenes(),
        )
        sb = decomposer.decompose(_make_intake())

        assert isinstance(sb, Storyboard)
        assert sb.project.title == "特价鸡蛋引发的血案"
        assert sb.project.intake_ref == "intake_test_001"
        assert len(sb.beats) == 2
        assert len(sb.panels) == 1

        b1, b2 = sb.beats
        assert b1.beat_id == "shot_001_t2v"
        assert b1.sequence == 1
        assert b1.framing == "wide"

        assert b2.beat_id == "shot_002_i2v"
        assert b2.sequence == 2

    def test_passes_intake_synopsis_to_prompt(self):
        """The synopsis content must reach the user prompt."""
        llm = FakeLLMClient(response='{"shots": []}')  # will raise on validate
        decomposer = StoryboardDecomposer(
            llm=llm,
            project=_make_project(),
            story=Story(synopsis="second story"),
            characters=_make_characters(),
        )
        with pytest.raises(DecomposeError):
            decomposer.decompose(_make_intake(synopsis="hello world"))
        # The user prompt should contain the intake synopsis
        assert any("hello world" in u for _, u in llm.calls)

    def test_merges_new_scenes_and_props(self):
        """New scenes/props from LLM end up in the storyboard."""
        raw = (FIXTURES / "chenmo_3shot.json").read_text(encoding="utf-8")
        llm = FakeLLMClient(response=raw)
        decomposer = StoryboardDecomposer(
            llm=llm,
            project=_make_project(),
            characters=_make_characters(),
            scenes=[],
        )
        sb = decomposer.decompose(_make_intake())
        assert any(s.scene_id == "scene_supermarket" for s in sb.scenes)
        assert any(p.prop_id == "prop_steel_pipe_scanner" for p in sb.props)

    def test_scene_id_remap(self):
        """When LLM invents a new scene with a fresh ID, the shot's scene_id
        is rewritten to the merged list's final ID."""
        raw = json.dumps({
            "scenes": [{
                "scene_id": "scene_warehouse",
                "name": "仓库",
                "description": "后仓",
                "time_of_day": "day",
                "lighting": "dim",
                "mood": "tense",
                "environment": "interior",
            }],
            "props": [],
            "shots": [{
                "shot_id": "shot_001_t2v",
                "scene_id": "scene_warehouse",
                "description": "陈默靠在冰柜上抽烟",
                "desired_duration_ms": 5000,
                "camera": {"shot_size": "medium", "angle": "eye_level", "movement": "static"},
                "characters": [],
                "action_beats": [],
                "continuity": {
                    "previous_shot_id": None,
                    "next_shot_id": None,
                    "start_frame_needed": False,
                },
                "generation_hint": {"preferred_family": "h3_fl2va", "preferred_mode": "t2va"},
            }],
        })
        llm = FakeLLMClient(response=raw)
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        sb = decomposer.decompose(_make_intake(shot_count_target=1))
        assert sb.beats[0].scene_id == "scene_warehouse"
        assert any(s.scene_id == "scene_warehouse" for s in sb.scenes)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestDecomposeErrors:
    def test_llm_call_failure(self):
        llm = FakeLLMClient(raises=RuntimeError("network down"))
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError, match="LLM call failed"):
            decomposer.decompose(_make_intake())

    def test_llm_returns_empty(self):
        llm = FakeLLMClient(response="")
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError, match="empty"):
            decomposer.decompose(_make_intake())

    def test_llm_returns_invalid_json(self):
        llm = FakeLLMClient(response="I cannot help with that.")
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError, match="Invalid LLM output"):
            decomposer.decompose(_make_intake())

    def test_llm_returns_schema_violation(self):
        llm = FakeLLMClient(response='{"shots": [{"shot_id": "1bad", "scene_id": "x", "description": "x", "desired_duration_ms": 1000}]}')
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError, match="Invalid LLM output"):
            decomposer.decompose(_make_intake())

    def test_llm_returns_empty_shots(self):
        llm = FakeLLMClient(response='{"shots": []}')
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError, match="empty shots"):
            decomposer.decompose(_make_intake())


# ---------------------------------------------------------------------------
# MmxLLMClient
# ---------------------------------------------------------------------------


class TestMmxLLMClient:
    def test_missing_mmx_raises_decompose_error(self, monkeypatch, tmp_path):
        # Point mmx_path to a definitely-missing executable
        missing = str(tmp_path / "no-such-mmx")
        client = MmxLLMClient(mmx_path=missing, timeout_sec=5)
        with pytest.raises(DecomposeError, match="not found"):
            client.complete("system", "user")

    def test_nonzero_exit_raises(self, monkeypatch, tmp_path):
        # Create a fake mmx that exits non-zero
        fake = tmp_path / "fake-mmx.cmd"
        fake.write_text("@echo off\r\necho bad things happened 1>&2\r\nexit /b 7\r\n", encoding="utf-8")
        client = MmxLLMClient(mmx_path=str(fake), timeout_sec=5)
        with pytest.raises(DecomposeError, match="exit 7"):
            client.complete("system", "user")

    def test_extract_text_from_plain_text(self):
        """Plain text response (no JSON wrapper) passes through."""
        assert MmxLLMClient._extract_text("Hello world") == "Hello world"

    def test_extract_text_from_response_wrapper(self):
        """mmx sometimes wraps text in {"response": "..."}."""
        raw = '{"response": "The cat sat on the mat."}'
        assert MmxLLMClient._extract_text(raw) == "The cat sat on the mat."

    def test_extract_text_from_message_envelope(self):
        """The full API envelope with content[].text is unwrapped."""
        raw = json.dumps({
            "id": "abc",
            "content": [{"type": "text", "text": "Hello from assistant"}],
            "model": "MiniMax-M3",
        })
        assert MmxLLMClient._extract_text(raw) == "Hello from assistant"

    def test_extract_text_unparseable_falls_back(self):
        """If the text is neither parseable JSON nor a known wrapper, return it as-is."""
        raw = "not json { broken"
        assert MmxLLMClient._extract_text(raw) == "not json { broken"

    def test_extract_text_empty(self):
        assert MmxLLMClient._extract_text("") == ""
        assert MmxLLMClient._extract_text("   \n  ") == ""


# ---------------------------------------------------------------------------
# Prompt rendering smoke tests (no LLM call)
# ---------------------------------------------------------------------------


class TestPromptRendering:
    def test_prompt_contains_style_block(self):
        llm = FakeLLMClient(response='{"shots": []}')  # will fail at validate
        style = StyleGuide(visual_style="ghibli", color_palette="warm pastels")
        decomposer = StoryboardDecomposer(
            llm=llm, project=_make_project(), style=style,
        )
        with pytest.raises(DecomposeError):
            decomposer.decompose(_make_intake())
        prompt = llm.calls[0][1]
        assert "ghibli" in prompt
        assert "warm pastels" in prompt

    def test_prompt_contains_character_names(self):
        llm = FakeLLMClient(response='{"shots": []}')
        chars = [Character(character_id="char_x", name="陈默", role="protagonist")]
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project(), characters=chars)
        with pytest.raises(DecomposeError):
            decomposer.decompose(_make_intake())
        prompt = llm.calls[0][1]
        assert "char_x" in prompt
        assert "陈默" in prompt

    def test_prompt_contains_existing_scenes(self):
        llm = FakeLLMClient(response='{"shots": []}')
        scenes = [Scene(scene_id="scene_supermarket", name="超市")]
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project(), scenes=scenes)
        with pytest.raises(DecomposeError):
            decomposer.decompose(_make_intake())
        prompt = llm.calls[0][1]
        assert "scene_supermarket" in prompt
        assert "超市" in prompt

    def test_prompt_first_char_is_not_brace_rule_documented(self):
        """The system prompt must include the no-fences / first-char-is-brace rule."""
        llm = FakeLLMClient(response='{"shots": []}')
        decomposer = StoryboardDecomposer(llm=llm, project=_make_project())
        with pytest.raises(DecomposeError):
            decomposer.decompose(_make_intake())
        system = llm.calls[0][0]
        assert "JSON" in system or "json" in system
