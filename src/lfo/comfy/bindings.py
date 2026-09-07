"""Resolve stable logical selectors to concrete ComfyUI node IDs."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .exceptions import BindingAmbiguousError, BindingNotFoundError

JsonScalar = str | int | float | bool | None


@dataclass
class Binding:
    """A logical reference to a node input within a workflow.

    Attributes:
        binding_id: Stable identifier for this binding (e.g. "prompt_text").
        selector_title: The ``_meta.title`` of the target node.
        selector_class_type: The ``class_type`` of the target node.
        input_name: The input slot name on the target node.
        resolved_node_id: Filled in after resolution (the numeric string key).
    """

    binding_id: str
    selector_title: str
    selector_class_type: str
    input_name: str
    resolved_node_id: str | None = None


class BindingResolver:
    """Resolve :class:`Binding` objects against a concrete workflow dict."""

    def __init__(self, workflow: dict):
        self.workflow = workflow

    # -- resolution -------------------------------------------------------- #

    def resolve_binding(self, binding: Binding) -> Binding:
        """Match *binding* to exactly one node by title + class_type.

        A binding must have a non-empty ``selector_title``. Matching always uses
        both ``_meta.title`` and ``class_type``; a missing title never falls back
        to a class-only match.

        Raises:
            BindingNotFoundError: zero matches or an empty selector title.
            BindingAmbiguousError: more than one match.
        """
        if not binding.selector_title:
            raise BindingNotFoundError(
                f"Binding '{binding.binding_id}' has empty selector_title "
                "— a stable _meta.title is required."
            )

        matches: list[str] = []
        for node_id, node_data in self.workflow.items():
            if not isinstance(node_data, dict):
                continue
            if node_data.get("class_type") != binding.selector_class_type:
                continue
            meta = node_data.get("_meta")
            if not isinstance(meta, dict) or meta.get("title") != binding.selector_title:
                continue
            matches.append(node_id)

        if not matches:
            raise BindingNotFoundError(
                f"No node matches title='{binding.selector_title}' "
                f"class_type='{binding.selector_class_type}' "
                f"(binding_id='{binding.binding_id}')"
            )
        if len(matches) > 1:
            raise BindingAmbiguousError(
                f"{len(matches)} nodes match title='{binding.selector_title}' "
                f"class_type='{binding.selector_class_type}' "
                f"(binding_id='{binding.binding_id}'): {matches}"
            )

        binding.resolved_node_id = matches[0]
        return binding

    # -- value injection --------------------------------------------------- #

    def apply_values(
        self, resolved_bindings: list[tuple[Binding, JsonScalar]]
    ) -> dict:
        """Inject values into a deep copy of the workflow.

        Each tuple is ``(binding, value)`` where *value* is written to
        ``workflow[node_id]["inputs"][binding.input_name]``.

        Returns the modified workflow dict (original is untouched).
        """
        new_workflow = copy.deepcopy(self.workflow)
        for binding, value in resolved_bindings:
            if binding.resolved_node_id is None:
                raise BindingNotFoundError(
                    f"Binding '{binding.binding_id}' has not been resolved"
                )
            node = new_workflow[binding.resolved_node_id]
            if "inputs" not in node:
                node["inputs"] = {}
            node["inputs"][binding.input_name] = value
        return new_workflow
