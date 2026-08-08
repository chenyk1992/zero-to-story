"""Visual Task Contract — validated, hashable, CJ1-serializable.

A VisualTaskPackage captures everything needed to execute a visual task:
purpose, operation, prompt, references, output contract, quality checks,
and continuity constraints. The content_hash is the LFO-CJ1 semantic hash
of the content fields (excludes routing/provider info).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfo.visual.errors import VisualContractError
from lfo.visual.hashing import hash_visual_object

# Allowed task types
_TASK_TYPES = ("visual.generate", "visual.edit")

# Purpose → allowed operations (spec §5)
_PURPOSE_OPERATIONS: dict[str, tuple[str, ...]] = {
    "character_reference": ("text_to_image", "reference_to_image"),
    "scene_reference": ("text_to_image", "reference_to_image"),
    "prop_reference": ("text_to_image", "reference_to_image"),
    "shot_start_frame": ("text_to_image", "reference_to_image"),
    "shot_end_frame": ("reference_to_image",),
    "continuity_edit": ("image_edit",),
}

# Operation → allowed task type
_OPERATION_TASK_TYPE: dict[str, str] = {
    "text_to_image": "visual.generate",
    "reference_to_image": "visual.generate",
    "multi_reference": "visual.generate",
    "image_edit": "visual.edit",
}


@dataclass(frozen=True)
class VisualTaskPackage:
    """Immutable visual task contract.

    Content hash covers: purpose, operation, task_type, prompt,
    reference_list, output_contract, technical_checks, review_checklist,
    continuity_constraints.
    """
    purpose: str
    operation: str
    task_type: str
    prompt: dict[str, Any] | None = None
    reference_list: tuple[dict[str, Any], ...] = ()
    output_contract: dict[str, Any] | None = None
    technical_checks: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    continuity_constraints: dict[str, Any] | None = None

    def content_hash(self) -> str:
        """LFO-CJ1 semantic hash of content fields."""
        obj: dict[str, Any] = {
            "purpose": self.purpose,
            "operation": self.operation,
            "task_type": self.task_type,
        }
        if self.prompt is not None:
            obj["prompt"] = self.prompt
        if self.reference_list:
            obj["reference_list"] = list(self.reference_list)
        if self.output_contract is not None:
            obj["output_contract"] = self.output_contract
        if self.technical_checks:
            obj["technical_checks"] = list(self.technical_checks)
        if self.review_checklist:
            obj["review_checklist"] = list(self.review_checklist)
        if self.continuity_constraints is not None:
            obj["continuity_constraints"] = self.continuity_constraints
        return hash_visual_object(obj)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        d: dict[str, Any] = {
            "purpose": self.purpose,
            "operation": self.operation,
            "task_type": self.task_type,
        }
        if self.prompt is not None:
            d["prompt"] = self.prompt
        if self.reference_list:
            d["reference_list"] = list(self.reference_list)
        if self.output_contract is not None:
            d["output_contract"] = self.output_contract
        if self.technical_checks:
            d["technical_checks"] = list(self.technical_checks)
        if self.review_checklist:
            d["review_checklist"] = list(self.review_checklist)
        if self.continuity_constraints is not None:
            d["continuity_constraints"] = self.continuity_constraints
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> VisualTaskPackage:
        """Deserialize from dict."""
        return VisualTaskPackage(
            purpose=d["purpose"],
            operation=d["operation"],
            task_type=d["task_type"],
            prompt=d.get("prompt"),
            reference_list=tuple(d.get("reference_list", [])),
            output_contract=d.get("output_contract"),
            technical_checks=tuple(d.get("technical_checks", [])),
            review_checklist=tuple(d.get("review_checklist", [])),
            continuity_constraints=d.get("continuity_constraints"),
        )


def validate_task_package(data: dict[str, Any]) -> VisualTaskPackage:
    """Validate raw dict and construct a VisualTaskPackage.

    Args:
        data: Raw dict with contract fields.

    Returns:
        Validated VisualTaskPackage.

    Raises:
        VisualContractError: On missing fields or illegal combinations.
    """
    if "purpose" not in data:
        raise VisualContractError("Missing required field: 'purpose'")
    if "operation" not in data:
        raise VisualContractError("Missing required field: 'operation'")
    if "task_type" not in data:
        raise VisualContractError("Missing required field: 'task_type'")

    purpose = data["purpose"]
    operation = data["operation"]
    task_type = data["task_type"]

    if task_type not in _TASK_TYPES:
        raise VisualContractError(
            f"Invalid task_type '{task_type}'. Must be one of {_TASK_TYPES}"
        )

    allowed_ops = _PURPOSE_OPERATIONS.get(purpose)
    if allowed_ops is None:
        raise VisualContractError(f"Unknown purpose '{purpose}'")
    if operation not in allowed_ops:
        raise VisualContractError(
            f"Purpose '{purpose}' does not allow operation '{operation}'. "
            f"Allowed: {allowed_ops}"
        )

    expected_type = _OPERATION_TASK_TYPE.get(operation)
    if expected_type is not None and task_type != expected_type:
        raise VisualContractError(
            f"Operation '{operation}' requires task_type '{expected_type}', "
            f"got '{task_type}'"
        )

    pkg = VisualTaskPackage(
        purpose=purpose,
        operation=operation,
        task_type=task_type,
        prompt=data.get("prompt"),
        reference_list=tuple(data.get("reference_list", [])),
        output_contract=data.get("output_contract"),
        technical_checks=tuple(data.get("technical_checks", [])),
        review_checklist=tuple(data.get("review_checklist", [])),
        continuity_constraints=data.get("continuity_constraints"),
    )

    # Trigger CJ1 float check eagerly so validation fails fast
    # (hash_visual_object raises LFO_CJ1_FLOAT_FORBIDDEN on floats).
    pkg.content_hash()

    return pkg
