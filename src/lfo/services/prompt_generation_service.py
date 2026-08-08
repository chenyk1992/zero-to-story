"""PromptGenerationService — generate prompt blueprints from storyboard shots.

Responsibilities:
- Iterate over shots in a storyboard
- For each shot, compile a PromptBlueprint using the appropriate compiler
- Flag shots that require visual input (visual.generate tasks)
- Return a generation plan with all blueprints and task requirements
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.planning.prompt_blueprint import (
    compile_first_last_blueprint,
    compile_i2v_blueprint,
    compile_r2v_blueprint,
    compile_t2va_blueprint,
)
from lfo.planning.schema import PromptBlueprint
from lfo.storyboard.storyboard import Shot, Storyboard


@dataclass
class ShotGenerationPlan:
    """Generation plan for a single shot."""

    shot_id: str
    blueprint: PromptBlueprint | None = None
    requires_visual_input: bool = False
    workflow_mode: str = ""  # 't2va' | 'i2v' | 'first_last' | 'r2v'
    task_type: str = ""  # 'video.h3' | 'visual.generate'
    references_needed: list[str] = field(default_factory=list)  # asset roles needed


@dataclass
class GenerationPlan:
    """Complete generation plan for a storyboard."""

    project_id: str
    shot_plans: list[ShotGenerationPlan] = field(default_factory=list)
    total_shots: int = 0
    visual_tasks_needed: int = 0


class PromptGenerationService:
    """Generate prompt blueprints and task plans from storyboard shots."""

    def __init__(self) -> None:
        pass

    def generate_plan(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> GenerationPlan:
        """Generate a complete generation plan from a storyboard.

        For each shot, determines the workflow mode and compiles a prompt blueprint.
        Shots with continuity from previous shots require visual input (I2V mode).
        Standalone shots use T2VA mode.

        Args:
            storyboard: The approved storyboard.
            project_id: The project ID for task creation.

        Returns:
            GenerationPlan with per-shot plans.
        """
        plan = GenerationPlan(project_id=project_id)

        for shot in storyboard.shots:
            shot_plan = self._plan_shot(shot, storyboard)
            plan.shot_plans.append(shot_plan)
            if shot_plan.requires_visual_input:
                plan.visual_tasks_needed += 1

        plan.total_shots = len(storyboard.shots)
        return plan

    def _plan_shot(
        self,
        shot: Shot,
        storyboard: Storyboard,
    ) -> ShotGenerationPlan:
        """Determine the generation approach for a single shot.

        R2V is only used when a shot needs visual input (continuity from
        a previous shot) AND has reference characters.  The first shot
        always uses T2VA even if characters have registered refs — there
        is no previous frame to be consistent with, so T2VA establishes
        the character look.
        """
        plan = ShotGenerationPlan(shot_id=shot.shot_id)

        # Determine workflow mode based on shot characteristics
        if shot.generation_hint and shot.generation_hint.preferred_mode:
            mode = shot.generation_hint.preferred_mode
        elif shot.continuity and shot.continuity.start_frame_needed:
            # Continuation shot — needs visual input from previous frame
            if self._needs_reference_images(shot, storyboard):
                mode = "r2v"
            else:
                mode = "i2v"
        else:
            # First shot or standalone — no previous frame to continue from
            mode = "t2va"

        plan.workflow_mode = mode
        plan.requires_visual_input = mode in ("i2v", "first_last", "r2v")

        # Compile the blueprint
        blueprint = self._compile_blueprint(shot, storyboard, mode)
        plan.blueprint = blueprint

        # Set task type
        if plan.requires_visual_input:
            plan.task_type = "visual.generate"
        else:
            plan.task_type = "video.h3"

        # Track reference needs
        if blueprint and blueprint.symbolic_references:
            plan.references_needed = [
                r.role for r in blueprint.symbolic_references if r.is_symbolic
            ]

        return plan

    def _compile_blueprint(
        self,
        shot: Shot,
        storyboard: Storyboard,
        mode: str,
    ) -> PromptBlueprint | None:
        """Compile a prompt blueprint based on workflow mode."""
        if mode == "t2va":
            return compile_t2va_blueprint(shot, storyboard)
        elif mode == "i2v":
            return compile_i2v_blueprint(shot, storyboard)
        elif mode == "first_last":
            return compile_first_last_blueprint(shot, storyboard)
        elif mode == "r2v":
            return compile_r2v_blueprint(shot, storyboard)
        return None

    def _needs_reference_images(
        self,
        shot: Shot,
        storyboard: Storyboard,
    ) -> bool:
        """Check if a shot needs reference images (R2V mode)."""
        # R2V is needed when characters have specific visual references
        for char_app in shot.characters:
            if char_app.character_id in storyboard.project.reference_character_order:
                return True
        return False

    def compile_all_blueprints(
        self,
        storyboard: Storyboard,
    ) -> list[PromptBlueprint]:
        """Compile prompt blueprints for all shots (without task planning).

        Args:
            storyboard: The approved storyboard.

        Returns:
            List of PromptBlueprint, one per shot.
        """
        blueprints = []
        for shot in storyboard.shots:
            mode = self._determine_mode(shot, storyboard)
            blueprint = self._compile_blueprint(shot, storyboard, mode)
            if blueprint is not None:
                blueprints.append(blueprint)
        return blueprints

    def _determine_mode(self, shot: Shot, storyboard: Storyboard) -> str:
        """Determine workflow mode for a shot.

        R2V only when shot needs visual input AND has reference characters.
        First shot always uses T2VA even with registered character refs.
        """
        if shot.generation_hint and shot.generation_hint.preferred_mode:
            return shot.generation_hint.preferred_mode
        elif shot.continuity and shot.continuity.start_frame_needed:
            if self._needs_reference_images(shot, storyboard):
                return "r2v"
            return "i2v"
        return "t2va"
