"""Tests for planning.render."""
from lfo.planning.render import render_dry_run_report
from lfo.planning.schema import (
    AssetRequirement,
    ExecutionPlan,
    PlannedTask,
)


class TestRenderDryRunReport:
    def test_empty_plan(self):
        """Empty plan should still produce a valid report."""
        plan = ExecutionPlan(project_id="proj_001")
        report = render_dry_run_report(plan)
        assert "# Execution Plan" in report
        assert "proj_001" in report

    def test_project_summary(self):
        """Report should contain project summary."""
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
        report = render_dry_run_report(plan)
        assert "Total Tasks" in report
        assert "1" in report

    def test_task_details(self):
        """Report should contain per-task details."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    workflow_id="h3_standard_i2v",
                    workflow_family="h3_fl2va",
                    workflow_mode="i2v",
                    selection_reason="has start frame",
                    aligned_frames=124,
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "task_video_shot_001" in report
        assert "h3_standard_i2v" in report
        assert "i2v" in report

    def test_continuity_chains(self):
        """Report should show continuity chains."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    serial_group="chain_001",
                ),
                PlannedTask(
                    logical_task_key="video/shot_002",
                    task_id="task_video_shot_002",
                    project_id="proj_001",
                    serial_group="chain_001",
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "chain_001" in report

    def test_blocked_tasks(self):
        """Report should show blocked tasks."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    status="blocked",
                    asset_requirements=[
                        AssetRequirement(
                            requirement_id="req_001",
                            target_id="shot_001",
                            asset_role="start_frame",
                            status="missing",
                            blocking_reason="Start frame required",
                        ),
                    ],
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "Blocked Tasks" in report
        assert "blocked" in report

    def test_asset_summary(self):
        """Report should summarize asset requirements."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    asset_requirements=[
                        AssetRequirement(
                            requirement_id="req_001",
                            target_id="shot_001",
                            asset_role="start_frame",
                        ),
                    ],
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "Asset Requirements" in report
        assert "start_frame" in report

    def test_no_blocked_tasks_success(self):
        """Report should show success when no blocked tasks."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_video_shot_001",
                    project_id="proj_001",
                    status="planned",
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "No blocked tasks" in report

    def test_dependencies_shown(self):
        """Task dependencies should appear in the report."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    project_id="proj_001",
                    depends_on=["task_b"],
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "task_b" in report

    def test_status_breakdown_table(self):
        """Status breakdown table should be present."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    project_id="proj_001",
                    status="planned",
                ),
                PlannedTask(
                    logical_task_key="video/shot_002",
                    task_id="task_b",
                    project_id="proj_001",
                    status="blocked",
                ),
            ],
        )
        report = render_dry_run_report(plan)
        assert "Status Breakdown" in report
        assert "planned" in report
        assert "blocked" in report

    def test_determinism(self):
        """Same plan → same report."""
        plan = ExecutionPlan(
            project_id="proj_001",
            planned_tasks=[
                PlannedTask(
                    logical_task_key="video/shot_001",
                    task_id="task_a",
                    project_id="proj_001",
                    aligned_frames=124,
                ),
            ],
        )
        r1 = render_dry_run_report(plan)
        r2 = render_dry_run_report(plan)
        assert r1 == r2
