"""Integration test: full pipeline with mocked FFmpeg.

Verifies: Normalize → Selection → EDL → Assembly → SRT → Final QC
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from lfo.core.database import Database
from lfo.planning.schema import PlannedTask
from lfo.services.pipeline_service import PipelineService
from lfo.services.storyboard_graph_service import TaskGraph
from lfo.storyboard.storyboard import (
    Camera,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Shot,
    Storyboard,
)


def make_storyboard(num_shots: int = 3) -> Storyboard:
    shots = []
    for i in range(num_shots):
        shot = Shot(
            shot_id=f"shot_{i + 1:03d}",
            display_index=i + 1,
            scene_id="scene_001",
            description=f"Shot {i + 1}",
            narration=f"第{i + 1}段旁白",
            desired_duration_ms=5000,
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)
    return Storyboard(
        project=ProjectInfo(project_id="proj-integration", title="Integration Test"),
        shots=shots,
    )


def make_planned_tasks(num_shots: int = 3) -> list[PlannedTask]:
    tasks = []
    for i in range(num_shots):
        tasks.append(PlannedTask(
            logical_task_key=f"video/shot_{i + 1:03d}",
            task_id=f"task_shot_{i + 1:03d}",
            project_id="proj-integration",
            target_ids=[f"shot_{i + 1:03d}"],
            workflow_mode="t2va" if i == 0 else "i2v",
        ))
    return tasks


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


class TestFullPipelineIntegration:
    """End-to-end pipeline test with mocked FFmpeg/ComfyUI."""

    def test_full_pipeline_flow(self, db, tmp_path):
        """Verify the complete flow from shot processing to final export."""
        service = PipelineService(
            db,
            output_dir=str(tmp_path / "pipeline"),
            auto_approve=True,
        )
        storyboard = make_storyboard(3)

        # Mock graph service
        planned_tasks = make_planned_tasks(3)
        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = TaskGraph(
            project_id="proj-integration",
            tasks=planned_tasks,
        )

        # Mock ComfyUI execution chain
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

        # Mock normalize to create real output file and register asset
        def mock_normalize(asset_id, profile_id):
            output_path = os.path.join(
                service.media_service.output_dir,
                f"{asset_id}_normalized_{profile_id}.mp4",
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"normalized_data")
            m = MagicMock()
            m.asset_id = f"norm-{asset_id}"
            m.file_path = output_path
            m.duration_sec = 5.0
            m.video_codec = "h264"
            m.audio_codec = "aac"
            m.audio_sample_rate = 48000
            m.audio_channels = 2
            m.width = 1080
            m.height = 1920
            m.fps = 24.0
            return m

        service.media_service = MagicMock()
        service.media_service.normalize.side_effect = mock_normalize
        service.media_service.output_dir = str(tmp_path / "pipeline" / "normalized")

        # Mock editorial service
        service.editorial_service = MagicMock()

        def mock_create_selection(project_id, shot_id, normalized_asset_id, **kwargs):
            m = MagicMock()
            m.selected_clip_id = f"clip-{shot_id}"
            m.normalized_asset_id = normalized_asset_id
            m.status = "draft"
            return m

        def mock_render(selected_clip_id):
            m = MagicMock()
            m.selected_clip_id = selected_clip_id
            m.status = "awaiting_review"
            m.output_asset_id = f"output-{selected_clip_id}"
            return m

        def mock_approve(selected_clip_id):
            m = MagicMock()
            m.selected_clip_id = selected_clip_id
            m.status = "approved"
            return m

        service.editorial_service.create_selection.side_effect = mock_create_selection
        service.editorial_service.render_selected_clip.side_effect = mock_render
        service.editorial_service.approve_selected_clip.side_effect = mock_approve

        # Mock end frame extractor
        service.end_frame_extractor = MagicMock()
        service.end_frame_extractor.extract_from_clip.return_value = MagicMock(
            success=True, file_path="/tmp/frame.png",
        )

        # Mock DB fetchone for asset_id lookups
        original_fetchone = db.fetchone
        def mock_fetchone(sql, params):
            if "attempt_id" in sql:
                return ("asset-raw-001",)
            if "output_asset_id" in sql and "selected_clip_id" in sql:
                return (f"output-{params[0]}",)
            return original_fetchone(sql, params)
        db.fetchone = mock_fetchone

        # Mock assembly pipeline
        service.edl_service = MagicMock()
        mock_edl = MagicMock()
        mock_edl.edl_id = "edl-int-001"
        service.edl_service.create_edl.return_value = mock_edl
        service.edl_service.approve_edl.return_value = mock_edl
        service.edl_service.resolve_clips.return_value = []

        service.assembly_service = MagicMock()
        service.assembly_service.build_from_edl.return_value = MagicMock(
            success=True,
            output_asset_id="asm-final-001",
            output_file_path=str(tmp_path / "pipeline" / "assembly" / "final.mp4"),
        )
        service.srt_generator = MagicMock()
        service.srt_generator.generate.return_value = MagicMock(
            success=True,
            file_path=str(tmp_path / "pipeline" / "srt" / "final.zh-CN.srt"),
            cue_count=3,
        )
        service.srt_generator.register_srt_asset.return_value = "srt-asset-001"
        service.final_qc_service = MagicMock()
        service.final_qc_service.validate.return_value = MagicMock(
            success=True, issues=[],
        )

        # Execute
        result = service.execute(storyboard)

        # Verify shot processing
        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert result.failed_tasks == 0
        for tr in result.task_results:
            assert tr.success
            assert tr.normalized_asset_id.startswith("norm-")
            assert tr.selected_clip_id.startswith("clip-")
            assert tr.end_frame_extracted

        # Verify assembly pipeline was triggered
        assert result.assembly_result.edl_id == "edl-int-001"
        assert result.assembly_result.output_asset_id == "asm-final-001"
        assert result.assembly_result.final_qc_passed
        assert result.success

        # Verify service call chain
        assert service.edl_service.create_edl.called
        assert service.edl_service.approve_edl.called
        assert service.assembly_service.build_from_edl.called
        assert service.srt_generator.generate.called
        assert service.final_qc_service.validate.called
