"""Workflow checks backed by the live registry validation path."""
from __future__ import annotations

import pathlib

from lfo.comfy.client import ComfyApiClient
from lfo.core.workflow_registry import WorkflowRegistry

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "workflows.runtime_compatible",
    severity=CheckSeverity.BLOCKER,
    description="Does /object_info confirm compatibility?",
)
def check_workflow_runtime_compatible(ctx: CheckContext) -> CheckResult:
    """Check each required workflow against the live ComfyUI instance."""
    if not ctx.required_workflow_ids:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No workflows required",
        )

    if ctx.machine_profile is None:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No machine profile available (cannot verify runtime compatibility)",
        )

    workflow_dir = pathlib.Path(__file__).resolve().parents[2] / "registry"
    model_dir = (
        pathlib.Path(ctx.machine_profile.comfyui.root) / "models"
        if ctx.machine_profile.comfyui.root
        else None
    )
    registry = WorkflowRegistry(workflow_dir)
    client = ComfyApiClient(ctx.machine_profile.comfyui.base_url)
    failed = []
    details: dict[str, dict] = {}
    for workflow_id in sorted(ctx.required_workflow_ids):
        try:
            registry.register(workflow_id)
            result = registry.check_runtime_compatibility(
                workflow_id,
                comfy_client=client,
                model_dir=str(model_dir) if model_dir is not None else None,
            )
        except Exception as exc:
            failed.append(workflow_id)
            details[workflow_id] = {
                "compatible": False,
                "error": str(exc),
            }
            continue

        details[workflow_id] = {
            "compatible": bool(result.get("compatible", False)),
            "level": result.get("level", ""),
            "checks": result.get("checks", []),
        }
        if not result.get("compatible", False):
            failed.append(workflow_id)

    if not failed:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message="All workflows runtime-compatible against live ComfyUI",
            details=details,
        )
    return CheckResult(
        check_id="workflows.runtime_compatible",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Runtime compatibility failed for: {', '.join(failed)}",
        details={"failed": failed, "workflows": details},
        remediation="Start the configured ComfyUI and install the required workflow nodes/models",
    )
