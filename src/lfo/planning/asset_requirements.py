"""Asset Requirement Planner — enumerates required assets per panel.

Given a panel and its workflow selection, determine what assets are needed.
"""
from __future__ import annotations

from lfo.planning.panel_pack import PanelPack
from lfo.storyboard.storyboard import Panel

from .schema import AssetRequirement
from .workflow_selector import WorkflowSelection


def plan_panel_asset_requirements(
    panel: Panel,
    pack: PanelPack,
    workflow_selection: WorkflowSelection,
) -> list[AssetRequirement]:
    """Enumerate required assets for a panel given the workflow selection.

    Rules:
        - t2va: no image requirements
        - i2v: requires start_frame
        - first_last: requires start_frame + end_frame
        - r2v: requires composition (BW storyboard) + character refs from pack

    Args:
        panel: The panel to plan assets for.
        pack: Resolved or partial PanelPack for the panel.
        workflow_selection: The selected workflow.

    Returns:
        List of AssetRequirement for the panel.
    """
    mode = workflow_selection.workflow_mode
    requirements: list[AssetRequirement] = []

    if mode == "t2va":
        return requirements

    if mode in ("i2v", "first_last"):
        requirements.append(AssetRequirement(
            requirement_id=f"req_{panel.panel_id}_start_frame",
            target_id=panel.panel_id,
            asset_role="start_frame",
            required=True,
            status="missing",
            blocking_reason="Start frame required for image-to-video",
        ))

        if mode == "first_last":
            requirements.append(AssetRequirement(
                requirement_id=f"req_{panel.panel_id}_end_frame",
                target_id=panel.panel_id,
                asset_role="end_frame",
                required=True,
                status="missing",
                blocking_reason="End frame required for first-last interpolation",
            ))

    elif mode == "r2v":
        if not pack.storyboard_bw_asset_id:
            requirements.append(AssetRequirement(
                requirement_id=f"req_{panel.panel_id}_composition_ref",
                target_id=panel.panel_id,
                asset_role="composition_ref",
                required=True,
                status="missing",
                blocking_reason="BW storyboard composition reference required for R2V",
            ))

        for ref in pack.refs:
            if ref.role == "character":
                requirements.append(AssetRequirement(
                    requirement_id=f"req_{ref.entity_id}_character_ref",
                    target_id=ref.entity_id,
                    asset_role="character_ref",
                    required=True,
                    status="missing",
                    blocking_reason="Character reference required for R2V",
                ))

    return requirements


def plan_asset_requirements(
    panel: Panel,
    pack: PanelPack,
    workflow_selection: WorkflowSelection,
) -> list[AssetRequirement]:
    """Alias for plan_panel_asset_requirements (panel-only execution path)."""
    return plan_panel_asset_requirements(panel, pack, workflow_selection)
