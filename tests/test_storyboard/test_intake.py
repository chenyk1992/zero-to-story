"""Tests for LFO Intake Schema."""
from lfo.storyboard.intake import (
    ORIGIN_AGENT_HYPOTHESIS,
    ORIGIN_AGENT_INFERRED,
    ORIGIN_USER,
    InputSourceType,
    Intake,
    IntakeConstraints,
    IntakeSource,
    Origin,
)


class TestOrigin:
    def test_default_origin_is_user(self):
        o = Origin()
        assert o.source == ORIGIN_USER
        assert o.confidence == "high"

    def test_agent_inferred_origin(self):
        o = Origin(
            source=ORIGIN_AGENT_INFERRED,
            confidence="medium",
            derived_from=["source_001"],
            reason="inferred from brief",
        )
        assert o.source == ORIGIN_AGENT_INFERRED
        assert o.derived_from == ["source_001"]

    def test_to_dict_round_trip(self):
        o = Origin(source=ORIGIN_AGENT_HYPOTHESIS, confidence="low")
        d = o.to_dict()
        restored = Origin.from_dict(d)
        assert restored.source == ORIGIN_AGENT_HYPOTHESIS
        assert restored.confidence == "low"


class TestIntakeSource:
    def test_create_source(self):
        s = IntakeSource(
            source_id="source_001",
            type=InputSourceType.CREATIVE_BRIEF,
            content="A robot in the rain.",
        )
        assert s.source_id == "source_001"
        assert s.type == "creative_brief"
        assert s.origin == ORIGIN_USER

    def test_to_dict_round_trip(self):
        s = IntakeSource(
            source_id="s1",
            type="screenplay",
            content="INT. ROBOT LAB - NIGHT",
            origin=ORIGIN_USER,
            metadata={"filename": "script.txt"},
        )
        d = s.to_dict()
        restored = IntakeSource.from_dict(d)
        assert restored.source_id == "s1"
        assert restored.metadata["filename"] == "script.txt"


class TestIntakeConstraints:
    def test_defaults(self):
        c = IntakeConstraints()
        assert c.target_duration_ms == 30000
        assert c.aspect_ratio == "9:16"
        assert c.delivery_width == 1080
        assert c.delivery_height == 1920

    def test_custom_constraints(self):
        c = IntakeConstraints(
            target_duration_ms=15000,
            aspect_ratio="16:9",
            visual_style="cyberpunk",
            max_characters=3,
        )
        assert c.target_duration_ms == 15000
        assert c.visual_style == "cyberpunk"

    def test_to_dict_round_trip(self):
        c = IntakeConstraints(visual_style="anime", mood="melancholic")
        d = c.to_dict()
        restored = IntakeConstraints.from_dict(d)
        assert restored.visual_style == "anime"
        assert restored.mood == "melancholic"

    def test_medium_lock_round_trip(self):
        """medium_lock field round-trips through to_dict/from_dict."""
        c = IntakeConstraints(
            visual_style="2d_anime",
            medium_lock="Medium: 2D hand-drawn animation. NOT 3D render.",
        )
        d = c.to_dict()
        assert d["medium_lock"] == "Medium: 2D hand-drawn animation. NOT 3D render."
        restored = IntakeConstraints.from_dict(d)
        assert restored.medium_lock == "Medium: 2D hand-drawn animation. NOT 3D render."


class TestIntake:
    def test_create_empty_intake(self):
        intake = Intake()
        assert intake.schema_version == "lfo.intake.v1"
        assert intake.project_id.startswith("proj_")

    def test_create_with_project_id(self):
        intake = Intake(project_id="proj_myfilm")
        assert intake.project_id == "proj_myfilm"

    def test_add_source(self):
        intake = Intake()
        src = intake.add_source(
            source_type=InputSourceType.CREATIVE_BRIEF,
            content="A robot in the rain.",
        )
        assert len(intake.sources) == 1
        assert src.source_id.startswith("source_")
        assert src.type == "creative_brief"
        assert src.origin == ORIGIN_USER

    def test_add_source_with_custom_id(self):
        intake = Intake()
        src = intake.add_source(
            source_type=InputSourceType.STORY_SYNOPSIS,
            content="Long story...",
            source_id="my_source_1",
        )
        assert src.source_id == "my_source_1"

    def test_primary_text(self):
        intake = Intake()
        intake.add_source(InputSourceType.CREATIVE_BRIEF, "First text.")
        intake.add_source(InputSourceType.STORY_SYNOPSIS, "Second text.")
        assert intake.primary_text() == "First text."

    def test_primary_text_empty(self):
        intake = Intake()
        assert intake.primary_text() == ""

    def test_to_dict_round_trip(self):
        intake = Intake(project_id="proj_test")
        intake.add_source(InputSourceType.CREATIVE_BRIEF, "A film about AI.")
        intake.constraints.visual_style = "noir"

        d = intake.to_dict()
        restored = Intake.from_dict(d)

        assert restored.project_id == "proj_test"
        assert len(restored.sources) == 1
        assert restored.sources[0].content == "A film about AI."
        assert restored.constraints.visual_style == "noir"

    def test_serialization_stability(self):
        """Same intake → same dict structure (for hashing)."""
        intake = Intake(project_id="proj_stable")
        intake.add_source(InputSourceType.CREATIVE_BRIEF, "Test content")

        d1 = intake.to_dict()
        d2 = intake.to_dict()
        assert d1 == d2
