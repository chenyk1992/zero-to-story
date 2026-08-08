"""Tests for CLI run command."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from lfo.cli.run_cmd import cmd_run
from tests.helpers.storyboard_fixtures import make_panel_storyboard_json, minimal_storyboard_dict, write_storyboard_json


def make_storyboard_json(tmp_path: Path, num_panels: int = 1) -> Path:
    if num_panels == 0:
        return write_storyboard_json(
            tmp_path,
            minimal_storyboard_dict(project_id="proj-test", title="Test Storyboard", beats=[], panels=[]),
        )
    return make_panel_storyboard_json(tmp_path, num_panels=num_panels, project_id="proj-test")


class TestCmdRun:
    def test_empty_storyboard_path(self):
        result = cmd_run(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower() or "storyboard_path" in result["error"]

    def test_file_not_found(self, tmp_path):
        result = cmd_run(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        result = cmd_run(storyboard_path=str(bad_file))
        assert result["success"] is False
        assert "failed to load" in result["error"].lower() or "storyboard" in result["error"].lower()

    def test_empty_storyboard_no_shots(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_panels=0)

        with patch("lfo.cli.run_cmd.PipelineService") as MockService:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.project_id = "proj-test"
            mock_result.total_tasks = 0
            mock_result.completed_tasks = 0
            mock_result.failed_tasks = 0
            mock_result.errors = {}
            mock_result.task_results = []
            mock_instance.execute.return_value = mock_result
            MockService.return_value = mock_instance

            result = cmd_run(storyboard_path=str(sb_path))

        assert result["success"] is True
        assert result["total_tasks"] == 0

    def test_success_single_shot(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_panels=1)

        with patch("lfo.cli.run_cmd.PipelineService") as MockService:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.project_id = "proj-test"
            mock_result.total_tasks = 1
            mock_result.completed_tasks = 1
            mock_result.failed_tasks = 0
            mock_result.errors = {}

            mock_task_result = MagicMock()
            mock_task_result.task_id = "task_panel_001"
            mock_task_result.shot_id = "panel_001"
            mock_task_result.success = True
            mock_task_result.status = "SUCCEEDED"
            mock_task_result.asset_id = "asset-001"
            mock_task_result.qc_passed = True
            mock_task_result.normalized = True
            mock_task_result.end_frame_extracted = True
            mock_task_result.error = ""
            mock_result.task_results = [mock_task_result]

            mock_instance.execute.return_value = mock_result
            MockService.return_value = mock_instance

            result = cmd_run(storyboard_path=str(sb_path))

        assert result["success"] is True
        assert result["project_id"] == "proj-test"
        assert result["total_tasks"] == 1
        assert result["completed_tasks"] == 1
        assert result["failed_tasks"] == 0
        assert len(result["task_results"]) == 1
        assert result["task_results"][0]["task_id"] == "task_panel_001"
        assert result["task_results"][0]["qc_passed"] is True

    def test_failure_reports_errors(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_panels=1)

        with patch("lfo.cli.run_cmd.PipelineService") as MockService:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.project_id = "proj-test"
            mock_result.total_tasks = 1
            mock_result.completed_tasks = 0
            mock_result.failed_tasks = 1
            mock_result.errors = {"task_panel_001": "ComfyUI timeout"}
            mock_result.task_results = []
            mock_instance.execute.return_value = mock_result
            MockService.return_value = mock_instance

            result = cmd_run(storyboard_path=str(sb_path))

        assert result["success"] is False
        assert result["failed_tasks"] == 1
        assert "task_panel_001" in result["errors"]
