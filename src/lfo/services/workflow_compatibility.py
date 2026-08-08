"""Workflow compatibility — 3-tier validation with per-machine tracking."""
from __future__ import annotations

import json
import os
import pathlib
from datetime import UTC

from lfo.config.machine_profile import MachineProfile
from lfo.environment.checks.base import (
    CheckResult,
    CheckSeverity,
    CheckStatus,
)


class WorkflowCompatibilityService:
    """Validate workflows with per-machine compatibility tracking.

    Three validation tiers:
    1. STATIC_VALID: JSON structure + hash + bindings
    2. RUNTIME_COMPATIBLE: /object_info + model deps
    3. SMOKE_TESTED: actual execution succeeded
    """

    def __init__(self, machine_profile: MachineProfile) -> None:
        self.profile = machine_profile
        self.machine_id = machine_profile.machine_id

    def get_compatibility_dir(self) -> pathlib.Path:
        """Return %APPDATA%/LFO/compatibility/<machine-id>/"""
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            appdata = str(pathlib.Path.home() / "AppData" / "Roaming")
        compat_dir = pathlib.Path(appdata) / "LFO" / "compatibility" / self.machine_id
        compat_dir.mkdir(parents=True, exist_ok=True)
        return compat_dir

    def _get_status_file(self, workflow_id: str) -> pathlib.Path:
        """Get the path to the compatibility status file for a workflow."""
        return self.get_compatibility_dir() / f"{workflow_id}.json"

    def check_static_validity(self, workflow_id: str) -> CheckResult:
        """STATIC_VALID: JSON structure + hash + bindings."""
        status = self.get_machine_status(workflow_id)
        if status in ("static_valid", "runtime_compatible", "smoke_tested"):
            return CheckResult(
                check_id="workflow.static_valid",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message=f"Workflow {workflow_id} is statically valid on {self.machine_id}",
            )
        return CheckResult(
            check_id="workflow.static_valid",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.FAILED,
            message=f"Workflow {workflow_id} not yet validated on {self.machine_id}",
            remediation="Run 'lfo workflow validate' to perform static validation",
        )

    def check_runtime_compatibility(self, workflow_id: str) -> CheckResult:
        """RUNTIME_COMPATIBLE: /object_info + model deps."""
        status = self.get_machine_status(workflow_id)
        if status in ("runtime_compatible", "smoke_tested"):
            return CheckResult(
                check_id="workflow.runtime_compatible",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message=f"Workflow {workflow_id} is runtime-compatible on {self.machine_id}",
            )
        return CheckResult(
            check_id="workflow.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.FAILED,
            message=f"Workflow {workflow_id} not runtime-verified on {self.machine_id}",
            remediation="Start ComfyUI and run 'lfo workflow validate'",
        )

    def record_static_valid(self, workflow_id: str) -> None:
        """Record STATIC_VALID status to machine-specific dir."""
        self._write_status(workflow_id, "static_valid")

    def record_runtime_compatible(self, workflow_id: str) -> None:
        """Record RUNTIME_COMPATIBLE status."""
        self._write_status(workflow_id, "runtime_compatible")

    def record_smoke_test(self, workflow_id: str, passed: bool) -> None:
        """Record SMOKE_TESTED status to machine-specific dir."""
        if passed:
            self._write_status(workflow_id, "smoke_tested")
        else:
            self._write_status(workflow_id, "smoke_failed")

    def get_machine_status(self, workflow_id: str) -> str:
        """Get highest achieved validation level on this machine.

        Returns one of: 'unknown', 'static_valid', 'runtime_compatible',
        'smoke_tested', 'smoke_failed'
        """
        status_file = self._get_status_file(workflow_id)
        if not status_file.exists():
            return "unknown"
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            return data.get("status", "unknown")
        except (json.JSONDecodeError, OSError):
            return "unknown"

    def compare_baseline(self, workflow_id: str) -> dict:
        """Compare current environment against recorded baseline.

        Returns a dict with 'changed' (bool) and 'details' (list of changes).
        """
        status_file = self._get_status_file(workflow_id)
        if not status_file.exists():
            return {"changed": True, "details": ["No baseline recorded"]}

        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"changed": True, "details": [f"Cannot read baseline: {exc}"]}

        changes = []
        baseline_gpu = data.get("gpu_name", "")
        current_gpu = self.profile.hardware.gpu_name
        if baseline_gpu and current_gpu and baseline_gpu != current_gpu:
            changes.append(f"GPU changed: {baseline_gpu} -> {current_gpu}")

        baseline_vram = data.get("vram_mib", 0)
        current_vram = self.profile.hardware.vram_mib
        if baseline_vram and current_vram and baseline_vram != current_vram:
            changes.append(f"VRAM changed: {baseline_vram} -> {current_vram}")

        return {"changed": len(changes) > 0, "details": changes}

    def _write_status(self, workflow_id: str, status: str) -> None:
        """Write compatibility status to disk."""
        from datetime import datetime

        status_file = self._get_status_file(workflow_id)
        data = {
            "workflow_id": workflow_id,
            "machine_id": self.machine_id,
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
            "gpu_name": self.profile.hardware.gpu_name,
            "vram_mib": self.profile.hardware.vram_mib,
        }
        status_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
