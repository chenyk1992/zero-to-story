"""Deterministic R2V Reference Planner.

Assigns reference images to R2V slots (max 3) following a strict priority:
1. Characters (ordered by reference_character_order from chain or project)
2. Composition
3. Scene
4. Key prop
5. Style

Rules:
- Max 2 identity characters for R2V (3+ → R2V_INELIGIBLE)
- Exactly 3 distinct references required (no duplicates, no blank padding)
- Dedup by asset_id first, then file_hash
- Same file with multiple roles → highest priority role only
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Shot, Storyboard

from .schema import ReferenceBinding

# Role priority: lower number = higher priority
_ROLE_PRIORITY = {
    "character": 0,
    "composition": 1,
    "scene": 2,
    "key_prop": 3,
    "style": 4,
}

# Max identity characters allowed for R2V
MAX_R2V_CHARACTERS = 2

# Number of reference slots in R2V
R2V_SLOT_COUNT = 3


def _get_character_order(storyboard: Storyboard, shot: Shot) -> list[str]:
    """Determine character ordering for R2V reference assignment.

    Priority:
    1. continuity_chain.reference_character_order (if shot is in a chain)
    2. project.reference_character_order
    3. fallback: characters in shot order
    """
    # Check continuity chains first
    for chain in storyboard.continuity_chains:
        if shot.shot_id in chain.shot_ids and chain.reference_character_order:
            return chain.reference_character_order

    # Fall back to project-level order
    if storyboard.project.reference_character_order:
        return storyboard.project.reference_character_order

    # Final fallback: characters in the order they appear in the shot
    return [c.character_id for c in shot.characters if c.character_id]


# Mapping from internal role name to the asset_role key used in available_assets
_ROLE_TO_ASSET_KEY = {
    "character": "character_ref",
    "composition": "composition_ref",
    "scene": "scene_ref",
    "key_prop": "key_prop_ref",
    "style": "style_ref",
}


def _resolve_asset_id(
    entity_id: str,
    role: str,
    available_assets: dict | None,
) -> tuple[str, bool]:
    """Resolve the asset_id for an entity/role combination.

    Returns (asset_id, is_symbolic).
    If no approved asset exists, returns a symbolic placeholder.
    """
    asset_key = _ROLE_TO_ASSET_KEY.get(role, role)
    if available_assets:
        entity_assets = available_assets.get(entity_id, {})
        asset_info = entity_assets.get(asset_key, {})
        if asset_info.get("status") == "approved":
            return asset_info.get("asset_id", f"asset_{entity_id}_{asset_key}"), False

    # Symbolic placeholder
    return f"SYMBOLIC_{entity_id}_{asset_key}", True


def plan_references(
    shot: Shot,
    storyboard: Storyboard,
    available_assets: dict | None = None,
) -> list[ReferenceBinding]:
    """Deterministic R2V slot assignment. Returns up to 3 ReferenceBinding.

    Args:
        shot: The shot to plan references for.
        storyboard: The full storyboard.
        available_assets: Dict of available approved assets.

    Returns:
        List of up to 3 ReferenceBinding with slot assignments.
        Returns empty list if R2V is ineligible (3+ identity characters).
    """
    # Count identity characters
    identity_chars = [c for c in shot.characters if c.character_id]
    if len(identity_chars) > MAX_R2V_CHARACTERS:
        return []  # R2V_INELIGIBLE

    # Build ordered candidate list: (priority, entity_id, role)
    candidates: list[tuple[int, str, str]] = []

    # 1. Characters in priority order
    char_order = _get_character_order(storyboard, shot)
    for _idx, char_id in enumerate(char_order):
        if char_id:
            # Use ordering index as sub-priority within characters
            candidates.append((_ROLE_PRIORITY["character"], char_id, "character"))

    # 2. Composition
    if shot.shot_id:
        candidates.append((_ROLE_PRIORITY["composition"], shot.shot_id, "composition"))

    # 3. Scene
    if shot.scene_id:
        candidates.append((_ROLE_PRIORITY["scene"], shot.scene_id, "scene"))

    # Sort candidates by priority
    candidates.sort(key=lambda c: c[0])

    # Assign slots with dedup
    bindings: list[ReferenceBinding] = []
    seen_asset_ids: set[str] = set()
    used_roles: dict[str, str] = {}  # entity_id → role (for multi-role dedup)
    slot = 1

    for _priority, entity_id, role in candidates:
        if slot > R2V_SLOT_COUNT:
            break

        # Skip if this entity already has a higher-priority role assigned
        if entity_id in used_roles:
            continue

        asset_id, is_symbolic = _resolve_asset_id(entity_id, role, available_assets)

        # Dedup by asset_id
        if asset_id in seen_asset_ids:
            # Same asset already used → skip but record the role
            continue

        seen_asset_ids.add(asset_id)
        used_roles[entity_id] = role
        bindings.append(ReferenceBinding(
            slot=slot,
            asset_id=asset_id,
            entity_id=entity_id,
            role=role,
            is_symbolic=is_symbolic,
        ))
        slot += 1

    return bindings
