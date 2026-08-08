"""Unit tests for RecoveryManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import AssetRecord, CollectResult, ComfyOutputCollector
from lfo.comfy.exceptions import ComfyUnreachableError
from lfo.comfy.recovery import RecoveryManager

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_client():
    return MagicMock(spec=ComfyApiClient)


@pytest.fixture
def mock_collector():
    return MagicMock(spec=ComfyOutputCollector)


@pytest.fixture
def manager(mock_client, mock_collector):
    return RecoveryManager(client=mock_client, collector=mock_collector)


@pytest.fixture
def db_record() -> dict:
    return {
        "prompt_id": "prompt-abc",
        "attempt_dir": "lfo/attempt-001",
        "project_id": "proj-1",
        "task_id": "task-1",
        "attempt_id": "attempt-001",
    }


@pytest.fixture
def sample_asset() -> AssetRecord:
    return AssetRecord(
        path=Path("/fake/video.mp4"),
        sha256="abc123",
        project_id="proj-1",
        task_id="task-1",
        attempt_id="attempt-001",
        size_bytes=1024,
    )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


class TestRecoverAttempt:
    def test_history_completed_and_assets_found(
        self, manager, mock_client, mock_collector, db_record, sample_asset
    ):
        mock_client.get_history.return_value = {
            "prompt-abc": {"status": {"completed": True}}
        }
        mock_collector.collect.return_value = CollectResult(
            success=True, assets=[sample_asset]
        )

        result = manager.recover_attempt(db_record)
        assert result.recovered is True
        assert result.asset_record == sample_asset
        assert result.method_used == "history+scan"

    def test_no_history_but_assets_on_disk(
        self, manager, mock_client, mock_collector, db_record, sample_asset
    ):
        mock_client.get_history.return_value = {}
        mock_collector.collect.return_value = CollectResult(
            success=True, assets=[sample_asset]
        )

        result = manager.recover_attempt(db_record)
        assert result.recovered is True
        assert result.method_used == "scan"

    def test_history_completed_but_no_files(
        self, manager, mock_client, mock_collector, db_record
    ):
        mock_client.get_history.return_value = {
            "prompt-abc": {"status": {"completed": True}}
        }
        mock_collector.collect.return_value = CollectResult(success=False)

        result = manager.recover_attempt(db_record)
        assert result.recovered is False
        assert result.method_used == "history"
        assert "no output files" in result.error.lower()

    def test_no_history_no_files(
        self, manager, mock_client, mock_collector, db_record
    ):
        mock_client.get_history.return_value = {}
        mock_collector.collect.return_value = CollectResult(success=False)

        result = manager.recover_attempt(db_record)
        assert result.recovered is False
        assert result.method_used == "none"

    def test_client_unreachable(
        self, manager, mock_client, mock_collector, db_record, sample_asset
    ):
        mock_client.get_history.side_effect = ComfyUnreachableError("down")
        mock_collector.collect.return_value = CollectResult(
            success=True, assets=[sample_asset]
        )

        result = manager.recover_attempt(db_record)
        assert result.recovered is True
        assert result.method_used == "scan"


class TestRecoverUncertainAttempt:
    def test_history_confirms_and_assets_found(
        self, manager, mock_client, mock_collector, db_record, sample_asset
    ):
        mock_client.get_history.return_value = {
            "prompt-abc": {"status": {"completed": True}}
        }
        mock_collector.collect.return_value = CollectResult(
            success=True, assets=[sample_asset]
        )

        result = manager.recover_uncertain_attempt(db_record)
        assert result.recovered is True
        assert result.method_used == "history_confirmed"

    def test_history_exists_but_no_outputs_yet(
        self, manager, mock_client, mock_collector, db_record
    ):
        mock_client.get_history.return_value = {
            "prompt-abc": {"status": {"completed": False}}
        }
        mock_collector.collect.return_value = CollectResult(success=False)

        result = manager.recover_uncertain_attempt(db_record)
        assert result.recovered is False
        assert result.method_used == "history"

    def test_no_history_but_files_on_disk(
        self, manager, mock_client, mock_collector, db_record, sample_asset
    ):
        mock_client.get_history.return_value = {}
        mock_collector.collect.return_value = CollectResult(
            success=True, assets=[sample_asset]
        )

        result = manager.recover_uncertain_attempt(db_record)
        assert result.recovered is True
        assert result.method_used == "scan_only"

    def test_completely_lost(
        self, manager, mock_client, mock_collector, db_record
    ):
        mock_client.get_history.return_value = {}
        mock_collector.collect.return_value = CollectResult(success=False)

        result = manager.recover_uncertain_attempt(db_record)
        assert result.recovered is False
        assert result.method_used == "none"
        assert "not found" in result.error.lower()
