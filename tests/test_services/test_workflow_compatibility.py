"""Tests for WorkflowCompatibilityService."""
from __future__ import annotations

import pytest

from lfo.config.machine_profile import MachineProfile
from lfo.services.workflow_compatibility import WorkflowCompatibilityService


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return MachineProfile(
        machine_id="test-machine",
        hardware=MachineProfile().hardware.__class__(gpu_name="RTX 5080", vram_mib=16384),
    )


from lfo.config.machine_profile import HardwareConfig


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return MachineProfile(
        machine_id="test-machine",
        hardware=HardwareConfig(gpu_name="RTX 5080", vram_mib=16384),
    )


class TestWorkflowCompatibilityService:
    def test_init(self, profile):
        svc = WorkflowCompatibilityService(profile)
        assert svc.machine_id == "test-machine"

    def test_compatibility_dir(self, profile):
        svc = WorkflowCompatibilityService(profile)
        d = svc.get_compatibility_dir()
        assert d.exists()
        assert "test-machine" in str(d)

    def test_unknown_status(self, profile):
        svc = WorkflowCompatibilityService(profile)
        assert svc.get_machine_status("h3_standard_t2v") == "unknown"

    def test_record_and_check_static_valid(self, profile):
        svc = WorkflowCompatibilityService(profile)
        svc.record_static_valid("h3_standard_t2v")
        assert svc.get_machine_status("h3_standard_t2v") == "static_valid"

        result = svc.check_static_validity("h3_standard_t2v")
        assert result.status.value == "passed"

    def test_record_and_check_runtime_compatible(self, profile):
        svc = WorkflowCompatibilityService(profile)
        svc.record_runtime_compatible("h3_standard_i2v")
        assert svc.get_machine_status("h3_standard_i2v") == "runtime_compatible"

        result = svc.check_runtime_compatibility("h3_standard_i2v")
        assert result.status.value == "passed"

    def test_record_smoke_test(self, profile):
        svc = WorkflowCompatibilityService(profile)
        svc.record_smoke_test("h3_standard_r2v", passed=True)
        assert svc.get_machine_status("h3_standard_r2v") == "smoke_tested"

    def test_smoke_failed(self, profile):
        svc = WorkflowCompatibilityService(profile)
        svc.record_smoke_test("h3_standard_r2v", passed=False)
        assert svc.get_machine_status("h3_standard_r2v") == "smoke_failed"

    def test_static_valid_fails_before_recording(self, profile):
        svc = WorkflowCompatibilityService(profile)
        result = svc.check_static_validity("h3_standard_t2v")
        assert result.status.value == "failed"

    def test_runtime_compatible_fails_before_recording(self, profile):
        svc = WorkflowCompatibilityService(profile)
        result = svc.check_runtime_compatibility("h3_standard_t2v")
        assert result.status.value == "failed"

    def test_compare_baseline_no_baseline(self, profile):
        svc = WorkflowCompatibilityService(profile)
        comparison = svc.compare_baseline("h3_standard_t2v")
        assert comparison["changed"] is True

    def test_compare_baseline_with_baseline(self, profile):
        svc = WorkflowCompatibilityService(profile)
        svc.record_runtime_compatible("h3_standard_t2v")
        comparison = svc.compare_baseline("h3_standard_t2v")
        # Same GPU and VRAM as baseline, so no changes
        assert comparison["changed"] is False

    def test_compare_baseline_gpu_changed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        # Record with one GPU
        profile1 = MachineProfile(
            machine_id="changed-machine",
            hardware=HardwareConfig(gpu_name="RTX 4090", vram_mib=24576),
        )
        svc1 = WorkflowCompatibilityService(profile1)
        svc1.record_runtime_compatible("h3_standard_t2v")

        # Now inspect with different GPU
        profile2 = MachineProfile(
            machine_id="changed-machine",
            hardware=HardwareConfig(gpu_name="RTX 5090", vram_mib=32768),
        )
        svc2 = WorkflowCompatibilityService(profile2)
        comparison = svc2.compare_baseline("h3_standard_t2v")
        assert comparison["changed"] is True
        assert any("GPU" in d for d in comparison["details"])
