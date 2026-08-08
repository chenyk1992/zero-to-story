"""VRAM gate for ComfyUI submissions.

Why this exists
---------------
On a single-GPU machine (e.g. RTX 5080 16GB), ComfyUI jobs can OOM. The
existing ``classify_failure()`` heuristic catches "oom/oom/503" only when
the keyword appears in the error string - but the cure is to avoid
launching a job that will collide with one already running.

This module provides a tiny, import-safe gate:

- ``get_gpu_status()`` - return a snapshot dict or ``None`` if NVML is
  unavailable (no driver, no NVIDIA GPU, import failure). Never raises.
- ``check_vram_gate(snapshot, required_free_bytes)`` - decide whether a
  new submission should be allowed right now.

Design constraints
------------------
- MUST be safe to import in CI (no NVIDIA driver) - pynvml import is
  deferred to ``_load_pynvml()`` and is the only thing tests should mock.
- Pure function (no I/O) so it can be unit-tested without hardware.
- Conservative defaults - false negatives (delaying a submission) are
  much cheaper than false positives (OOM crash + retry loop).
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

#: Used when no explicit required_free_bytes is provided. Keep at most
#: 80% of total VRAM in use, i.e. always leave 20% headroom.
DEFAULT_HIGH_WATER_RATIO = 0.80

#: When a gate denial needs to wait, sleep this many seconds before the
#: next poll. Short enough to feel responsive, long enough to give
#: ComfyUI time to free memory.
DEFAULT_RETRY_WAIT_SECONDS = 30


@dataclass(frozen=True)
class VramGateDecision:
    """Outcome of a single gate check.

    Attributes:
        allowed: True iff a new submission should proceed now.
        reason: One of ``"ok"``, ``"insufficient_free_vram"``,
            ``"high_water_mark"``, ``"no_gpu_info"``.
        wait_seconds: When ``allowed`` is False, how long to sleep
            before the next check. Zero when allowed.
    """

    allowed: bool
    reason: str
    wait_seconds: int


def _load_pynvml() -> Any:
    """Return the pynvml module, or ``None`` if it cannot be imported.

    Deferred import keeps the module importable in environments without
    the NVIDIA driver. Tests mock this function.
    """
    try:
        import pynvml  # type: ignore[import-not-found]
        return pynvml
    except Exception:
        return None


def get_gpu_status() -> dict | None:
    """Return a snapshot of device-0 memory, or ``None`` if unavailable.

    Returns a dict with keys: ``device_index``, ``used_bytes``,
    ``total_bytes``, ``free_bytes``, ``used_ratio``. Never raises.
    """
    pynvml = _load_pynvml()
    if pynvml is None:
        return None

    try:
        pynvml.nvmlInit()
    except Exception:
        return None

    try:
        count = pynvml.nvmlDeviceGetCount()
        if count <= 0:
            return None
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

        used = int(mem.used)
        total = int(mem.total)
        free = total - used
        ratio = (used / total) if total > 0 else 1.0

        return {
            "device_index": 0,
            "used_bytes": used,
            "total_bytes": total,
            "free_bytes": free,
            "used_ratio": ratio,
        }
    except Exception:
        return None
    finally:
        with contextlib.suppress(Exception):
            pynvml.nvmlShutdown()


def check_vram_gate(
    snapshot: dict | None,
    required_free_bytes: int = 0,
    high_water_ratio: float = DEFAULT_HIGH_WATER_RATIO,
) -> VramGateDecision:
    """Decide whether a new submission should be allowed right now.

    Args:
        snapshot: Result of ``get_gpu_status()`` or ``None`` (no GPU info).
        required_free_bytes: If > 0, gate denies when free VRAM is below
            this value. If 0, falls back to the ratio heuristic.
        high_water_ratio: Used only when ``required_free_bytes == 0``.
            Gate denies when ``used_ratio`` exceeds this value.

    Returns:
        A :class:`VramGateDecision`. When denied, ``wait_seconds`` is
        ``DEFAULT_RETRY_WAIT_SECONDS``.
    """
    if snapshot is None:
        # No GPU info available — fail open. Submission will still be
        # caught by ComfyUI's own error handling.
        return VramGateDecision(allowed=True, reason="no_gpu_info", wait_seconds=0)

    if required_free_bytes > 0:
        if snapshot["free_bytes"] >= required_free_bytes:
            return VramGateDecision(allowed=True, reason="ok", wait_seconds=0)
        return VramGateDecision(
            allowed=False,
            reason="insufficient_free_vram",
            wait_seconds=DEFAULT_RETRY_WAIT_SECONDS,
        )

    # Ratio-based fallback
    if snapshot["used_ratio"] < high_water_ratio:
        return VramGateDecision(allowed=True, reason="ok", wait_seconds=0)
    return VramGateDecision(
        allowed=False,
        reason="high_water_mark",
        wait_seconds=DEFAULT_RETRY_WAIT_SECONDS,
    )
