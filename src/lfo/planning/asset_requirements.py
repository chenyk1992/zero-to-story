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
        - blocked: derive requirements from missing_requirements and pack gaps

    Args:
        panel: The panel to plan assets for.
        pack: Resolved or partial PanelPack for the panel.
        workflow_selection: The selected workflow.

    Returns:
        List of AssetRequirement for the panel.
    """
    if workflow_selection.selection_status == "blocked":
        return _blocked_panel_asset_requirements(
            panel,
            pack,
            workflow_selection,
        )

    if workflow_selection.selection_status == "confirmed":
        return []

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


def _blocked_panel_asset_requirements(
    panel: Panel,
    pack: PanelPack,
    workflow_selection: WorkflowSelection,
) -> list[AssetRequirement]:
    """Build asset requirements for a blocked panel selection."""
    requirements: list[AssetRequirement] = []
    seen: set[str] = set()

    def _add_requirement(
        *,
        requirement_id: str,
        target_id: str,
        asset_role: str,
        blocking_reason: str,
    ) -> None:
        key = f"{target_id}:{asset_role}"
        if key in seen:
            return
        seen.add(key)
        requirements.append(AssetRequirement(
            requirement_id=requirement_id,
            target_id=target_id,
            asset_role=asset_role,
            required=True,
            status="missing",
            blocking_reason=blocking_reason,
        ))

    for index, missing in enumerate(workflow_selection.missing_requirements):
        role, target_id, reason = _parse_missing_requirement(missing, panel, pack)
        _add_requirement(
            requirement_id=f"req_{panel.panel_id}_blocked_{index}",
            target_id=target_id,
            asset_role=role,
            blocking_reason=reason,
        )

    if workflow_selection.workflow_mode == "r2v":
        if not pack.storyboard_bw_asset_id:
            _add_requirement(
                requirement_id=f"req_{panel.panel_id}_composition_ref",
                target_id=panel.panel_id,
                asset_role="composition_ref",
                blocking_reason="BW storyboard composition reference required for R2V",
            )

        for ref in pack.refs:
            if ref.role == "character":
                _add_requirement(
                    requirement_id=f"req_{ref.entity_id}_character_ref",
                    target_id=ref.entity_id,
                    asset_role="character_ref",
                    blocking_reason="Character reference required for R2V",
                )

        if not any(r.asset_role == "character_ref" for r in requirements):
            _add_requirement(
                requirement_id=f"req_{panel.panel_id}_character_ref",
                target_id=panel.panel_id,
                asset_role="character_ref",
                blocking_reason="At least one approved character reference required for R2V",
            )

    return requirements


def _parse_missing_requirement(
    missing: str,
    panel: Panel,
    pack: PanelPack,
) -> tuple[str, str, str]:
    """Map a missing_requirements string to (asset_role, target_id, reason)."""
    if "character_ref" in missing:
        for ref in pack.refs:
            if ref.role == "character":
                return "character_ref", ref.entity_id, missing
        return "character_ref", panel.panel_id, missing
    if "composition" in missing:
        return "composition_ref", panel.panel_id, missing
    if missing in ("start_frame", "end_frame", "composition_ref", "character_ref"):
        return missing, panel.panel_id, missing
    return "composition_ref", panel.panel_id, missing


def plan_asset_requirements(
    panel: Panel,
    pack: PanelPack,
    workflow_selection: WorkflowSelection,
) -> list[AssetRequirement]:
    """Alias for plan_panel_asset_requirements (panel-only execution path)."""
    return plan_panel_asset_requirements(panel, pack, workflow_selection)
