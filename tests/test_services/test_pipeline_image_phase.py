"""Tests for PipelineService Phase 0 (image generation)."""
from __future__ import annotations

from unittest.mock import MagicMock

from lfo.core.database import Database
from lfo.services.pipeline_service import PipelineService
from lfo.storyboard.storyboard import (
    Character,
    ProjectInfo,
    Storyboard,
)


def make_storyboard_with_characters(num_characters: int = 1, with_ref: bool = False) -> Storyboard:
    """Create a storyboard with characters."""
    characters = []
    for i in range(num_characters):
        char = Character(
            character_id=f"char_{i + 1:03d}",
            name=f"Character {i + 1}",
            gender="female",
            age="20-30",
            distinguishing_features="",
            ref_image_path=f"/tmp/existing_{i}.png" if with_ref else "",
            ref_asset_id=f"asset-existing-{i}" if with_ref else "",
            role="protagonist",
            description="A character",
        )
        characters.append(char)

    return Storyboard(
        project=ProjectInfo(project_id="proj-img-phase", title="Image Phase Test"),
        shots=[],
        characters=characters,
    )


class TestRunImagePhase:
    """Test _run_image_phase method."""

    def test_all_have_refs_skips(self):
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db)
        storyboard = make_storyboard_with_characters(2, with_ref=True)

        result = service._run_image_phase(storyboard)

        assert result["status"] == "skipped"
        assert result["requests_count"] == 0

    def test_builds_requests_when_missing_refs(self, tmp_path):
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db, output_dir=str(tmp_path))
        storyboard = make_storyboard_with_characters(2, with_ref=False)

        result = service._run_image_phase(storyboard)

        assert result["status"] == "waiting"
        assert result["requests_count"] == 2
        assert "batch_id" in result
        assert "batch_path" in result
        assert "results_path" in result

    def test_collects_when_results_exist(self, tmp_path):
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db, output_dir=str(tmp_path))
        storyboard = make_storyboard_with_characters(1, with_ref=False)

        # First call writes batch
        first_result = service._run_image_phase(storyboard)
        assert first_result["status"] == "waiting"

        # Simulate agent writing results
        import json
        from pathlib import Path
        results_path = Path(first_result["results_path"])
        batch_path = Path(first_result["batch_path"])
        batch_data = json.loads(batch_path.read_text(encoding="utf-8"))

        # Create dummy image
        img_path = tmp_path / "char_sheet.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        results_data = {
            "batch_id": first_result["batch_id"],
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

        # Second call should collect
        second_result = service._run_image_phase(storyboard)
        assert second_result["status"] == "collected"
        assert second_result["success_count"] == 1
        assert second_result["fail_count"] == 0


class TestExecuteWithImagePhase:
    """Test execute() with image phase integration."""

    def test_skip_images_bypasses_phase(self):
        """skip_images=True should skip image phase entirely."""
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db, skip_images=True)
        storyboard = make_storyboard_with_characters(2, with_ref=False)

        # Mock graph service
        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = MagicMock(tasks=[])

        result = service.execute(storyboard)

        # Should have empty image phase (skipped)
        assert result.image_phase == {}
        assert result.paused is False

    def test_image_phase_waits_when_no_results(self, tmp_path):
        """When images are needed but not yet generated, pipeline pauses."""
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db, output_dir=str(tmp_path))
        storyboard = make_storyboard_with_characters(1, with_ref=False)

        # Mock graph service (should not be reached)
        service.graph_service = MagicMock()

        result = service.execute(storyboard)

        assert result.paused is True
        assert result.image_phase["status"] == "waiting"
        assert "image_phase" in result.errors

    def test_image_phase_continues_when_results_exist(self, tmp_path):
        """When results file exists, pipeline collects and continues."""
        import json
        db = Database(":memory:")
        db.init_schema()
        service = PipelineService(db, output_dir=str(tmp_path))
        storyboard = make_storyboard_with_characters(1, with_ref=False)

        # Manually create batch and results using the same paths as _run_image_phase
        batch = service.character_sheet_service.build_requests(storyboard, "proj-img-phase")
        batch_path = service.character_sheet_service.write_requests(
            batch, service.novel_id, service.chapter_id,
        )
        results_path = batch_path.with_name(f"{batch.batch_id}_results.json")

        img_path = tmp_path / "char_sheet.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        batch_data = json.loads(batch_path.read_text(encoding="utf-8"))
        results_data = {
            "batch_id": batch.batch_id,
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

        # Mock graph service to return empty tasks
        service.graph_service = MagicMock()
        service.graph_service.build_graph.return_value = MagicMock(tasks=[])

        result = service.execute(storyboard)

        assert result.paused is False
        assert result.image_phase["status"] == "collected"
        assert result.image_phase["success_count"] == 1
