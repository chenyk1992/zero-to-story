"""Workflow loading, format detection, and validation."""

from __future__ import annotations

import json
from pathlib import Path

from .exceptions import WorkflowFormatError


class WorkflowLoader:
    """Static helpers for loading and inspecting ComfyUI workflow files."""

    @staticmethod
    def load(path: Path) -> dict:
        """Load a workflow JSON file and return the parsed dict."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")
        if not file_path.is_file():
            raise WorkflowFormatError(f"Not a file: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise WorkflowFormatError(
                f"Invalid JSON in workflow file {file_path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise WorkflowFormatError(
                f"Workflow must be a JSON object, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def is_api_format(workflow: dict) -> bool:
        """Return ``True`` if *workflow* is in ComfyUI API format.

        API format: numeric string keys, each value has a ``class_type`` field.
        UI format has additional metadata and different structure.
        """
        if not workflow:
            return False
        sample = list(workflow.items())[:5]
        for key, val in sample:
            if not isinstance(key, str) or not key.isdigit():
                return False
            if not isinstance(val, dict) or "class_type" not in val:
                return False
        return True

    @staticmethod
    def get_node(workflow: dict, node_id: str) -> dict:
        """Return the node data for *node_id*."""
        if node_id not in workflow:
            raise KeyError(f"Node '{node_id}' not found in workflow")
        return workflow[node_id]

    @staticmethod
    def find_nodes_by_class(workflow: dict, class_type: str) -> list[tuple[str, dict]]:
        """Return ``[(node_id, node_data), ...]`` for all nodes matching *class_type*."""
        results: list[tuple[str, dict]] = []
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == class_type:
                results.append((node_id, node_data))
        return results

    @staticmethod
    def find_node_by_title(workflow: dict, title: str) -> tuple[str, dict] | None:
        """Find a node by its ``_meta.title`` field.

        Returns ``(node_id, node_data)`` or ``None``.
        """
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict):
                meta = node_data.get("_meta", {})
                if meta.get("title") == title:
                    return (node_id, node_data)
        return None

    @staticmethod
    def validate_workflow(workflow: dict) -> list[str]:
        """Validate the workflow structure.

        Returns a list of error strings (empty = valid).
        """
        errors: list[str] = []
        if not isinstance(workflow, dict):
            return ["Workflow must be a dict"]

        if not workflow:
            errors.append("Workflow is empty")
            return errors

        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                errors.append(f"Node '{node_id}': expected dict, got {type(node_data).__name__}")
                continue
            if "class_type" not in node_data:
                errors.append(f"Node '{node_id}': missing 'class_type'")
            if "inputs" not in node_data:
                errors.append(f"Node '{node_id}': missing 'inputs' dict")

        return errors
