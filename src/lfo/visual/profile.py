"""Visual Generation Profile — content validation and CJ1 hashing (spec §14).

A profile captures per-project visual generation policy:
- visual_input_policy: 'allow_t2va_fallback' (default) | 'visual_required'
- technical_checks: auto-run QC checks (decodable, hash, dimensions, mime, ...)
- review_checklist: human review items (identity, costume, composition, ...)
- extra: preserved arbitrary keys for forward compatibility
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lfo.visual.errors import VisualContractError
from lfo.visual.hashing import hash_visual_object

# Valid visual input policies (spec §6)
_VALID_POLICIES = ("allow_t2va_fallback", "visual_required")


@dataclass(frozen=True)
class VisualProfile:
    """Immutable visual generation profile."""
    visual_input_policy: str = "allow_t2va_fallback"
    technical_checks: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # frozen dataclass post-init validation
        if self.visual_input_policy not in _VALID_POLICIES:
            raise VisualContractError(
                f"Invalid visual_input_policy '{self.visual_input_policy}'. "
                f"Must be one of {_VALID_POLICIES}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        d: dict[str, Any] = {
            "visual_input_policy": self.visual_input_policy,
        }
        if self.technical_checks:
            d["technical_checks"] = list(self.technical_checks)
        if self.review_checklist:
            d["review_checklist"] = list(self.review_checklist)
        if self.extra:
            d.update(self.extra)
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> VisualProfile:
        """Deserialize from dict."""
        known = {"visual_input_policy", "technical_checks", "review_checklist"}
        extra = {k: v for k, v in d.items() if k not in known}
        return VisualProfile(
            visual_input_policy=d.get("visual_input_policy", "allow_t2va_fallback"),
            technical_checks=tuple(d.get("technical_checks", [])),
            review_checklist=tuple(d.get("review_checklist", [])),
            extra=extra,
        )


def validate_profile_content(content: dict[str, Any]) -> VisualProfile:
    """Validate raw profile content and construct a VisualProfile.

    Args:
        content: Raw profile dict.

    Returns:
        Validated VisualProfile.

    Raises:
        VisualContractError: On invalid policy value.
    """
    policy = content.get("visual_input_policy", "allow_t2va_fallback")

    if policy not in _VALID_POLICIES:
        raise VisualContractError(
            f"Invalid visual_input_policy '{policy}'. Must be one of {_VALID_POLICIES}"
        )

    known = {"visual_input_policy", "technical_checks", "review_checklist"}
    extra = {k: v for k, v in content.items() if k not in known}

    return VisualProfile(
        visual_input_policy=policy,
        technical_checks=tuple(content.get("technical_checks", [])),
        review_checklist=tuple(content.get("review_checklist", [])),
        extra=extra,
    )


def hash_profile_content(content: dict[str, Any]) -> str:
    """Compute LFO-CJ1 hash of profile content.

    Args:
        content: Raw profile dict.

    Returns:
        SHA-256 hex digest of canonical serialization.
    """
    return hash_visual_object(dict(content))
