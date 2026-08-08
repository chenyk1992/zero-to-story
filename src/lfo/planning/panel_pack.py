from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_PURPOSE_COMPOSITION = "仅参考构图和动作链，不采用线稿画风。"
DEFAULT_PURPOSE_CHARACTER = "保持身份、发型、服饰、体型与关键道具不变。"
DEFAULT_PURPOSE_CONTINUITY_CHAR = "仅作为前段人物连续性参考。"

_VALID_ROLES = frozenset({"character", "scene", "prop", "style", "composition"})


@dataclass
class PanelPackRef:
    slot: int
    role: str
    asset_id: str
    entity_id: str
    purpose: str


@dataclass
class PanelPack:
    panel_id: str
    beat_range: tuple[int, int]
    storyboard_bw_asset_id: str
    refs: list[PanelPackRef]
    characters_in_panel: list[str] = field(default_factory=list)
    trim_reason: str | None = None


def _is_continuity_character(ref: PanelPackRef) -> bool:
    return ref.role == "continuity_character" or (
        ref.role == "character" and ref.purpose == DEFAULT_PURPOSE_CONTINUITY_CHAR
    )


def _ref_trim_priority(ref: PanelPackRef) -> int:
    if ref.role == "composition":
        return 0
    if ref.role == "character" and not _is_continuity_character(ref):
        return 1
    if _is_continuity_character(ref):
        return 2
    if ref.role == "scene":
        return 3
    if ref.role == "prop":
        return 4
    if ref.role == "style":
        return 5
    return 99


def _copy_ref(ref: PanelPackRef, *, slot: int) -> PanelPackRef:
    return PanelPackRef(
        slot=slot,
        role=ref.role,
        asset_id=ref.asset_id,
        entity_id=ref.entity_id,
        purpose=ref.purpose,
    )


def trim_panel_pack(
    candidates: list[PanelPackRef],
    *,
    composition: PanelPackRef,
    max_ref_images: int,
) -> tuple[list[PanelPackRef], str | None]:
    limit = min(9, max_ref_images)
    ordered = [composition] + sorted(candidates, key=_ref_trim_priority)
    if len(ordered) <= limit:
        return [_copy_ref(ref, slot=i + 1) for i, ref in enumerate(ordered)], None

    kept = ordered[:limit]
    dropped = ordered[limit:]
    dropped_roles = ", ".join(sorted({r.role for r in dropped}))
    reason = (
        f"trimmed {len(dropped)} ref(s) ({dropped_roles}) "
        f"to fit max_ref_images={max_ref_images}"
    )
    return [_copy_ref(ref, slot=i + 1) for i, ref in enumerate(kept)], reason


def _composition_last(refs: list[PanelPackRef]) -> list[PanelPackRef]:
    non_comp = [r for r in refs if r.role != "composition"]
    comp = [r for r in refs if r.role == "composition"]
    ordered = non_comp + comp
    return [_copy_ref(ref, slot=i + 1) for i, ref in enumerate(ordered)]


def build_panel_pack(
    panel_id: str,
    beat_range: tuple[int, int],
    bw_asset_id: str,
    character_assets: list[tuple[str, str]],
    scene_assets: list[tuple[str, str]] | None = None,
    prop_assets: list[tuple[str, str]] | None = None,
    continuity_character_assets: list[tuple[str, str]] | None = None,
    max_ref_images: int = 3,
) -> PanelPack:
    candidates: list[PanelPackRef] = []

    for entity_id, asset_id in character_assets:
        candidates.append(
            PanelPackRef(
                slot=0,
                role="character",
                asset_id=asset_id,
                entity_id=entity_id,
                purpose=DEFAULT_PURPOSE_CHARACTER,
            )
        )

    for entity_id, asset_id in continuity_character_assets or []:
        candidates.append(
            PanelPackRef(
                slot=0,
                role="character",
                asset_id=asset_id,
                entity_id=entity_id,
                purpose=DEFAULT_PURPOSE_CONTINUITY_CHAR,
            )
        )

    for entity_id, asset_id in scene_assets or []:
        candidates.append(
            PanelPackRef(
                slot=0,
                role="scene",
                asset_id=asset_id,
                entity_id=entity_id,
                purpose=f"参考场景 {entity_id} 的环境与空间关系。",
            )
        )

    for entity_id, asset_id in prop_assets or []:
        candidates.append(
            PanelPackRef(
                slot=0,
                role="prop",
                asset_id=asset_id,
                entity_id=entity_id,
                purpose=f"保持道具 {entity_id} 的外观一致。",
            )
        )

    composition = PanelPackRef(
        slot=0,
        role="composition",
        asset_id=bw_asset_id,
        entity_id=panel_id,
        purpose=DEFAULT_PURPOSE_COMPOSITION,
    )

    trimmed, trim_reason = trim_panel_pack(
        candidates,
        composition=composition,
        max_ref_images=max_ref_images,
    )
    refs = _composition_last(trimmed)

    return PanelPack(
        panel_id=panel_id,
        beat_range=beat_range,
        storyboard_bw_asset_id=bw_asset_id,
        refs=refs,
        characters_in_panel=[entity_id for entity_id, _ in character_assets],
        trim_reason=trim_reason,
    )


def validate_panel_pack(pack: PanelPack, *, max_ref_images: int) -> list[str]:
    errors: list[str] = []

    if not pack.panel_id:
        errors.append("panel_id is required")
    if not pack.storyboard_bw_asset_id:
        errors.append("storyboard_bw_asset_id is required")

    limit = min(9, max_ref_images)
    ref_count = len(pack.refs)
    if ref_count < 2:
        errors.append(f"refs must contain at least 2 items, got {ref_count}")
    if ref_count > limit:
        errors.append(f"refs must contain at most {limit} items, got {ref_count}")

    roles = {ref.role for ref in pack.refs}
    if "composition" not in roles:
        errors.append("refs must include a composition reference")
    if "character" not in roles:
        errors.append("refs must include at least one character identity reference")

    expected_slots = list(range(1, ref_count + 1))
    actual_slots = [ref.slot for ref in pack.refs]
    if actual_slots != expected_slots:
        errors.append(f"ref slots must be numbered 1..{ref_count}, got {actual_slots}")

    for ref in pack.refs:
        if ref.role not in _VALID_ROLES:
            errors.append(f"invalid ref role: {ref.role}")
        if not ref.asset_id:
            errors.append(f"ref slot {ref.slot} missing asset_id")
        if not ref.entity_id:
            errors.append(f"ref slot {ref.slot} missing entity_id")
        if not ref.purpose:
            errors.append(f"ref slot {ref.slot} missing purpose")

    return errors


def panel_pack_to_dict(pack: PanelPack) -> dict:
    return {
        "panel_id": pack.panel_id,
        "beat_range": list(pack.beat_range),
        "storyboard_bw_asset_id": pack.storyboard_bw_asset_id,
        "refs": [
            {
                "slot": ref.slot,
                "role": ref.role,
                "asset_id": ref.asset_id,
                "entity_id": ref.entity_id,
                "purpose": ref.purpose,
            }
            for ref in pack.refs
        ],
        "characters_in_panel": list(pack.characters_in_panel),
        "trim_reason": pack.trim_reason,
    }


def panel_pack_from_dict(data: dict) -> PanelPack:
    beat_range_raw = data["beat_range"]
    beat_range = (int(beat_range_raw[0]), int(beat_range_raw[1]))
    refs = [
        PanelPackRef(
            slot=int(ref["slot"]),
            role=str(ref["role"]),
            asset_id=str(ref["asset_id"]),
            entity_id=str(ref["entity_id"]),
            purpose=str(ref["purpose"]),
        )
        for ref in data.get("refs", [])
    ]
    return PanelPack(
        panel_id=str(data["panel_id"]),
        beat_range=beat_range,
        storyboard_bw_asset_id=str(data["storyboard_bw_asset_id"]),
        refs=refs,
        characters_in_panel=[str(c) for c in data.get("characters_in_panel", [])],
        trim_reason=data.get("trim_reason"),
    )
