"""Visual asset readiness check — dual gate for video READY promotion.

Implements the policy-aware readiness check from spec §6 and §19:
- Read active profile visual_input_policy
- allow_t2va_fallback: missing visuals are OK (T2VA fallback)
- visual_required: missing visuals block readiness
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.application.asset_service import AssetBindingService, AssetNotReadyError
from lfo.application.visual_profile_service import VisualProfileService
from lfo.core.database import Database


@dataclass
class VisualAssetReadinessResult:
    """Result of checking whether visual assets are ready for a shot."""

    ready: bool
    missing_roles: list[str]
    details: dict = field(default_factory=dict)


def check_visual_assets_ready(
    db: Database,
    *,
    project_id: str,
    shot_id: str,
    required_roles: list[str],
) -> VisualAssetReadinessResult:
    """Check whether required visual assets are ready for a shot.

    Reads the active profile's visual_input_policy and checks each
    required role for an approved asset binding.

    Policy behavior:
    - allow_t2va_fallback (default): missing visuals don't block — the
      workflow selector may choose T2VA instead. Returns ready=True.
    - visual_required: missing visuals block. Returns ready=False with
      the list of missing roles.

    Args:
        db: Database instance.
        project_id: The project ID.
        shot_id: The shot ID (used as entity_id for asset lookups).
        required_roles: List of asset roles that must be satisfied
            (e.g. ["start_frame"], ["character_ref", "scene_ref"]).

    Returns:
        VisualAssetReadinessResult with ready flag and missing roles.
    """
    # Read active profile policy
    profile_service = VisualProfileService(db)
    active = profile_service.get_active(project_id)
    policy = "allow_t2va_fallback"
    if active:
        policy = active.get("content", {}).get(
            "visual_input_policy", "allow_t2va_fallback"
        )

    # Check each required role for an approved binding
    binding_service = AssetBindingService(db)
    missing_roles: list[str] = []
    role_details: dict = {}

    for role in required_roles:
        try:
            approved = binding_service.get_current_approved_asset(
                project_id=project_id,
                entity_type="shot",
                entity_id=shot_id,
                asset_role=role,
            )
            role_details[role] = {
                "asset_id": approved.asset_id,
                "status": "approved",
            }
        except AssetNotReadyError as exc:
            missing_roles.append(role)
            role_details[role] = {"status": "missing", "reason": exc.reason}

    # Policy decision
    if policy == "visual_required":
        ready = len(missing_roles) == 0
    else:
        # allow_t2va_fallback: T2VA fallback is always available
        ready = True

    return VisualAssetReadinessResult(
        ready=ready,
        missing_roles=missing_roles,
        details={
            "policy": policy,
            "roles": role_details,
        },
    )
