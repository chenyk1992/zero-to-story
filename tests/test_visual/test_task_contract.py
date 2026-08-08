"""Tests for VisualTaskPackage (visual task contract)."""
from __future__ import annotations

import pytest

from lfo.core.canonical import LFO_CJ1_FLOAT_FORBIDDEN
from lfo.visual.errors import VisualContractError
from lfo.visual.task_contract import VisualTaskPackage, validate_task_package


def test_contract_with_required_fields_valid():
    """Minimum valid contract: purpose + operation + task_type."""
    pkg = validate_task_package({
        "purpose": "character_reference",
        "operation": "text_to_image",
        "task_type": "visual.generate",
    })
    assert pkg.purpose == "character_reference"
    assert pkg.operation == "text_to_image"
    assert pkg.task_type == "visual.generate"


def test_contract_full_fields_valid():
    """Full contract with all optional fields."""
    pkg = validate_task_package({
        "purpose": "continuity_edit",
        "operation": "image_edit",
        "task_type": "visual.edit",
        "prompt": {"text": "a hero pose"},
        "reference_list": [{"asset_id": "r1", "role": "source"}],
        "output_contract": {"format": "png", "width": 1024, "height": 1024},
        "technical_checks": ["decodable", "hash", "dimensions"],
        "review_checklist": ["identity", "costume"],
        "continuity_constraints": {"color_grade": "warm"},
    })
    assert pkg.prompt == {"text": "a hero pose"}
    assert len(pkg.reference_list) == 1
    assert pkg.output_contract["format"] == "png"
    assert "decodable" in pkg.technical_checks
    assert "identity" in pkg.review_checklist


def test_contract_missing_purpose_raises():
    with pytest.raises(VisualContractError, match="purpose"):
        validate_task_package({
            "operation": "text_to_image",
            "task_type": "visual.generate",
        })


def test_contract_missing_operation_raises():
    with pytest.raises(VisualContractError, match="operation"):
        validate_task_package({
            "purpose": "character_reference",
            "task_type": "visual.generate",
        })


def test_contract_missing_task_type_raises():
    with pytest.raises(VisualContractError, match="task_type"):
        validate_task_package({
            "purpose": "character_reference",
            "operation": "text_to_image",
        })


def test_contract_invalid_task_type_raises():
    with pytest.raises(VisualContractError, match="task_type"):
        validate_task_package({
            "purpose": "character_reference",
            "operation": "text_to_image",
            "task_type": "video.h3",
        })


def test_contract_continuity_requires_image_edit():
    """continuity_edit purpose must pair with image_edit operation."""
    with pytest.raises(VisualContractError):
        validate_task_package({
            "purpose": "continuity_edit",
            "operation": "text_to_image",
            "task_type": "visual.edit",
        })


def test_contract_generate_requires_generate_task_type():
    """text_to_image operation must pair with visual.generate task_type."""
    with pytest.raises(VisualContractError):
        validate_task_package({
            "purpose": "character_reference",
            "operation": "text_to_image",
            "task_type": "visual.edit",
        })


def test_contract_content_hash_stable():
    """Same contract → same CJ1 hash (key order independent)."""
    a = validate_task_package({
        "purpose": "scene_reference",
        "operation": "reference_to_image",
        "task_type": "visual.generate",
        "prompt": {"text": "forest"},
    })
    b = validate_task_package({
        "task_type": "visual.generate",
        "prompt": {"text": "forest"},
        "operation": "reference_to_image",
        "purpose": "scene_reference",
    })
    assert a.content_hash() == b.content_hash()


def test_contract_content_hash_differs_with_content():
    """Different prompt → different hash."""
    a = validate_task_package({
        "purpose": "character_reference",
        "operation": "text_to_image",
        "task_type": "visual.generate",
        "prompt": {"text": "A"},
    })
    b = validate_task_package({
        "purpose": "character_reference",
        "operation": "text_to_image",
        "task_type": "visual.generate",
        "prompt": {"text": "B"},
    })
    assert a.content_hash() != b.content_hash()


def test_contract_prompt_no_floats():
    """LFO-CJ1 must reject floats in prompt."""
    with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
        validate_task_package({
            "purpose": "character_reference",
            "operation": "text_to_image",
            "task_type": "visual.generate",
            "prompt": {"temperature": 0.7},
        })


def test_contract_to_dict_round_trip():
    """to_dict → from_dict preserves all fields."""
    original = validate_task_package({
        "purpose": "prop_reference",
        "operation": "text_to_image",
        "task_type": "visual.generate",
        "prompt": {"text": "a sword"},
        "reference_list": [{"asset_id": "r1"}],
        "output_contract": {"format": "png"},
    })
    d = original.to_dict()
    restored = VisualTaskPackage.from_dict(d)
    assert restored.purpose == original.purpose
    assert restored.prompt == original.prompt
    assert restored.reference_list == original.reference_list
    assert restored.content_hash() == original.content_hash()
