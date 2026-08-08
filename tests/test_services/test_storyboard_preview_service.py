"""Tests for StoryboardPreviewService."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.core.database import Database
from lfo.services.storyboard_preview_service import StoryboardPreviewService
from lfo.storyboard.storyboard import (
    Character,
    CharacterAppearance,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)
from tests.helpers.storyboard_fixtures import make_panel_storyboard


def make_storyboard(num_panels: int = 1, project_id: str = "proj-preview") -> Storyboard:
    """Create a storyboard with N panels (one beat each)."""
    return make_panel_storyboard(
        num_panels,
        project_id=project_id,
        title="Preview Test",
        style=StyleGuide(
            visual_style="realistic",
            medium_lock="Medium: Photorealistic cinematic footage.",
            style_keywords=["cinematic", "natural_light"],
        ),
    )


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def service(db) -> StoryboardPreviewService:
    return StoryboardPreviewService(db, output_root="/tmp/test")


class TestBuildRequests:
    """Test preview request building and sheet grouping."""

    def test_no_shots_empty_batch(self, service):
        storyboard = make_storyboard(0)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 0

    def test_single_shot_single_sheet(self, service):
        storyboard = make_storyboard(1)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 1
        assert batch.requests[0].type == "storyboard_preview"
        assert batch.requests[0].shot_range == ["panel_001"]

    def test_8_shots_single_sheet(self, service):
        storyboard = make_storyboard(8)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 1
        assert len(batch.requests[0].shot_range) == 8

    def test_9_shots_two_sheets(self, service):
        storyboard = make_storyboard(9)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 2
        assert batch.requests[0].shot_range == [f"panel_{i:03d}" for i in range(1, 9)]
        assert batch.requests[1].shot_range == ["panel_008", "panel_009"]

    def test_15_shots_two_sheets(self, service):
        storyboard = make_storyboard(15)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 2
        assert len(batch.requests[0].shot_range) == 8
        assert len(batch.requests[1].shot_range) == 8
        assert batch.requests[1].shot_range[0] == "panel_008"

    def test_16_shots_three_sheets(self, service):
        storyboard = make_storyboard(16)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 3
        assert batch.requests[0].shot_range[0] == "panel_001"
        assert batch.requests[1].shot_range[0] == "panel_008"
        assert batch.requests[2].shot_range[0] == "panel_015"

    def test_22_shots_three_sheets(self, service):
        storyboard = make_storyboard(22)
        batch = service.build_requests(storyboard, "proj-preview")
        assert len(batch.requests) == 3
        assert batch.requests[0].shot_range[0] == "panel_001"
        assert batch.requests[1].shot_range[0] == "panel_008"
        assert batch.requests[2].shot_range[0] == "panel_015"
        assert len(batch.requests[2].shot_range) == 8

    def test_prompt_contains_shot_descriptions(self, service):
        storyboard = make_storyboard(3)
        batch = service.build_requests(storyboard, "proj-preview")
        prompt = batch.requests[0].prompt
        assert "Panel 1" in prompt
        assert "Panel 2" in prompt
        assert "Panel 3" in prompt
        assert "Shot 1 description" in prompt
        assert "black and white" in prompt
        assert "stick-figure" in prompt

    def test_prompt_contains_medium_lock(self, service):
        storyboard = make_storyboard(2)
        batch = service.build_requests(storyboard, "proj-preview")
        prompt = batch.requests[0].prompt
        assert "Medium: Photorealistic" in prompt

    def test_prompt_contains_style_keywords(self, service):
        storyboard = make_storyboard(2)
        batch = service.build_requests(storyboard, "proj-preview")
        prompt = batch.requests[0].prompt
        assert "cinematic" in prompt

    def test_bridge_panel_in_prompt(self, service):
        storyboard = make_storyboard(9)
        batch = service.build_requests(storyboard, "proj-preview")
        sheet2_prompt = batch.requests[1].prompt
        assert "bridge from previous sheet" in sheet2_prompt

    def test_panel_descriptions_include_key_props(self, service):
        chenmo = Character(
            character_id="char_chenmo",
            name="陈默",
            key_prop="绑钢管的扫码枪",
        )
        appearance = [CharacterAppearance(character_id="char_chenmo", screen_position="center")]
        storyboard = make_panel_storyboard(
            2,
            project_id="proj-preview",
            title="Preview Test",
            with_characters=appearance,
            style=StyleGuide(
                visual_style="realistic",
                medium_lock="Medium: Photorealistic cinematic footage.",
                style_keywords=["cinematic", "natural_light"],
            ),
        )
        storyboard.characters = [chenmo]
        batch = service.build_requests(storyboard, "proj-preview")
        prompt = batch.requests[0].prompt
        assert "绑钢管的扫码枪" in prompt
        assert "carries" in prompt

    def test_template_has_hard_no_text_constraint(self, service):
        storyboard = make_storyboard(2)
        batch = service.build_requests(storyboard, "proj-preview")
        prompt = batch.requests[0].prompt
        assert "NO TEXT" in prompt
        assert "NO LABELS" in prompt
        assert "NO SPEECH BUBBLES" in prompt
        assert "HARD CONSTRAINT" in prompt
        assert "not render any text" in prompt

    def test_output_paths(self, service):
        storyboard = make_storyboard(16)
        batch = service.build_requests(storyboard, "proj-preview")
        paths = [r.output_path for r in batch.requests]
        assert len(paths) == len(set(paths))
        assert "storyboard_preview_sheet01" in paths[0]
        assert "storyboard_preview_sheet02" in paths[1]

    def test_batch_metadata(self, service):
        storyboard = make_storyboard(3)
        batch = service.build_requests(storyboard, "proj-preview")
        assert batch.project_id == "proj-preview"
        assert batch.phase == "storyboard_preview"
        assert batch.batch_id.startswith("batch_preview_")
        assert batch.created_at != ""


class TestWriteRequests:
    def test_write_creates_file(self, service, tmp_path):
        storyboard = make_storyboard(3)
        batch = service.build_requests(storyboard, "proj-preview")
        path = service.write_requests(batch, "novel1", "chapter1")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["batch_id"] == batch.batch_id
        assert data["phase"] == "storyboard_preview"

    def test_write_creates_directories(self, db, tmp_path):
        service = StoryboardPreviewService(db, output_root=str(tmp_path))
        storyboard = make_storyboard(2)
        batch = service.build_requests(storyboard, "proj-preview")
        path = service.write_requests(batch, "novel_deep", "chapter_deep")
        assert path.exists()
        assert "novel_deep" in str(path)
        assert "chapter_deep" in str(path)


class TestCollectResults:
    def _make_batch_and_results(self, service, storyboard, tmp_path):
        batch = service.build_requests(storyboard, "proj-preview")
        batch_path = service.write_requests(batch, "n1", "c1")
        results_path = batch_path.with_name(f"{batch.batch_id}_results.json")

        img_path = tmp_path / "preview.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        results_data = {
            "batch_id": batch.batch_id,
            "results": [
                {
                    "request_id": req.request_id,
                    "status": "completed",
                    "result_asset_path": str(img_path),
                    "result_seed": 42,
                    "error": "",
                    "completed_at": "2026-01-01T00:00:00Z",
                }
                for req in batch.requests
            ],
        }
        results_path.write_text(json.dumps(results_data), encoding="utf-8")
        return batch, results_path

    def test_collect_all_success(self, service, tmp_path):
        storyboard = make_storyboard(3)
        batch, results_path = self._make_batch_and_results(service, storyboard, tmp_path)
        collected = service.collect_results(batch, str(results_path), storyboard)
        assert len(collected) == 1
        assert all(c.success for c in collected)
        assert collected[0].asset_id != ""

    def test_collect_missing_file(self, service, tmp_path):
        storyboard = make_storyboard(1)
        batch, results_path = self._make_batch_and_results(service, storyboard, tmp_path)
        results_data = json.loads(results_path.read_text(encoding="utf-8"))
        results_data["results"][0]["result_asset_path"] = "/nonexistent/path.png"
        results_path.write_text(json.dumps(results_data), encoding="utf-8")
        collected = service.collect_results(batch, str(results_path), storyboard)
        assert len(collected) == 1
        assert collected[0].success is False
        assert "not found" in collected[0].error.lower()

    def test_collect_failed_status(self, service, tmp_path):
        storyboard = make_storyboard(1)
        batch, results_path = self._make_batch_and_results(service, storyboard, tmp_path)
        results_data = json.loads(results_path.read_text(encoding="utf-8"))
        results_data["results"][0]["status"] = "failed"
        results_data["results"][0]["error"] = "Model timeout"
        results_path.write_text(json.dumps(results_data), encoding="utf-8")
        collected = service.collect_results(batch, str(results_path), storyboard)
        assert collected[0].success is False
        assert "Model timeout" in collected[0].error

    def test_collect_results_file_not_found(self, service, tmp_path):
        storyboard = make_storyboard(1)
        batch = service.build_requests(storyboard, "proj-preview")
        collected = service.collect_results(batch, "/nonexistent/results.json", storyboard)
        assert len(collected) == 1
        assert collected[0].success is False
        assert "not found" in collected[0].error.lower()

    def test_asset_registered_in_db(self, service, tmp_path):
        storyboard = make_storyboard(1)
        batch, results_path = self._make_batch_and_results(service, storyboard, tmp_path)
        collected = service.collect_results(batch, str(results_path), storyboard)
        assert collected[0].success is True
        row = service.db.fetchone(
            "SELECT asset_id, asset_type, task_id FROM assets WHERE asset_id = ?",
            (collected[0].asset_id,),
        )
        assert row is not None
        assert row[0] == collected[0].asset_id
        assert row[1] == "image"
        assert row[2] is None
