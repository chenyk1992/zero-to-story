"""LFO Planning — task planning and video prompt blueprint generation.

Modules:
- schema: Data structures (ExecutionPlan, PlannedTask, PromptBlueprint, etc.)
- segmenter: Storyboard -> logical tasks
- workflow_selector: Panel Pack conditions -> workflow selection
- asset_requirements: Enumerate required assets per panel
- prompt_blueprint: Video prompt blueprint compilers
- duration: Frame count calculation
- dag: Task dependency graph builder
- validator: Plan integrity checks
- materializer: execution_plan.json -> SQLite tasks
- render: execution_plan -> dry_run_report.md
"""
from lfo.planning.asset_requirements import plan_asset_requirements, plan_panel_asset_requirements
from .dag import build_task_dependencies
from .duration import compute_aligned_frames
from .materializer import PlanMaterializer
from .prompt_blueprint import (
    compile_first_last_blueprint,
    compile_i2v_blueprint,
    compile_r2v_blueprint,
    compile_t2va_blueprint,
)
from .render import render_dry_run_report
from .schema import (
    AssetRequirement,
    ExecutionPlan,
    PlannedTask,
    PromptBlueprint,
    PromptPart,
    ReferenceBinding,
)
from .segmenter import segment_storyboard
from .validator import ValidationResult, validate_execution_plan
from .workflow_selector import WorkflowSelection, select_workflow_for_panel

__all__ = [
    # schema
    "ReferenceBinding",
    "PromptPart",
    "PromptBlueprint",
    "AssetRequirement",
    "PlannedTask",
    "ExecutionPlan",
    # segmenter
    "segment_storyboard",
    # workflow_selector
    "select_workflow_for_panel",
    "WorkflowSelection",
    # asset_requirements
    "plan_asset_requirements",
    "plan_panel_asset_requirements",
    # prompt_blueprint
    "compile_t2va_blueprint",
    "compile_i2v_blueprint",
    "compile_first_last_blueprint",
    "compile_r2v_blueprint",
    # duration
    "compute_aligned_frames",
    # dag
    "build_task_dependencies",
    # validator
    "validate_execution_plan",
    "ValidationResult",
    # materializer
    "PlanMaterializer",
    # render
    "render_dry_run_report",
]
