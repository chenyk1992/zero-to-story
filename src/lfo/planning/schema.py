"""Planning data structures — ExecutionPlan, PlannedTask, PromptBlueprint, etc.

These dataclasses represent the full output of the planning phase:
an execution plan with all tasks, prompt blueprints, and asset requirements.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------------------
# Reference binding
# ---------------------------------------------------------------------------

@dataclass
class ReferenceBinding:
    """A resolved reference image binding for R2V."""
    slot: int                      # 1, 2, or 3
    asset_id: str                  # resolved asset ID (or symbolic placeholder)
    entity_id: str                 # character_id, shot_id, etc.
    role: str                      # 'character' | 'composition' | 'scene' | 'key_prop' | 'style'
    is_symbolic: bool = False      # True when asset not yet materialized

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ReferenceBinding:
        return cls(**data)


# ---------------------------------------------------------------------------
# Prompt blueprint
# ---------------------------------------------------------------------------

@dataclass
class PromptPart:
    """A single semantic part of a video prompt."""
    part_type: str                 # 'subject' | 'scene' | 'action' | 'camera' | 'end_state' | 'audio' | 'negative'
    content: str                   # the text content
    source: str = ""               # where this part came from (for traceability)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PromptPart:
        return cls(**data)


@dataclass
class PromptBlueprint:
    """A video prompt blueprint — semantic parts before asset materialization."""
    blueprint_id: str              # e.g. "pb_panel_01"
    compiler_name: str             # e.g. "h3_r2v_prompt_blueprint"
    target_panel_ids: list[str] = field(default_factory=list)
    target_shot_ids: list[str] = field(default_factory=list)  # legacy alias
    workflow_mode: str = ""        # 't2va' | 'i2v' | 'first_last' | 'r2v'
    parts: list[PromptPart] = field(default_factory=list)
    symbolic_references: list[ReferenceBinding] = field(default_factory=list)
    materialization_status: str = "complete"  # 'complete' | 'waiting_assets'
    content_hash: str = ""         # LFO-CJ1 hash of the blueprint

    def to_dict(self) -> dict:
        return {
            "blueprint_id": self.blueprint_id,
            "compiler_name": self.compiler_name,
            "target_panel_ids": self.target_panel_ids,
            "target_shot_ids": self.target_shot_ids,
            "workflow_mode": self.workflow_mode,
            "parts": [p.to_dict() for p in self.parts],
            "symbolic_references": [r.to_dict() for r in self.symbolic_references],
            "materialization_status": self.materialization_status,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PromptBlueprint:
        parts = [PromptPart.from_dict(p) for p in data.pop("parts", [])]
        refs = [ReferenceBinding.from_dict(r) for r in data.pop("symbolic_references", [])]
        return cls(parts=parts, symbolic_references=refs, **data)


# ---------------------------------------------------------------------------
# Asset requirement
# ---------------------------------------------------------------------------

@dataclass
class AssetRequirement:
    """A required asset that is not yet available."""
    requirement_id: str            # e.g. "req_shot003_start_frame"
    target_id: str                 # shot_id or character_id
    asset_role: str                # 'start_frame' | 'end_frame' | 'character_ref' | 'scene_ref' | 'composition_ref'
    required: bool = True
    status: str = "missing"        # 'missing' | 'available' | 'blocked'
    blocking_reason: str = ""      # why this requirement blocks

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AssetRequirement:
        return cls(**data)


# ---------------------------------------------------------------------------
# Planned task
# ---------------------------------------------------------------------------

@dataclass
class PlannedTask:
    """A single planned task in the execution plan."""
    logical_task_key: str          # e.g. "video/panel_01"
    task_id: str                   # e.g. "task_panel_01"
    project_id: str = ""
    task_type: str = "video.h3"
    target_ids: list[str] = field(default_factory=list)
    workflow_id: str = ""          # e.g. "h3_standard_i2v"
    workflow_family: str = ""      # e.g. "h3_fl2va"
    workflow_mode: str = ""        # e.g. "i2v"
    selection_reason: str = ""     # why this workflow was selected
    fallback_workflow_ids: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # list of task_ids
    serial_group: str = ""
    priority_class: int = 30
    prompt_blueprint_id: str = ""
    asset_requirements: list[AssetRequirement] = field(default_factory=list)
    status: str = "PLANNED"        # 'PLANNED' | 'BLOCKED' | 'WAITING_ASSETS' — must match TaskStatus enum values (uppercase)
    content_hash: str = ""
    dependency_hash: str = ""      # NULL until assets materialized
    params_hash: str = ""          # NULL until assets materialized
    idempotency_key: str = ""      # NULL until assets materialized
    aligned_frames: int = 0        # computed frame count
    reference_bindings: list[ReferenceBinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "logical_task_key": self.logical_task_key,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "task_type": self.task_type,
            "target_ids": self.target_ids,
            "workflow_id": self.workflow_id,
            "workflow_family": self.workflow_family,
            "workflow_mode": self.workflow_mode,
            "selection_reason": self.selection_reason,
            "fallback_workflow_ids": self.fallback_workflow_ids,
            "depends_on": self.depends_on,
            "serial_group": self.serial_group,
            "priority_class": self.priority_class,
            "prompt_blueprint_id": self.prompt_blueprint_id,
            "asset_requirements": [a.to_dict() for a in self.asset_requirements],
            "status": self.status,
            "content_hash": self.content_hash,
            "dependency_hash": self.dependency_hash,
            "params_hash": self.params_hash,
            "idempotency_key": self.idempotency_key,
            "aligned_frames": self.aligned_frames,
            "reference_bindings": [r.to_dict() for r in self.reference_bindings],
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlannedTask:
        assets = [AssetRequirement.from_dict(a) for a in data.pop("asset_requirements", [])]
        refs = [ReferenceBinding.from_dict(r) for r in data.pop("reference_bindings", [])]
        return cls(asset_requirements=assets, reference_bindings=refs, **data)


# ---------------------------------------------------------------------------
# Execution plan
# ---------------------------------------------------------------------------

@dataclass
class ExecutionPlan:
    """Complete execution plan for a project."""
    project_id: str = ""
    schema_version: str = "lfo.execution_plan.v1"
    planned_tasks: list[PlannedTask] = field(default_factory=list)
    prompt_blueprints: list[PromptBlueprint] = field(default_factory=list)
    asset_requirements: list[AssetRequirement] = field(default_factory=list)
    created_at: str = ""           # ISO 8601
    content_hash: str = ""         # hash of the entire plan

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "schema_version": self.schema_version,
            "planned_tasks": [t.to_dict() for t in self.planned_tasks],
            "prompt_blueprints": [b.to_dict() for b in self.prompt_blueprints],
            "asset_requirements": [a.to_dict() for a in self.asset_requirements],
            "created_at": self.created_at,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionPlan:
        tasks = [PlannedTask.from_dict(t) for t in data.pop("planned_tasks", [])]
        blueprints = [PromptBlueprint.from_dict(b) for b in data.pop("prompt_blueprints", [])]
        assets = [AssetRequirement.from_dict(a) for a in data.pop("asset_requirements", [])]
        return cls(
            planned_tasks=tasks,
            prompt_blueprints=blueprints,
            asset_requirements=assets,
            **data,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> ExecutionPlan:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
