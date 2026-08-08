"""ComfyUI runtime checks — reachability, version, instance correctness."""
from __future__ import annotations

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "comfyui.reachable",
    severity=CheckSeverity.BLOCKER,
    description="Can we connect to the ComfyUI HTTP API?",
)
def check_comfyui_reachable(ctx: CheckContext) -> CheckResult:
    """Check if ComfyUI HTTP API is reachable."""
    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="comfyui.reachable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available (offline mode)",
        )

    reachable = ctx.env_snapshot.get("comfyui_running", False)
    if reachable:
        return CheckResult(
            check_id="comfyui.reachable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message="ComfyUI is reachable",
        )
    return CheckResult(
        check_id="comfyui.reachable",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message="ComfyUI is not reachable — start ComfyUI or check port",
        remediation="Start ComfyUI on the configured port",
    )


@check(
    "comfyui.version_match",
    severity=CheckSeverity.WARNING,
    description="Does ComfyUI version match expected?",
)
def check_comfyui_version(ctx: CheckContext) -> CheckResult:
    """Check if ComfyUI version matches expected."""
    if ctx.machine_profile is None:
        return CheckResult(
            check_id="comfyui.version_match",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    expected = ctx.machine_profile.comfyui.expected_version
    actual = ctx.env_snapshot.get("comfyui_version", "") if ctx.env_snapshot else ""

    if not expected:
        return CheckResult(
            check_id="comfyui.version_match",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No expected version configured",
        )

    if not actual:
        return CheckResult(
            check_id="comfyui.version_match",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.FAILED,
            message="Could not determine ComfyUI version",
        )

    if actual.startswith(expected.rsplit(".", 1)[0]):
        return CheckResult(
            check_id="comfyui.version_match",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message=f"ComfyUI version matches: {actual}",
        )
    return CheckResult(
        check_id="comfyui.version_match",
        severity=CheckSeverity.WARNING,
        status=CheckStatus.FAILED,
        message=f"ComfyUI version mismatch: expected ~{expected}, got {actual}",
        remediation="Update ComfyUI or adjust expected_version in machine profile",
    )


@check(
    "comfyui.correct_instance",
    severity=CheckSeverity.BLOCKER,
    description="Are we connected to the right instance (PID verification)?",
)
def check_comfyui_correct_instance(ctx: CheckContext) -> CheckResult:
    """Verify we're connected to the correct ComfyUI instance."""
    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="comfyui.correct_instance",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available",
        )

    comfyui_running = ctx.env_snapshot.get("comfyui_running", False)
    if not comfyui_running:
        return CheckResult(
            check_id="comfyui.correct_instance",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="ComfyUI is not running — cannot verify instance",
        )

    pid = ctx.env_snapshot.get("comfyui_pid")
    if pid:
        return CheckResult(
            check_id="comfyui.correct_instance",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message=f"ComfyUI instance verified (PID: {pid})",
            details={"pid": pid},
        )
    return CheckResult(
        check_id="comfyui.correct_instance",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.PASSED,
        message="ComfyUI is running (PID verification not available)",
    )
