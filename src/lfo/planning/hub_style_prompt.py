from __future__ import annotations

from lfo.planning.panel_pack import PanelPack, PanelPackRef


def _format_picture_binding(ref: PanelPackRef) -> str:
    return f"图片{ref.slot}是{ref.entity_id}，{ref.purpose}"


def compile_hub_style_panel_prompt(
    *,
    pack: PanelPack,
    opening: str,
    action_chain: str,
    sound_design: str,
    medium_lock: str,
    quality_negatives: str = "",
) -> str:
    sections: list[str] = []

    if opening.strip():
        sections.append(opening.strip())

    for ref in sorted(pack.refs, key=lambda r: r.slot):
        sections.append(_format_picture_binding(ref))

    if action_chain.strip():
        sections.append(action_chain.strip())

    if sound_design.strip():
        sections.append(sound_design.strip())

    if medium_lock.strip():
        sections.append(medium_lock.strip())

    if quality_negatives.strip():
        sections.append(quality_negatives.strip())

    return "\n".join(sections)
