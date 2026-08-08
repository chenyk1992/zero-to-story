"""FakeManagedProvider — test double for managed visual providers.

Simulates submit/collect/cancel with configurable fault injection
for testing error paths (corrupt, wrong_size, timeout, unavailable, hash_mismatch).
"""
from __future__ import annotations

import uuid
from typing import Any

from lfo.visual.capabilities import ProviderProbeResult, VisualCapabilities
from lfo.visual.providers.base import ManagedVisualProvider


class FakeManagedProvider(ManagedVisualProvider):
    """In-memory fake managed provider for testing."""

    def __init__(
        self,
        *,
        provider_revision_id: str,
        config: dict[str, Any],
        capabilities: dict[str, Any],
    ) -> None:
        self._revision_id = provider_revision_id
        self._config = config
        self._capabilities = VisualCapabilities(**capabilities)
        self._next_response: dict[str, Any] = {}
        self._submitted: dict[str, dict[str, Any]] = {}
        self._collect_count: dict[str, int] = {}

    @property
    def provider_revision_id(self) -> str:
        return self._revision_id

    def declared_capabilities(self) -> VisualCapabilities:
        return self._capabilities

    def probe(self) -> ProviderProbeResult:
        """Probe availability. Respects 'unavailable' fault if set."""
        import datetime
        now = datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%fZ"
        )
        if self._next_response.get("unavailable"):
            return ProviderProbeResult(
                available=False,
                checked_at=now,
                latency_ms=None,
                provider_version=None,
                capabilities=self._capabilities,
                error_code="UNAVAILABLE",
                message="Provider unavailable (fake)",
            )
        return ProviderProbeResult(
            available=True,
            checked_at=now,
            latency_ms=10,
            provider_version="fake-1.0",
            capabilities=self._capabilities,
            error_code=None,
            message=None,
        )

    def set_next_response(
        self,
        *,
        corrupt: bool = False,
        wrong_size: bool = False,
        timeout: bool = False,
        unavailable: bool = False,
        hash_mismatch: bool = False,
    ) -> None:
        """Configure the fault for the next submit/collect cycle."""
        self._next_response = {
            "corrupt": corrupt,
            "wrong_size": wrong_size,
            "timeout": timeout,
            "unavailable": unavailable,
            "hash_mismatch": hash_mismatch,
        }

    def submit(self, task_package: dict[str, Any]) -> str:
        """Simulate submission. Returns execution ID."""
        if self._next_response.get("unavailable"):
            raise RuntimeError("Provider unavailable (fake)")
        execution_id = str(uuid.uuid4())
        self._submitted[execution_id] = task_package
        self._collect_count[execution_id] = 0
        return execution_id

    def collect(self, execution_id: str) -> dict[str, Any]:
        """Simulate result collection.

        Returns a manifest dict. Faults (corrupt, wrong_size, hash_mismatch)
        are consumed once and only affect the first collect call.
        """
        if execution_id not in self._submitted:
            raise ValueError(f"Unknown execution '{execution_id}'")

        count = self._collect_count.get(execution_id, 0)
        self._collect_count[execution_id] = count + 1

        fault = dict(self._next_response)
        # Consume one-shot faults
        self._next_response = {
            k: False for k in self._next_response
        }

        if fault.get("timeout"):
            raise TimeoutError("Execution timed out (fake)")

        # Build a fake result manifest
        task_pkg = self._submitted[execution_id]
        content: dict[str, Any] = {
            "file_path": "fake_output.png",
            "width": 1024,
            "height": 1024,
        }

        if fault.get("wrong_size"):
            content["width"] = 640
            content["height"] = 640

        import hashlib
        fake_bytes = b"fake image content"
        file_hash = hashlib.sha256(fake_bytes).hexdigest()

        if fault.get("hash_mismatch"):
            file_hash = "f" * 64  # wrong hash

        if fault.get("corrupt"):
            file_hash = "not-a-valid-hash"

        return {
            "task_id": task_pkg.get("task_id", ""),
            "content": content,
            "file_hash": file_hash,
        }

    def cancel(self, execution_id: str) -> None:
        """Cancel a fake execution."""
        self._submitted.pop(execution_id, None)
        self._collect_count.pop(execution_id, None)
