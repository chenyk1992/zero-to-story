"""Tests for LFO Markdown renderer."""
from lfo.storyboard.intake import Intake
from lfo.storyboard.render import render_intake_md, render_storyboard_md
from lfo.storyboard.storyboard import (
    REVIEW_APPROVED,
    ActionBeat,
    Camera,
    Character,
    CharacterAppearance,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Scene,
    Shot,
    Story,
    Storyboard,
)


class TestRenderIntakeMD:
    def test_render_empty_intake(self):
        intake = Intake(project_id="proj_test")
        md = render_intake_md(intake)
        assert "# 项目输入" in md
        assert "proj_test" in md

    def test_render_with_sources(self):
        intake = Intake()
        intake.add_source("creative_brief", "A robot in the rain.")
        md = render_intake_md(intake)
        assert "A robot in the rain." in md
        assert "creative_brief" in md

    def test_render_with_constraints(self):
        intake = Intake()
        intake.add_source("creative_brief", "Test")
        intake.constraints.visual_style = "cyberpunk"
        intake.constraints.aspect_ratio = "16:9"
        md = render_intake_md(intake)
        assert "cyberpunk" in md
        assert "16:9" in md


class TestRenderStoryboardMD:
    def test_render_empty_storyboard(self):
        sb = Storyboard(project=ProjectInfo(project_id="proj_001", title="Test"))
        md = render_storyboard_md(sb)
        assert "# Test" in md
        assert "proj_001" in md

    def test_render_review_status_cn(self):
        sb = Storyboard(project=ProjectInfo(project_id="p1", title="T"))
        sb.review.status = REVIEW_APPROVED
        md = render_storyboard_md(sb)
        assert "已批准" in md

    def test_render_story(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            story=Story(logline="A robot remembers.", synopsis="Long story..."),
        )
        md = render_storyboard_md(sb)
        assert "A robot remembers." in md
        assert "Long story..." in md

    def test_render_characters(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            characters=[
                Character(character_id="c1", name="Mira", role="protagonist",
                          description="A young scientist"),
            ],
        )
        md = render_storyboard_md(sb)
        assert "Mira" in md
        assert "protagonist" in md

    def test_render_scenes(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            scenes=[
                Scene(scene_id="s1", name="Rainy Street", environment="exterior"),
            ],
        )
        md = render_storyboard_md(sb)
        assert "Rainy Street" in md

    def test_render_shots(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            scenes=[Scene(scene_id="sc1", name="Street")],
            shots=[
                Shot(
                    shot_id="shot_001",
                    display_index=1,
                    scene_id="sc1",
                    desired_duration_ms=5000,
                    camera=Camera(shot_size="wide", movement="static"),
                    description="A wide shot of the street.",
                    characters=[
                        CharacterAppearance(
                            character_id="c1",
                            screen_position="center",
                            action="walks forward",
                        )
                    ],
                    action_beats=[
                        ActionBeat(sequence=1, description="Enters frame"),
                    ],
                ),
            ],
            characters=[Character(character_id="c1", name="Mira")],
        )
        md = render_storyboard_md(sb)
        assert "Shot 1" in md
        assert "wide" in md
        assert "walks forward" in md
        assert "Enters frame" in md
        assert "5.0s" in md or "5000" in md

    def test_render_continuity(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            scenes=[Scene(scene_id="sc1")],
            shots=[
                Shot(
                    shot_id="s1",
                    scene_id="sc1",
                    desired_duration_ms=3000,
                    continuity=ContinuityInfo(
                        start_state="standing",
                        end_state="sitting",
                    ),
                ),
            ],
        )
        md = render_storyboard_md(sb)
        assert "standing" in md
        assert "sitting" in md

    def test_render_generation_hint(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="p1", title="T"),
            scenes=[Scene(scene_id="sc1")],
            shots=[
                Shot(
                    shot_id="s1",
                    scene_id="sc1",
                    desired_duration_ms=3000,
                    generation_hint=GenerationHint(
                        preferred_family="h3_fl2va",
                        preferred_mode="i2v",
                    ),
                ),
            ],
        )
        md = render_storyboard_md(sb)
        assert "h3_fl2va" in md
        assert "i2v" in md
