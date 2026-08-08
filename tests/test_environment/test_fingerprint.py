"""Tests for environment fingerprint."""
from __future__ import annotations

from lfo.environment.discovery import DiscoveredEnvironment
from lfo.environment.fingerprint import (
    EnvironmentSnapshot,
    compute_execution_environment_hash,
    create_environment_snapshot,
)


class TestEnvironmentSnapshot:
    def test_defaults(self):
        snap = EnvironmentSnapshot(
            machine_id="test",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="",
            comfyui_version="",
            input_root="",
            output_root="",
            python_version="",
            torch_version="",
            gpu_name="",
        )
        assert snap.machine_id == "test"
        assert snap.execution_environment_hash != ""

    def test_hash_excludes_paths(self):
        """Same version but different paths should produce same hash."""
        snap1 = EnvironmentSnapshot(
            machine_id="m1",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="/path/a",
            comfyui_version="0.30.0",
            input_root="/input/a",
            output_root="/output/a",
            python_version="3.12",
            torch_version="2.5.0",
            gpu_name="RTX 5080",
        )
        snap2 = EnvironmentSnapshot(
            machine_id="m2",
            captured_at="2024-01-02T00:00:00Z",
            comfyui_root="/completely/different/path",
            comfyui_version="0.30.0",
            input_root="/other/input",
            output_root="/other/output",
            python_version="3.12",
            torch_version="2.5.0",
            gpu_name="RTX 5080",
        )
        assert snap1.execution_environment_hash == snap2.execution_environment_hash

    def test_hash_changes_with_version(self):
        snap1 = EnvironmentSnapshot(
            machine_id="m1",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="",
            comfyui_version="0.30.0",
            input_root="",
            output_root="",
            python_version="",
            torch_version="",
            gpu_name="",
        )
        snap2 = EnvironmentSnapshot(
            machine_id="m1",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="",
            comfyui_version="0.31.0",
            input_root="",
            output_root="",
            python_version="",
            torch_version="",
            gpu_name="",
        )
        assert snap1.execution_environment_hash != snap2.execution_environment_hash

    def test_to_dict_round_trip(self):
        snap = EnvironmentSnapshot(
            machine_id="test",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="/root",
            comfyui_version="0.30.0",
            input_root="/in",
            output_root="/out",
            python_version="3.12",
            torch_version="2.5",
            gpu_name="RTX 5080",
            extra={"key": "value"},
        )
        d = snap.to_dict()
        restored = EnvironmentSnapshot.from_dict(d)
        assert restored.machine_id == snap.machine_id
        assert restored.comfyui_version == snap.comfyui_version
        assert restored.extra == snap.extra


class TestCreateEnvironmentSnapshot:
    def test_from_discovery(self):
        discovery = DiscoveredEnvironment(
            gpu_name="RTX 5080",
            vram_mib=16384,
        )
        snap = create_environment_snapshot(
            machine_id="test-machine",
            discovery=discovery,
            comfyui_version="0.30.0",
        )
        assert snap.machine_id == "test-machine"
        assert snap.gpu_name == "RTX 5080"
        assert snap.comfyui_version == "0.30.0"
        assert snap.captured_at != ""


class TestComputeExecutionEnvironmentHash:
    def test_deterministic(self):
        h1 = compute_execution_environment_hash(
            workflow_hashes={"wf1": "abc123"},
            model_fingerprints={"m1": "def456"},
        )
        h2 = compute_execution_environment_hash(
            workflow_hashes={"wf1": "abc123"},
            model_fingerprints={"m1": "def456"},
        )
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = compute_execution_environment_hash(workflow_hashes={"wf1": "aaa"})
        h2 = compute_execution_environment_hash(workflow_hashes={"wf1": "bbb"})
        assert h1 != h2

    def test_empty(self):
        h = compute_execution_environment_hash()
        assert len(h) == 64  # SHA-256 hex
