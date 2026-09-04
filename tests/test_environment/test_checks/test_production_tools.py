from __future__ import annotations

import argparse
import subprocess
from unittest.mock import Mock

import pytest

from lfo.cli import doctor_cmd, preflight_cmd
from lfo.config.machine_profile import ComfyUIConfig, MachineProfile
from lfo.environment.checks.base import CheckContext, CheckStatus
from lfo.environment.checks.comfy_runtime import check_comfyui_reachable
from lfo.environment.checks.tools import check_comfy_cli, check_ffprobe


def test_comfy_check_uses_profile_executable_and_verifies_protocol(monkeypatch):
    context = CheckContext(
        machine_profile=MachineProfile(comfyui=ComfyUIConfig(cli="custom-comfy")),
        required_tools={"comfy"},
    )
    which = Mock(return_value="custom-comfy.exe")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "--wait --json", ""))
    monkeypatch.setattr("lfo.environment.checks.tools.shutil.which", which)
    monkeypatch.setattr("lfo.environment.checks.tools.subprocess.run", run)
    assert check_comfy_cli(context).status == CheckStatus.PASSED
    which.assert_called_once_with("custom-comfy")
    assert run.call_args.args[0][-2:] == ["run", "--help"]
    assert "--workflow" not in run.call_args.args[0]


def test_comfy_check_rejects_old_cli_without_json(monkeypatch):
    monkeypatch.setattr("lfo.environment.checks.tools.shutil.which", lambda _: "comfy.exe")
    monkeypatch.setattr("lfo.environment.checks.tools.subprocess.run", lambda *a, **k:
                        subprocess.CompletedProcess([], 0, "--wait", ""))
    assert check_comfy_cli(CheckContext(required_tools={"comfy"})).status == CheckStatus.FAILED


@pytest.mark.parametrize("fn,tool", [(check_comfy_cli, "comfy"), (check_ffprobe, "ffprobe")])
def test_missing_production_tool_is_a_blocker(monkeypatch, fn, tool):
    monkeypatch.setattr("lfo.environment.checks.tools.shutil.which", lambda _: None)
    result = fn(CheckContext(required_tools={tool}))
    assert result.status == CheckStatus.FAILED
    assert result.remediation


@pytest.mark.parametrize("reachable", [True, False])
def test_comfy_reachability_is_checked_without_cached_snapshot(monkeypatch, reachable):
    probe = Mock(return_value={"system": {}}) if reachable else Mock(side_effect=OSError("offline"))
    monkeypatch.setattr("lfo.environment.checks.comfy_runtime.ComfyApiClient.get_system_stats", probe)
    result = check_comfyui_reachable(CheckContext(machine_profile=MachineProfile()))
    assert result.status == (CheckStatus.PASSED if reachable else CheckStatus.FAILED)
    probe.assert_called_once_with()


@pytest.mark.parametrize("module,command,name", [
    (doctor_cmd, doctor_cmd.DoctorCommand, "doctor"),
    (preflight_cmd, preflight_cmd.PreflightCommand, "preflight"),
])
def test_failed_diagnostics_keep_actionable_details(monkeypatch, module, command, name):
    result = {"success": False, "results": [{
        "check_id": "tools.comfy_cli_available", "status": "failed",
        "severity": "blocker", "message": "comfy executable missing",
        "remediation": "Install comfy-cli",
    }]}
    monkeypatch.setattr(module, f"cmd_{name}", lambda **kwargs: result)
    args = argparse.Namespace(machine_id="local", workflow_id="", project_id="",
                              workflow_ids=[], model_ids=[], tool_ids=[])
    response = command.execute(None, args)
    assert not response.ok
    assert response.data == result
    assert response.error["message"] == "comfy executable missing"


def test_preflight_defaults_include_required_production_tools(monkeypatch):
    contexts = []
    monkeypatch.setattr(preflight_cmd, "load_machine_profile", lambda _: MachineProfile())
    monkeypatch.setattr(preflight_cmd.PreflightService, "preflight", lambda self, ctx:
                        contexts.append(ctx) or [])
    assert preflight_cmd.cmd_preflight(machine_id="local")["success"]
    assert contexts[0].required_tools == {"comfy", "ffmpeg", "ffprobe"}
