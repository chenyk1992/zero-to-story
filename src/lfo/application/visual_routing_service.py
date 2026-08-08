"""Visual Routing Service — routes visual tasks to providers (spec §15–17).

Routing order: override → purpose rules → defaults → fallbacks.
Scope priority: project > global.
Writes routing_snapshot_json to the contract.
Transitions to READY + ROUTED or WAITING_ASSETS + BLOCKED.
"""
from __future__ import annotations

import json
from typing import Any

from lfo.application.visual_provider_service import VisualProviderService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.capabilities import VisualCapabilities
from lfo.visual.errors import VisualProviderError
from lfo.visual.providers.registry import ProviderRegistry
from lfo.visual.stages import VisualStage


class VisualRoutingService:
    """Route visual tasks to providers."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._provider_svc = VisualProviderService(db)
        self._task_svc = VisualTaskService(db)
        self._registry = ProviderRegistry(db)

    def route(self, task_id: str) -> dict[str, Any]:
        """Route a visual task to the best available provider.

        1. Get task contract (purpose, required capabilities)
        2. Check provider_override
        3. Resolve active providers (project scope > global)
        4. Match by capability
        5. Write routing_snapshot_json
        6. Transition to READY + ROUTED or WAITING_ASSETS + BLOCKED

        Args:
            task_id: The visual task to route.

        Returns:
            Dict with routing result (provider_id, revision_id, etc.).

        Raises:
            VisualProviderError: On routing failure.
        """
        contract = self.db.fetchone(
            """SELECT purpose, provider_id, provider_revision_id,
                      routing_snapshot_json
               FROM visual_task_contracts WHERE task_id = ?""",
            (task_id,),
        )
        if contract is None:
            raise VisualProviderError(f"No contract found for task {task_id}")

        purpose = contract["purpose"]
        override_id = contract["provider_id"]

        # Get task's project
        task_row = self.db.fetchone(
            "SELECT project_id FROM tasks WHERE task_id = ?", (task_id,)
        )
        if task_row is None:
            raise VisualProviderError(f"Task {task_id} not found")
        project_id = task_row["project_id"]

        # Determine required capabilities from purpose
        required = self._required_capabilities(purpose)

        # 1. Override wins
        if override_id:
            provider = self._try_resolve(override_id, project_id)
            if provider:
                return self._apply_route(task_id, provider, "override")

        # 2. Resolve active providers for project
        #    (project scope first, then global)
        providers = self._list_active_providers(project_id)

        # 3. Match by capability
        for provider_id, rev_id, caps_json in providers:
            caps = VisualCapabilities(**json.loads(caps_json))
            if self._capabilities_match(caps, required):
                return self._apply_route(
                    task_id,
                    {"provider_id": provider_id, "revision_id": rev_id,
                     "capabilities": caps},
                    "capability_match",
                )

        # 4. No provider found → BLOCKED
        self._task_svc.transition(
            task_id,
            expected_task_status=TaskStatus.PLANNED,
            expected_visual_stage=VisualStage.UNROUTED,
            new_task_status=TaskStatus.WAITING_ASSETS,
            new_visual_stage=VisualStage.BLOCKED,
            reason="no matching provider",
        )
        return {
            "routed": False,
            "reason": "no matching provider",
            "provider_id": None,
            "revision_id": None,
        }

    def dry_run(
        self,
        *,
        project_id: str,
        purpose: str,
        required_capabilities: list[str],
    ) -> dict[str, Any]:
        """Simulate routing without modifying any state.

        Returns which provider would be selected.
        """
        required = VisualCapabilities(**{
            cap: True for cap in required_capabilities
        } if required_capabilities else {})

        providers = self._list_active_providers(project_id)
        for provider_id, rev_id, caps_json in providers:
            caps = VisualCapabilities(**json.loads(caps_json))
            if self._capabilities_match(caps, required):
                return {
                    "routed": True,
                    "provider_id": provider_id,
                    "revision_id": rev_id,
                    "capabilities": caps,
                }
        return {
            "routed": False,
            "reason": "no matching provider",
            "provider_id": None,
            "revision_id": None,
        }

    def _apply_route(
        self,
        task_id: str,
        provider: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        """Apply a route: write snapshot, update contract, transition."""
        provider_id = provider["provider_id"]
        revision_id = provider["revision_id"]

        # Write routing snapshot to contract
        snapshot = {
            "provider_id": provider_id,
            "provider_revision_id": revision_id,
            "routed_at": _now(),
            "reason": reason,
        }
        self.db.execute(
            """UPDATE visual_task_contracts
               SET provider_id = ?, provider_revision_id = ?,
                   routing_snapshot_json = ?, updated_at = ?
               WHERE task_id = ?""",
            (
                provider_id, revision_id,
                json.dumps(snapshot, ensure_ascii=False),
                _now(),
                task_id,
            ),
        )

        # Transition to READY + ROUTED
        self._task_svc.transition(
            task_id,
            expected_task_status=TaskStatus.PLANNED,
            expected_visual_stage=VisualStage.UNROUTED,
            new_task_status=TaskStatus.READY,
            new_visual_stage=VisualStage.ROUTED,
            reason=f"routed to {provider_id}",
        )

        return {
            "routed": True,
            "provider_id": provider_id,
            "revision_id": revision_id,
        }

    def _list_active_providers(
        self, project_id: str
    ) -> list[tuple[str, str, str]]:
        """List active providers ordered by scope priority (project > global).

        Returns list of (provider_id, revision_id, capabilities_json).
        """
        # Project scope first
        rows = self.db.fetchall(
            """SELECT provider_id, revision_id, capabilities
               FROM visual_provider_revisions
               WHERE scope_type = 'project' AND scope_id = ?
                     AND status = 'active'
               ORDER BY activated_at DESC""",
            (project_id,),
        )
        # Then global scope
        rows += self.db.fetchall(
            """SELECT provider_id, revision_id, capabilities
               FROM visual_provider_revisions
               WHERE scope_type = 'global' AND status = 'active'
               ORDER BY activated_at DESC""",
            (),
        )
        return [(r["provider_id"], r["revision_id"], r["capabilities"]) for r in rows]

    def _try_resolve(
        self, provider_id: str, project_id: str
    ) -> dict[str, Any] | None:
        """Try to resolve an active provider by ID."""
        result = self._provider_svc.resolve_active(
            provider_id, project_id=project_id
        )
        if result is None:
            return None
        return {
            "provider_id": result["provider_id"],
            "revision_id": result["revision_id"],
            "capabilities": VisualCapabilities(**result["capabilities"]),
        }

    def _required_capabilities(self, purpose: str) -> VisualCapabilities:
        """Determine required capabilities from purpose."""
        if purpose in ("character_reference", "scene_reference", "prop_reference"):
            return VisualCapabilities(text_to_image=True)
        elif purpose == "shot_start_frame" or purpose == "shot_end_frame":
            return VisualCapabilities(reference_to_image=True)
        elif purpose == "continuity_edit":
            return VisualCapabilities(image_edit=True)
        return VisualCapabilities(text_to_image=True)

    def _capabilities_match(
        self, available: VisualCapabilities, required: VisualCapabilities
    ) -> bool:
        """Check if available capabilities satisfy required."""
        for field in (
            "text_to_image", "reference_to_image", "multi_reference",
            "image_edit", "inpainting", "character_multiview",
            "storyboard_frame", "transparent_output",
        ):
            if getattr(required, field) and not getattr(available, field):
                return False
        return True


def _now() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%fZ"
    )
