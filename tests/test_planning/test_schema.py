"""Tests for planning.schema data structures."""
import json

from lfo.planning.schema import (
    AssetRequirement,
    ExecutionPlan,
    PlannedTask,
    PromptBlueprint,
    PromptPart,
    ReferenceBinding,
)


class TestReferenceBinding:
    def test_create(self):
        rb = ReferenceBinding(slot=1, asset_id="asset_001", entity_id="char_001", role="character")
        assert rb.slot == 1
        assert rb.is_symbolic is False

    def test_symbolic(self):
        rb = ReferenceBinding(slot=2, asset_id="PLACEHOLDER", entity_id="shot_001",
                              role="composition", is_symbolic=True)
        assert rb.is_symbolic is True

    def test_round_trip(self):
        rb = ReferenceBinding(slot=3, asset_id="a1", entity_id="e1", role="scene")
        d = rb.to_dict()
        restored = ReferenceBinding.from_dict(d)
        assert restored.slot == 3
        assert restored.asset_id == "a1"
        assert restored.role == "scene"


class TestPromptPart:
    def test_create(self):
        pp = PromptPart(part_type="subject", content="A hero walks", source="shot.characters")
        assert pp.part_type == "subject"
        assert pp.source == "shot.characters"

    def test_default_source(self):
        pp = PromptPart(part_type="scene", content="Rainy street")
        assert pp.source == ""

    def test_round_trip(self):
        pp = PromptPart(part_type="camera", content="close_up", source="shot.camera")
        restored = PromptPart.from_dict(pp.to_dict())
        assert restored.part_type == "camera"
        assert restored.content == "close_up"


class TestPromptBlueprint:
    def test_create(self):
        pb = PromptBlueprint(
            blueprint_id="pb_video_shot_003",
            compiler_name="h3_r2v_prompt_blueprint",
            target_shot_ids=["shot_003"],
            workflow_mode="r2v",
        )
        assert pb.materialization_status == "complete"
        assert pb.parts == []

    def test_with_parts(self):
        pb = PromptBlueprint(
            blueprint_id="pb_001",
            compiler_name="t2va",
            parts=[
                PromptPart(part_type="subject", content="Hero"),
                PromptPart(part_type="scene", content="Street"),
            ],
        )
        assert len(pb.parts) == 2

    def test_round_trip(self):
        pb = PromptBlueprint(
            blueprint_id="pb_001",
            compiler_name="test",
            target_shot_ids=["s1"],
            workflow_mode="i2v",
            parts=[PromptPart(part_type="action", content="walks")],
            symbolic_references=[
                ReferenceBinding(slot=1, asset_id="sym", entity_id="s1", role="scene", is_symbolic=True)
            ],
            materialization_status="waiting_assets",
        )
        restored = PromptBlueprint.from_dict(pb.to_dict())
        assert restored.blueprint_id == "pb_001"
        assert len(restored.parts) == 1
        assert restored.parts[0].content == "walks"
        assert len(restored.symbolic_references) == 1
        assert restored.symbolic_references[0].is_symbolic is True


class TestAssetRequirement:
    def test_create(self):
        ar = AssetRequirement(
            requirement_id="req_shot003_start_frame",
            target_id="shot_003",
            asset_role="start_frame",
        )
        assert ar.required is True
        assert ar.status == "missing"

    def test_blocked(self):
        ar = AssetRequirement(
            requirement_id="req_001",
            target_id="shot_001",
            asset_role="end_frame",
            status="blocked",
            blocking_reason="upstream failed",
        )
        assert ar.blocking_reason == "upstream failed"

    def test_round_trip(self):
        ar = AssetRequirement(
            requirement_id="req_001", target_id="s1", asset_role="character_ref",
            required=False, status="available",
        )
        restored = AssetRequirement.from_dict(ar.to_dict())
        assert restored.required is False
        assert restored.status == "available"


class TestPlannedTask:
    def test_create(self):
        pt = PlannedTask(
            logical_task_key="video/shot_003",
            task_id="task_video_shot_003",
            project_id="proj_001",
        )
        assert pt.task_type == "video.h3"
        assert pt.priority_class == 30
        assert pt.status == "PLANNED"

    def test_defaults(self):
        pt = PlannedTask(logical_task_key="video/shot_001", task_id="task_video_shot_001")
        assert pt.depends_on == []
        assert pt.aligned_frames == 0

    def test_round_trip(self):
        pt = PlannedTask(
            logical_task_key="video/shot_001",
            task_id="task_video_shot_001",
            project_id="proj_001",
            task_type="video.h3",
            target_ids=["shot_001"],
            workflow_id="h3_standard_i2v",
            workflow_family="h3_fl2va",
            workflow_mode="i2v",
            selection_reason="has start frame",
            aligned_frames=124,
            asset_requirements=[
                AssetRequirement(
                    requirement_id="req_001", target_id="shot_001", asset_role="start_frame",
                )
            ],
        )
        restored = PlannedTask.from_dict(pt.to_dict())
        assert restored.task_id == "task_video_shot_001"
        assert restored.workflow_id == "h3_standard_i2v"
        assert restored.aligned_frames == 124
        assert len(restored.asset_requirements) == 1
        assert restored.asset_requirements[0].asset_role == "start_frame"


class TestExecutionPlan:
    def test_create(self):
        plan = ExecutionPlan(project_id="proj_001")
        assert plan.schema_version == "lfo.execution_plan.v1"
        assert plan.planned_tasks == []

    def test_to_json(self):
        plan = ExecutionPlan(project_id="proj_001", created_at="2026-01-01T00:00:00Z")
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert data["project_id"] == "proj_001"

    def test_from_json(self):
        plan = ExecutionPlan(project_id="proj_001", created_at="2026-01-01T00:00:00Z")
        json_str = plan.to_json()
        restored = ExecutionPlan.from_json(json_str)
        assert restored.project_id == "proj_001"
        assert restored.created_at == "2026-01-01T00:00:00Z"

    def test_full_round_trip(self):
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    aligned_frames=124,
                )
            ],
            prompt_blueprints=[
                PromptBlueprint(
                    blueprint_id="pb_001",
                    compiler_name="t2va",
                    workflow_mode="t2va",
                )
            ],
            asset_requirements=[
                AssetRequirement(
                    requirement_id="req_001", target_id="shot_001", asset_role="start_frame",
                )
            ],
        )
        restored = ExecutionPlan.from_dict(plan.to_dict())
        assert restored.project_id == "proj_001"
        assert len(restored.planned_tasks) == 1
        assert restored.planned_tasks[0].aligned_frames == 124
        assert len(restored.prompt_blueprints) == 1
        assert len(restored.asset_requirements) == 1
