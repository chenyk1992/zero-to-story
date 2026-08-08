"""Tests for EnvironmentSnapshotService."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from lfo.config.machine_profile import ComfyUIConfig, MachineProfile
from lfo.core.database import Database
from lfo.environment.discovery import DiscoveredEnvironment
from lfo.environment.fingerprint import EnvironmentSnapshot
from lfo.services.environment_snapshot_service import (
    EnvironmentSnapshotService,
)


@pytest.fixture
def db() -> Database:
    """Create an in-memory database with schema."""
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def service(db: Database) -> EnvironmentSnapshotService:
    return EnvironmentSnapshotService(db)


@pytest.fixture
def machine_profile() -> MachineProfile:
    return MachineProfile(
        machine_id="test-machine",
        comfyui=ComfyUIConfig(base_url="http://127.0.0.1:8188", root="D:/cyuiEnv"),
    )


def make_snapshot(
    machine_id: str = "test-machine",
    comfyui_version: str = "0.30.0",
) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        machine_id=machine_id,
        captured_at="2026-01-01T00:00:00.000000Z",
        comfyui_root="D:/cyuiEnv",
        comfyui_version=comfyui_version,
        input_root="D:/cyuiEnv/input",
        output_root="D:/cyuiEnv/output",
        python_version="3.12.10",
        torch_version="2.5.0",
        gpu_name="NVIDIA GeForce RTX 5080",
    )


class TestSaveSnapshot:
    def test_save_and_retrieve(self, service: EnvironmentSnapshotService):
        snapshot = make_snapshot()
        record = service.save_snapshot(snapshot)
        assert record.snapshot_id is not None
        assert record.machine_id == "test-machine"
        assert record.execution_environment_hash == snapshot.execution_environment_hash

    def test_save_persists_all_fields(self, service: EnvironmentSnapshotService):
        snapshot = make_snapshot()
        record = service.save_snapshot(snapshot)
        retrieved = service.get_by_id(record.snapshot_id)
        assert retrieved is not None
        assert retrieved.machine_id == "test-machine"
        assert retrieved.snapshot_json["comfyui_version"] == "0.30.0"
        assert retrieved.snapshot_json["gpu_name"] == "NVIDIA GeForce RTX 5080"


class TestGetLatest:
    def test_no_snapshots(self, service: EnvironmentSnapshotService):
        result = service.get_latest("nonexistent")
        assert result is None

    def test_returns_most_recent(self, service: EnvironmentSnapshotService):
        old = make_snapshot()
        old.captured_at = "2026-01-01T00:00:00.000000Z"
        service.save_snapshot(old)

        new = make_snapshot()
        new.captured_at = "2026-01-02T00:00:00.000000Z"
        service.save_snapshot(new)

        latest = service.get_latest("test-machine")
        assert latest is not None
        assert latest.captured_at == "2026-01-02T00:00:00.000000Z"


class TestGetById:
    def test_existing(self, service: EnvironmentSnapshotService):
        snapshot = make_snapshot()
        record = service.save_snapshot(snapshot)
        retrieved = service.get_by_id(record.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == record.snapshot_id

    def test_nonexistent(self, service: EnvironmentSnapshotService):
        result = service.get_by_id("nonexistent-id")
        assert result is None


class TestListSnapshots:
    def test_empty(self, service: EnvironmentSnapshotService):
        results = service.list_snapshots("nonexistent")
        assert results == []

    def test_limit(self, service: EnvironmentSnapshotService):
        for i in range(5):
            s = make_snapshot()
            s.captured_at = f"2026-01-0{i + 1}T00:00:00.000000Z"
            service.save_snapshot(s)

        results = service.list_snapshots("test-machine", limit=3)
        assert len(results) == 3

    def test_order(self, service: EnvironmentSnapshotService):
        for i in range(3):
            s = make_snapshot()
            s.captured_at = f"2026-01-0{i + 1}T00:00:00.000000Z"
            service.save_snapshot(s)

        results = service.list_snapshots("test-machine")
        # Most recent first
        assert results[0].captured_at > results[1].captured_at


class TestHashMatches:
    def test_matching_hash(self, service: EnvironmentSnapshotService):
        snapshot = make_snapshot()
        record = service.save_snapshot(snapshot)
        assert service.hash_matches(
            record.snapshot_id, snapshot.execution_environment_hash
        )

    def test_mismatched_hash(self, service: EnvironmentSnapshotService):
        snapshot = make_snapshot()
        record = service.save_snapshot(snapshot)
        assert not service.hash_matches(record.snapshot_id, "different-hash")

    def test_nonexistent_snapshot(self, service: EnvironmentSnapshotService):
        assert not service.hash_matches("nonexistent", "any-hash")


class TestCaptureAndSave:
    def test_capture_uses_discovery(
        self,
        service: EnvironmentSnapshotService,
        machine_profile: MachineProfile,
    ):
        mock_discovery = DiscoveredEnvironment(
            comfyui_running=True,
            comfyui_pid=1234,
            comfyui_port=8188,
            gpu_name="RTX 5080",
            vram_mib=16384,
            has_ffmpeg=True,
        )
        with patch("lfo.services.environment_snapshot_service.discover_environment",
            return_value=mock_discovery,
        ):
            record = service.capture_and_save(machine_profile)

        assert record.machine_id == "test-machine"
        assert record.snapshot_json["machine_id"] == "test-machine"
