"""Read-only validation of a workflow against the provider's node schemas."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from lfo.comfy.workflow import WorkflowLoader

# These nodes have stable, scalar configuration. Dynamic reference/format
# inputs are bound elsewhere and validated by ComfyUI at submission.
CONFIGURATION_NODES = frozenset({
    "UNETLoader", "CLIPLoader", "VAELoader", "ApplyVDNH3",
    "MiniMaxH3SigmaShift", "BasicScheduler", "KSamplerSelect",
})


def validate_workflow_environment(
    workflow: dict[str, Any], object_info: dict[str, Any],
    *, required_node_classes: Iterable[str] = (),
) -> None:
    """Reject missing nodes, models or incompatible configuration before upload.

    ComfyUI remains responsible for full graph validation. Model selectors
    prove discoverability; checkpoint bundle completeness is checked by the
    workflow registry's existing model dependency checks.
    """
    errors = WorkflowLoader.validate_workflow(workflow)
    if errors:
        raise ValueError("Invalid ComfyUI workflow: " + "; ".join(errors))
    for class_type in sorted(set(required_node_classes)):
        if class_type not in object_info:
            errors.append(f"Missing ComfyUI node: {class_type}")
    for node in workflow.values():
        class_type = node["class_type"]
        schema = object_info.get(class_type)
        if not isinstance(schema, dict):
            errors.append(f"Missing ComfyUI node: {class_type}")
            continue
        if class_type not in CONFIGURATION_NODES:
            continue
        input_schema = schema.get("input", {})
        required = input_schema.get("required", {})
        declared = {**required, **input_schema.get("optional", {})}
        inputs = node.get("inputs", {})
        for name in required.keys() - inputs.keys():
            errors.append(f"{class_type}.{name}: required input is missing")
        for name, value in inputs.items():
            label = f"{class_type}.{name}"
            spec = declared.get(name)
            if not spec:
                errors.append(f"{label}: input is not supported by the installed node")
                continue
            if isinstance(value, list):  # Graph links are validated by ComfyUI.
                continue
            kind = spec[0]
            options = kind if isinstance(kind, list) else (
                spec[1].get("options", []) if kind == "COMBO" and len(spec) > 1 else []
            )
            if (isinstance(kind, list) or kind == "COMBO") and value not in options:
                errors.append(f"{label}: {value!r} is unavailable in the installed node")
            elif kind == "BOOLEAN" and not isinstance(value, bool):
                errors.append(f"{label}: expected a boolean")
            elif kind == "INT" and (isinstance(value, bool) or not isinstance(value, int)):
                errors.append(f"{label}: expected an integer")
            elif kind == "FLOAT" and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"{label}: expected a number")
            elif kind == "STRING" and not isinstance(value, str):
                errors.append(f"{label}: expected a string")
    if errors:
        raise ValueError("ComfyUI workflow environment is incompatible: " + "; ".join(errors))
