"""Tests for visual.image_request — image request/response schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.visual.image_request import (
    ImageRequest,
    ImageRequestBatch,
    ImageResult,
    ImageResultBatch,
    read_batch,
    read_results,
    write_batch,
    write_results,
)


class TestImageRequest:
    def test_to_dict_round_trip(self):
        req = ImageRequest(
            request_id="imgreq_test_001",
            type="character_sheet",
            status="pending",
            prompt="A hero",
            aspect_ratio="16:9",
            resolution="2K",
            output_path="workspace/proj/ref_images/char_001.png",
            character_id="char_001",
        )
        d = req.to_dict()
        assert d["request_id"] == "imgreq_test_001"
        assert d["type"] == "character_sheet"
        assert d["character_id"] == "char_001"
        req2 = ImageRequest.from_dict(d)
        assert req2.request_id == req.request_id
        assert req2.prompt == req.prompt

    def test_shot_range_field(self):
        req = ImageRequest(
            type="storyboard_preview",
            shot_range=["shot_001", "shot_002"],
        )
        d = req.to_dict()
        assert d["shot_range"] == ["shot_001", "shot_002"]
        req2 = ImageRequest.from_dict(d)
        assert req2.shot_range == ["shot_001", "shot_002"]


class TestImageRequestBatch:
    def test_to_dict_round_trip(self):
        req = ImageRequest(request_id="r1", type="character_sheet")
        batch = ImageRequestBatch(
            batch_id="batch_001",
            project_id="proj_001",
            phase="character_sheets",
            requests=[req],
        )
        d = batch.to_dict()
        assert d["batch_id"] == "batch_001"
        assert d["phase"] == "character_sheets"
        assert len(d["requests"]) == 1
        batch2 = ImageRequestBatch.from_dict(d)
        assert batch2.batch_id == "batch_001"
        assert len(batch2.requests) == 1
        assert batch2.requests[0].request_id == "r1"


class TestImageResult:
    def test_to_dict_round_trip(self):
        result = ImageResult(
            request_id="r1",
            status="completed",
            result_asset_path="workspace/proj/ref_images/char.png",
            result_seed=42,
        )
        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["result_seed"] == 42
        result2 = ImageResult.from_dict(d)
        assert result2.request_id == "r1"
        assert result2.result_seed == 42


class TestImageResultBatch:
    def test_to_dict_round_trip(self):
        result = ImageResult(request_id="r1", status="completed")
        batch = ImageResultBatch(batch_id="batch_001", results=[result])
        d = batch.to_dict()
        assert d["batch_id"] == "batch_001"
        assert len(d["results"]) == 1
        batch2 = ImageResultBatch.from_dict(d)
        assert batch2.batch_id == "batch_001"


class TestFileIO:
    def test_write_and_read_batch(self, tmp_path: Path):
        req = ImageRequest(request_id="r1", type="character_sheet", prompt="test")
        batch = ImageRequestBatch(
            batch_id="batch_001",
            project_id="proj_001",
            phase="character_sheets",
            requests=[req],
        )
        path = str(tmp_path / "batch.json")
        write_batch(batch, path)

        # Verify file exists and is valid JSON
        assert Path(path).exists()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["batch_id"] == "batch_001"

        # Read back
        batch2 = read_batch(path)
        assert batch2.batch_id == "batch_001"
        assert len(batch2.requests) == 1
        assert batch2.requests[0].prompt == "test"

    def test_write_and_read_results(self, tmp_path: Path):
        result = ImageResult(
            request_id="r1",
            status="completed",
            result_asset_path="workspace/proj/img.png",
        )
        batch = ImageResultBatch(batch_id="batch_001", results=[result])
        path = str(tmp_path / "results.json")
        write_results(batch, path)

        batch2 = read_results(path)
        assert batch2.batch_id == "batch_001"
        assert len(batch2.results) == 1
        assert batch2.results[0].status == "completed"

    def test_read_missing_batch_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_batch(str(tmp_path / "nonexistent.json"))

    def test_read_missing_results_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_results(str(tmp_path / "nonexistent.json"))
