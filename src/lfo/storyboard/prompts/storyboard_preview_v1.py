"""Storyboard preview prompt template renderer."""
from __future__ import annotations

from pathlib import Path

from lfo.storyboard.storyboard import Shot, Storyboard

_TEMPLATE_PATH = Path(__file__).resolve().parent / "storyboard_preview_v1.j2"


def render_storyboard_preview_prompt(
    storyboard: Storyboard,
    shots: list[Shot],
    sheet_number: int,
    total_sheets: int,
    is_bridge: bool = False,
    bridge_description: str = "",
) -> str:
    """Render the storyboard_preview_v1.j2 template.

    Uses simple string replacement (no Jinja2 dependency), consistent
    with the character sheet prompt rendering approach.

    Args:
        storyboard: The storyboard (for style context).
        shots: Shots to include in this preview sheet (in panel order).
        sheet_number: 1-based sheet number.
        total_sheets: Total number of preview sheets.
        is_bridge: Whether panel 1 is a bridge panel from the previous sheet.
        bridge_description: Description of the bridge panel (when is_bridge=True).

    Returns:
        Fully rendered prompt string.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    style = storyboard.style

    # Build panel descriptions
    panel_lines: list[str] = []
    # Build a character_id → Character lookup for key prop + signature action
    char_lookup: dict[str, "Character"] = {c.character_id: c for c in storyboard.characters}
    for idx, shot in enumerate(shots):
        panel_no = idx + 1
        camera = shot.camera

        if idx == 0 and is_bridge:
            # Bridge panel — use previous sheet's last shot description
            panel_lines.append(
                f"Panel {panel_no} (bridge from previous sheet): {bridge_description}"
            )
            continue

        # Regular panel — include key props to anchor character identity
        prop_notes: list[str] = []
        for c in shot.characters:
            ch = char_lookup.get(c.character_id)
            if ch and ch.key_prop:
                prop_notes.append(f"{ch.name or ch.character_id} carries {ch.key_prop}")
        prop_str = "; ".join(prop_notes) if prop_notes else ""

        char_names = [c.character_id for c in shot.characters]
        char_str = ", ".join(char_names) if char_names else "no characters"
        action_str = shot.action_beats[0].description if shot.action_beats else shot.description

        desc_line = f"Panel {panel_no}: [{camera.shot_size}/{camera.angle}] {shot.description}"
        if prop_str:
            desc_line += f" ({prop_str})"
        desc_line += f" (characters: {char_str}, key action: {action_str})"
        panel_lines.append(desc_line)

    panel_block = "\n".join(panel_lines)

    # Style line
    style_keywords_str = ", ".join(style.style_keywords) if style.style_keywords else ""
    style_line = f"STYLE KEYWORDS: {style_keywords_str}" if style_keywords_str else ""

    replacements = {
        "{{ panel_count }}": str(len(shots)),
        "{{ sheet_number }}": str(sheet_number),
        "{{ total_sheets }}": str(total_sheets),
        "{{ panel_block }}": panel_block,
        "{{ style_line }}": style_line,
        "{{ medium_lock }}": style.medium_lock or "",
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result
