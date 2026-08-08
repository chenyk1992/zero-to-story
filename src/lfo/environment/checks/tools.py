"""Tool checks — FFmpeg, Python availability."""
from __future__ import annotations

import shutil

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check(
    "tools.ffmpeg_available",
    severity=CheckSeverity.BLOCKER,
    description="Is FFmpeg installed and accessible?",
)
def check_ffmpeg(ctx: CheckContext) -> CheckResult:
    """Check if FFmpeg is available."""
    if "ffmpeg" not in ctx.required_tools:
        return CheckResult(
            check_id="tools.ffmpeg_available",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.SKIPPED,
            message="FFmpeg not required",
        )

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return CheckResult(
            check_id="tools.ffmpeg_available",
            severity=CheckSeverity.BLOCKER,
            status=CheckStatus.PASSED,
            message=f"FFmpeg found: {ffmpeg_path}",
            details={"path": ffmpeg_path},
        )
    return CheckResult(
        check_id="tools.ffmpeg_available",
        severity=CheckSeverity.BLOCKER,
        status=CheckStatus.FAILED,
        message="FFmpeg not found in PATH",
        remediation="Install FFmpeg and add to PATH",
    )


@check(
    "tools.python_available",
    severity=CheckSeverity.INFO,
    description="Is the expected Python version available?",
)
def check_python(ctx: CheckContext) -> CheckResult:
    """Check if Python is available and matches expected version."""
    if "python" not in ctx.required_tools:
        return CheckResult(
            check_id="tools.python_available",
            severity=CheckSeverity.INFO,
            status=CheckStatus.SKIPPED,
            message="Python not explicitly required",
        )

    if ctx.machine_profile is None:
        return CheckResult(
            check_id="tools.python_available",
            severity=CheckSeverity.INFO,
            status=CheckStatus.SKIPPED,
            message="No machine profile available",
        )

    python_path = ctx.machine_profile.comfyui.python_path
    if not python_path:
        return CheckResult(
            check_id="tools.python_available",
            severity=CheckSeverity.INFO,
            status=CheckStatus.SKIPPED,
            message="Python path not configured",
        )

    import pathlib

    path = pathlib.Path(python_path)
    if path.exists():
        return CheckResult(
            check_id="tools.python_available",
            severity=CheckSeverity.INFO,
            status=CheckStatus.PASSED,
            message=f"Python executable found: {python_path}",
            details={"path": python_path},
        )
    return CheckResult(
        check_id="tools.python_available",
        severity=CheckSeverity.INFO,
        status=CheckStatus.FAILED,
        message=f"Python not found at configured path: {python_path}",
        remediation="Update python_path in machine profile",
    )
