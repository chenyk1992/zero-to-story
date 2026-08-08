"""Tests for PromptGenerationService."""
from __future__ import annotations

from lfo.services.prompt_generation_service import (
    PromptGenerationService,
)
from lfo.storyboard.storyboard import (
    Camera,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Shot,
    Storyboard,
)


def make_storyboard(num_shots: int = 3) -> Storyboard:
    """Create a test storyboard with the given number of shots."""
    shots = []
    for i in range(num_shots):
        shot = Shot(
            shot_id=f"shot_{i + 1:03d}",
            display_index=i + 1,
            scene_id="scene_001",
            description=f"Shot {i + 1} description",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(
                start_frame_needed=(i > 0),  # First shot doesn't need start frame
            ),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)

    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        shots=shots,
    )


class TestGeneratePlan:
    def test_generates_plan_for_all_shots(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(3)
        plan = service.generate_plan(storyboard, "proj-test")
        assert plan.total_shots == 3
        assert len(plan.shot_plans) == 3

    def test_first_shot_is_t2va(self):
        """First shot (no continuity) should use T2VA mode."""
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        plan = service.generate_plan(storyboard, "proj-test")
        assert plan.shot_plans[0].workflow_mode == "t2va"
        assert not plan.shot_plans[0].requires_visual_input

    def test_continuation_shot_requires_visual_input(self):
        """Shots with continuity should need visual input."""
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        plan = service.generate_plan(storyboard, "proj-test")
        # Second shot has start_frame_needed=True
        assert plan.shot_plans[1].requires_visual_input

    def test_counts_visual_tasks_needed(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(3)
        plan = service.generate_plan(storyboard, "proj-test")
        # Shots 2 and 3 have start_frame_needed=True
        assert plan.visual_tasks_needed == 2

    def test_blueprint_created_for_each_shot(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        plan = service.generate_plan(storyboard, "proj-test")
        for sp in plan.shot_plans:
            assert sp.blueprint is not None

    def test_task_type_set_correctly(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        plan = service.generate_plan(storyboard, "proj-test")
        # First shot: T2VA → video.h3
        assert plan.shot_plans[0].task_type == "video.h3"
        # Second shot: I2V → visual.generate (requires visual input)
        assert plan.shot_plans[1].task_type == "visual.generate"


class TestCompileAllBlueprints:
    def test_compile_all_returns_list(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(3)
        blueprints = service.compile_all_blueprints(storyboard)
        assert len(blueprints) == 3

    def test_blueprints_have_correct_mode(self):
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        blueprints = service.compile_all_blueprints(storyboard)
        assert blueprints[0].workflow_mode == "t2va"
        assert blueprints[1].workflow_mode == "i2v"


class TestWorkflowModeSelection:
    def test_explicit_hint_overrides_default(self):
        """If generation_hint has workflow_mode, use it."""
        service = PromptGenerationService()
        storyboard = make_storyboard(1)
        storyboard.shots[0].generation_hint.preferred_mode = "r2v"
        storyboard.shots[0].continuity.start_frame_needed = False
        plan = service.generate_plan(storyboard, "proj-test")
        assert plan.shot_plans[0].workflow_mode == "r2v"

    def test_empty_storyboard(self):
        service = PromptGenerationService()
        storyboard = Storyboard(project=ProjectInfo(project_id="p"), shots=[])
        plan = service.generate_plan(storyboard, "p")
        assert plan.total_shots == 0
        assert plan.visual_tasks_needed == 0

    def test_first_shot_with_reference_chars_stays_t2va(self):
        """First shot should stay T2VA even with reference characters.

        R2V is only used for continuation shots that need visual input.
        The first shot establishes the character look, so it stays T2VA.
        """
        from lfo.storyboard.storyboard import CharacterAppearance
        service = PromptGenerationService()
        storyboard = make_storyboard(2)
        # Add a reference character to the project
        storyboard.project.reference_character_order = ["char_001"]
        # Both shots have the character
        for shot in storyboard.shots:
            shot.characters = [CharacterAppearance(character_id="char_001")]
        plan = service.generate_plan(storyboard, "proj-test")
        # First shot: T2VA (no continuity, even with reference char)
        assert plan.shot_plans[0].workflow_mode == "t2va"
        assert not plan.shot_plans[0].requires_visual_input
        # Second shot: R2V (continuity + reference char)
        assert plan.shot_plans[1].workflow_mode == "r2v"
        assert plan.shot_plans[1].requires_visual_input
