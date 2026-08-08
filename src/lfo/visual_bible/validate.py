"""Visual Bible validation — structural checks before hashing."""
from __future__ import annotations

from lfo.visual_bible.schema import VisualBible


def validate_visual_bible(vb: VisualBible) -> tuple[bool, list[str]]:
    """Validate visual bible structure. Returns (valid, errors)."""
    errors = []

    if not vb.project_id:
        errors.append("project_id is required")

    # Validate color palette hex codes
    for color in vb.color_palette:
        if not color.hex_code.startswith('#') or len(color.hex_code) not in (4, 7):
            errors.append(
                f"Color {color.name}: invalid hex code {color.hex_code}"
            )

    # Validate characters have required fields
    for char_name, char_data in vb.characters.items():
        if isinstance(char_data, dict) and 'description' not in char_data:
            errors.append(f"Character {char_name}: missing description")

    return len(errors) == 0, errors
