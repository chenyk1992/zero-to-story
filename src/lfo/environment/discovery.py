"""Environment auto-discovery — detect ComfyUI, Python, GPU, FFmpeg."""
from __future__ import annotations

import pathlib
import shutil
from dataclasses import dataclass

from .process_inspection import get_process_executable_path, get_process_pid_by_port


@dataclass
class DiscoveredEnvironment:
    """Result of auto-discovering the local environment."""

    comfyui_running: bool = False
    comfyui_pid: int | None = None
    comfyui_port: int = 0
    comfyui_root: pathlib.Path | None = None
    python_path: pathlib.Path | None = None
    python_version: str = ""
    gpu_name: str = ""
    vram_mib: int = 0
    has_ffmpeg: bool = False
    input_dir: pathlib.Path | None = None
    output_dir: pathlib.Path | None = None


def discover_environment(
    expected_port: int = 8188,
) -> DiscoveredEnvironment:
    """Auto-detect local ComfyUI environment. No side effects."""
    result = DiscoveredEnvironment()

    # Check FFmpeg
    result.has_ffmpeg = shutil.which("ffmpeg") is not None

    # Find ComfyUI process
    pid = get_process_pid_by_port(expected_port)
    if pid is not None:
        result.comfyui_running = True
        result.comfyui_pid = pid
        result.comfyui_port = expected_port

        # Try to find the Python executable
        exe = get_process_executable_path(pid)
        if exe:
            result.python_path = pathlib.Path(exe)

    # Detect GPU
    gpu_name, vram_mib = detect_gpu()
    result.gpu_name = gpu_name
    result.vram_mib = vram_mib

    return result


def find_comfyui_process(port: int = 8188) -> int | None:
    """Find running ComfyUI process PID. None if not found."""
    return get_process_pid_by_port(port)


def detect_gpu() -> tuple[str, int]:
    """Detect GPU name and VRAM.

    Tries nvidia-smi first, then NVML (pynvml).
    Returns (name, vram_mib).
    """
    # Try nvidia-smi
    name, vram = _detect_gpu_nvidia_smi()
    if name:
        return name, vram

    # Try NVML
    name, vram = _detect_gpu_nvml()
    if name:
        return name, vram

    return "", 0


def _detect_gpu_nvidia_smi() -> tuple[str, int]:
    """Detect GPU via nvidia-smi CLI."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                name = parts[0].strip()
                vram_mib = int(float(parts[1].strip()))
                return name, vram_mib
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return "", 0


def _detect_gpu_nvml() -> tuple[str, int]:
    """Detect GPU via NVML (pynvml)."""
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        total_bytes = int(mem_info.total)
        vram_mib = total_bytes // (1024 * 1024)
        pynvml.nvmlShutdown()
        return name, vram_mib
    except Exception:
        return "", 0


def find_python(
    comfyui_root: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """Find the Python interpreter for ComfyUI (venv or system).

    If comfyui_root is given, check for a venv/Scripts/python.exe inside it.
    Falls back to system python.
    """
    if comfyui_root is not None:
        # Check for venv
        venv_python = comfyui_root / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python

        # Check for embedded Python
        embedded = comfyui_root / "python_embedded" / "python.exe"
        if embedded.exists():
            return embedded

    # Fall back to system Python
    system_python = shutil.which("python")
    if system_python:
        return pathlib.Path(system_python)

    return None
