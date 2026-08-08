"""Manual spike script: measure model switching cost.

Usage:
    python scripts/spike_model_switch.py

This script measures:
1. Current GPU VRAM usage
2. Model files present on disk
3. Estimated VRAM for each model
4. Recommendation: simultaneous vs sequential loading

No models are downloaded or loaded — this is a read-only probe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lfo.environment.tools.resource_probe import (
    estimate_loading_strategy,
    probe_gpu,
    report_to_json,
    scan_models,
)


def _find_comfyui_model_dirs() -> list[str]:
    """Try to locate ComfyUI model directories from common paths."""
    candidates = []

    # Check environment variable
    comfy_root = os.environ.get("COMFYUI_ROOT", "")
    if comfy_root:
        candidates.append(os.path.join(comfy_root, "models"))

    # Common default locations
    home = Path.home()
    common_roots = [
        home / "ComfyUI" / "models",
        home / "comfyui" / "models",
        _PROJECT_ROOT / "comfy" / "models",
        Path(r"C:\ComfyUI\models"),
    ]
    for root in common_roots:
        if root.is_dir():
            candidates.append(str(root))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def main() -> None:
    print("=" * 60)
    print("LFO Phase 5A — Model Switching Spike")
    print("=" * 60)

    # 1. GPU info
    print("\n[1] Probing GPU...")
    gpu = probe_gpu()
    if gpu.error:
        print(f"    WARNING: {gpu.error}")
        print("    Running in estimation-only mode (no real VRAM data).")
    else:
        print(f"    GPU: {gpu.name}")
        print(f"    Driver: {gpu.driver_version}")
        print(f"    CUDA: {gpu.cuda_version or 'unknown'}")
        print(f"    VRAM Total: {gpu.vram_total_mb} MB ({gpu.vram_total_mb / 1024:.1f} GB)")
        print(f"    VRAM Used:  {gpu.vram_used_mb} MB")
        print(f"    VRAM Free:  {gpu.vram_free_mb} MB")

    # 2. Scan model directories
    print("\n[2] Scanning for model files...")
    model_dirs = _find_comfyui_model_dirs()
    if model_dirs:
        print(f"    Found {len(model_dirs)} model directory(ies):")
        for d in model_dirs:
            print(f"      - {d}")
    else:
        print("    No model directories found. Set COMFYUI_ROOT or place models in a standard location.")
        model_dirs = []

    models = scan_models(model_dirs)
    if models:
        print(f"\n    Found {len(models)} model file(s):")
        for m in models:
            print(f"      - {m.name}")
            print(f"        Size: {_format_size(m.size_bytes)}, Est. VRAM: {m.vram_estimate_mb} MB")
    else:
        print("    No .safetensors files found in scanned directories.")

    # 3. Strategy estimation
    print("\n[3] Loading strategy estimation...")
    report = estimate_loading_strategy(gpu, models)
    print(f"    Total model size: {_format_size(report.total_model_size_mb * 1024 * 1024)}")
    print(f"    Total est. VRAM:  {report.total_vram_estimate_mb} MB")
    if report.vram_headroom_mb is not None:
        print(f"    VRAM headroom:    {report.vram_headroom_mb} MB")
    print(f"    Simultaneous:     {report.can_load_simultaneously}")
    print(f"\n    Recommendation: {report.recommendation}")

    # 4. JSON report
    print("\n[4] Full JSON report:")
    print(report_to_json(report))

    print("\n" + "=" * 60)
    print("Spike complete. No models were loaded or modified.")
    print("=" * 60)


if __name__ == "__main__":
    main()
