"""Tests for CLI images command."""
from __future__ import annotations

import json
from pathlib import Path

from lfo.cli.images_cmd import cmd_images_build, cmd_images_collect


def make_storyboard_json(tmp_path: Path, num_characters: int = 1, with_ref: bool = False) -> Path:
    """Create a minimal valid storyboard JSON with characters."""
    characters = []
    for i in range(num_characters):
        char = {
            "character_id": f"char_{i + 1:03d}",
            "name": f"Character {i + 1}",
            "gender": "female" if i % 2 == 0 else "male",
            "age": "20-30",
            "distinguishing_features": "",
            "signature_action": "drinks coffee",
            "key_prop": "laptop",
            "role": "protagonist",
            "description": "A software engineer",
        }
        if with_ref:
            char["ref_image_path"] = f"/tmp/existing_ref_{i}.png"
            char["ref_asset_id"] = f"asset-existing-{i}"
        characters.append(char)

    data = {
        "project": {"project_id": "proj-img-test", "title": "Image Test"},
        "characters": characters,
        "shots": [
            {
                "shot_id": "shot_001",
                "display_index": 1,
                "scene_id": "scene_001",
                "description": "A shot",
                "camera": {"shot_size": "medium", "movement": "static"},
                "continuity": {"start_frame_needed": False},
                "generation_hint": {},
            }
        ],
    }

    sb_path = tmp_path / "test_storyboard.json"
    sb_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return sb_path


class TestCmdImagesBuild:
    """Test lfo images build command."""

    def test_empty_storyboard_path(self):
        result = cmd_images_build(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_images_build(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        result = cmd_images_build(storyboard_path=str(bad_file))
        assert result["success"] is False
        assert "failed to load" in result["error"].lower()

    def test_all_have_refs_skips(self, tmp_path):
        """All characters already have ref images — should skip."""
        sb_path = make_storyboard_json(tmp_path, num_characters=2, with_ref=True)
        result = cmd_images_build(storyboard_path=str(sb_path))
        assert result["success"] is True
        assert result["status"] == "skipped"
        assert result["requests_count"] == 0

    def test_builds_requests(self, tmp_path):
        """Characters without refs should produce requests."""
        sb_path = make_storyboard_json(tmp_path, num_characters=2, with_ref=False)
        result = cmd_images_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["status"] == "waiting"
        assert result["requests_count"] == 2
        assert "batch_id" in result
        assert "batch_path" in result
        assert "results_path" in result
        assert Path(result["batch_path"]).exists()

    def test_partial_refs(self, tmp_path):
        """Mix of characters with and without refs — only missing ones get requests."""
        sb_path = make_storyboard_json(tmp_path, num_characters=1, with_ref=True)
        # Add a character without ref
        data = json.loads(sb_path.read_text(encoding="utf-8"))
        data["characters"].append({
            "character_id": "char_002",
            "name": "Character 2",
            "gender": "male",
            "age": "20-30",
            "distinguishing_features": "",
            "signature_action": "",
            "key_prop": "",
            "role": "supporting",
            "description": "A designer",
        })
        sb_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = cmd_images_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is True
        assert result["status"] == "waiting"
        assert result["requests_count"] == 1


class TestCmdImagesCollect:
    """Test lfo images collect command."""

    def test_empty_storyboard_path(self):
        result = cmd_images_collect(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_images_collect(storyboard_path=str(tmp_path / "nonexistent.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_no_image_requests_dir(self, tmp_path):
        """No image_requests directory — should fail with helpful message."""
        sb_path = make_storyboard_json(tmp_path, num_characters=1)
        result = cmd_images_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "image_requests" in result["error"].lower()

    def test_no_results_file(self, tmp_path):
        """Batch file exists but no results file yet."""
        sb_path = make_storyboard_json(tmp_path, num_characters=1)
        # Build first to create the batch file
        cmd_images_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))

        result = cmd_images_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert result["success"] is False
        assert "results file not found" in result["error"].lower() or "generate images" in result["error"].lower()

    def test_collect_results(self, tmp_path):
        """Full flow: build → simulate agent → collect."""
        sb_path = make_storyboard_json(tmp_path, num_characters=1)

        # Build requests
        build_result = cmd_images_build(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert build_result["success"] is True
        assert build_result["status"] == "waiting"

        # Simulate agent writing results
        results_path = Path(build_result["results_path"])
        batch_path = Path(build_result["batch_path"])
        batch_data = json.loads(batch_path.read_text(encoding="utf-8"))

        # Create a dummy image file
        img_path = tmp_path / "test_char.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal PNG header

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

        # Now collect
        collect_result = cmd_images_collect(storyboard_path=str(sb_path), output_dir=str(tmp_path))
        assert collect_result["success"] is True
        assert collect_result["status"] == "collected"
        assert collect_result["total"] == 1
        assert collect_result["success_count"] == 1
        assert collect_result["fail_count"] == 0
        assert collect_result["results"][0]["character_id"] == "char_001"
        assert collect_result["results"][0]["success"] is True
