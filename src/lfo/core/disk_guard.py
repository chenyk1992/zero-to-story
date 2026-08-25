"""Disk-space preflight for batch pipeline runs.

The pipeline writes a lot of large files (raw ComfyUI output, end-frame PNGs,
SRT, final assembly). On a single-machine setup
the user can easily run out of disk without warning. This module gives
the pipeline a place to ask "is there enough room before we start?" and
decide between OK / warn-only / hard-block.

Design constraints
------------------
- Pure function on top of ``shutil.disk_usage``; never raises — returns
  ``level="unknown"`` if the OS call fails. The pipeline must always
  be able to start.
- Caller decides what to do with a ``warn`` (log + continue) vs
  ``critical`` (log + ask the user, or refuse if --strict).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

#: Default warn threshold: 50 GB free. Below this we start flagging
#: future runs in a multi-shot batch (a single ComfyUI video can be
#: 0.5-2 GB; a 5-shot day is 2.5-10 GB; 50 GB gives ~1 week of buffer).
DEFAULT_WARN_THRESHOLD_GB = 50

#: Default critical threshold: 5 GB free. Below this we risk an
#: out-of-disk crash mid-pipeline.
DEFAULT_CRITICAL_THRESHOLD_GB = 5


@dataclass(frozen=True)
class DiskSpaceStatus:
    """Result of a single disk-space check.

    Attributes:
        path: The path that was checked.
        free_bytes: Free space at ``path`` in bytes (``0`` if unknown).
        total_bytes: Total capacity at ``path`` in bytes (``0`` if unknown).
        level: One of ``"ok"``, ``"warn"``, ``"critical"``, ``"unknown"``.
        should_warn: True for ``warn`` and ``critical`` (and ``unknown``).
        should_block: True only for ``critical``. The pipeline should
            refuse to start unless the caller has explicitly opted in.
        error: When ``level="unknown"``, the underlying error message.
    """

    path: str
    free_bytes: int
    total_bytes: int
    level: str
    should_warn: bool
    should_block: bool
    error: str = ""


def check_disk_space(
    path: str,
    warn_threshold_gb: int = DEFAULT_WARN_THRESHOLD_GB,
    critical_threshold_gb: int = DEFAULT_CRITICAL_THRESHOLD_GB,
) -> DiskSpaceStatus:
    """Check free space at ``path`` against the warn/critical thresholds.

    Never raises. Returns a status whose ``level`` is one of
    ``ok / warn / critical / unknown``.
    """
    try:
        usage = shutil.disk_usage(path)
    except Exception as e:
        return DiskSpaceStatus(
            path=path,
            free_bytes=0,
            total_bytes=0,
            level="unknown",
            should_warn=True,
            should_block=False,
            error=str(e),
        )

    free = int(usage.free)
    total = int(usage.total)
    free_gb = free / (1024**3)

    if free_gb < critical_threshold_gb:
        level = "critical"
    elif free_gb < warn_threshold_gb:
        level = "warn"
    else:
        level = "ok"

    return DiskSpaceStatus(
        path=path,
        free_bytes=free,
        total_bytes=total,
        level=level,
        should_warn=(level in ("warn", "critical")),
        should_block=(level == "critical"),
    )
