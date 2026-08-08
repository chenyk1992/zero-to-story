"""Tests for CLI preview command."""
from __future__ import annotations

import json
from pathlib import Path

from lfo.cli.preview_cmd import cmd_preview_build, cmd_preview_collect
from tests.helpers.storyboard_fixtures import make_panel_storyboard_json, minimal_storyboard_dict, write_storyboard_json


class TestCmdPreviewBuild:
    def test_empty_storyboard_path(self):
        result = cmd_preview_build(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_preview_build(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        result = cmd_preview_build(storyboard_path=str(bad_file))
        assert result["success"] is False
        assert "failed to load" in result["error"].lower()

    def test_no_shots(self, tmp_path):
        sb_path = write_storyboard_json(
            tmp_path,
            minimal_storyboard_dict(project_id="proj-empty", beats=[], panels=[]),
            filename="empty.json",
        )
        result = cmd_preview_build(storyboard_path=str(sb_path))
        assert result["success"] is False
        assert "no panels" in result["error"].lower()

    def test_builds_requests(self, tmp_path):
        sb_path = make_panel_storyboard_json(tmp_path, num_panels=3, project_id="proj-preview-test")
        result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["status"] == "waiting"
        assert result["requests_count"] == 1
        assert result["total_panels"] == 3
        assert "batch_id" in result
        assert Path(result["batch_path"]).exists()

    def test_multi_sheet(self, tmp_path):
        sb_path = make_panel_storyboard_json(tmp_path, num_panels=16, project_id="proj-preview-test")
        result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["requests_count"] == 3
        assert result["total_panels"] == 16


class TestCmdPreviewCollect:
    def test_empty_storyboard_path(self):
        result = cmd_preview_collect(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_preview_collect(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_no_image_requests_dir(self, tmp_path):
        sb_path = make_panel_storyboard_json(tmp_path, num_panels=1)
        result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "image_requests" in result["error"].lower()

    def test_no_results_file(self, tmp_path):
        sb_path = make_panel_storyboard_json(tmp_path, num_panels=3)
        cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "generate images" in result["error"].lower() or "not found" in result["error"].lower()

    def test_collect_results(self, tmp_path):
        sb_path = make_panel_storyboard_json(tmp_path, num_panels=3)
        build_result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert build_result["success"] is True

        results_path = Path(build_result["results_path"])
        batch_path = Path(build_result["batch_path"])
        batch_data = json.loads(batch_path.read_text(encoding="utf-8"))

        img_path = tmp_path / "preview_sheet.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        results_data = {
            "batch_id": build_result["batch_id"],
            "results": [
                {
                    "request_id": batch_data["requests"][0]["request_id"],
                    "status": "completed",
                    "result_asset_path": str(img_path),
                    "result_seed": 42,
                    "error": "",
                    "completed_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
        results_path.write_text(json.dumps(results_data, ensure_ascii=False), encoding="utf-8")

        collect_result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert collect_result["success"] is True
        assert collect_result["status"] == "collected"
        assert collect_result["total"] == 1
        assert collect_result["success_count"] == 1
        assert collect_result["fail_count"] == 0
        assert collect_result["results"][0]["success"] is True
