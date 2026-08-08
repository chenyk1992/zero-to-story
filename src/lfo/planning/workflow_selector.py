"""Workflow Selector — chooses the best workflow for a panel PanelPack."""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.core.workflow_registry import KNOWN_WORKFLOWS
from lfo.planning.panel_pack import (
    PanelPack,
    validate_panel_pack,
    validate_panel_pack_approvals,
)

_DEFAULT_MAX_REF_IMAGES = 3


@dataclass
class WorkflowSelection:
    """Result of selecting a workflow for a panel."""
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


def select_workflow_for_panel(
    pack: PanelPack,
    *,
    force_fl2va: bool = False,
    max_ref_images: int = _DEFAULT_MAX_REF_IMAGES,
    available_assets: dict | None = None,
) -> WorkflowSelection:
    """Select the workflow for a panel from its reference pack.

    Panel-level rules (spec §8.1):
    - Valid PanelPack with approved assets → confirmed r2v
    - force_fl2va → explicit i2v override
    - Incomplete pack or unapproved assets → blocked r2v
    """
    if force_fl2va:
        manifest = _get_manifest("h3_standard_i2v")
        return WorkflowSelection(
            workflow_id="h3_standard_i2v",
            workflow_family=manifest.family if manifest else "h3_fl2va",
            workflow_mode="i2v",
            reason="force_fl2va: explicit FL2VA override",
            selection_status="confirmed",
        )

    errors = validate_panel_pack(pack, max_ref_images=max_ref_images)
    if not errors and available_assets:
        errors = validate_panel_pack_approvals(pack, available_assets)
    if errors:
        return _blocked_selection("r2v", errors)

    manifest = _get_manifest("h3_standard_r2v")
    return WorkflowSelection(
        workflow_id="h3_standard_r2v",
        workflow_family=manifest.family if manifest else "h3_ref2va",
        workflow_mode="r2v",
        reason=(
            f"PanelPack valid: {len(pack.refs)} ref(s) with composition and identity"
        ),
        selection_status="confirmed",
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
