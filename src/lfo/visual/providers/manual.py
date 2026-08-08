"""ManualProvider — human-driven exchange provider (spec §15–17)."""
from __future__ import annotations

from typing import Any

from lfo.visual.capabilities import ProviderProbeResult, VisualCapabilities
from lfo.visual.providers.base import ExchangeVisualProvider


class ManualProvider(ExchangeVisualProvider):
    """Provider that relies on human manual export/import."""

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

    @property
    def provider_revision_id(self) -> str:
        return self._revision_id

    def declared_capabilities(self) -> VisualCapabilities:
        return self._capabilities

    def probe(self) -> ProviderProbeResult:
        import datetime
        now = datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%fZ"
        )
        return ProviderProbeResult(
            available=True,
            checked_at=now,
            latency_ms=None,
            provider_version=None,
            capabilities=self._capabilities,
            error_code=None,
            message="Manual provider (no probe needed)",
        )

    def export_task(self, task_id: str) -> str:
        """No-op for manual — returns a placeholder exchange ID."""
        import uuid
        return str(uuid.uuid4())

    def import_result(self, manifest: dict[str, Any]) -> str:
        """Manual import — returns asset_id from manifest."""
        return manifest.get("asset_id", "")
