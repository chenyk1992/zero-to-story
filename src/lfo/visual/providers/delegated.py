"""DelegatedProvider — delegated agent exchange provider (spec §15–17)."""
from __future__ import annotations

from typing import Any

from lfo.visual.capabilities import ProviderProbeResult, VisualCapabilities
from lfo.visual.providers.base import ExchangeVisualProvider


class DelegatedProvider(ExchangeVisualProvider):
    """Provider that delegates to an external agent."""

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
            message="Delegated provider (agent-managed)",
        )

    def export_task(self, task_id: str) -> str:
        """Export task for delegated agent processing."""
        import uuid
        return str(uuid.uuid4())

    def import_result(self, manifest: dict[str, Any]) -> str:
        """Import result from delegated agent."""
        return manifest.get("asset_id", "")
