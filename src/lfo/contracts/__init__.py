"""LFO Video Execution Package v1 — public contract models.

This package defines the sole public boundary between Creative Skills and LFO:
a Skill submits a ``VideoExecutionPackage``; LFO executes it.

Constraints:
- Models are dataclasses with strict ``from_dict`` / ``to_dict``.
- Unknown *core* fields are rejected; ``extensions`` are preserved opaquely.
- H3 frame grids, resolution limits, reference slot counts, etc. live in backend
  manifests — not here. This package is backend-agnostic.
"""
from __future__ import annotations

from .assets import AssetSource, AssetSpec, ProvenanceSpec, ReviewDeclaration
from .builder import VideoPackageBuilder
from .clips import (
    AudioPolicy,
    AudioTrackSpec,
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    ReferenceSpec,
    SubtitleCue,
    SubtitleSpec,
)
from .errors import ValidationError, ValidationResult
from .package import (
    SCHEMA_ID,
    ApprovalDeclaration,
    ProjectInfo,
    VideoExecutionPackage,
    validate_package,
)
from .timeline import OutputPolicy
from .validation import package_content_hash

__all__ = [
    "SCHEMA_ID",
    "ApprovalDeclaration",
    "AssetSource",
    "AssetSpec",
    "AudioPolicy",
    "AudioTrackSpec",
    "BindingPolicy",
    "ClipSpec",
    "GenerationRequirements",
    "GenerationSpec",
    "OutputPolicy",
    "ProjectInfo",
    "ProvenanceSpec",
    "ReferenceSpec",
    "ReviewDeclaration",
    "SubtitleCue",
    "SubtitleSpec",
    "ValidationError",
    "ValidationResult",
    "VideoExecutionPackage",
    "VideoPackageBuilder",
    "package_content_hash",
    "validate_package",
]
