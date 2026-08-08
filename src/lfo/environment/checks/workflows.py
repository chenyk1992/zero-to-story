"""Workflow checks — hash match, bindings, runtime compatibility."""
from __future__ import annotations

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "workflows.hash_match",
    severity=CheckSeverity.BLOCKER,
    description="Do workflow files match registered hashes?",
)
def check_workflow_hash_match(ctx: CheckContext) -> CheckResult:
    """Check if workflow files match registered hashes."""
    if not ctx.required_workflow_ids:
        return CheckResult(
            check_id="workflows.hash_match",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No workflows required",
        )

    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="workflows.hash_match",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available",
        )

    workflow_hashes = ctx.env_snapshot.get("workflow_hashes", {})
    missing = []
    for wf_id in ctx.required_workflow_ids:
        if wf_id not in workflow_hashes:
            missing.append(wf_id)

    if not missing:
        return CheckResult(
            check_id="workflows.hash_match",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message=f"All {len(ctx.required_workflow_ids)} workflow hashes matched",
        )
    return CheckResult(
        check_id="workflows.hash_match",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Workflow hash check incomplete for: {', '.join(missing)}",
        details={"incomplete": missing},
    )


@check(
    "workflows.bindings_resolvable",
    severity=CheckSeverity.BLOCKER,
    description="Can all node bindings be resolved?",
)
def check_workflow_bindings(ctx: CheckContext) -> CheckResult:
    """Check if workflow node bindings are resolvable."""
    if not ctx.required_workflow_ids:
        return CheckResult(
            check_id="workflows.bindings_resolvable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No workflows required",
        )

    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="workflows.bindings_resolvable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available",
        )

    bindings_status = ctx.env_snapshot.get("bindings_resolvable", {})
    failed = []
    for wf_id in ctx.required_workflow_ids:
        if not bindings_status.get(wf_id, False):
            failed.append(wf_id)

    if not failed:
        return CheckResult(
            check_id="workflows.bindings_resolvable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message="All workflow bindings resolvable",
        )
    return CheckResult(
        check_id="workflows.bindings_resolvable",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Binding resolution failed for: {', '.join(failed)}",
        details={"failed": failed},
    )


@check(
    "workflows.runtime_compatible",
    severity=CheckSeverity.BLOCKER,
    description="Does /object_info confirm compatibility?",
)
def check_workflow_runtime_compatible(ctx: CheckContext) -> CheckResult:
    """Check if /object_info confirms workflow compatibility."""
    if not ctx.required_workflow_ids:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No workflows required",
        )

    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available",
        )

    runtime_status = ctx.env_snapshot.get("runtime_compatible", {})
    comfyui_running = ctx.env_snapshot.get("comfyui_running", False)

    if not comfyui_running:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="ComfyUI not running — cannot verify runtime compatibility",
        )

    failed = []
    for wf_id in ctx.required_workflow_ids:
        if not runtime_status.get(wf_id, False):
            failed.append(wf_id)

    if not failed:
        return CheckResult(
            check_id="workflows.runtime_compatible",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message="All workflows runtime-compatible",
        )
    return CheckResult(
        check_id="workflows.runtime_compatible",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Runtime compatibility failed for: {', '.join(failed)}",
        details={"failed": failed},
    )
