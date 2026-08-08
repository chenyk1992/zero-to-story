"""Hardware checks — GPU, VRAM, RAM."""
from __future__ import annotations

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "hardware.gpu_available",
    severity=CheckSeverity.BLOCKER,
    description="Is NVIDIA GPU detected?",
)
def check_gpu_available(ctx: CheckContext) -> CheckResult:
    """Check if an NVIDIA GPU is available."""
    if ctx.env_snapshot is None:
        # Fallback to machine profile
        if ctx.machine_profile and ctx.machine_profile.hardware.gpu_name:
            return CheckResult(
                check_id="hardware.gpu_available",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message=f"GPU from profile: {ctx.machine_profile.hardware.gpu_name}",
            )
        return CheckResult(
            check_id="hardware.gpu_available",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No environment data available",
        )

    gpu_name = ctx.env_snapshot.get("gpu_name", "")
    if gpu_name:
        return CheckResult(
            check_id="hardware.gpu_available",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message=f"GPU detected: {gpu_name}",
            details={"gpu_name": gpu_name},
        )

    return CheckResult(
        check_id="hardware.gpu_available",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message="No NVIDIA GPU detected",
        remediation="Ensure NVIDIA drivers are installed and GPU is visible",
    )


@check(
    "hardware.vram_sufficient",
    severity=CheckSeverity.WARNING,
    description="Is free VRAM above threshold?",
)
def check_vram_sufficient(ctx: CheckContext) -> CheckResult:
    """Check if VRAM is sufficient."""
    from lfo.config.defaults import DEFAULT_MIN_FREE_VRAM_MIB

    if ctx.machine_profile is None:
        return CheckResult(
            check_id="hardware.vram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    vram_mib = ctx.machine_profile.hardware.vram_mib
    if vram_mib <= 0:
        return CheckResult(
            check_id="hardware.vram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="VRAM amount not configured",
        )

    if vram_mib >= DEFAULT_MIN_FREE_VRAM_MIB:
        return CheckResult(
            check_id="hardware.vram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message=f"VRAM sufficient: {vram_mib} MiB ({vram_mib / 1024:.1f} GiB)",
            details={"vram_mib": vram_mib},
        )
    return CheckResult(
        check_id="hardware.vram_sufficient",
        severity=CheckSeverity.WARNING,
        status=CheckStatus.FAILED,
        message=f"Low VRAM: {vram_mib} MiB (need {DEFAULT_MIN_FREE_VRAM_MIB} MiB)",
        details={"vram_mib": vram_mib, "threshold_mib": DEFAULT_MIN_FREE_VRAM_MIB},
    )


@check(
    "hardware.ram_sufficient",
    severity=CheckSeverity.WARNING,
    description="Is total RAM above threshold?",
)
def check_ram_sufficient(ctx: CheckContext) -> CheckResult:
    """Check if system RAM is sufficient."""
    from lfo.config.defaults import DEFAULT_MIN_FREE_RAM_MIB

    if ctx.machine_profile is None:
        return CheckResult(
            check_id="hardware.ram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    ram_mib = ctx.machine_profile.hardware.ram_mib
    if ram_mib <= 0:
        return CheckResult(
            check_id="hardware.ram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="RAM amount not configured",
        )

    if ram_mib >= DEFAULT_MIN_FREE_RAM_MIB:
        return CheckResult(
            check_id="hardware.ram_sufficient",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message=f"RAM sufficient: {ram_mib} MiB ({ram_mib / 1024:.1f} GiB)",
            details={"ram_mib": ram_mib},
        )
    return CheckResult(
        check_id="hardware.ram_sufficient",
        severity=CheckSeverity.WARNING,
        status=CheckStatus.FAILED,
        message=f"Low RAM: {ram_mib} MiB (need {DEFAULT_MIN_FREE_RAM_MIB} MiB)",
        details={"ram_mib": ram_mib, "threshold_mib": DEFAULT_MIN_FREE_RAM_MIB},
    )
