"""BackendRegistry — store and query backend manifests by backend_id.

The registry is an in-memory index used at materialization time. It holds
all registered ``CapabilityManifest`` instances and supports lookup by
backend_id + revision or by operation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capabilities import CapabilityManifest


@dataclass
class BackendRegistry:
    """In-memory registry of backend capability manifests."""

    _manifests: dict[str, CapabilityManifest] = field(default_factory=dict)
    # Index: operation -> list of (backend_id, revision) keys
    _op_index: dict[str, list[str]] = field(default_factory=dict)

    def register(self, manifest: CapabilityManifest) -> None:
        """Register a capability manifest.

        Raises:
            ValueError if a manifest with the same backend_id + revision
            and a different workflow_hash is already registered.
        """
        key = self._key(manifest.backend_id, manifest.revision)
        existing = self._manifests.get(key)
        if existing is not None and existing.workflow_hash != manifest.workflow_hash:
            raise ValueError(
                f"Backend {manifest.backend_id!r} revision {manifest.revision!r} "
                f"already registered with different workflow_hash"
            )
        self._manifests[key] = manifest
        # Update operation index
        for op in manifest.operations:
            if op not in self._op_index:
                self._op_index[op] = []
            if key not in self._op_index[op]:
                self._op_index[op].append(key)

    def get(self, backend_id: str, revision: str) -> CapabilityManifest | None:
        """Get manifest by backend_id + revision."""
        key = self._key(backend_id, revision)
        return self._manifests.get(key)

    def query_by_operation(self, operation: str) -> list[CapabilityManifest]:
        """Return all manifests that support the given operation."""
        keys = self._op_index.get(operation, [])
        return [self._manifests[k] for k in keys if k in self._manifests]

    def all_manifests(self) -> list[CapabilityManifest]:
        """Return all registered manifests."""
        return list(self._manifests.values())

    @property
    def count(self) -> int:
        return len(self._manifests)

    @staticmethod
    def _key(backend_id: str, revision: str) -> str:
        return f"{backend_id}@{revision}"
