"""CapabilityManifest — declares what a backend/workflow revision can do.

All backend-specific constraints (frame grids, resolution limits, reference
slots, fps, audio capability) live here, not in generic validators.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapabilityManifest:
    """Immutable capability declaration for a backend workflow revision.

    A ``CapabilityManifest`` is the single source of truth for what a backend
    can and cannot do. Generic code never hardcodes H3's ``17k+5`` frame rule
    or ``864x480/24`` defaults — those live in the manifest that H3 provides.
    """

    # --- Identity ---
    backend_id: str
    revision: str
    workflow_hash: str

    # --- Operations ---
    operations: list[str] = field(default_factory=list)

    # --- Input constraints ---
    accepted_media_types: list[str] = field(default_factory=list)
    max_references: int = 0

    # --- Temporal constraints ---
    duration_constraints: dict[str, Any] = field(default_factory=dict)
    frame_constraints: dict[str, Any] = field(default_factory=dict)

    # --- Spatial constraints ---
    resolution_constraints: dict[str, Any] = field(default_factory=dict)
    fps_constraints: list[float] = field(default_factory=list)

    # --- Audio ---
    native_audio_capability: str = "none"  # "none" | "optional" | "always"

    # --- Reproducibility ---
    seed_capability: bool = False
    reproducibility_claim: str = "non_reproducible"  # exact | best_effort | non_reproducible

    # --- Requirements ---
    required_models: list[str] = field(default_factory=list)
    required_nodes: list[str] = field(default_factory=list)

    # --- Output signature ---
    output_signature: dict[str, Any] = field(default_factory=dict)

    # --- Extensions ---
    extensions: dict[str, Any] = field(default_factory=dict)

    def supports_operation(self, operation: str) -> bool:
        return operation in self.operations

    def accepts_media_type(self, media_type: str) -> bool:
        return media_type in self.accepted_media_types

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityManifest:
        if not isinstance(data, dict):
            raise TypeError(f"CapabilityManifest: expected dict, got {type(data).__name__}")
        backend_id = data.get("backend_id")
        if not isinstance(backend_id, str) or not backend_id:
            raise ValueError("CapabilityManifest.backend_id: required string")
        revision = data.get("revision")
        if not isinstance(revision, str) or not revision:
            raise ValueError("CapabilityManifest.revision: required string")
        workflow_hash = data.get("workflow_hash")
        if not isinstance(workflow_hash, str) or not workflow_hash:
            raise ValueError("CapabilityManifest.workflow_hash: required string")
        native_audio = data.get("native_audio_capability", "none")
        if native_audio not in ("none", "optional", "always"):
            raise ValueError(
                f"CapabilityManifest.native_audio_capability: must be "
                f"none|optional|always, got {native_audio!r}"
            )
        repro = data.get("reproducibility_claim", "non_reproducible")
        if repro not in ("exact", "best_effort", "non_reproducible"):
            raise ValueError(
                f"CapabilityManifest.reproducibility_claim: must be "
                f"exact|best_effort|non_reproducible, got {repro!r}"
            )
        max_refs = data.get("max_references", 0)
        if not isinstance(max_refs, int) or isinstance(max_refs, bool) or max_refs < 0:
            raise ValueError("CapabilityManifest.max_references: required non-negative int")
        return cls(
            backend_id=backend_id,
            revision=revision,
            workflow_hash=workflow_hash,
            operations=list(data.get("operations", [])),
            accepted_media_types=list(data.get("accepted_media_types", [])),
            max_references=max_refs,
            duration_constraints=dict(data.get("duration_constraints", {})),
            frame_constraints=dict(data.get("frame_constraints", {})),
            resolution_constraints=dict(data.get("resolution_constraints", {})),
            fps_constraints=list(data.get("fps_constraints", [])),
            native_audio_capability=native_audio,
            seed_capability=bool(data.get("seed_capability", False)),
            reproducibility_claim=repro,
            required_models=list(data.get("required_models", [])),
            required_nodes=list(data.get("required_nodes", [])),
            output_signature=dict(data.get("output_signature", {})),
            extensions=dict(data.get("extensions", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "revision": self.revision,
            "workflow_hash": self.workflow_hash,
            "operations": list(self.operations),
            "accepted_media_types": list(self.accepted_media_types),
            "max_references": self.max_references,
            "duration_constraints": dict(self.duration_constraints),
            "frame_constraints": dict(self.frame_constraints),
            "resolution_constraints": dict(self.resolution_constraints),
            "fps_constraints": list(self.fps_constraints),
            "native_audio_capability": self.native_audio_capability,
            "seed_capability": self.seed_capability,
            "reproducibility_claim": self.reproducibility_claim,
            "required_models": list(self.required_models),
            "required_nodes": list(self.required_nodes),
            "output_signature": dict(self.output_signature),
            "extensions": dict(self.extensions),
        }
