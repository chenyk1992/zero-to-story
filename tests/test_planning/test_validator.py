"""Tests for planning.validator."""
from lfo.planning.schema import ExecutionPlan, PlannedTask
from lfo.planning.validator import ValidationResult, validate_execution_plan


class TestValidationResult:
    def test_default_valid(self):
        r = ValidationResult(is_valid=True)
        assert r.is_valid is True
        assert r.errors == []

    def test_add_error(self):
        r = ValidationResult(is_valid=True)
        r.add_error("something wrong")
        assert r.is_valid is False
        assert "something wrong" in r.errors

    def test_add_warning(self):
        r = ValidationResult(is_valid=True)
        r.add_warning("beware")
        assert r.is_valid is True
        assert "beware" in r.warnings


class TestValidateExecutionPlan:
    def test_empty_plan_valid(self):
        plan = ExecutionPlan(project_id="proj_001")
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_unique_task_ids(self):
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(logical_task_key="video/shot_001", task_id="task_video_shot_001"),
                PlannedTask(logical_task_key="video/shot_002", task_id="task_video_shot_002"),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_duplicate_task_ids(self):
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(logical_task_key="video/shot_001", task_id="same_id"),
                PlannedTask(logical_task_key="video/shot_002", task_id="same_id"),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("Duplicate" in e for e in result.errors)

    def test_unknown_workflow_id(self):
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    workflow_id="nonexistent_workflow",
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("unknown workflow_id" in e for e in result.errors)

    def test_known_workflow_id_valid(self):
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    workflow_id="h3_standard_t2v",
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_frame_count_aligned(self):
        """Frame count 124 (17*7+5) should be valid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    aligned_frames=124,
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_frame_count_not_aligned(self):
        """Frame count 123 (not 17k+5) should be invalid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    aligned_frames=123,
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("not aligned" in e for e in result.errors)

    def test_frame_count_below_minimum(self):
        """Frame count below minimum (5) should be invalid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    aligned_frames=3,
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("below minimum" in e for e in result.errors)

    def test_frame_count_above_maximum(self):
        """Frame count above maximum (3600) should be invalid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    aligned_frames=5000,
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("above maximum" in e for e in result.errors)

    def test_no_circular_deps(self):
        """Acyclic graph should be valid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    depends_on=["task_b"],
                ),
                PlannedTask(
                    logical_task_key="video/shot_002",
                    task_id="task_b",
                    depends_on=["task_c"],
                ),
                PlannedTask(
                    logical_task_key="video/shot_003",
                    task_id="task_c",
                    depends_on=[],
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_circular_deps(self):
        """Circular dependency should be detected."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    depends_on=["task_b"],
                ),
                PlannedTask(
                    logical_task_key="video/shot_002",
                    task_id="task_b",
                    depends_on=["task_a"],
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("Circular" in e for e in result.errors)

    def test_self_loop(self):
        """Self-dependency should be detected as circular."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    depends_on=["task_a"],
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False

    def test_ready_task_with_fingerprints(self):
        """READY task with complete fingerprints should be valid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    status="READY",
                    dependency_hash="dep_hash_123",
                    params_hash="params_hash_456",
                    idempotency_key="idem_key_789",
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_ready_task_missing_fingerprints(self):
        """READY task without fingerprints should be invalid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    status="READY",
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is False
        assert any("READY" in e and "fingerprint" in e for e in result.errors)

    def test_planned_task_null_fingerprints_ok(self):
        """PLANNED task with NULL fingerprints should be valid."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    status="planned",
                    dependency_hash="",
                    params_hash="",
                    idempotency_key="",
                ),
            ],
        )
        result = validate_execution_plan(plan)
        assert result.is_valid is True

    def test_determinism(self):
        """Same plan → same validation result."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    aligned_frames=124,
                ),
            ],
        )
        r1 = validate_execution_plan(plan)
        r2 = validate_execution_plan(plan)
        assert r1.is_valid == r2.is_valid
        assert r1.errors == r2.errors
