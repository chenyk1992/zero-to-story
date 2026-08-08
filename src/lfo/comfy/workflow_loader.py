"""WorkflowLoader — load workflow JSON from the registry and apply parameters.

Responsibilities:
- Load a workflow JSON file from the ComfyUI workflows directory
- Find nodes by their _meta title (e.g. "LFO.Reference01")
- Apply parameter values (prompt, duration, uploaded image filenames)
- Return the final workflow dict ready for submit_prompt
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default workflow directory — bundled registry JSON files live here.
# Each workflow_id maps to a file named "<workflow_id>.json".
DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"


def find_node_by_title(workflow: dict, title: str) -> str | None:
    """Find a node key in the workflow dict by its _meta.title.

    Args:
        workflow: The workflow dict (node_key -> node_def).
        title: The _meta.title to search for.

    Returns:
        The node key (e.g. "6") or None if not found.
    """
    for node_key, node_def in workflow.items():
        meta = node_def.get("_meta", {})
        if meta.get("title") == title:
            return node_key
    return None


def load_workflow(workflow_id: str, registry_dir: Path | None = None) -> dict:
    """Load a workflow JSON from the registry directory.

    Args:
        workflow_id: The workflow identifier (e.g. "h3_standard_r2v").
        registry_dir: Optional override for the registry directory.
            Defaults to the project's ``src/lfo/registry/`` directory.

    Returns:
        The workflow dict.

    Raises:
        FileNotFoundError: If the workflow JSON file doesn't exist.
    """
    reg_dir = registry_dir or DEFAULT_REGISTRY_DIR
    workflow_path = reg_dir / f"{workflow_id}.json"
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    with workflow_path.open("r", encoding="utf-8") as f:
        workflow = json.load(f)

    logger.info("Loaded workflow %s from %s", workflow_id, workflow_path)
    return workflow


def apply_text_input(workflow: dict, title: str, value: str) -> bool:
    """Set a text input value on a node found by _meta title.

    Args:
        workflow: The workflow dict (mutated in-place).
        title: The _meta.title of the target node.
        value: The string value to set.

    Returns:
        True if the node was found and updated, False otherwise.
    """
    node_key = find_node_by_title(workflow, title)
    if node_key is None:
        logger.warning("Node with title '%s' not found in workflow", title)
        return False

    node = workflow[node_key]
    inputs = node.get("inputs", {})

    # PrimitiveStringMultiline uses "value"
    if "value" in inputs:
        inputs["value"] = value
        logger.debug("Set %s.inputs.value = '%s...'", node_key, value[:50])
        return True

    logger.warning("Node %s has no 'value' input field", node_key)
    return False


def apply_float_input(workflow: dict, title: str, value: float) -> bool:
    """Set a float input value on a node found by _meta title.

    Args:
        workflow: The workflow dict (mutated in-place).
        title: The _meta.title of the target node.
        value: The float value to set.

    Returns:
        True if the node was found and updated, False otherwise.
    """
    node_key = find_node_by_title(workflow, title)
    if node_key is None:
        logger.warning("Node with title '%s' not found in workflow", title)
        return False

    node = workflow[node_key]
    inputs = node.get("inputs", {})

    if "value" in inputs:
        inputs["value"] = value
        logger.debug("Set %s.inputs.value = %s", node_key, value)
        return True

    logger.warning("Node %s has no 'value' input field", node_key)
    return False


def apply_image_input(workflow: dict, title: str, filename: str) -> bool:
    """Set an uploaded image filename on a LoadImage node found by _meta title.

    Args:
        workflow: The workflow dict (mutated in-place).
        title: The _meta.title of the target LoadImage node.
        filename: The uploaded image filename (just the name, not full path).

    Returns:
        True if the node was found and updated, False otherwise.
    """
    node_key = find_node_by_title(workflow, title)
    if node_key is None:
        logger.warning("Node with title '%s' not found in workflow", title)
        return False

    node = workflow[node_key]
    inputs = node.get("inputs", {})

    if "image" in inputs:
        inputs["image"] = filename
        logger.debug("Set %s.inputs.image = '%s'", node_key, filename)
        return True

    logger.warning("Node %s has no 'image' input field", node_key)
    return False


def apply_filename_prefix(workflow: dict, title: str, prefix: str) -> bool:
    """Set the filename_prefix on a SaveVideo node found by _meta title.

    Args:
        workflow: The workflow dict (mutated in-place).
        title: The _meta.title of the target SaveVideo node.
        prefix: The filename prefix string.

    Returns:
        True if the node was found and updated, False otherwise.
    """
    node_key = find_node_by_title(workflow, title)
    if node_key is None:
        logger.warning("Node with title '%s' not found in workflow", title)
        return False

    node = workflow[node_key]
    inputs = node.get("inputs", {})

    if "filename_prefix" in inputs:
        inputs["filename_prefix"] = prefix
        logger.debug("Set %s.inputs.filename_prefix = '%s'", node_key, prefix)
        return True

    logger.warning("Node %s has no 'filename_prefix' input field", node_key)
    return False


def deep_copy_workflow(workflow: dict) -> dict:
    """Return a deep copy of the workflow dict so the original is not mutated."""
    return copy.deepcopy(workflow)


# Prompt part order for assembly
_PART_ORDER = [
    "subject",
    "scene",
    "action",
    "camera",
    "end_state",
    "audio",
    "style",
    "style_keywords",
    "negative",
]


def blueprint_to_text(blueprint) -> str:
    """Convert a PromptBlueprint to a single text string for the LFO.Prompt input.

    Parts are assembled in semantic order, joined by newlines.
    Empty parts are skipped.
    """
    if not blueprint or not blueprint.parts:
        return ""

    # Group parts by type in the defined order
    parts_by_type: dict[str, list[str]] = {}
    for part in blueprint.parts:
        if not part.content or not part.content.strip():
            continue
        parts_by_type.setdefault(part.part_type, []).append(part.content.strip())

    ordered_parts: list[str] = []
    for ptype in _PART_ORDER:
        if ptype in parts_by_type:
            ordered_parts.extend(parts_by_type[ptype])

    # Append any remaining types not in the order list
    for ptype, contents in parts_by_type.items():
        if ptype not in _PART_ORDER:
            ordered_parts.extend(contents)

    return "\n".join(ordered_parts)
