"""Live workflow compatibility checks."""
from __future__ import annotations

from lfo.config.machine_profile import ComfyUIConfig, MachineProfile
from lfo.environment.checks import workflows
from lfo.environment.checks.base import CheckContext, CheckStatus


class _FakeClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url


def test_runtime_compatibility_uses_live_registry_and_ignores_snapshot(monkeypatch, tmp_path):
    calls: list[tuple[str, str, str | None]] = []

    class FakeRegistry:
        def __init__(self, workflow_dir):
            self.workflow_dir = workflow_dir

        def register(self, workflow_id: str):
            calls.append((f"register:{workflow_id}", "", None))

        def check_runtime_compatibility(self, workflow_id, *, comfy_client, model_dir):
            calls.append((workflow_id, comfy_client.base_url, model_dir))
            return {
                "compatible": True,
                "level": "RUNTIME_COMPATIBLE",
                "checks": [{"name": "workflow_environment", "status": "pass"}],
            }

    monkeypatch.setattr(workflows, "WorkflowRegistry", FakeRegistry)
    monkeypatch.setattr(workflows, "ComfyApiClient", _FakeClient)
    profile = MachineProfile(
        machine_id="test-machine",
        comfyui=ComfyUIConfig(
            base_url="http://127.0.0.1:8189",
            root=str(tmp_path / "ComfyUI"),
        ),
    )
    context = CheckContext(
        machine_profile=profile,
        env_snapshot={
            "comfyui_running": False,
            "runtime_compatible": {"h3_standard_fl2va": False},
        },
        required_workflow_ids={"h3_standard_fl2va"},
    )

    result = workflows.check_workflow_runtime_compatible(context)

    assert result.status == CheckStatus.PASSED
    assert calls[0][0] == "register:h3_standard_fl2va"
    assert calls[1] == (
        "h3_standard_fl2va",
        "http://127.0.0.1:8189",
        str(tmp_path / "ComfyUI" / "models"),
    )


def test_runtime_compatibility_reports_live_failure(monkeypatch):
    class FakeRegistry:
        def __init__(self, workflow_dir):
            pass

        def register(self, workflow_id: str):
            pass

        def check_runtime_compatibility(self, workflow_id, *, comfy_client, model_dir):
            return {
                "compatible": False,
                "level": "STATIC_VALID",
                "checks": [{"name": "workflow_environment", "status": "fail"}],
            }

    monkeypatch.setattr(workflows, "WorkflowRegistry", FakeRegistry)
    monkeypatch.setattr(workflows, "ComfyApiClient", _FakeClient)
    context = CheckContext(
        machine_profile=MachineProfile(
            comfyui=ComfyUIConfig(base_url="http://127.0.0.1:8189"),
        ),
        required_workflow_ids={"h3_standard_r2v"},
    )

    result = workflows.check_workflow_runtime_compatible(context)

    assert result.status == CheckStatus.FAILED
    assert result.details["failed"] == ["h3_standard_r2v"]
    assert result.details["workflows"]["h3_standard_r2v"]["compatible"] is False


def test_runtime_compatibility_skips_without_workflow_ids(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("live compatibility must not run without workflows")

    monkeypatch.setattr(workflows, "WorkflowRegistry", fail_if_called)
    result = workflows.check_workflow_runtime_compatible(CheckContext())

    assert result.status == CheckStatus.SKIPPED
