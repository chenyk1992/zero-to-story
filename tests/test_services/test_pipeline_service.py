"""Tests for PipelineService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lfo.core.database import Database
from lfo.planning.schema import PlannedTask
from lfo.services.pipeline_service import PipelineResult, PipelineService, TaskPipelineResult
from lfo.services.storyboard_graph_service import TaskGraph
from lfo.storyboard.storyboard import ProjectInfo, Storyboard
from tests.helpers.storyboard_fixtures import make_panel_storyboard


def make_storyboard(num_panels: int = 2) -> Storyboard:
    return make_panel_storyboard(num_panels, project_id="proj-pipeline-test", title="Test")


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


class TestExecute:
    def test_empty_storyboard(self, db):
        service = PipelineService(db)
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-empty"),
            beats=[],
            panels=[],
        )

        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = TaskGraph(
            project_id="proj-empty",
            tasks=[],
        )

        result = service.execute(storyboard)

        assert result.success is True
        assert result.total_tasks == 0

    def test_creates_graph_from_storyboard(self, db):
        service = PipelineService(db, auto_approve=True)
        storyboard = make_storyboard(2)

        planned_tasks = [
            PlannedTask(
                logical_task_key="video/panel_001",
                task_id="task_panel_001",
                project_id="proj-pipeline-test",
                target_ids=["panel_001"],
                workflow_mode="r2v",
            ),
        ]
        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = TaskGraph(
            project_id="proj-pipeline-test",
            tasks=planned_tasks,
        )

        service.readiness_service = MagicMock()
        service.readiness_service.promote_to_ready.return_value = MagicMock(
            success=True, materialization_id="mat-001",
        )
        service.execution_facade = MagicMock()
        service.execution_facade.run_ready_task.return_value = MagicMock(
            success=True, attempt_id="att-001", prompt_id="prompt-001",
        )
        service.video_collect = MagicMock()
        service.video_collect.collect.return_value = MagicMock(
            success=True, assets=[MagicMock()],
        )
        service.qc_service = MagicMock()
        service.qc_service.check_asset.return_value = MagicMock(passed=True, status="PASS")
        service.media_service = MagicMock()
        service.media_service.normalize.return_value = MagicMock(
            file_path="/tmp/norm.mp4", asset_id="norm-asset-001",
        )
        service.editorial_service = MagicMock()
        service.editorial_service.create_selection.return_value = MagicMock(
            selected_clip_id="clip-001",
            normalized_asset_id="norm-asset-001",
        )
        service.editorial_service.render_selected_clip.return_value = MagicMock(
            selected_clip_id="clip-001",
            status="awaiting_review",
        )
        service.editorial_service.approve_selected_clip.return_value = MagicMock(
            selected_clip_id="clip-001",
            status="approved",
        )
        service.end_frame_extractor = MagicMock()
        service.end_frame_extractor.extract_from_clip.return_value = MagicMock(
            success=True, file_path="/tmp/frame.png",
        )

        service.edl_service = MagicMock()
        mock_edl = MagicMock()
        mock_edl.edl_id = "edl-001"
        service.edl_service.create_edl.return_value = mock_edl
        service.edl_service.approve_edl.return_value = mock_edl
        service.edl_service.resolve_clips.return_value = []
        service.assembly_service = MagicMock()
        service.assembly_service.build_from_edl.return_value = MagicMock(
            success=True, output_asset_id="asm-001", output_file_path="/tmp/final.mp4",
        )
        service.srt_generator = MagicMock()
        service.srt_generator.generate.return_value = MagicMock(
            success=False, error="no narration", file_path="", cue_count=0,
        )
        service.final_qc_service = MagicMock()
        service.final_qc_service.validate.return_value = MagicMock(
            success=True, issues=[],
        )

        def mock_fetchone(sql, params):
            if "asset_id" in sql:
                return ("asset-001",)
            return None
        db.fetchone = mock_fetchone

        result = service.execute(storyboard)

        assert result.total_tasks == 1
        assert result.completed_tasks == 1
        assert result.failed_tasks == 0
        assert result.task_results[0].selected_clip_id == "clip-001"
        assert result.task_results[0].end_frame_extracted is True

    def test_task_failure_stops_pipeline(self, db):
        service = PipelineService(db)
        storyboard = make_storyboard(1)

        planned_tasks = [
            PlannedTask(
                logical_task_key="video/panel_001",
                task_id="task_panel_001",
                project_id="proj-pipeline-test",
                target_ids=["panel_001"],
            ),
        ]
        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = TaskGraph(
            project_id="proj-pipeline-test",
            tasks=planned_tasks,
        )

        service.readiness_service = MagicMock()
        service.readiness_service.promote_to_ready.return_value = MagicMock(success=True)
        service.execution_facade = MagicMock()
        service.execution_facade.run_ready_task.return_value = MagicMock(
            success=False, message="Task not in READY state",
        )

        result = service.execute(storyboard)

        assert result.success is False
        assert result.failed_tasks == 1
        assert "task_panel_001" in result.errors


class TestTaskPipelineResult:
    def test_default_values(self):
        result = TaskPipelineResult(task_id="t1", shot_id="s1")
        assert result.success is False
        assert result.qc_passed is False
        assert result.normalized is False
        assert result.end_frame_extracted is False


class TestPipelineResult:
    def test_default_values(self):
        result = PipelineResult(project_id="p1")
        assert result.success is False
        assert result.total_tasks == 0
        assert result.completed_tasks == 0
        assert result.failed_tasks == 0
