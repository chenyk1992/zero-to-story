"""Model checks — presence and verification."""
from __future__ import annotations

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "models.all_required_present",
    severity=CheckSeverity.BLOCKER,
    description="Are all required models available?",
)
def check_models_present(ctx: CheckContext) -> CheckResult:
    """Check if all required models are present."""
    if not ctx.required_model_ids:
        return CheckResult(
            check_id="models.all_required_present",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No models required",
        )

    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="models.all_required_present",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available (cannot verify models)",
        )

    present_models = ctx.env_snapshot.get("models_present", {})
    missing = []
    for model_id in ctx.required_model_ids:
        if model_id not in present_models or not present_models[model_id]:
            missing.append(model_id)

    if not missing:
        return CheckResult(
            check_id="models.all_required_present",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message=f"All {len(ctx.required_model_ids)} required models present",
        )
    return CheckResult(
        check_id="models.all_required_present",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Missing {len(missing)} model(s): {', '.join(missing)}",
        details={"missing": missing},
        remediation="Download missing models to the configured model directories",
    )


@check(
    "models.hash_verified",
    severity=CheckSeverity.INFO,
    description="Have SHA-256 hashes been verified?",
)
def check_models_hash_verified(ctx: CheckContext) -> CheckResult:
    """Check if model hashes have been verified."""
    if not ctx.required_model_ids:
        return CheckResult(
            check_id="models.hash_verified",
            severity=CheckSeverity.INFO,
            status=CheckStatus.SKIPPED,
            message="No models required",
        )

    if ctx.env_snapshot is None:
        return CheckResult(
            check_id="models.hash_verified",
            severity=CheckSeverity.INFO,
            status=CheckStatus.SKIPPED,
            message="No environment snapshot available",
        )

    verified_models = ctx.env_snapshot.get("models_verified", {})
    verified_count = sum(
        1 for mid in ctx.required_model_ids
        if verified_models.get(mid, False)
    )

    if verified_count == len(ctx.required_model_ids):
        return CheckResult(
            check_id="models.hash_verified",
            severity=CheckSeverity.INFO,
            status=CheckStatus.PASSED,
            message=f"All {verified_count} model hashes verified",
        )
    return CheckResult(
        check_id="models.hash_verified",
        severity=CheckSeverity.INFO,
        status=CheckStatus.FAILED,
        message=f"Only {verified_count}/{len(ctx.required_model_ids)} models hash-verified",
        details={"verified": verified_count, "total": len(ctx.required_model_ids)},
        remediation="Run strict model verification (lfo machine validate)",
    )
