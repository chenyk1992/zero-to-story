"""Tests for CLI command functions."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from lfo.cli.config_cmd import cmd_config_resolve
from lfo.cli.doctor_cmd import cmd_doctor
from lfo.cli.machine_cmd import (
    cmd_machine_add,
    cmd_machine_inspect,
    cmd_machine_list,
    cmd_machine_validate,
)
from lfo.cli.preflight_cmd import cmd_preflight
from lfo.cli.setup import cmd_setup
from lfo.cli.workflow_cmd import cmd_workflow_fork


class TestCmdSetup:
    def test_setup_does_not_create_runtime_database_or_snapshot(self, monkeypatch):
        discovery = SimpleNamespace(comfyui_running=False, comfyui_pid=None,
                                    gpu_name="test", vram_mib=1000)
        monkeypatch.setattr(
            "lfo.services.environment_service.EnvironmentService.discover_and_create_profile",
            lambda self, machine_id, save: (discovery, None),
        )
        result = cmd_setup(machine_id="test-setup")
        assert result["success"] is True
        assert result["machine_id"] == "test-setup"
        assert "snapshot_id" not in result
        assert not Path(os.environ["LFO_WORKSPACE"]).exists()


class TestCmdDoctor:
    def test_no_profile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_doctor(machine_id="nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_with_workflow_id(self, monkeypatch, tmp_path):
        """When profile doesn't exist, should fail gracefully."""
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_doctor(machine_id="no-profile", workflow_id="h3_standard_fl2va")
        assert result["success"] is False


class TestCmdPreflight:
    def test_no_profile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_preflight(project_id="p1", machine_id="no-profile")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_basic_call(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_preflight(project_id="p1", machine_id="no-profile")
        assert "success" in result


class TestCmdMachineList:
    def test_list(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_machine_list()
        assert result["success"] is True
        assert isinstance(result["machines"], list)


class TestCmdMachineInspect:
    def test_no_id(self):
        result = cmd_machine_inspect(machine_id="")
        assert result["success"] is False

    def test_nonexistent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_machine_inspect(machine_id="nonexistent")
        assert result["success"] is False


class TestCmdMachineValidate:
    def test_no_id(self):
        result = cmd_machine_validate(machine_id="")
        assert result["success"] is False

    def test_nonexistent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_machine_validate(machine_id="nonexistent")
        assert result["success"] is False


class TestCmdMachineAdd:
    def test_no_id(self):
        result = cmd_machine_add(machine_id="")
        assert result["success"] is False


class TestCmdConfigResolve:
    def test_basic(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = cmd_config_resolve(project_path="", machine_id="")
        assert result["success"] is True
        assert "config" in result


class TestCmdWorkflowFork:
    def test_no_source(self):
        result = cmd_workflow_fork(source_id="", new_id="new_wf")
        assert result["success"] is False

    def test_no_new_id(self):
        result = cmd_workflow_fork(source_id="h3_standard_fl2va", new_id="")
        assert result["success"] is False

    def test_unknown_source(self):
        result = cmd_workflow_fork(source_id="unknown_wf", new_id="new_wf")
        assert result["success"] is False
        assert "unknown" in result["error"].lower() or "Unknown" in result["error"]

    def test_already_exists(self):
        result = cmd_workflow_fork(
            source_id="h3_standard_fl2va",
            new_id="h3_standard_r2v",  # already exists
        )
        assert result["success"] is False
        assert "exists" in result["error"].lower()

    def test_success(self):
        result = cmd_workflow_fork(
            source_id="h3_standard_fl2va",
            new_id="h3_custom_fl2va_v2",
        )
        assert result["success"] is True
        assert result["new_id"] == "h3_custom_fl2va_v2"
        assert "manifest" in result
