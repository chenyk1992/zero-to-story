"""Visual Task Compiler identity (spec §10).

The compiler identity captures the toolchain version that produced a
visual task contract, so toolchain changes invalidate downstream results.
Persisted as `compiler_identity_json` in visual_task_contracts.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VisualTaskCompilerIdentity:
    """Identity of the visual task compiler toolchain."""
    name: str
    semver: str
    source_hash: str | None = None


# Module-level compiler identity — frozen for the process lifetime.
_COMPILER_IDENTITY = VisualTaskCompilerIdentity(
    name="lfo-visual",
    semver="1.0.0",
    source_hash=None,
)


def get_compiler_identity() -> VisualTaskCompilerIdentity:
    """Return the current visual task compiler identity."""
    return _COMPILER_IDENTITY


def compiler_identity_json() -> str:
    """Serialize the compiler identity to JSON for persistence."""
    return json.dumps(asdict(_COMPILER_IDENTITY), ensure_ascii=False)
