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
from .operations import validate_operation_references
from .package import (
    SCHEMA_ID,
    ApprovalDeclaration,
    ProjectInfo,
    VideoExecutionPackage,
    validate_package,
)
from .production_lock import (
    AUDIO_ACCEPTANCE_EXTENSION,
    PRODUCTION_LOCK_EXTENSION,
    PROMPT_MANIFEST_EXTENSION,
    PROMPT_MANIFEST_MUTABLE_FIELDS,
    aggregate_plan_hash,
    build_production_lock,
    clip_plan_hash,
    package_plan_hash,
    package_plan_payload,
    validate_audio_acceptance,
    validate_production_lock,
    with_production_lock,
)
from .timeline import OutputPolicy, TimelineSegment, TimelineSpec
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
    "TimelineSegment",
    "TimelineSpec",
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
    "validate_operation_references",
    "AUDIO_ACCEPTANCE_EXTENSION",
    "PROMPT_MANIFEST_EXTENSION",
    "PROMPT_MANIFEST_MUTABLE_FIELDS",
    "PRODUCTION_LOCK_EXTENSION",
    "aggregate_plan_hash",
    "build_production_lock",
    "clip_plan_hash",
    "package_plan_hash",
    "package_plan_payload",
    "validate_audio_acceptance",
    "validate_production_lock",
    "with_production_lock",
    "validate_package",
]
