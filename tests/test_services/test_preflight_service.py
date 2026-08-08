"""Tests for PreflightService."""
from __future__ import annotations

import pytest

from lfo.config.machine_profile import ComfyUIConfig, HardwareConfig, MachineProfile, StorageConfig
from lfo.environment.checks.base import CheckResult, CheckSeverity, CheckStatus
from lfo.environment.fingerprint import EnvironmentSnapshot
from lfo.services.preflight_service import PreflightContext, PreflightService


@pytest.fixture
def basic_profile():
    return MachineProfile(
        machine_id="test",
        comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
        storage=StorageConfig(
            comfy_input="/tmp/input",
            comfy_output="/tmp/output",
            lfo_cache="/tmp/cache",
        ),
        hardware=HardwareConfig(gpu_name="RTX 5080", vram_mib=16384, ram_mib=32768),
    )


class TestPreflightContext:
    def test_defaults(self):
        ctx = PreflightContext(project_id="p1", machine_id="m1")
        assert ctx.project_id == "p1"
        assert ctx.required_workflow_ids == set()
        assert ctx.required_model_ids == set()
        assert ctx.required_tools == set()

    def test_with_requirements(self):
        ctx = PreflightContext(
            project_id="p1",
            machine_id="m1",
            required_workflow_ids={"h3_standard_t2v"},
            required_model_ids={"minimax_h3_fl2va_int8"},
            required_tools={"ffmpeg", "python"},
        )
        assert "h3_standard_t2v" in ctx.required_workflow_ids
        assert "ffmpeg" in ctx.required_tools


class TestPreflightService:
    def test_init(self, basic_profile):
        svc = PreflightService(basic_profile)
        assert svc.profile == basic_profile

    def test_preflight_basic(self, basic_profile):
        svc = PreflightService(basic_profile)
        ctx = PreflightContext(
            project_id="test-proj",
            machine_id="test",
            required_tools={"ffmpeg"},
        )
        results = svc.preflight(ctx)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_preflight_with_snapshot(self, basic_profile):
        svc = PreflightService(basic_profile)
        snapshot = EnvironmentSnapshot(
            machine_id="test",
            captured_at="2024-01-01T00:00:00Z",
            comfyui_root="/comfy",
            comfyui_version="0.30.0",
            input_root="/input",
            output_root="/output",
            python_version="3.12",
            torch_version="2.5",
            gpu_name="RTX 5080",
        )
        ctx = PreflightContext(project_id="p", machine_id="test")
        results = svc.preflight(ctx, snapshot=snapshot)
        assert isinstance(results, list)

    def test_has_blockers_false(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.INFO, CheckStatus.PASSED, "ok"),
        ]
        assert svc.has_blockers(results) is False

    def test_has_blockers_true(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.BLOCKER, CheckStatus.FAILED, "blocked"),
        ]
        assert svc.has_blockers(results) is True

    def test_has_blockers_warning_not_blocker(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.WARNING, CheckStatus.FAILED, "warn"),
        ]
        assert svc.has_blockers(results) is False

    def test_get_status_passed(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.INFO, CheckStatus.PASSED, "ok"),
        ]
        assert svc.get_status(results) == "passed"

    def test_get_status_blocked(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.BLOCKER, CheckStatus.FAILED, "blocked"),
        ]
        assert svc.get_status(results) == "blocked"

    def test_get_status_warning(self, basic_profile):
        svc = PreflightService(basic_profile)
        results = [
            CheckResult("test", CheckSeverity.WARNING, CheckStatus.FAILED, "warn"),
        ]
        assert svc.get_status(results) == "warning"
