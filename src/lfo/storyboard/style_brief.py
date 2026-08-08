"""Style Brief — generate Medium Lock statements from visual style descriptions.

Medium Lock is a hard style-consistency constraint appended to every prompt.
Format: "Medium: {positive description}. NOT {excluded style 1}, NOT {excluded style 2}."

Usage:
    from lfo.storyboard.style_brief import build_medium_lock, MEDIUM_LOCK_TEMPLATES

    lock = build_medium_lock("2d_anime")
    # -> "Medium: 2D hand-drawn animation with painted backgrounds. NOT 3D render, NOT photoreal, NOT live-action."
"""
from __future__ import annotations

# Mapping from visual_style keywords to Medium Lock templates.
# The first match wins (case-insensitive substring search).
MEDIUM_LOCK_TEMPLATES: list[tuple[str, str]] = [
    (
        "3d",
        "Medium: 3D rendered scene with cinematic composition, clean geometry, stylized realism. NOT 2D anime cel-shading, NOT live-action, NOT sketch.",
    ),
    (
        "cyberpunk",
        "Medium: Photorealistic cinematic footage with neon-lit cyberpunk aesthetic. NOT anime, NOT cartoon, NOT flat illustration.",
    ),
    (
        "anime",
        "Medium: 2D hand-drawn animation with painted backgrounds, clean line art, cel-shading. NOT 3D render, NOT photoreal, NOT live-action.",
    ),
    (
        "2d",
        "Medium: 2D hand-drawn animation with painted backgrounds. NOT 3D render, NOT photoreal, NOT live-action.",
    ),
    (
        "realistic",
        "Medium: Photorealistic cinematic footage with natural lighting. NOT animation, NOT illustration, NOT CGI look.",
    ),
    (
        "photo",
        "Medium: Photorealistic cinematic footage with natural lighting. NOT animation, NOT illustration, NOT CGI look.",
    ),
    (
        "watercolor",
        "Medium: Watercolor painting with soft edges and visible brushstrokes. NOT 3D render, NOT photoreal, NOT digital art.",
    ),
    (
        "oil",
        "Medium: Oil painting with visible brushstrokes and rich texture. NOT 3D render, NOT photoreal, NOT digital art.",
    ),
    (
        "sketch",
        "Medium: Pencil sketch drawing with visible strokes and hatching. NOT 3D render, NOT photoreal, NOT finished illustration.",
    ),
    (
        "cartoon",
        "Medium: Stylized cartoon with bold outlines and flat colors. NOT photoreal, NOT 3D render, NOT realistic.",
    ),
    (
        "pixel",
        "Medium: Pixel art with retro game aesthetic, limited color palette. NOT 3D render, NOT photoreal, NOT vector art.",
    ),
    (
        "ghibli",
        "Medium: 2D hand-drawn animation in Studio Ghibli style with watercolor backgrounds, soft lighting. NOT 3D render, NOT photoreal, NOT live-action.",
    ),
]

# Default fallback when no keyword matches.
DEFAULT_MEDIUM_LOCK = (
    "Medium: Cinematic composition with consistent visual style. NOT mixed styles, NOT inconsistent aesthetics."
)


def build_medium_lock(visual_style: str, user_override: str = "") -> str:
    """Generate a Medium Lock statement.

    Priority:
    1. If user_override is non-empty, use it directly.
    2. If visual_style is empty, return empty string (no lock).
    3. Match visual_style against MEDIUM_LOCK_TEMPLATES (substring, case-insensitive).
    4. Fallback to DEFAULT_MEDIUM_LOCK if no match.

    Args:
        visual_style: e.g. "2d_anime", "cyberpunk realistic", "ghibli"
        user_override: explicit Medium Lock from user input (wins if set)

    Returns:
        A complete Medium Lock sentence, or empty string if no style info.
    """
    if user_override:
        return user_override

    if not visual_style:
        return ""

    style_lower = visual_style.lower()
    for keyword, lock in MEDIUM_LOCK_TEMPLATES:
        if keyword in style_lower:
            return lock

    return DEFAULT_MEDIUM_LOCK


# Stop words to filter out from style keywords.
# These are common English/Chinese words that have no visual signal —
# splitting "anime style" should yield ["anime"], not ["anime", "style"].
STYLE_KEYWORD_STOPWORDS: set[str] = {
    # English stopwords
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "his", "her",
    "style", "styled", "based", "type", "look", "lookin", "looking",
    "inspired", "vibe", "vibes", "feel", "feels", "aesthetic",
    # Generic adverbs / modifiers
    "very", "really", "quite", "super", "ultra", "more", "less",
    "high", "low", "medium", "small", "big", "large", "tall", "short",
    # Chinese stopwords (single chars and common particles)
    "的", "了", "在", "是", "和", "与", "或", "及", "等", "之", "为",
}


def build_style_keywords(visual_style: str) -> list[str]:
    """Extract style keywords from a visual_style string.

    Splits on common separators, filters stopwords, and deduplicates
    (preserving first occurrence order).

    Args:
        visual_style: e.g. "cyberpunk realistic, neon-lit"

    Returns:
        List of meaningful keywords, e.g. ["cyberpunk", "realistic", "neon-lit"]
    """
    if not visual_style:
        return []

    # Split on common separators (comma, semicolon, Chinese comma, whitespace)
    import re
    parts = re.split(r"[,，、;；\s]+", visual_style.strip())

    # Filter stopwords (case-insensitive) and empty strings
    seen: set[str] = set()
    result: list[str] = []
    for p in parts:
        p_stripped = p.strip()
        if not p_stripped:
            continue
        if p_stripped.lower() in STYLE_KEYWORD_STOPWORDS:
            continue
        if p_stripped in seen:
            continue
        seen.add(p_stripped)
        result.append(p_stripped)

    return result
