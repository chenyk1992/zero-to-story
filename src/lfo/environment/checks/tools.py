"""Checks for the executables used by synchronous video production."""
from __future__ import annotations

import shutil
import subprocess

from .base import (
    CheckContext,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    check,
)


@check("tools.comfy_cli_available", severity=CheckSeverity.BLOCKER)
def check_comfy_cli(ctx: CheckContext) -> CheckResult:
    """Verify the configured executable supports the current run protocol."""
    check_id = "tools.comfy_cli_available"
    if "comfy" not in ctx.required_tools:
        return CheckResult(check_id, CheckSeverity.BLOCKER, CheckStatus.SKIPPED,
                           "comfy-cli not required")
    binary = ctx.machine_profile.comfyui.cli if ctx.machine_profile else "comfy"
    path = shutil.which(binary)
    if path:
        try:
            result = subprocess.run(
                [path, "--skip-prompt", "--where", "local", "run", "--help"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=15, check=False,
            )
            help_text = result.stdout + result.stderr
            if result.returncode == 0 and "--wait" in help_text and "--json" in help_text:
                return CheckResult(check_id, CheckSeverity.BLOCKER, CheckStatus.PASSED,
                                   f"comfy-cli run --wait --json available: {path}")
            message = "Configured comfy-cli does not support run --wait --json"
        except (OSError, subprocess.TimeoutExpired) as exc:
            message = f"Could not run configured comfy-cli: {exc}"
    else:
        message = f"comfy-cli executable not found: {binary}"
    return CheckResult(check_id, CheckSeverity.BLOCKER, CheckStatus.FAILED, message,
                       remediation="Install current official comfy-cli and configure comfyui.cli or PATH")


@check("tools.ffprobe_available", severity=CheckSeverity.BLOCKER)
def check_ffprobe(ctx: CheckContext) -> CheckResult:
    """FFprobe is needed for asset probing and the minimal technical QC."""
    check_id = "tools.ffprobe_available"
    if "ffprobe" not in ctx.required_tools:
        return CheckResult(check_id, CheckSeverity.BLOCKER, CheckStatus.SKIPPED,
                           "FFprobe not required")
    path = shutil.which("ffprobe")
    return CheckResult(
        check_id, CheckSeverity.BLOCKER, CheckStatus.PASSED if path else CheckStatus.FAILED,
        f"FFprobe found: {path}" if path else "FFprobe not found in PATH",
        remediation=None if path else "Install FFmpeg including ffprobe and add its bin directory to PATH",
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
