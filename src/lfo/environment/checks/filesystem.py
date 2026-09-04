"""Filesystem checks — directory permissions, disk space."""
from __future__ import annotations

import os
import shutil

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "storage.input_writable",
    severity=CheckSeverity.BLOCKER,
    description="Can we write to ComfyUI input directory?",
)
def check_input_writable(ctx: CheckContext) -> CheckResult:
    """Check if ComfyUI input directory is writable."""
    if ctx.machine_profile is None:
        return CheckResult(
            check_id="storage.input_writable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    input_dir = ctx.machine_profile.storage.comfy_input
    if not input_dir:
        return CheckResult(
            check_id="storage.input_writable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="ComfyUI input directory not configured; API upload will be used",
        )

    import pathlib

    path = pathlib.Path(input_dir)
    if path.exists() and path.is_dir():
        # Test write with a probe file
        try:
            probe = path / ".lfo_write_probe"
            probe.write_text("ok")
            probe.unlink()
            return CheckResult(
                check_id="storage.input_writable",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message=f"Input directory writable: {input_dir}",
            )
        except (OSError, PermissionError) as exc:
            return CheckResult(
                check_id="storage.input_writable",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.FAILED,
                message=f"Input directory not writable: {exc}",
            )

    return CheckResult(
        check_id="storage.input_writable",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Input directory does not exist: {input_dir}",
        remediation=f"Create the directory: mkdir {input_dir}",
    )


@check(
    "storage.output_readable",
    severity=CheckSeverity.BLOCKER,
    description="Can we read from ComfyUI output directory?",
)
def check_output_readable(ctx: CheckContext) -> CheckResult:
    """Check if ComfyUI output directory is readable."""
    if ctx.machine_profile is None:
        return CheckResult(
            check_id="storage.output_readable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    output_dir = ctx.machine_profile.storage.comfy_output
    if not output_dir:
        return CheckResult(
            check_id="storage.output_readable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="ComfyUI output directory not configured; outputs will be downloaded via /view",
        )

    import pathlib

    path = pathlib.Path(output_dir)
    if path.exists() and path.is_dir():
        # Check we can list the directory
        try:
            list(path.iterdir())
            return CheckResult(
                check_id="storage.output_readable",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.PASSED,
                message=f"Output directory readable: {output_dir}",
            )
        except (OSError, PermissionError) as exc:
            return CheckResult(
                check_id="storage.output_readable",
                severity=CheckSeverity.BLOCKER,
                status=CheckStatus.FAILED,
                message=f"Output directory not readable: {exc}",
            )

    return CheckResult(
        check_id="storage.output_readable",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message=f"Output directory does not exist: {output_dir}",
        remediation=f"Create the directory: mkdir {output_dir}",
    )


@check(
    "storage.disk_space",
    severity=CheckSeverity.WARNING,
    description="Is there enough free disk space?",
)
def check_disk_space(ctx: CheckContext) -> CheckResult:
    """Check available disk space."""
    if ctx.machine_profile is None:
        return CheckResult(
            check_id="storage.disk_space",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    output_dir = ctx.machine_profile.storage.comfy_output
    if not output_dir:
        return CheckResult(
            check_id="storage.disk_space",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.SKIPPED,
            message="No output directory configured for disk space check",
        )

    import pathlib

    path = pathlib.Path(output_dir)
    # Walk up to find an existing parent
    while not path.exists() and path.parent != path:
        path = path.parent

    try:
        usage = shutil.disk_usage(str(path))
        free_mib = usage.free / (1024 * 1024)
        # Use default threshold (5GB) since we import from config defaults
        from lfo.config.defaults import DEFAULT_MIN_FREE_DISK_MIB

        threshold = DEFAULT_MIN_FREE_DISK_MIB
        if free_mib < threshold:
            return CheckResult(
                check_id="storage.disk_space",
                severity=CheckSeverity.WARNING,
                status=CheckStatus.FAILED,
                message=f"Low disk space: {free_mib:.0f} MiB free (need {threshold} MiB)",
                details={"free_mib": free_mib, "threshold_mib": threshold},
            )
        return CheckResult(
            check_id="storage.disk_space",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.PASSED,
            message=f"Disk space OK: {free_mib:.0f} MiB free",
            details={"free_mib": free_mib},
        )
    except (OSError, FileNotFoundError) as exc:
        return CheckResult(
            check_id="storage.disk_space",
            severity=CheckSeverity.WARNING,
            status=CheckStatus.FAILED,
            message=f"Could not check disk space: {exc}",
        )


@check(
    "storage.project_writable",
    severity=CheckSeverity.BLOCKER,
    description="Can we write to project directory?",
)
def check_project_writable(ctx: CheckContext) -> CheckResult:
    """Check if project directory is writable."""
    if ctx.machine_profile is None:
        return CheckResult(
            check_id="storage.project_writable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    projects_dir = ctx.machine_profile.storage.lfo_projects
    if not projects_dir:
        return CheckResult(
            check_id="storage.project_writable",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="No projects directory configured",
        )

    import pathlib

    path = pathlib.Path(projects_dir)
    # Diagnostics must not create project directories or overwrite probe files
    # in persistent user data. The actual output operation verifies write access.
    while not path.exists() and path.parent != path:
        path = path.parent
    writable = path.is_dir() and os.access(path, os.W_OK)
    return CheckResult(
        check_id="storage.project_writable",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.PASSED if writable else CheckStatus.FAILED,
        message=f"Project parent access {'available' if writable else 'unavailable'}: {path}",
    )
