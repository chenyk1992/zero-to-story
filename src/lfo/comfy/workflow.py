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
    def is_api_format(workflow: object) -> bool:
        """Return ``True`` if *workflow* is in ComfyUI API format.

        API format uses numeric string node IDs and a complete node shape. UI
        format has additional metadata and a different structure.
        """
        return not WorkflowLoader._shape_errors(workflow)

    @staticmethod
    def find_nodes_by_class(workflow: dict, class_type: str) -> list[tuple[str, dict]]:
        """Return ``[(node_id, node_data), ...]`` for all nodes matching *class_type*."""
        results: list[tuple[str, dict]] = []
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == class_type:
                results.append((node_id, node_data))
        return results

    @staticmethod
    def validate_workflow(workflow: object) -> list[str]:
        """Validate the workflow structure.

        Returns a list of error strings (empty = valid).
        """
        return WorkflowLoader._shape_errors(workflow)

    @staticmethod
    def _shape_errors(workflow: object) -> list[str]:
        """Return structural errors shared by format detection and validation."""
        if not isinstance(workflow, dict):
            return ["Workflow must be a dict"]
        if not workflow:
            return ["Workflow is empty"]

        errors: list[str] = []
        for node_id, node_data in workflow.items():
            if not isinstance(node_id, str) or not node_id.isdigit():
                errors.append(f"Node '{node_id}': expected a numeric string ID")
            if not isinstance(node_data, dict):
                errors.append(f"Node '{node_id}': expected dict, got {type(node_data).__name__}")
                continue

            class_type = node_data.get("class_type")
            if not isinstance(class_type, str) or not class_type:
                if "class_type" not in node_data:
                    errors.append(f"Node '{node_id}': missing 'class_type'")
                else:
                    errors.append(f"Node '{node_id}': 'class_type' must be a non-empty string")

            inputs = node_data.get("inputs")
            if not isinstance(inputs, dict):
                if "inputs" not in node_data:
                    errors.append(f"Node '{node_id}': missing 'inputs' dict")
                else:
                    errors.append(
                        f"Node '{node_id}': 'inputs' must be a dict, "
                        f"got {type(inputs).__name__}"
                    )
        return errors
