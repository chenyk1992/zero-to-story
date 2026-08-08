"""Visual Provider Service — scoped provider revision lifecycle.

Supports three provider types (manual, delegated, managed) across two
scopes (project, global). At most one active revision per (provider_id,
scope). Resolution priority: project scope > global scope.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from lfo.core.database import Database
from lfo.visual.errors import VisualProviderError
from lfo.visual.provider_config import validate_provider_config


class VisualProviderService:
    """Manage visual provider revisions with CAS activation."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_draft(
        self,
        *,
        provider_id: str,
        scope_type: str,
        scope_id: str,
        provider_type: str,
        adapter_name: str,
        config: dict[str, Any],
        capabilities: dict[str, Any],
        serial_group: str | None = None,
        max_concurrency: int = 1,
    ) -> str:
        """Create a new provider revision draft.

        Args:
            provider_id: Stable provider identifier.
            scope_type: 'project' or 'global'.
            scope_id: Project ID or '*'.
            provider_type: 'manual', 'delegated', or 'managed'.
            adapter_name: Adapter implementation name.
            config: Provider config dict (validated).
            capabilities: Capability flags dict.
            serial_group: Optional serialization group.
            max_concurrency: Max concurrent executions.

        Returns:
            The new revision_id.

        Raises:
            VisualProviderError: On invalid config.
        """
        # Validates config (raises VisualProviderError on invalid)
        validated = validate_provider_config(provider_type, config)

        revision_id = str(uuid.uuid4())
        now = _now()

        # Set parent to current active revision in same scope (linear lineage)
        parent = self._find_active_revision(provider_id, scope_type, scope_id)

        self.db.execute(
            """INSERT INTO visual_provider_revisions
               (revision_id, provider_id, scope_type, scope_id,
                provider_type, adapter_name, config, capabilities,
                status, parent_revision_id, serial_group,
                max_concurrency, activated_at,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                revision_id, provider_id, scope_type, scope_id,
                provider_type, adapter_name,
                json.dumps(validated, ensure_ascii=False),
                json.dumps(capabilities, ensure_ascii=False),
                "draft",
                parent,
                serial_group,
                max_concurrency,
                None,
                now, now,
            ),
        )
        return revision_id

    def activate(self, provider_revision_id: str, *, allow_unavailable: bool = False) -> None:
        """Activate a provider revision, superseding any active in same scope.

        Args:
            provider_revision_id: The revision to activate.
            allow_unavailable: If True, skip availability probe.

        Raises:
            VisualProviderError: If revision not found or not a draft.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                """SELECT provider_id, scope_type, scope_id, status
                   FROM visual_provider_revisions WHERE revision_id = ?""",
                (provider_revision_id,),
            ).fetchone()
            if row is None:
                raise VisualProviderError(
                    f"Provider revision '{provider_revision_id}' not found"
                )
            if row["status"] != "draft":
                raise VisualProviderError(
                    f"Cannot activate revision in state '{row['status']}'"
                )

            provider_id = row["provider_id"]
            scope_type = row["scope_type"]
            scope_id = row["scope_id"]
            now = _now()

            # Supersede existing active in same scope
            conn.execute(
                """UPDATE visual_provider_revisions
                   SET status = 'superseded', updated_at = ?
                   WHERE provider_id = ? AND scope_type = ? AND scope_id = ?
                   AND status = 'active'""",
                (now, provider_id, scope_type, scope_id),
            )

            # Activate this revision
            cursor = conn.execute(
                """UPDATE visual_provider_revisions
                   SET status = 'active', activated_at = ?, updated_at = ?
                   WHERE revision_id = ? AND status = 'draft'""",
                (now, now, provider_revision_id),
            )
            if cursor.rowcount != 1:
                raise VisualProviderError(
                    f"Failed to activate revision '{provider_revision_id}': "
                    "concurrent modification detected"
                )

    def disable(self, provider_revision_id: str) -> None:
        """Disable an active provider revision.

        Args:
            provider_revision_id: The revision to disable.

        Raises:
            VisualProviderError: If revision not found or not active.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT status FROM visual_provider_revisions WHERE revision_id = ?",
                (provider_revision_id,),
            ).fetchone()
            if row is None:
                raise VisualProviderError(
                    f"Provider revision '{provider_revision_id}' not found"
                )
            now = _now()
            cursor = conn.execute(
                """UPDATE visual_provider_revisions
                   SET status = 'disabled', updated_at = ?
                   WHERE revision_id = ? AND status = 'active'""",
                (now, provider_revision_id),
            )
            if cursor.rowcount != 1:
                raise VisualProviderError(
                    f"Cannot disable revision '{provider_revision_id}': "
                    f"not in active state (current: {row['status']})"
                )

    def resolve_active(self, provider_id: str, *, project_id: str) -> dict[str, Any] | None:
        """Resolve the active provider revision for a provider.

        Priority: project scope > global scope.

        Returns:
            Dict with revision fields, or None if no active revision.
        """
        # Try project scope first
        row = self.db.fetchone(
            """SELECT revision_id, provider_id, scope_type, scope_id,
                      provider_type, adapter_name, config, capabilities,
                      status, activated_at
               FROM visual_provider_revisions
               WHERE provider_id = ? AND scope_type = 'project' AND scope_id = ?
                     AND status = 'active'
               ORDER BY activated_at DESC
               LIMIT 1""",
            (provider_id, project_id),
        )
        if row is None:
            # Fall back to global scope
            row = self.db.fetchone(
                """SELECT revision_id, provider_id, scope_type, scope_id,
                          provider_type, adapter_name, config, capabilities,
                          status, activated_at
                   FROM visual_provider_revisions
                   WHERE provider_id = ? AND scope_type = 'global'
                         AND status = 'active'
                   ORDER BY activated_at DESC
                   LIMIT 1""",
                (provider_id,),
            )
        if row is None:
            return None

        return {
            "revision_id": row["revision_id"],
            "provider_id": row["provider_id"],
            "scope_type": row["scope_type"],
            "scope_id": row["scope_id"],
            "provider_type": row["provider_type"],
            "adapter_name": row["adapter_name"],
            "config": json.loads(row["config"]),
            "capabilities": json.loads(row["capabilities"]),
            "status": row["status"],
            "activated_at": row["activated_at"],
        }

    def _find_active_revision(
        self, provider_id: str, scope_type: str, scope_id: str
    ) -> str | None:
        """Find the currently active revision in a scope (for parent linkage)."""
        row = self.db.fetchone(
            """SELECT revision_id FROM visual_provider_revisions
               WHERE provider_id = ? AND scope_type = ? AND scope_id = ?
                     AND status = 'active'
               LIMIT 1""",
            (provider_id, scope_type, scope_id),
        )
        return row["revision_id"] if row else None


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%fZ"
    )
