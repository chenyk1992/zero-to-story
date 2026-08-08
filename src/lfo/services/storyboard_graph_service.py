"""StoryboardGraphService — convert storyboard to task dependency graph.

Responsibilities:
- Take an approved storyboard
- Use PromptGenerationService to plan shot modes
- Create tasks with proper dependencies:
  - First shot (T2V): no dependencies
  - Continuation shots (I2V/R2V): depend on previous shot's output
- Materialize tasks to the database
- Return the execution plan with the full dependency graph

This is the "D" step: Storyboard → Task Graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from lfo.application.visual_profile_service import VisualProfileService
from lfo.core.database import Database
from lfo.planning.materializer import PlanMaterializer
from lfo.planning.reference_planner import plan_references
from lfo.planning.schema import (
    AssetRequirement,
    ExecutionPlan,
    PlannedTask,
)
from lfo.services.prompt_generation_service import (
    GenerationPlan,
    PromptGenerationService,
    ShotGenerationPlan,
)
from lfo.storyboard.storyboard import Storyboard

# Mapping from workflow_mode to workflow_id
MODE_TO_WORKFLOW = {
    "t2va": "h3_standard_t2v",
    "i2v": "h3_standard_i2v",
    "first_last": "h3_standard_i2v",  # Same workflow supports i2v and first_last
    "r2v": "h3_standard_r2v",
}

# Mapping from workflow_mode to workflow_family
MODE_TO_FAMILY = {
    "t2va": "h3_fl2va",
    "i2v": "h3_fl2va",
    "first_last": "h3_fl2va",
    "r2v": "h3_ref2va",
}


@dataclass
class TaskGraph:
    """Result of storyboard → task graph conversion."""

    project_id: str
    tasks: list[PlannedTask] = field(default_factory=list)
    execution_plan: ExecutionPlan | None = None
    materialization_summary: dict = field(default_factory=dict)


class StoryboardGraphService:
    """Convert a storyboard into a task dependency graph."""

    def __init__(
        self,
        db: Database,
        prompt_service: PromptGenerationService | None = None,
        materializer: PlanMaterializer | None = None,
    ) -> None:
        self.db = db
        self.prompt_service = prompt_service or PromptGenerationService()
        self.materializer = materializer or PlanMaterializer(db)

    # -- public API ------------------------------------------------------- #

    def build_graph(self, storyboard: Storyboard) -> TaskGraph:
        """Build a task dependency graph from a storyboard.

        Steps:
        1. Generate shot plan (mode selection for each shot)
        2. Create tasks with dependencies
        3. Materialize to database
        4. Return the graph

        Args:
            storyboard: The approved storyboard.

        Returns:
            TaskGraph with all tasks and their dependencies.
        """
        project_id = storyboard.project.project_id

        # 1. Generate shot plan
        gen_plan = self.prompt_service.generate_plan(storyboard, project_id)

        # 2. Create tasks
        tasks = self._create_tasks(gen_plan, storyboard)

        # 3. Build execution plan
        exec_plan = ExecutionPlan(
            project_id=project_id,
            planned_tasks=tasks,
        )

        # 4. Materialize to DB
        summary = self.materializer.apply(exec_plan)

        return TaskGraph(
            project_id=project_id,
            tasks=tasks,
            execution_plan=exec_plan,
            materialization_summary=summary,
        )

    # -- task creation --------------------------------------------------- #

    def _create_tasks(
        self,
        gen_plan: GenerationPlan,
        storyboard: Storyboard,
    ) -> list[PlannedTask]:
        """Create PlannedTask objects from a generation plan.

        When the active profile policy is ``visual_required`` and a shot
        requires visual input, a ``visual.generate`` task is inserted
        before the video task to produce the start frame.  The video
        task then depends on the visual task instead of directly on the
        previous shot.
        """
        tasks: list[PlannedTask] = []
        prev_task_id: str | None = None

        # Read active profile policy (default: allow_t2va_fallback)
        policy = self._get_visual_policy(gen_plan.project_id)

        # Collect available_assets from db: {entity_id: {asset_role: {status, asset_id}}}
        available_assets = self._load_available_assets(gen_plan.project_id)

        for shot_plan in gen_plan.shot_plans:
            task_id = f"task_{shot_plan.shot_id}"

            # Determine dependencies
            depends_on: list[str] = []
            asset_reqs: list[AssetRequirement] = []

            if shot_plan.requires_visual_input and policy == "visual_required":
                # Insert a visual.generate task to produce the start frame
                visual_task_id = f"visual_{shot_plan.shot_id}_start_frame"
                visual_depends = [prev_task_id] if prev_task_id else []

                visual_task = PlannedTask(
                    logical_task_key=f"visual/{shot_plan.shot_id}/start_frame",
                    task_id=visual_task_id,
                    project_id=gen_plan.project_id,
                    task_type="visual.generate",
                    target_ids=[shot_plan.shot_id],
                    workflow_id="",
                    workflow_family="",
                    workflow_mode="t2i",
                    selection_reason=(
                        "visual_required policy: generate start frame"
                    ),
                    depends_on=visual_depends,
                    serial_group=gen_plan.project_id,
                    priority_class=35,  # Higher priority than video (30)
                    prompt_blueprint_id="",
                    asset_requirements=[AssetRequirement(
                        requirement_id=f"req_{shot_plan.shot_id}_start_frame",
                        target_id=shot_plan.shot_id,
                        asset_role="start_frame",
                        required=True,
                        status="missing",
                        blocking_reason="Start frame will be generated by visual task",
                    )],
                    status="PLANNED" if not visual_depends else "WAITING_ASSETS",
                    aligned_frames=0,  # Not applicable for image generation
                )
                tasks.append(visual_task)

                # Video task depends on the visual task
                depends_on.append(visual_task_id)
                asset_reqs.append(AssetRequirement(
                    requirement_id=f"req_{shot_plan.shot_id}_start_frame",
                    target_id=shot_plan.shot_id,
                    asset_role="start_frame",
                    required=True,
                    status="missing",
                    blocking_reason="Start frame from visual.generate task",
                ))
            elif prev_task_id and shot_plan.requires_visual_input:
                # Existing behavior: depend on previous shot's output
                depends_on.append(prev_task_id)
                asset_reqs.append(AssetRequirement(
                    requirement_id=f"req_{shot_plan.shot_id}_prev_frame",
                    target_id=shot_plan.shot_id,
                    asset_role="start_frame",
                    required=True,
                    status="missing",
                    blocking_reason=f"Requires end frame from {prev_task_id}",
                ))

            # Create the video task
            # For R2V: resolve reference_bindings from available_assets + shot
            ref_bindings: list = []
            if shot_plan.workflow_mode == "r2v":
                # Find the matching Shot in the storyboard
                shot_obj = next(
                    (s for s in storyboard.shots if s.shot_id == shot_plan.shot_id),
                    None,
                )
                if shot_obj is not None:
                    ref_bindings = plan_references(shot_obj, storyboard, available_assets)

            task = PlannedTask(
                logical_task_key=f"video/{shot_plan.shot_id}",
                task_id=task_id,
                project_id=gen_plan.project_id,
                task_type="video.h3",
                target_ids=[shot_plan.shot_id],
                workflow_id=MODE_TO_WORKFLOW.get(shot_plan.workflow_mode, "h3_standard_t2v"),
                workflow_family=MODE_TO_FAMILY.get(shot_plan.workflow_mode, "h3_fl2va"),
                workflow_mode=shot_plan.workflow_mode,
                selection_reason=self._selection_reason(shot_plan),
                depends_on=depends_on,
                serial_group=gen_plan.project_id,  # All shots in a project are serial
                priority_class=30,
                prompt_blueprint_id=f"pb_{shot_plan.shot_id}",
                asset_requirements=asset_reqs,
                reference_bindings=ref_bindings,
                status="WAITING_ASSETS",
                aligned_frames=124,  # Standard 5s @ 24fps
            )

            tasks.append(task)
            prev_task_id = task_id

        return tasks

    def _get_visual_policy(self, project_id: str) -> str:
        """Read the active visual generation profile policy.

        Returns the policy string (``allow_t2va_fallback`` or
        ``visual_required``).  Defaults to ``allow_t2va_fallback`` when
        no active profile exists.
        """
        try:
            profile_service = VisualProfileService(self.db)
            active = profile_service.get_active(project_id)
            if active:
                return active.get("content", {}).get(
                    "visual_input_policy", "allow_t2va_fallback"
                )
        except Exception:
            # If profile lookup fails, default to fallback (never block)
            pass
        return "allow_t2va_fallback"

    def _load_available_assets(self, project_id: str) -> dict:
        """Load approved assets from DB into the format plan_references expects.

        Returns:
            Dict of {entity_id: {asset_role: {status, asset_id}}} for all
            approved assets in the project.
        """
        # Schema: asset_bindings (binding_id, asset_id, project_id, entity_type,
        # entity_id, asset_role, validity) + asset_reviews (asset_id, manual_review_status)
        rows = self.db.fetchall(
            """SELECT ab.entity_id, ab.asset_role, ab.asset_id, ar.manual_review_status
               FROM asset_bindings ab
               LEFT JOIN asset_reviews ar ON ab.asset_id = ar.asset_id
                                          AND ar.manual_review_status = 'approved'
               WHERE ab.project_id = ? AND ab.validity = 'current'""",
            (project_id,),
        )

        result: dict = {}
        for entity_id, asset_role, asset_id, review_status in rows:
            if review_status != "approved":
                continue
            result.setdefault(entity_id, {})[asset_role] = {
                "status": "approved",
                "asset_id": asset_id,
            }
        return result

    _REASON_MAP: ClassVar[dict[str, str]] = {
        "t2va": "First shot or standalone: text-to-video",
        "i2v": "Continuation shot: image-to-video with visual input",
        "first_last": "First+last frame control",
        "r2v": "Reference-based: character continuity",
    }

    @staticmethod
    def _selection_reason(shot_plan: ShotGenerationPlan) -> str:
        """Generate a human-readable reason for workflow selection."""
        return (
            StoryboardGraphService._REASON_MAP.get(shot_plan.workflow_mode)
            or f"Mode: {shot_plan.workflow_mode}"
        )
