"""Tests for profile content validation."""
from __future__ import annotations

import pytest

from lfo.visual.errors import VisualContractError
from lfo.visual.profile import VisualProfile, validate_profile_content


def test_profile_with_visual_input_policy_valid():
    """Profile must include visual_input_policy."""
    p = validate_profile_content({
        "visual_input_policy": "allow_t2va_fallback",
    })
    assert p.visual_input_policy == "allow_t2va_fallback"


def test_profile_visual_required_valid():
    """visual_required is a valid policy."""
    p = validate_profile_content({
        "visual_input_policy": "visual_required",
    })
    assert p.visual_input_policy == "visual_required"


def test_profile_default_policy():
    """If visual_input_policy omitted, default is allow_t2va_fallback."""
    p = validate_profile_content({})
    assert p.visual_input_policy == "allow_t2va_fallback"


def test_profile_invalid_policy_raises():
    with pytest.raises(VisualContractError, match="visual_input_policy"):
        validate_profile_content({
            "visual_input_policy": "block_everything",
        })


def test_profile_has_technical_and_review_fields():
    """Profile carries technical_checks and review_checklist as separate fields."""
    p = validate_profile_content({
        "visual_input_policy": "allow_t2va_fallback",
        "technical_checks": ["decodable", "hash", "dimensions", "mime"],
        "review_checklist": ["identity", "costume", "composition"],
    })
    assert "decodable" in p.technical_checks
    assert "identity" in p.review_checklist


def test_profile_extra_keys_preserved():
    """Extra keys in profile content are preserved as extra."""
    p = validate_profile_content({
        "visual_input_policy": "allow_t2va_fallback",
        "custom_field": "custom_value",
    })
    assert p.extra["custom_field"] == "custom_value"


def test_profile_hash_stable():
    """Same profile → same CJ1 hash (key order independent)."""
    from lfo.visual.profile import hash_profile_content
    a = hash_profile_content({"visual_input_policy": "visual_required", "k": 1})
    b = hash_profile_content({"k": 1, "visual_input_policy": "visual_required"})
    assert a == b


def test_profile_to_dict_round_trip():
    """to_dict → from_dict preserves fields."""
    original = validate_profile_content({
        "visual_input_policy": "visual_required",
        "technical_checks": ["decodable"],
        "review_checklist": ["identity"],
        "extra_key": "v",
    })
    d = original.to_dict()
    restored = VisualProfile.from_dict(d)
    assert restored.visual_input_policy == original.visual_input_policy
    assert restored.technical_checks == original.technical_checks
    assert restored.review_checklist == original.review_checklist
