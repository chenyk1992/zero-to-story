"""Purpose → operation → task type derivation (spec §5).

The caller passes `purpose` only; the service derives operation and
task type. Operations that depend on reference availability choose
between text_to_image and reference_to_image.
"""
from __future__ import annotations

# Purpose → task type
_PURPOSE_TO_TASK_TYPE: dict[str, str] = {
    "character_reference": "visual.generate",
    "scene_reference": "visual.generate",
    "prop_reference": "visual.generate",
    "shot_start_frame": "visual.generate",
    "shot_end_frame": "visual.generate",
    "continuity_edit": "visual.edit",
}

# Purpose → default operation (when references are unavailable)
_PURPOSE_TO_OPERATION: dict[str, str] = {
    "character_reference": "text_to_image",
    "scene_reference": "text_to_image",
    "prop_reference": "text_to_image",
    "shot_start_frame": "text_to_image",
    "shot_end_frame": "reference_to_image",
    "continuity_edit": "image_edit",
}

# Purpose → reference-aware operation (when references ARE available)
_PURPOSE_TO_OPERATION_WITH_REFS: dict[str, str] = {
    "character_reference": "reference_to_image",
    "scene_reference": "reference_to_image",
    "prop_reference": "reference_to_image",
    "shot_start_frame": "reference_to_image",
    "shot_end_frame": "reference_to_image",
    "continuity_edit": "image_edit",
}


def derive_task_type(purpose: str) -> str:
    """Derive task type from purpose.

    Args:
        purpose: The visual purpose string.

    Returns:
        'visual.generate' or 'visual.edit'.

    Raises:
        ValueError: If the purpose is not recognised.
    """
    if purpose not in _PURPOSE_TO_TASK_TYPE:
        raise ValueError(f"Unknown visual purpose: {purpose!r}")
    return _PURPOSE_TO_TASK_TYPE[purpose]


def derive_operation(purpose: str, has_references: bool) -> str:
    """Derive operation from purpose and reference availability.

    Args:
        purpose: The visual purpose string.
        has_references: Whether reference images are available.

    Returns:
        The operation name (e.g. 'text_to_image', 'reference_to_image',
        'image_edit').

    Raises:
        ValueError: If the purpose is not recognised.
    """
    if purpose not in _PURPOSE_TO_OPERATION:
        raise ValueError(f"Unknown visual purpose: {purpose!r}")
    if has_references:
        return _PURPOSE_TO_OPERATION_WITH_REFS[purpose]
    return _PURPOSE_TO_OPERATION[purpose]
