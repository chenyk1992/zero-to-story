"""BackendManifest — top-level manifest with validation and JSON loading.

A ``BackendManifest`` wraps a :class:`CapabilityManifest` with metadata
(authorship, description, environment requirements) and provides structure
validation and JSON file loading.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

from .capabilities import CapabilityManifest


@dataclass
class BackendManifest:
    """Complete backend manifest including capability and metadata."""

    capability: CapabilityManifest
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    authors: list[str] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackendManifest:
        if not isinstance(data, dict):
            raise TypeError(f"BackendManifest: expected dict, got {type(data).__name__}")
        cap_data = data.get("capability")
        if not isinstance(cap_data, dict):
            raise ValueError("BackendManifest.capability: required object")
        capability = CapabilityManifest.from_dict(cap_data)
        return cls(
            capability=capability,
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            authors=list(data.get("authors", [])),
            environment=dict(data.get("environment", {})),
            extensions=dict(data.get("extensions", {})),
        )

    @classmethod
    def from_json(cls, path: pathlib.Path | str) -> BackendManifest:
        """Load a BackendManifest from a JSON file."""
        p = pathlib.Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise TypeError(f"{p}: expected JSON object, got {type(data).__name__}")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.to_dict(),
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "authors": list(self.authors),
            "environment": dict(self.environment),
            "extensions": dict(self.extensions),
        }


def validate_manifest(data: dict[str, Any]) -> list[str]:
    """Validate a raw manifest dict. Returns a list of human-readable errors.

    An empty list means the manifest is structurally valid. This function
    never raises — it collects all errors it can find.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$: expected JSON object"]

    cap = data.get("capability")
    if not isinstance(cap, dict):
        errors.append("$.capability: required object")
        return errors  # Can't validate further without capability

    # Required capability fields
    for field_name in ("backend_id", "revision", "workflow_hash"):
        v = cap.get(field_name)
        if not isinstance(v, str) or not v:
            errors.append(f"$.capability.{field_name}: required string")

    # Operations
    ops = cap.get("operations")
    if not isinstance(ops, list):
        errors.append("$.capability.operations: required array of strings")
    else:
        for i, op in enumerate(ops):
            if not isinstance(op, str):
                errors.append(f"$.capability.operations[{i}]: must be string")

    # accepted_media_types
    mt = cap.get("accepted_media_types")
    if not isinstance(mt, list):
        errors.append("$.capability.accepted_media_types: required array")
    else:
        for i, m in enumerate(mt):
            if not isinstance(m, str):
                errors.append(f"$.capability.accepted_media_types[{i}]: must be string")

    # max_references
    mr = cap.get("max_references")
    if not isinstance(mr, int) or isinstance(mr, bool) or mr < 0:
        errors.append("$.capability.max_references: required non-negative integer")

    # native_audio_capability
    na = cap.get("native_audio_capability", "none")
    if na not in ("none", "optional", "always"):
        errors.append(
            f"$.capability.native_audio_capability: must be none|optional|always, got {na!r}"
        )

    # reproducibility_claim
    rc = cap.get("reproducibility_claim", "non_reproducible")
    if rc not in ("exact", "best_effort", "non_reproducible"):
        errors.append(
            f"$.capability.reproducibility_claim: must be "
            f"exact|best_effort|non_reproducible, got {rc!r}"
        )

    # Constraint dicts
    for key in ("duration_constraints", "frame_constraints", "resolution_constraints"):
        v = cap.get(key)
        if not isinstance(v, dict):
            errors.append(f"$.capability.{key}: required object")

    # fps_constraints
    fps = cap.get("fps_constraints")
    if not isinstance(fps, list):
        errors.append("$.capability.fps_constraints: required array")

    # seed_capability
    sc = cap.get("seed_capability")
    if not isinstance(sc, bool):
        errors.append("$.capability.seed_capability: required boolean")

    return errors
