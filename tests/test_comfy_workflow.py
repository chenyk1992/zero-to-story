"""Tests for ComfyUI API workflow shape checks."""

from lfo.comfy.workflow import WorkflowLoader


def _node(*, class_type: object = "LoadImage", inputs: object = None) -> dict:
    return {
        "class_type": class_type,
        "inputs": {} if inputs is None else inputs,
    }


def test_is_api_format_checks_every_node() -> None:
    workflow = {str(index): _node() for index in range(1, 7)}
    workflow["6"] = {"inputs": {}}

    assert WorkflowLoader.is_api_format(workflow) is False


def test_validate_workflow_checks_node_shape_and_numeric_ids() -> None:
    errors = WorkflowLoader.validate_workflow(
        {
            "one": _node(),
            "2": _node(class_type=""),
            "3": _node(class_type=42),
            "4": _node(inputs=[]),
            "5": {"class_type": "SaveVideo"},
        }
    )

    assert any("numeric string ID" in error for error in errors)
    assert any("class_type" in error and "non-empty string" in error for error in errors)
    assert any("inputs" in error and "must be a dict" in error for error in errors)
    assert any("missing 'inputs' dict" in error for error in errors)
