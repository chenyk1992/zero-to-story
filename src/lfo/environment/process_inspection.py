"""Low-level process inspection utilities — PID, command-line reading."""
from __future__ import annotations

import subprocess


def get_process_pid_by_port(port: int) -> int | None:
    """Find PID listening on a given TCP port.

    Uses PowerShell Get-NetTCPConnection (Windows-compatible).
    Returns None if no process is listening on the port.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetTCPConnection -LocalPort {port} -State Listen "
                f"-ErrorAction SilentlyContinue).OwningProcess",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        pid_str = result.stdout.strip()
        if pid_str and pid_str.isdigit():
            return int(pid_str)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def get_process_command_line(pid: int) -> str | None:
    """Get the command line of a running process.

    Uses PowerShell Get-CimInstance Win32_Process.
    Returns None if the process doesn't exist or can't be queried.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        cmd = result.stdout.strip()
        return cmd if cmd else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def get_process_executable_path(pid: int) -> str | None:
    """Get the executable path for a given PID via PowerShell.

    Returns None if the process doesn't exist.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").ExecutablePath",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        exe = result.stdout.strip()
        return exe if exe else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def is_process_running(pid: int) -> bool:
    """Check if a process is still alive.

    Uses PowerShell Get-Process for Windows compatibility.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue) -ne $null",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip().lower() == "true"
    except (subprocess.TimeoutExpired, OSError):
        return False
