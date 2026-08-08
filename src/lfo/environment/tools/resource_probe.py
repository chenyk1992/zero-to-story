"""Resource feasibility probe — GPU, VRAM, model loading estimation."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class GPUInfo:
    """GPU information gathered from nvidia-smi."""

    name: str | None = None
    vram_total_mb: int | None = None
    vram_used_mb: int | None = None
    vram_free_mb: int | None = None
    cuda_version: str | None = None
    driver_version: str | None = None
    error: str | None = None


@dataclass
class ModelResource:
    """A model file and its estimated VRAM footprint."""

    name: str
    path: str
    size_bytes: int
    vram_estimate_mb: int  # Estimated VRAM usage when loaded
    load_time_estimate_s: float | None = None


@dataclass
class ResourceReport:
    """Aggregated resource feasibility report."""

    gpu: GPUInfo
    models: list[ModelResource] = field(default_factory=list)
    total_model_size_mb: int = 0
    total_vram_estimate_mb: int = 0
    vram_headroom_mb: int | None = None
    can_load_simultaneously: bool = False
    recommendation: str = ""


# VRAM estimation multipliers by model precision
# Pruned int8 models need ~1.0-1.2x file size when loaded
# fp16 models need ~1.5-2x file size
_VRAM_MULTIPLIERS = {
    "int8": 1.1,
    "fp8": 1.15,
    "nf4": 1.2,
    "fp4": 1.2,
    "fp16": 1.75,
    "bf16": 1.75,
    "fp32": 2.0,
}

# Keywords that indicate precision in filenames
_PRECISION_KEYWORDS = [
    ("int8", "int8"),
    ("fp8", "fp8"),
    ("nf4", "nf4"),
    ("fp4", "fp4"),
    ("fp16", "fp16"),
    ("bf16", "bf16"),
    ("pruned", "int8"),  # pruned models are typically int8
]


def _detect_precision(filename: str) -> str:
    """Detect model precision from filename.

    Returns one of: int8, fp8, nf4, fp4, fp16, bf16, fp32.
    Defaults to fp16 (most common for video models).
    """
    lower = filename.lower()
    for keyword, precision in _PRECISION_KEYWORDS:
        if keyword in lower:
            return precision
    return "fp16"


def _estimate_vram_mb(size_bytes: int, precision: str) -> int:
    """Estimate VRAM usage in MiB from file size and precision."""
    multiplier = _VRAM_MULTIPLIERS.get(precision, 1.75)
    return int((size_bytes * multiplier) / (1024 * 1024))


def probe_gpu(timeout: float = 10.0) -> GPUInfo:
    """Probe GPU information using nvidia-smi.

    Args:
        timeout: Maximum seconds to wait for nvidia-smi.

    Returns:
        GPUInfo with populated fields, or error set if unavailable.
    """
    info = GPUInfo()

    smi_path = _find_nvidia_smi()
    if smi_path is None:
        info.error = "nvidia-smi not found in PATH or standard locations"
        return info

    try:
        result = subprocess.run(
            [
                smi_path,
                "--query-gpu=name,memory.total,memory.used,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            info.error = f"nvidia-smi returned code {result.returncode}: {result.stderr.strip()}"
            return info

        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) < 5:
            info.error = f"Unexpected nvidia-smi output format: {result.stdout.strip()}"
            return info

        info.name = parts[0]
        info.vram_total_mb = int(float(parts[1]))
        info.vram_used_mb = int(float(parts[2]))
        info.vram_free_mb = int(float(parts[3]))
        info.driver_version = parts[4]

    except subprocess.TimeoutExpired:
        info.error = f"nvidia-smi timed out after {timeout}s"
    except (ValueError, IndexError) as e:
        info.error = f"Failed to parse nvidia-smi output: {e}"
    except OSError as e:
        info.error = f"Failed to run nvidia-smi: {e}"

    # Try to get CUDA version separately
    info.cuda_version = _probe_cuda_version(timeout)

    return info


def _find_nvidia_smi() -> str | None:
    """Locate nvidia-smi executable."""
    # Check PATH first
    for name in ("nvidia-smi", "nvidia-smi.exe"):
        found = _which(name)
        if found:
            return found

    # Check standard Windows installation paths
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidates = [
        os.path.join(
            program_files_x86, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"
        ),
        os.path.join(
            program_files, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"
        ),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def _which(name: str) -> str | None:
    """Cross-platform shutil.which replacement."""
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(dir_path, name)
        if os.path.isfile(full):
            return full
    return None


def _probe_cuda_version(timeout: float) -> str | None:
    """Try to detect CUDA version from nvidia-smi header."""
    smi_path = _find_nvidia_smi()
    if smi_path is None:
        return None
    try:
        result = subprocess.run(
            [smi_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # nvidia-smi top-level output includes "CUDA Version: X.X"
        for line in result.stdout.splitlines():
            if "CUDA Version:" in line:
                return line.split("CUDA Version:")[-1].strip().split()[0]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def scan_models(model_dirs: list[str]) -> list[ModelResource]:
    """Scan directories for .safetensors model files.

    Args:
        model_dirs: List of directory paths to scan.

    Returns:
        List of ModelResource for each .safetensors file found.
    """
    models: list[ModelResource] = []

    for dir_str in model_dirs:
        dir_path = Path(dir_str)
        if not dir_path.is_dir():
            continue

        for safetensor in dir_path.rglob("*.safetensors"):
            size = safetensor.stat().st_size
            precision = _detect_precision(safetensor.name)
            vram_mb = _estimate_vram_mb(size, precision)

            models.append(
                ModelResource(
                    name=safetensor.name,
                    path=str(safetensor),
                    size_bytes=size,
                    vram_estimate_mb=vram_mb,
                )
            )

    # Sort by VRAM estimate descending (largest first)
    models.sort(key=lambda m: m.vram_estimate_mb, reverse=True)
    return models


def estimate_loading_strategy(
    gpu: GPUInfo,
    models: list[ModelResource],
    vram_utilization_threshold: float = 0.8,
) -> ResourceReport:
    """Estimate whether models can coexist in VRAM.

    Args:
        gpu: Probed GPU information.
        models: List of models to evaluate.
        vram_utilization_threshold: Max fraction of VRAM that should be
            occupied by models (default 0.8 = leave 20% headroom).

    Returns:
        ResourceReport with recommendation.
    """
    report = ResourceReport(gpu=gpu, models=models)

    if not models:
        report.recommendation = "No models to evaluate."
        return report

    # Aggregate totals
    report.total_model_size_mb = sum(m.size_bytes for m in models) // (1024 * 1024)
    report.total_vram_estimate_mb = sum(m.vram_estimate_mb for m in models)

    if gpu.vram_total_mb is None or gpu.vram_total_mb <= 0:
        report.recommendation = (
            "Cannot determine GPU VRAM. Manual verification required."
        )
        return report

    usable_vram_mb = int(gpu.vram_total_mb * vram_utilization_threshold)
    report.vram_headroom_mb = gpu.vram_total_mb - report.total_vram_estimate_mb

    if report.total_vram_estimate_mb <= usable_vram_mb:
        report.can_load_simultaneously = True
        report.recommendation = (
            f"simultaneous: all {len(models)} models fit in VRAM "
            f"(need {report.total_vram_estimate_mb} MB, "
            f"have {gpu.vram_total_mb} MB total, "
            f"{usable_vram_mb} MB usable at {vram_utilization_threshold:.0%} threshold)."
        )
    else:
        report.can_load_simultaneously = False
        report.recommendation = (
            f"sequential: models require {report.total_vram_estimate_mb} MB "
            f"but only {usable_vram_mb} MB usable "
            f"({gpu.vram_total_mb} MB total). "
            f"Load/unload models on demand."
        )

    return report


def report_to_dict(report: ResourceReport) -> dict:
    """Convert a ResourceReport to a JSON-serializable dict."""
    return {
        "gpu": asdict(report.gpu),
        "models": [asdict(m) for m in report.models],
        "total_model_size_mb": report.total_model_size_mb,
        "total_vram_estimate_mb": report.total_vram_estimate_mb,
        "vram_headroom_mb": report.vram_headroom_mb,
        "can_load_simultaneously": report.can_load_simultaneously,
        "recommendation": report.recommendation,
    }


def report_to_json(report: ResourceReport, indent: int = 2) -> str:
    """Serialize a ResourceReport to JSON string."""
    return json.dumps(report_to_dict(report), indent=indent, ensure_ascii=False)
