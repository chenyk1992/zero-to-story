"""Workflow Selector — chooses the best workflow for a shot.

Selection rules (in priority order):
1. 2+ identity characters with approved refs AND approved composition/scene ref → r2v
2. 1 identity character with approved ref AND approved composition/scene ref → r2v
3. Approved start frame + approved end frame → first_last
4. Approved start frame (no end frame) → i2v
5. Otherwise → t2va

For MVP, available_assets is typically empty, so most selections will be
"provisional" with missing_requirements listing what's needed.

T2VA fallback policy (spec §6):
- ``allow_t2va_fallback`` (default): when visuals are missing, the
  selector falls back to T2VA.  This keeps existing E2E flows green.
- ``visual_required``: when a shot forces visual input (continuity or
  preferred_mode) but assets are missing, the selector returns the
  forced mode with ``selection_status="blocked"`` instead of falling
  back to T2VA.  The caller is expected to insert a visual.generate
  task to produce the missing asset.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.core.workflow_registry import KNOWN_WORKFLOWS
from lfo.storyboard.storyboard import Shot, Storyboard


@dataclass
class WorkflowSelection:
    """Result of selecting a workflow for a shot."""
    workflow_id: str
    workflow_family: str
    workflow_mode: str
    reason: str
    fallback_workflow_ids: list[str] = field(default_factory=list)
    selection_status: str = "confirmed"  # 'confirmed' | 'provisional' | 'blocked'
    missing_requirements: list[str] = field(default_factory=list)


def _get_manifest(workflow_id: str):
    """Get the manifest for a workflow ID, or None if unknown."""
    return KNOWN_WORKFLOWS.get(workflow_id)


def _has_approved_asset(available_assets: dict | None, entity_id: str, asset_role: str) -> bool:
    """Check if an approved asset exists for an entity.

    available_assets format: {entity_id: {asset_role: {"status": "approved", ...}}}
    """
    if not available_assets:
        return False
    entity_assets = available_assets.get(entity_id, {})
    asset_info = entity_assets.get(asset_role, {})
    return asset_info.get("status") == "approved"


def _shot_forces_visual_input(shot: Shot) -> str | None:
    """Determine if a shot forces visual input (regardless of assets).

    Returns the forced workflow mode ("i2v", "first_last", "r2v") or None.
    A shot forces visual input when continuity requires a start frame or
    an explicit preferred_mode was set.
    """
    preferred = shot.generation_hint.preferred_mode if shot.generation_hint else None
    if preferred in ("i2v", "first_last", "r2v"):
        return preferred
    if shot.continuity.start_frame_needed:
        return "i2v"
    return None


def select_workflow(
    shot: Shot,
    storyboard: Storyboard,
    available_assets: dict | None = None,
    *,
    visual_input_policy: str = "allow_t2va_fallback",
) -> WorkflowSelection:
    """Select the best workflow for a shot based on storyboard semantics.

    Args:
        shot: The shot to select a workflow for.
        storyboard: The full storyboard (for character/scene lookups).
        available_assets: Dict of available approved assets, keyed by entity_id.
        visual_input_policy: Policy for handling missing visuals.
            "allow_t2va_fallback" (default) falls back to T2VA.
            "visual_required" blocks on missing visuals (returns "blocked").

    Returns:
        WorkflowSelection with workflow_id, mode, reason, and status.
    """
    assets = available_assets or {}

    # Count identity characters in the shot
    identity_chars = [c for c in shot.characters if c.character_id]
    has_composition = _has_approved_asset(assets, shot.shot_id, "composition_ref")
    has_scene_ref = _has_approved_asset(assets, shot.scene_id, "scene_ref")
    has_start_frame = _has_approved_asset(assets, shot.shot_id, "start_frame")
    has_end_frame = _has_approved_asset(assets, shot.shot_id, "end_frame")

    # Check character refs for identity characters
    chars_with_refs = 0
    for char_app in identity_chars:
        if _has_approved_asset(assets, char_app.character_id, "character_ref"):
            chars_with_refs += 1

    # Shots that force visual input (continuity or explicit preference)
    forced_mode = _shot_forces_visual_input(shot)

    # Rule 1 & 2: R2V — identity character(s) with refs + composition/scene ref
    # AND the shot actually needs visual input (continuity or explicit preference).
    # Having refs alone is not enough — the first shot establishes the look.
    if chars_with_refs >= 1 and (has_composition or has_scene_ref) and forced_mode:
        manifest = _get_manifest("h3_standard_r2v")
        return WorkflowSelection(
            workflow_id="h3_standard_r2v",
            workflow_family=manifest.family if manifest else "h3_ref2va",
            workflow_mode="r2v",
            reason=(
                f"R2V eligible: {chars_with_refs} character(s) with approved refs "
                f"and approved {'composition' if has_composition else 'scene'} ref"
            ),
            selection_status="confirmed",
        )

    # Rule 3: First-Last — approved start + end frame
    if has_start_frame and has_end_frame:
        manifest = _get_manifest("h3_standard_i2v")
        return WorkflowSelection(
            workflow_id="h3_standard_i2v",
            workflow_family=manifest.family if manifest else "h3_fl2va",
            workflow_mode="first_last",
            reason="Has approved start frame and approved end frame",
            selection_status="confirmed",
        )

    # Rule 4: I2V — approved start frame only
    if has_start_frame:
        manifest = _get_manifest("h3_standard_i2v")
        return WorkflowSelection(
            workflow_id="h3_standard_i2v",
            workflow_family=manifest.family if manifest else "h3_fl2va",
            workflow_mode="i2v",
            reason="Has approved start frame (no end frame)",
            selection_status="confirmed",
        )

    # Rule 5: T2VA — fallback
    # Build missing requirements for provisional status
    missing: list[str] = []
    if not has_start_frame:
        missing.append("start_frame")
    if not has_end_frame:
        missing.append("end_frame")
    if chars_with_refs < 1:
        missing.append("character_ref")
    if not has_composition and not has_scene_ref:
        missing.append("composition_or_scene_ref")

    # T2VA policy check (spec §6): when visual_required and the shot
    # forces visual input, do NOT fall back to T2VA — return the forced
    # mode with "blocked" so the caller can insert a visual.generate.
    if visual_input_policy == "visual_required" and forced_mode is not None:
        return _blocked_selection(forced_mode, missing)

    manifest = _get_manifest("h3_standard_t2v")
    return WorkflowSelection(
        workflow_id="h3_standard_t2v",
        workflow_family=manifest.family if manifest else "h3_fl2va",
        workflow_mode="t2va",
        reason="No approved image assets available — text-to-video fallback",
        fallback_workflow_ids=["h3_standard_i2v", "h3_standard_r2v"],
        selection_status="provisional",
        missing_requirements=missing,
    )


def _blocked_selection(
    mode: str,
    missing: list[str],
) -> WorkflowSelection:
    """Build a blocked WorkflowSelection for a forced-but-unavailable mode.

    Used when visual_input_policy is "visual_required" and the shot
    forces a visual-input mode but the required assets are missing.
    """
    if mode == "r2v":
        manifest = _get_manifest("h3_standard_r2v")
        return WorkflowSelection(
            workflow_id="h3_standard_r2v",
            workflow_family=manifest.family if manifest else "h3_ref2va",
            workflow_mode="r2v",
            reason="visual_required: shot forces R2V but assets missing — needs visual.generate",
            selection_status="blocked",
            missing_requirements=missing,
        )
    if mode == "first_last":
        manifest = _get_manifest("h3_standard_i2v")
        return WorkflowSelection(
            workflow_id="h3_standard_i2v",
            workflow_family=manifest.family if manifest else "h3_fl2va",
            workflow_mode="first_last",
            reason="visual_required: shot forces first_last but assets missing — needs visual.generate",
            selection_status="blocked",
            missing_requirements=missing,
        )
    # Default: i2v
    manifest = _get_manifest("h3_standard_i2v")
    return WorkflowSelection(
        workflow_id="h3_standard_i2v",
        workflow_family=manifest.family if manifest else "h3_fl2va",
        workflow_mode="i2v",
        reason="visual_required: shot forces I2V but start frame missing — needs visual.generate",
        selection_status="blocked",
        missing_requirements=missing,
    )
