"""Tests for CharacterSheetService — build and collect character sheet requests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lfo.storyboard.prompts.character_sheet_v1 import render_character_sheet_prompt
from lfo.storyboard.storyboard import (
    Character,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)
from lfo.services.character_sheet_service import CharacterSheetService
from lfo.visual.image_request import ImageRequestBatch, write_results, ImageResultBatch, ImageResult


class TestRenderCharacterSheetPrompt:
    """Test the prompt template rendering."""

    def test_basic_render(self):
        char = Character(
            character_id="char_chenmo",
            name="Chen Mo",
            description="Young man in blue supermarket uniform",
            distinguishing_features="messy short black hair, smirk",
            signature_action="leans against counter",
            key_prop="steel-pipe scanner gun",
        )
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            style=StyleGuide(
                visual_style="2d_anime",
                medium_lock="Medium: 2D anime. NOT 3D.",
                style_keywords=["cinematic", "neon-lit"],
            ),
        )
        prompt = render_character_sheet_prompt(char, sb)
        assert "Chen Mo" in prompt
        assert "Young man in blue supermarket uniform" in prompt
        assert "leans against counter" in prompt
        assert "steel-pipe scanner gun" in prompt
        assert "Medium: 2D anime. NOT 3D." in prompt
        assert "cinematic, neon-lit" in prompt

    def test_no_signature_action(self):
        char = Character(
            character_id="char_001",
            name="Test",
            description="A character",
        )
        sb = Storyboard(project=ProjectInfo(project_id="proj_001"))
        prompt = render_character_sheet_prompt(char, sb)
        assert "natural standing pose" in prompt

    def test_no_key_prop(self):
        char = Character(
            character_id="char_001",
            name="Test",
            description="A character",
        )
        sb = Storyboard(project=ProjectInfo(project_id="proj_001"))
        prompt = render_character_sheet_prompt(char, sb)
        assert "Key prop:" not in prompt

    def test_no_style_info(self):
        char = Character(
            character_id="char_001",
            name="Test",
            description="A character",
        )
        sb = Storyboard(project=ProjectInfo(project_id="proj_001"))
        prompt = render_character_sheet_prompt(char, sb)
        # Should still render without errors
        assert "Test" in prompt
        assert "STYLE KEYWORDS:" in prompt
        # Empty medium_lock → trailing empty line
        assert prompt.endswith("\n\n")


class TestCharacterSheetServiceBuild:
    """Test building image requests."""

    def test_build_requests_for_all_characters(self):
        char1 = Character(character_id="char_001", name="Hero", description="Brave hero")
        char2 = Character(character_id="char_002", name="Villain", description="Evil villain")
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[char1, char2],
        )
        service = CharacterSheetService(db=MagicMock(), output_root="/tmp/test")
        batch = service.build_requests(sb, "proj_001")

        assert batch.phase == "character_sheets"
        assert len(batch.requests) == 2
        assert batch.requests[0].character_id == "char_001"
        assert batch.requests[1].character_id == "char_002"
        assert batch.requests[0].type == "character_sheet"
        assert batch.requests[0].output_path.endswith(".png")

    def test_skip_characters_with_existing_ref(self):
        char1 = Character(
            character_id="char_001",
            name="Hero",
            description="Brave",
            ref_image_path="workspace/proj/ref_images/char_001.png",
        )
        char2 = Character(character_id="char_002", name="Villain", description="Evil")
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[char1, char2],
        )
        service = CharacterSheetService(db=MagicMock(), output_root="/tmp/test")
        batch = service.build_requests(sb, "proj_001")

        assert len(batch.requests) == 1
        assert batch.requests[0].character_id == "char_002"

    def test_empty_characters(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[],
        )
        service = CharacterSheetService(db=MagicMock(), output_root="/tmp/test")
        batch = service.build_requests(sb, "proj_001")
        assert len(batch.requests) == 0


class TestCharacterSheetServiceCollect:
    """Test collecting agent results."""

    def test_collect_successful_results(self, tmp_path: Path):
        char = Character(character_id="char_001", name="Hero", description="Brave")
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[char],
        )
        service = CharacterSheetService(db=MagicMock(), output_root=str(tmp_path))

        # Build batch
        batch = service.build_requests(sb, "proj_001")

        # Create a fake image file
        img_path = tmp_path / "proj_001" / "ref_images" / "char_char_001_sheet.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_path.write_bytes(b"fake_png_data")

        # Write fake results
        results = ImageResultBatch(
            batch_id=batch.batch_id,
            results=[
                ImageResult(
                    request_id=batch.requests[0].request_id,
                    status="completed",
                    result_asset_path=str(img_path),
                ),
            ],
        )
        results_path = str(tmp_path / "proj_001" / "image_requests" / f"{batch.batch_id}_results.json")
        write_results(results, results_path)

        # Collect
        collected = service.collect_results(batch, results_path, sb)
        assert len(collected) == 1
        assert collected[0].success is True
        assert collected[0].asset_id != ""
        assert collected[0].file_path == str(img_path)

        # Verify backfill
        assert char.ref_asset_id != ""
        assert char.ref_image_path == str(img_path)

    def test_collect_failed_result(self, tmp_path: Path):
        char = Character(character_id="char_001", name="Hero", description="Brave")
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[char],
        )
        service = CharacterSheetService(db=MagicMock(), output_root=str(tmp_path))
        batch = service.build_requests(sb, "proj_001")

        # Write failed results
        results = ImageResultBatch(
            batch_id=batch.batch_id,
            results=[
                ImageResult(
                    request_id=batch.requests[0].request_id,
                    status="failed",
                    error="API timeout",
                ),
            ],
        )
        results_path = str(tmp_path / "results.json")
        write_results(results, results_path)

        collected = service.collect_results(batch, results_path, sb)
        assert collected[0].success is False
        assert "API timeout" in collected[0].error

    def test_collect_missing_file(self, tmp_path: Path):
        char = Character(character_id="char_001", name="Hero", description="Brave")
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            characters=[char],
        )
        service = CharacterSheetService(db=MagicMock(), output_root=str(tmp_path))
        batch = service.build_requests(sb, "proj_001")

        # Write results pointing to non-existent file
        results = ImageResultBatch(
            batch_id=batch.batch_id,
            results=[
                ImageResult(
                    request_id=batch.requests[0].request_id,
                    status="completed",
                    result_asset_path="workspace/nonexistent.png",
                ),
            ],
        )
        results_path = str(tmp_path / "results.json")
        write_results(results, results_path)

        collected = service.collect_results(batch, results_path, sb)
        assert collected[0].success is False
        assert "not found" in collected[0].error
