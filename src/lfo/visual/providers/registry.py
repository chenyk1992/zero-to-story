"""Provider registry — resolves provider instances by revision ID.

Wraps VisualProviderService to instantiate the right provider class
from a provider revision.
"""
from __future__ import annotations

from typing import Any

from lfo.core.database import Database
from lfo.visual.providers.base import (
    VisualProvider,
)
from lfo.visual.providers.fake_managed import FakeManagedProvider


class ProviderRegistry:
    """Resolve provider instances from revision IDs."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, provider_revision_id: str) -> VisualProvider:
        """Get a provider instance by revision ID.

        Args:
            provider_revision_id: The revision ID to look up.

        Returns:
            A provider instance.

        Raises:
            ValueError: If revision not found or unknown provider type.
        """
        row = self.db.fetchone(
            """SELECT provider_type, config, capabilities
               FROM visual_provider_revisions
               WHERE revision_id = ? AND status = 'active'""",
            (provider_revision_id,),
        )
        if row is None:
            raise ValueError(
                f"Active provider revision '{provider_revision_id}' not found"
            )

        provider_type = row["provider_type"]
        config = _parse_json(row["config"])
        capabilities = _parse_json(row["capabilities"])

        if provider_type == "managed":
            return FakeManagedProvider(
                provider_revision_id=provider_revision_id,
                config=config,
                capabilities=capabilities,
            )
        elif provider_type == "manual":
            from lfo.visual.providers.manual import ManualProvider
            return ManualProvider(
                provider_revision_id=provider_revision_id,
                config=config,
                capabilities=capabilities,
            )
        elif provider_type == "delegated":
            from lfo.visual.providers.delegated import DelegatedProvider
            return DelegatedProvider(
                provider_revision_id=provider_revision_id,
                config=config,
                capabilities=capabilities,
            )
        else:
            raise ValueError(f"Unknown provider type '{provider_type}'")


def _parse_json(raw: str | None) -> dict[str, Any]:
    """Parse JSON string to dict."""
    import json
    if not raw:
        return {}
    return json.loads(raw)
