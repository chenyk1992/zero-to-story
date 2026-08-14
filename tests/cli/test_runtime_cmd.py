"""Runtime CLI registration and facade dispatch tests."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field

from lfo.application.video_runtime import (
    ExportResult2,
    PlanResult,
    ReviewResult,
    RunResult,
    StatusResult,
    ValidationResult2,
)
from lfo.cli.registry import CommandRegistry
from lfo.cli.runtime_cmd import (
    cmd_cancel,
    cmd_execute,
    cmd_export,
    cmd_plan,
    cmd_retry,
    cmd_review,
    cmd_runtime_status,
    cmd_validate,
)


def _package_json(tmp_path: pathlib.Path) -> pathlib.Path:
    data = {
        "schema": "lfo.video-execution.v1",
        "package_id": "test-pkg",
        "revision": 1,
        "project": {"title": "Test", "project_id": "test-project"},
        "assets": [],
        "clips": [{
            "clip_id": "clip-001",
            "sequence": 1,
            "duration_ms": 5000,
            "generation": {"operation": "video.text_to_video", "prompt": "A sunset"},
        }],
        "output": {},
    }
    path = tmp_path / "execution-package.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@dataclass
class StubRuntime:
    """Test double proving commands call the facade rather than copy behavior."""

    calls: list[tuple] = field(default_factory=list)

    def validate(self, path):
        self.calls.append(("validate", path))
        return ValidationResult2(valid=True)

    def plan(self, path):
        self.calls.append(("plan", path))
        return PlanResult(plan_id="plan-1", clip_plans=[{"clip_id": "clip-001"}])

    def execute(self, path, approval=False):
        self.calls.append(("execute", path, approval))
        return RunResult(run_id="run-1", status="COMPLETED", clip_count=1)

    def status(self, run_id):
        self.calls.append(("status", run_id))
        return StatusResult(run_id=run_id, status="RUNNING", tasks={"t": "READY"})

    def retry(self, run_id, scope=None):
        self.calls.append(("retry", run_id, scope))
        return RunResult(run_id=run_id, status="COMPLETED", clip_count=1)

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))

    def review(self, run_id, target, decision):
        self.calls.append(("review", run_id, target, decision))
        return ReviewResult(review_id="review-1", decision=decision)

    def export(self, run_id):
        self.calls.append(("export", run_id))
        return ExportResult2(export_id="export-1", status="READY", file_path="out.mp4")


def _factory_with(stub: StubRuntime):
    return lambda: stub


def test_runtime_commands_are_registered() -> None:
    commands = CommandRegistry.all_commands()
    assert {"validate", "plan", "execute", "status", "retry", "cancel", "review", "export"} <= set(commands)


def test_direct_commands_delegate_to_injected_runtime(tmp_path: pathlib.Path) -> None:
    package_path = str(_package_json(tmp_path))
    stub = StubRuntime()
    factory = _factory_with(stub)

    assert cmd_validate(package_path, runtime_factory=factory)["valid"]
    assert cmd_plan(package_path, runtime_factory=factory)["success"]
    assert cmd_execute(package_path, approve=True, runtime_factory=factory)["status"] == "COMPLETED"
    assert cmd_runtime_status("run-1", runtime_factory=factory)["status"] == "RUNNING"
    assert cmd_retry("run-1", "clip-001", runtime_factory=factory)["success"]
    assert cmd_cancel("run-1", runtime_factory=factory)["success"]
    assert cmd_review("run-1", "clip-001", "approved", runtime_factory=factory)["success"]
    assert cmd_export("run-1", runtime_factory=factory)["file_path"] == "out.mp4"

    assert [call[0] for call in stub.calls] == [
        "validate", "plan", "execute", "status", "retry", "cancel", "review", "export",
    ]
    assert stub.calls[2][-1] is True
    assert stub.calls[4][-1] == "clip-001"


def test_commands_forward_persistent_runtime_configuration(tmp_path: pathlib.Path) -> None:
    observed: dict[str, pathlib.Path] = {}
    stub = StubRuntime()

    def factory(**kwargs):
        observed.update(kwargs)
        return stub

    cmd_validate(
        str(_package_json(tmp_path)),
        db_path=str(tmp_path / "execution.db"),
        workspace_root=str(tmp_path / "workspace"),
        runtime_factory=factory,
    )
    assert observed == {
        "db_path": tmp_path / "execution.db",
        "workspace_root": tmp_path / "workspace",
    }


def test_commands_reject_missing_required_values() -> None:
    assert not cmd_validate("")["success"]
    assert not cmd_plan("")["success"]
    assert not cmd_execute("")["success"]
    assert not cmd_runtime_status("")["success"]
    assert not cmd_retry("")["success"]
    assert not cmd_cancel("")["success"]
    assert not cmd_review("", "clip", "approved")["success"]
    assert not cmd_export("")["success"]


def test_cli_subprocess_dispatch_and_help(tmp_path: pathlib.Path) -> None:
    package_path = _package_json(tmp_path)
    help_result = subprocess.run(
        [sys.executable, "-m", "lfo.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    for command in ("validate", "plan", "execute", "status", "retry", "cancel", "review", "export"):
        assert command in help_result.stdout

    result = subprocess.run(
        [sys.executable, "-m", "lfo.cli.main", "--json", "validate", str(package_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "validate"
