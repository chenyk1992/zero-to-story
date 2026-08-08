"""StoryboardGraphService — convert storyboard to task dependency graph.

Responsibilities:
- Take an approved storyboard
- Use PanelGenerationService to plan panel modes
- Create tasks with proper dependencies:
  - Panel video tasks in narrative order
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
from lfo.planning.schema import (
    ExecutionPlan,
    PlannedTask,
    ReferenceBinding,
)
from lfo.services.panel_generation_service import (
    GenerationPlan,
    PanelGenerationPlan,
    PanelGenerationService,
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
        panel_service: PanelGenerationService | None = None,
        materializer: PlanMaterializer | None = None,
    ) -> None:
        self.db = db
        self.panel_service = panel_service or PanelGenerationService()
        self.materializer = materializer or PlanMaterializer(db)

    # -- public API ------------------------------------------------------- #

    def build_graph(self, storyboard: Storyboard) -> TaskGraph:
        """Build a task dependency graph from a storyboard.

        Steps:
        1. Generate panel plan (mode selection for each panel)
        2. Create tasks with dependencies
        3. Materialize to database
        4. Return the graph

        Args:
            storyboard: The approved storyboard.

        Returns:
            TaskGraph with all tasks and their dependencies.
        """
        project_id = storyboard.project.project_id

        available_assets = self._load_available_assets(project_id)
        gen_plan = self.panel_service.generate_plan(
            storyboard,
            project_id,
            available_assets=available_assets,
        )

        tasks = self._create_tasks(gen_plan, storyboard)

        exec_plan = ExecutionPlan(
            project_id=project_id,
            planned_tasks=tasks,
        )

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
        """Create PlannedTask objects from a panel generation plan."""
        tasks: list[PlannedTask] = []
        prev_task_id: str | None = None

        for panel_plan in gen_plan.panel_plans:
            task_id = f"task_{panel_plan.panel_id}"
            depends_on: list[str] = [prev_task_id] if prev_task_id else []

            ref_bindings = _reference_bindings_from_pack(panel_plan)

            panel = storyboard.panel_by_id(panel_plan.panel_id)
            aligned_frames = 0
            if panel is not None:
                aligned_frames = max(1, (panel.desired_duration_ms * 24) // 1000)

            task = PlannedTask(
                logical_task_key=f"video/{panel_plan.panel_id}",
                task_id=task_id,
                project_id=gen_plan.project_id,
                task_type=panel_plan.task_type,
                target_ids=[panel_plan.panel_id],
                workflow_id=panel_plan.workflow_id,
                workflow_family=MODE_TO_FAMILY.get(
                    panel_plan.workflow_mode,
                    "h3_fl2va",
                ),
                workflow_mode=panel_plan.workflow_mode,
                selection_reason=self._selection_reason(panel_plan),
                depends_on=depends_on,
                serial_group=gen_plan.project_id,
                priority_class=30,
                prompt_blueprint_id=f"pb_{panel_plan.panel_id}",
                asset_requirements=[],
                reference_bindings=ref_bindings,
                status="WAITING_ASSETS" if depends_on else "PLANNED",
                aligned_frames=aligned_frames,
            )

            tasks.append(task)
            prev_task_id = task_id

        return tasks

    def _get_visual_policy(self, project_id: str) -> str:
        """Read the active visual generation profile policy."""
        try:
            profile_service = VisualProfileService(self.db)
            active = profile_service.get_active(project_id)
            if active:
                return active.get("content", {}).get(
                    "visual_input_policy", "allow_t2va_fallback"
                )
        except Exception:
            pass
        return "allow_t2va_fallback"

    def _load_available_assets(self, project_id: str) -> dict:
        """Load approved assets from DB into the format plan_references expects."""
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
        "t2va": "Text-to-video fallback",
        "i2v": "Image-to-video with visual input",
        "first_last": "First+last frame control",
        "r2v": "Reference-based: PanelPack composition + identity refs",
    }

    @staticmethod
    def _selection_reason(panel_plan: PanelGenerationPlan) -> str:
        """Generate a human-readable reason for workflow selection."""
        return (
            StoryboardGraphService._REASON_MAP.get(panel_plan.workflow_mode)
            or f"Mode: {panel_plan.workflow_mode}"
        )


def _reference_bindings_from_pack(panel_plan: PanelGenerationPlan) -> list[ReferenceBinding]:
    if panel_plan.workflow_mode != "r2v":
        return []
    return [
        ReferenceBinding(
            slot=ref.slot,
            asset_id=ref.asset_id,
            entity_id=ref.entity_id,
            role=ref.role,
        )
        for ref in panel_plan.pack.refs
    ]
