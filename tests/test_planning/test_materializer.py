"""Tests for planning.materializer."""
import pytest

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.planning.materializer import PlanMaterializer
from lfo.planning.schema import ExecutionPlan, PlannedTask


@pytest.fixture
def db():
    """Create an in-memory database with schema."""
    database = Database(":memory:")
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def materializer(db):
    return PlanMaterializer(db)


class TestPlanMaterializer:
    def test_insert_new_tasks(self, materializer):
        """New tasks should be inserted."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                ),
            ],
        )
        result = materializer.apply(plan)
        assert result["inserted"] == 1
        assert result["updated"] == 0
        assert result["superseded"] == 0

    def test_update_existing_task(self, materializer):
        """Existing tasks should be updated, not duplicated."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    workflow_id="h3_standard_t2v",
                ),
            ],
        )
        # First apply
        materializer.apply(plan)
        # Second apply (same task_id)
        plan.planned_tasks[0].workflow_id = "h3_standard_i2v"
        result = materializer.apply(plan)
        assert result["inserted"] == 0
        assert result["updated"] == 1

        # Verify only one row exists
        rows = materializer.db.fetchall(
            "SELECT * FROM tasks WHERE task_id = ?", ("task_video_shot_001",)
        )
        assert len(rows) == 1

    def test_supersede_removed_tasks(self, materializer):
        """Tasks in DB but not in plan should be marked SUPERSEDED."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                ),
                PlannedTask(
                    logical_task_key="video/shot_002",
                    task_id="task_video_shot_002",
                    project_id="proj_001",
                ),
            ],
        )
        materializer.apply(plan)

        # Now remove shot_002 from plan
        plan.planned_tasks = [t for t in plan.planned_tasks if t.task_id != "task_video_shot_002"]
        result = materializer.apply(plan)

        assert result["superseded"] == 1
        row = materializer.db.fetchone(
            "SELECT status FROM tasks WHERE task_id = ?", ("task_video_shot_002",)
        )
        assert row["status"] == TaskStatus.SUPERSEDED.value

    def test_no_supersede_when_disabled(self, materializer):
        """With mark_superceded=False, old tasks should remain unchanged."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                ),
            ],
        )
        materializer.apply(plan)

        # Empty plan, but don't supersede
        plan.planned_tasks = []
        result = materializer.apply(plan, mark_superceded=False)
        assert result["superseded"] == 0

        row = materializer.db.fetchone(
            "SELECT status FROM tasks WHERE task_id = ?", ("task_video_shot_001",)
        )
        assert row["status"] != TaskStatus.SUPERSEDED.value

    def test_multiple_tasks(self, materializer):
        """Multiple tasks should all be inserted."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key=f"video/shot_{i:03d}",
                    task_id=f"task_video_shot_{i:03d}",
                    project_id="proj_001",
                )
                for i in range(1, 6)
            ],
        )
        result = materializer.apply(plan)
        assert result["inserted"] == 5
        assert result["total"] == 5

    def test_fields_preserved(self, materializer):
        """Task fields should be correctly stored."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    task_type="video.h3",
                    workflow_id="h3_standard_i2v",
                    workflow_mode="i2v",
                    serial_group="chain_001",
                    priority_class=20,
                    aligned_frames=124,
                    content_hash="abc123",
                ),
            ],
        )
        materializer.apply(plan)

        row = materializer.db.fetchone(
            "SELECT * FROM tasks WHERE task_id = ?", ("task_video_shot_001",)
        )
        assert row["task_type"] == "video.h3"
        assert row["project_id"] == "proj_001"
        assert row["serial_group"] == "chain_001"
        assert row["priority_class"] == 20
        assert row["content_hash"] == "abc123"

    def test_does_not_delete(self, materializer):
        """Materializer should never delete tasks."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                ),
            ],
        )
        materializer.apply(plan)

        # Empty plan
        plan.planned_tasks = []
        materializer.apply(plan)

        # Task should still exist (as SUPERSEDED)
        row = materializer.db.fetchone(
            "SELECT * FROM tasks WHERE task_id = ?", ("task_video_shot_001",)
        )
        assert row is not None

    def test_summary_total(self, materializer):
        """Summary total should match plan task count."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key=f"video/shot_{i:03d}",
                    task_id=f"task_video_shot_{i:03d}",
                    project_id="proj_001",
                )
                for i in range(1, 4)
            ],
        )
        result = materializer.apply(plan)
        assert result["total"] == 3
