"""Character sheet prompt template renderer."""
from __future__ import annotations

from pathlib import Path

from lfo.storyboard.storyboard import Character, Storyboard

_TEMPLATE_PATH = Path(__file__).resolve().parent / "character_sheet_v1.j2"


def render_character_sheet_prompt(character: Character, storyboard: Storyboard) -> str:
    """Render the character_sheet_v1.j2 template.

    Uses simple string replacement (no Jinja2 dependency), consistent
    with the decompose prompt rendering approach.

    Args:
        character: The character to generate a reference sheet for.
        storyboard: The parent storyboard (for style context).

    Returns:
        Fully rendered prompt string.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    style = storyboard.style

    # Pre-compute conditional content
    if character.signature_action:
        signature_pose = character.signature_action
    else:
        signature_pose = "natural standing pose, weight shifted to one leg"

    if character.key_prop:
        keyprop_line = f"- Key prop: {character.key_prop}, held naturally in hand or nearby"
    else:
        keyprop_line = ""

    style_keywords_str = ", ".join(style.style_keywords) if style.style_keywords else ""

    replacements = {
        "{{ character_name }}": character.name,
        "{{ character_description }}": character.description,
        "{{ character_distinguishing_features }}": character.distinguishing_features,
        "{{ character_signature_pose }}": signature_pose,
        "{{ character_keyprop_line }}": keyprop_line,
        "{{ style_keywords }}": style_keywords_str,
        "{{ medium_lock }}": style.medium_lock or "",
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result
