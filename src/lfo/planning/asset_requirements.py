"""Asset Requirement Planner — enumerates required assets per shot.

Given a shot and its workflow selection, determine what assets are needed.
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Shot

from .schema import AssetRequirement
from .workflow_selector import WorkflowSelection


def plan_asset_requirements(
    shot: Shot,
    workflow_selection: WorkflowSelection,
) -> list[AssetRequirement]:
    """Enumerate required assets for a shot given the workflow selection.

    Rules:
        - t2va: no image requirements
        - i2v: requires start_frame
        - first_last: requires start_frame + end_frame
        - r2v: requires character_ref (for identity characters), scene_ref, composition_ref

    Args:
        shot: The shot to plan assets for.
        workflow_selection: The selected workflow (determines which assets are needed).

    Returns:
        List of AssetRequirement for the shot.
    """
    mode = workflow_selection.workflow_mode
    requirements: list[AssetRequirement] = []

    if mode == "t2va":
        # Text-to-video needs no image assets
        return requirements

    if mode in ("i2v", "first_last"):
        # Both i2v and first_last need a start frame
        requirements.append(AssetRequirement(
            requirement_id=f"req_{shot.shot_id}_start_frame",
            target_id=shot.shot_id,
            asset_role="start_frame",
            required=True,
            status="missing",
            blocking_reason="Start frame required for image-to-video",
        ))

        if mode == "first_last":
            requirements.append(AssetRequirement(
                requirement_id=f"req_{shot.shot_id}_end_frame",
                target_id=shot.shot_id,
                asset_role="end_frame",
                required=True,
                status="missing",
                blocking_reason="End frame required for first-last interpolation",
            ))

    elif mode == "r2v":
        # R2V needs character refs for identity characters
        for char_app in shot.characters:
            if char_app.character_id:
                requirements.append(AssetRequirement(
                    requirement_id=f"req_{char_app.character_id}_character_ref",
                    target_id=char_app.character_id,
                    asset_role="character_ref",
                    required=True,
                    status="missing",
                    blocking_reason="Character reference required for R2V",
                ))

        # Scene reference
        if shot.scene_id:
            requirements.append(AssetRequirement(
                requirement_id=f"req_{shot.scene_id}_scene_ref",
                target_id=shot.scene_id,
                asset_role="scene_ref",
                required=True,
                status="missing",
                blocking_reason="Scene reference required for R2V",
            ))

        # Composition reference
        requirements.append(AssetRequirement(
            requirement_id=f"req_{shot.shot_id}_composition_ref",
            target_id=shot.shot_id,
            asset_role="composition_ref",
            required=True,
            status="missing",
            blocking_reason="Composition reference required for R2V",
        ))

    return requirements
