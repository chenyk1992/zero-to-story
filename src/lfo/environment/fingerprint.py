"""Dual fingerprint — environment snapshot + execution environment hash."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .discovery import DiscoveredEnvironment


@dataclass
class EnvironmentSnapshot:
    """Full environment snapshot for traceability (may include paths)."""

    machine_id: str
    captured_at: str  # ISO 8601
    comfyui_root: str
    comfyui_version: str
    input_root: str
    output_root: str
    python_version: str
    torch_version: str
    gpu_name: str
    extra: dict = field(default_factory=dict)

    @property
    def execution_environment_hash(self) -> str:
        """Hash excluding paths — used for cache/params comparison."""
        return compute_execution_environment_hash(self)

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "captured_at": self.captured_at,
            "comfyui_root": self.comfyui_root,
            "comfyui_version": self.comfyui_version,
            "input_root": self.input_root,
            "output_root": self.output_root,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "gpu_name": self.gpu_name,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EnvironmentSnapshot:
        extra = data.pop("extra", {})
        return cls(extra=extra, **data)


def create_environment_snapshot(
    machine_id: str,
    discovery: DiscoveredEnvironment,
    comfyui_root: str = "",
    comfyui_version: str = "",
    input_root: str = "",
    output_root: str = "",
    python_version: str = "",
    torch_version: str = "",
    extra: dict | None = None,
) -> EnvironmentSnapshot:
    """Create a snapshot from discovery results."""
    now = datetime.now(UTC).isoformat()

    # Use comfyui_root from machine_profile if not provided
    if not comfyui_root and discovery.comfyui_root:
        comfyui_root = str(discovery.comfyui_root)
    if not input_root and discovery.input_dir:
        input_root = str(discovery.input_dir)
    if not output_root and discovery.output_dir:
        output_root = str(discovery.output_dir)

    return EnvironmentSnapshot(
        machine_id=machine_id,
        captured_at=now,
        comfyui_root=comfyui_root,
        comfyui_version=comfyui_version,
        input_root=input_root,
        output_root=output_root,
        python_version=python_version,
        torch_version=torch_version,
        gpu_name=discovery.gpu_name,
        extra=extra or {},
    )


def compute_execution_environment_hash(
    snapshot: EnvironmentSnapshot | None = None,
    *,
    workflow_hashes: dict[str, str] | None = None,
    node_schema_hashes: dict[str, str] | None = None,
    model_fingerprints: dict[str, str] | None = None,
) -> str:
    """Compute hash that EXCLUDES paths but INCLUDES execution-affecting values.

    This hash is used for cache comparison: if the execution environment
    hash changes, cached results may be stale.
    """
    components: dict[str, str] = {}

    if snapshot is not None:
        # Include execution-affecting values, exclude paths
        if snapshot.comfyui_version:
            components["comfyui_version"] = snapshot.comfyui_version
        if snapshot.python_version:
            components["python_version"] = snapshot.python_version
        if snapshot.torch_version:
            components["torch_version"] = snapshot.torch_version
        if snapshot.gpu_name:
            components["gpu_name"] = snapshot.gpu_name

    if workflow_hashes:
        for k in sorted(workflow_hashes):
            components[f"wf:{k}"] = workflow_hashes[k]

    if node_schema_hashes:
        for k in sorted(node_schema_hashes):
            components[f"schema:{k}"] = node_schema_hashes[k]

    if model_fingerprints:
        for k in sorted(model_fingerprints):
            components[f"model:{k}"] = model_fingerprints[k]

    # Deterministic serialization
    raw = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
