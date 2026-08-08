"""Tests for CLI preview command."""
from __future__ import annotations

import json
from pathlib import Path

from lfo.cli.preview_cmd import cmd_preview_build, cmd_preview_collect


def make_storyboard_json(tmp_path: Path, num_shots: int = 1) -> Path:
    """Create a minimal valid storyboard JSON with shots."""
    shots = []
    for i in range(num_shots):
        shots.append({
            "shot_id": f"shot_{i + 1:03d}",
            "display_index": i + 1,
            "scene_id": "scene_001",
            "description": f"Shot {i + 1} description",
            "camera": {"shot_size": "medium", "movement": "static", "angle": "eye_level"},
            "continuity": {"start_frame_needed": i > 0},
            "generation_hint": {},
        })

    data = {
        "project": {"project_id": "proj-preview-test", "title": "Preview Test"},
        "shots": shots,
    }

    sb_path = tmp_path / "test_storyboard.json"
    sb_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return sb_path


class TestCmdPreviewBuild:
    """Test lfo preview build command."""

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
        sb_path = tmp_path / "empty.json"
        sb_path.write_text(
            json.dumps({"project": {"project_id": "proj-empty"}, "shots": []}),
            encoding="utf-8",
        )
        result = cmd_preview_build(storyboard_path=str(sb_path))
        assert result["success"] is False
        assert "no shots" in result["error"].lower()

    def test_builds_requests(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_shots=3)
        result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["status"] == "waiting"
        assert result["requests_count"] == 1
        assert result["total_shots"] == 3
        assert "batch_id" in result
        assert Path(result["batch_path"]).exists()

    def test_multi_sheet(self, tmp_path):
        """16 shots should produce 3 preview sheets."""
        sb_path = make_storyboard_json(tmp_path, num_shots=16)
        result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["requests_count"] == 3
        assert result["total_shots"] == 16


class TestCmdPreviewCollect:
    """Test lfo preview collect command."""

    def test_empty_storyboard_path(self):
        result = cmd_preview_collect(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_preview_collect(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_no_image_requests_dir(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_shots=1)
        result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "image_requests" in result["error"].lower()

    def test_no_results_file(self, tmp_path):
        sb_path = make_storyboard_json(tmp_path, num_shots=3)
        # Build first to create the batch file
        cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))

        result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "generate images" in result["error"].lower() or "not found" in result["error"].lower()

    def test_collect_results(self, tmp_path):
        """Full flow: build → simulate agent → collect."""
        sb_path = make_storyboard_json(tmp_path, num_shots=3)

        # Build requests
        build_result = cmd_preview_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert build_result["success"] is True

        # Simulate agent writing results
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

        # Collect
        collect_result = cmd_preview_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert collect_result["success"] is True
        assert collect_result["status"] == "collected"
        assert collect_result["total"] == 1
        assert collect_result["success_count"] == 1
        assert collect_result["fail_count"] == 0
        assert collect_result["results"][0]["success"] is True
