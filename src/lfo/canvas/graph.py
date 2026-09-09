"""Validation and input resolution for the lightweight canvas graph.

The canvas keeps a generation component self-contained: image and video
nodes carry their own prompt and can carry a real existing asset.  Generation
history and derived outputs are metadata on that same node; they are not
additional executable nodes.  Provider-specific rules remain in Skills and
adapters, while this module only enforces the graph contract and resolves
provider-neutral inputs.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

NODE_TYPES = frozenset({"asset", "image", "video", "document", "section"})
GENERATION_NODE_TYPES = frozenset({"image", "video"})
NODE_CATEGORIES = frozenset({"character", "storyboard", "board", "image", "video", "document"})
TARGET_HANDLES = frozenset(
    {
        "first_frame",
        "last_frame",
        "reference_image",
        "reference_video",
        "reference_audio",
        "related",
    }
)
SINGLE_INPUT_HANDLES = frozenset({"first_frame", "last_frame"})
MEDIA_INPUT_HANDLES = frozenset(
    {"first_frame", "last_frame", "reference_image", "reference_video", "reference_audio"}
)
PARAMETER_FIELDS = ("duration", "aspect_ratio", "megapixels")
OUTPUT_STATUSES = frozenset({"succeeded"})
ASSET_KINDS = frozenset({"image", "video", "audio"})
OUTPUT_HANDLE = "output"
OUTPUT_HANDLE_PREFIX = "output:"


class CanvasError(ValueError):
    """Base error for graph validation and snapshot resolution.

    ``code``, ``message`` and ``status`` deliberately mirror the shape used by
    the store exceptions so an HTTP bridge can serialize either kind uniformly.
    """

    status = 400

    def __init__(self, message: str, *, code: str = "invalid_graph", status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        if status is not None:
            self.status = status


class CanvasGraphError(CanvasError):
    """Compatibility name for callers that only handle graph errors."""


class GraphValidationError(CanvasGraphError):
    """The graph has an invalid shape or an invalid connection."""


class SnapshotResolutionError(CanvasGraphError):
    """The graph is saveable, but a runnable input cannot be resolved."""

    def __init__(self, message: str, *, code: str = "invalid_snapshot"):
        super().__init__(message, code=code)


class MissingInputError(SnapshotResolutionError):
    """A required value or an upstream generated result is unavailable."""


def empty_graph() -> dict[str, Any]:
    """Return a new empty graph with all view fields present."""

    return {
        "nodes": [],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached, canonical-enough graph copy.

    Draft graphs may omit semantic generation fields such as ``prompt``,
    ``mode`` or ``provider``.  They still need a structurally valid node and
    edge shape.  Unknown provider IDs and unknown option fields are preserved
    for later Skill validation.
    """

    if not isinstance(graph, Mapping):
        raise GraphValidationError("graph must be an object", code="graph_type")

    result = deepcopy(dict(graph))
    nodes_value = result.get("nodes", [])
    edges_value = result.get("edges", [])
    if not _is_sequence(nodes_value):
        raise GraphValidationError("graph.nodes must be an array", code="nodes_type")
    if not _is_sequence(edges_value):
        raise GraphValidationError("graph.edges must be an array", code="edges_type")

    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, raw_node in enumerate(nodes_value):
        node = dict(_require_mapping(raw_node, f"nodes[{index}]"))
        node_id = _require_string(node.get("id"), f"nodes[{index}].id")
        if node_id in node_ids:
            raise GraphValidationError(f"duplicate node id: {node_id}", code="duplicate_node_id")
        node_ids.add(node_id)

        node_type = _require_string(node.get("type"), f"nodes[{index}].type")
        if node_type not in NODE_TYPES:
            raise GraphValidationError(f"unknown node type: {node_type}", code="unknown_node_type")

        position = node.get("position")
        if not isinstance(position, Mapping):
            raise GraphValidationError(
                f"nodes[{index}].position must be an object", code="position_type"
            )
        _require_number(position.get("x"), f"nodes[{index}].position.x")
        _require_number(position.get("y"), f"nodes[{index}].position.y")

        data = node.get("data", {})
        if not isinstance(data, Mapping):
            raise GraphValidationError(
                f"nodes[{index}].data must be an object", code="node_data_type"
            )
        _validate_node_data(data, index, node_type)
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()
    incoming_single: set[tuple[str, str]] = set()
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for index, raw_edge in enumerate(edges_value):
        edge = dict(_require_mapping(raw_edge, f"edges[{index}]"))
        edge_id = _require_string(edge.get("id"), f"edges[{index}].id")
        if edge_id in edge_ids:
            raise GraphValidationError(f"duplicate edge id: {edge_id}", code="duplicate_edge_id")
        edge_ids.add(edge_id)

        source = _require_string(edge.get("source"), f"edges[{index}].source")
        target = _require_string(edge.get("target"), f"edges[{index}].target")
        source_handle = _require_string(edge.get("sourceHandle"), f"edges[{index}].sourceHandle")
        target_handle = _require_string(edge.get("targetHandle"), f"edges[{index}].targetHandle")
        if source not in node_ids:
            raise GraphValidationError(
                f"edge {edge_id} references unknown source node: {source}",
                code="unknown_edge_source",
            )
        if target not in node_ids:
            raise GraphValidationError(
                f"edge {edge_id} references unknown target node: {target}",
                code="unknown_edge_target",
            )
        derived_id = _parse_source_handle(source_handle, f"edges[{index}].sourceHandle")
        if "require_accept" in edge and not isinstance(edge["require_accept"], bool):
            raise GraphValidationError("require_accept must be boolean", code="accept_type")
        if edge.get("require_accept") and not edge.get("source_run_id"):
            raise GraphValidationError("采用依赖需要明确 source_run_id", code="missing_source_run")
        if "source_run_id" in edge:
            _require_string(edge["source_run_id"], "source_run_id")
        if target_handle not in TARGET_HANDLES:
            raise GraphValidationError(
                f"unknown target handle: {target_handle}", code="target_handle"
            )
        pair = (target, target_handle)
        if target_handle in SINGLE_INPUT_HANDLES and pair in incoming_single:
            raise GraphValidationError(
                f"target handle accepts only one input: {target}:{target_handle}",
                code="duplicate_single_input",
            )
        if target_handle in SINGLE_INPUT_HANDLES:
            incoming_single.add(pair)

        source_type = _node_type(nodes, source)
        target_type = _node_type(nodes, target)
        if not _connection_is_possible(
            source_type, target_type, target_handle, derived_id=derived_id
        ):
            raise GraphValidationError(
                f"cannot connect {source_type} to {target_type}.{target_handle}",
                code="incompatible_edge",
            )

        # Related edges are workspace annotations.  They may form cycles and
        # never participate in the execution DAG.
        if target_handle != "related":
            adjacency[source].append(target)
        edges.append(edge)

    _reject_cycles(adjacency)

    viewport = result.get("viewport", empty_graph()["viewport"])
    if not isinstance(viewport, Mapping):
        raise GraphValidationError("graph.viewport must be an object", code="viewport_type")
    for field in ("x", "y", "zoom"):
        _require_number(viewport.get(field), f"viewport.{field}")
    if float(viewport["zoom"]) <= 0:
        raise GraphValidationError("graph.viewport.zoom must be positive", code="viewport_zoom")

    selection = result.get("selection", [])
    if not _is_sequence(selection):
        raise GraphValidationError("graph.selection must be an array", code="selection_type")
    for index, selected_id in enumerate(selection):
        selected_id = _require_string(selected_id, f"selection[{index}]")
        if selected_id not in node_ids:
            raise GraphValidationError(
                f"selection references unknown node: {selected_id}", code="selection_node"
            )

    result["nodes"] = nodes
    result["edges"] = edges
    result["viewport"] = dict(viewport)
    result["selection"] = list(selection)
    workspace = result.get("workspace")
    if workspace is not None:
        workspace = _require_mapping(workspace, "graph.workspace")
        _validate_workspace(workspace)
        result["workspace"] = dict(workspace)
    return result


def resolve_snapshot(
    canvas: Mapping[str, Any], node_id: str, runs: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Resolve a generation node into provider-neutral effective inputs.

    Prompt text is always read from the target image/video node.  A connected
    media source uses an explicitly bound ``source_run_id`` when supplied;
    ``require_accept`` additionally requires its reviewed actual file version.
    Ordinary inputs use the newest succeeded run, or the embedded ``data.asset``.
    ``output:<derived_id>`` selects one immutable derived output on that source
    node.  Related edges are intentionally ignored.
    """

    if not isinstance(canvas, Mapping):
        raise SnapshotResolutionError("canvas must be an object", code="canvas_type")
    graph = validate_graph(_as_mapping(canvas.get("graph"), "canvas.graph"))
    node = _find_node(graph["nodes"], node_id)
    node_type = node["type"]
    if node_type not in GENERATION_NODE_TYPES:
        raise SnapshotResolutionError(
            f"node {node_id} is not a generation node", code="not_generation_node"
        )
    data = node["data"]

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise MissingInputError(f"node {node_id} has no prompt", code="missing_prompt")

    mode = data.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise MissingInputError(f"node {node_id} has no generation mode", code="missing_mode")

    provider = data.get("provider")
    if provider is None or provider == "":
        raise MissingInputError("请选择当前可用的生成方式", code="missing_provider")
    if not isinstance(provider, str):
        raise SnapshotResolutionError(
            f"node {node_id}.data.provider must be a string", code="provider_type"
        )
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        raise SnapshotResolutionError(
            f"node {node_id}.data.model must be a string", code="model_type"
        )

    parameters: dict[str, Any] = {
        field: deepcopy(data[field])
        for field in PARAMETER_FIELDS
        if field in data and data[field] is not None
    }
    options = data.get("options", {})
    if not isinstance(options, Mapping):
        raise SnapshotResolutionError(
            f"node {node_id}.data.options must be an object", code="options_type"
        )
    provider_options = options.get(provider, {})
    if provider_options is None:
        provider_options = {}
    if not isinstance(provider_options, Mapping):
        raise SnapshotResolutionError(
            f"options for provider {provider} must be an object", code="provider_options_type"
        )
    if set(provider_options).intersection(PARAMETER_FIELDS):
        raise SnapshotResolutionError(
            "专属参数不能覆盖时长、画幅或像素预算，请直接修改对应栏目",
            code="hidden_parameter_override",
        )
    parameters.update(deepcopy(dict(provider_options)))

    input_values: dict[str, Any] = {
        "reference_images": [],
        "reference_videos": [],
        "reference_audios": [],
    }
    canvas_id = canvas.get("id")
    run_list = [
        run for run in (runs or []) if canvas_id is None or run.get("canvas_id") == canvas_id
    ]
    incoming = [edge for edge in graph["edges"] if edge["target"] == node_id]
    for edge in incoming:
        target_handle = edge["targetHandle"]
        if target_handle == "related":
            continue
        source = _find_node(graph["nodes"], edge["source"])
        assets = _resolve_source_assets(
            source,
            run_list,
            graph,
            source_handle=edge["sourceHandle"],
            source_run_id=edge.get("source_run_id"),
            require_accept=edge.get("require_accept", False),
        )
        if not assets:
            raise MissingInputError(
                f"input {source['id']} has no usable output", code="missing_upstream_result"
            )
        selected = _select_assets(assets, target_handle)
        if not selected:
            raise MissingInputError(
                f"input {source['id']} cannot provide {target_handle}",
                code="input_kind_mismatch",
            )
        if target_handle in {"first_frame", "last_frame"}:
            input_values[target_handle] = selected[0]
        elif target_handle == "reference_image":
            input_values["reference_images"].extend(selected)
        elif target_handle == "reference_video":
            input_values["reference_videos"].extend(selected)
        elif target_handle == "reference_audio":
            input_values["reference_audios"].extend(selected)

    return {
        "node_id": node_id,
        "node_type": node_type,
        "provider": provider,
        "model": model,
        "mode": mode,
        "prompt": prompt,
        "parameters": parameters,
        "inputs": input_values,
    }


def _validate_node_data(data: Mapping[str, Any], index: int, node_type: str) -> None:
    for field in ("label", "prompt", "provider", "model", "mode"):
        if field in data and data[field] is not None and not isinstance(data[field], str):
            raise GraphValidationError(
                f"nodes[{index}].data.{field} must be a string", code="node_data_field_type"
            )
    for field in ("duration", "megapixels"):
        if field in data and data[field] is not None:
            _require_number(data[field], f"nodes[{index}].data.{field}")
    if (
        "aspect_ratio" in data
        and data["aspect_ratio"] is not None
        and not isinstance(data["aspect_ratio"], str)
    ):
        raise GraphValidationError(
            f"nodes[{index}].data.aspect_ratio must be a string", code="node_data_field_type"
        )
    category = data.get("category")
    if category is not None:
        if not isinstance(category, str):
            raise GraphValidationError(
                f"nodes[{index}].data.category must be a string", code="node_data_field_type"
            )
        if category not in NODE_CATEGORIES:
            raise GraphValidationError(
                f"unknown node category: {category}", code="unknown_node_category"
            )
    for field in ("panel_id", "description", "content", "source_path", "status"):
        if field in data and data[field] is not None and not isinstance(data[field], str):
            raise GraphValidationError(
                f"nodes[{index}].data.{field} must be a string", code="node_data_field_type"
            )
    if node_type == "section":
        for field in ("width", "height"):
            if field in data and data[field] is not None:
                _require_number(data[field], f"nodes[{index}].data.{field}")
    options = data.get("options")
    if options is not None:
        if not isinstance(options, Mapping):
            raise GraphValidationError(
                f"nodes[{index}].data.options must be an object", code="options_type"
            )
        for provider_id, provider_options in options.items():
            if not isinstance(provider_id, str) or not isinstance(provider_options, Mapping):
                raise GraphValidationError(
                    f"nodes[{index}].data.options must map provider IDs to objects",
                    code="provider_options_type",
                )

    asset = data.get("asset")
    if asset is not None:
        _validate_asset(asset, f"nodes[{index}].data.asset", allow_empty=True)
    _validate_history(data.get("history"), f"nodes[{index}].data.history")
    _validate_derived_outputs(data.get("derived_outputs"), f"nodes[{index}].data.derived_outputs")


def _validate_history(value: Any, field: str) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        raise GraphValidationError(f"{field} must be an array", code="history_type")
    ids: set[str] = set()
    for index, raw_item in enumerate(value):
        item = _require_mapping(raw_item, f"{field}[{index}]")
        item_id = _require_string(item.get("id"), f"{field}[{index}].id")
        if item_id in ids:
            raise GraphValidationError(
                f"duplicate history id: {item_id}", code="duplicate_history_id"
            )
        ids.add(item_id)
        _require_string(item.get("label"), f"{field}[{index}].label")
        _validate_asset(item.get("asset"), f"{field}[{index}].asset")
        if not isinstance(item.get("generation_snapshot"), Mapping):
            raise GraphValidationError(
                f"{field}[{index}].generation_snapshot must be an object",
                code="generation_snapshot_type",
            )
        for optional in ("status", "source_path"):
            if (
                optional in item
                and item[optional] is not None
                and not isinstance(item[optional], str)
            ):
                raise GraphValidationError(
                    f"{field}[{index}].{optional} must be a string",
                    code="history_field_type",
                )


def _validate_derived_outputs(value: Any, field: str) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        raise GraphValidationError(f"{field} must be an array", code="derived_outputs_type")
    ids: set[str] = set()
    for index, raw_item in enumerate(value):
        item = _require_mapping(raw_item, f"{field}[{index}]")
        item_id = _require_string(item.get("id"), f"{field}[{index}].id")
        if item_id in ids:
            raise GraphValidationError(
                f"duplicate derived output id: {item_id}", code="duplicate_derived_output_id"
            )
        ids.add(item_id)
        _require_string(item.get("label"), f"{field}[{index}].label")
        _validate_asset(item.get("asset"), f"{field}[{index}].asset")
        if (
            "source_version" in item
            and item["source_version"] is not None
            and not isinstance(item["source_version"], str)
        ):
            raise GraphValidationError(
                f"{field}[{index}].source_version must be a string",
                code="derived_output_field_type",
            )


def _validate_workspace(workspace: Mapping[str, Any]) -> None:
    for field in ("story", "chapter", "summary", "source"):
        if (
            field in workspace
            and workspace[field] is not None
            and not isinstance(workspace[field], str)
        ):
            raise GraphValidationError(
                f"graph.workspace.{field} must be a string", code="workspace_field_type"
            )


def _validate_asset(value: Any, field: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, Mapping):
        raise GraphValidationError(f"{field} must be an object", code="asset_type")
    path = value.get("path")
    kind = value.get("kind")
    if (path is None or path == "") and allow_empty:
        return
    if not isinstance(path, str) or not path.strip():
        raise GraphValidationError(f"{field}.path must be a non-empty string", code="asset_path")
    if not isinstance(kind, str) or kind not in ASSET_KINDS:
        raise GraphValidationError(
            f"{field}.kind must be one of image, video, audio", code="asset_kind"
        )
    if "name" in value and value["name"] is not None and not isinstance(value["name"], str):
        raise GraphValidationError(f"{field}.name must be a string", code="asset_name")


def _resolve_source_assets(
    source: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any] | None = None,
    *,
    source_handle: str = OUTPUT_HANDLE,
    source_run_id: str | None = None,
    require_accept: bool = False,
) -> list[dict[str, Any]]:
    derived_id = _parse_source_handle(source_handle, "sourceHandle")
    source_type = source["type"]
    selected_run = None
    if source_run_id is not None:
        selected_run = next(
            (
                run
                for run in runs
                if run.get("id") == source_run_id
                and run.get("node_id") == source["id"]
                and run.get("status") == "succeeded"
            ),
            None,
        )
        if selected_run is None:
            raise MissingInputError("指定的上游成品尚未成功", code="missing_source_run")
        if require_accept and (selected_run.get("review") or {}).get("decision") != "ACCEPT":
            raise MissingInputError("指定的上游成品尚未采用", code="upstream_not_accepted")
    if source_type == "asset":
        if derived_id is not None:
            raise MissingInputError(
                f"asset node {source['id']} has no derived output: {derived_id}",
                code="missing_derived_output",
            )
        asset = source["data"].get("asset")
        if asset is None:
            raise MissingInputError(f"asset node {source['id']} has no asset", code="missing_asset")
        _validate_asset(asset, f"asset node {source['id']}.data.asset")
        return [dict(asset)]

    if source_type not in GENERATION_NODE_TYPES:
        raise MissingInputError(
            f"node {source['id']} cannot provide media", code="missing_upstream_result"
        )

    if derived_id is not None:
        entries = source["data"].get("derived_outputs") or []
        entry = next(
            (
                item
                for item in entries
                if isinstance(item, Mapping) and item.get("id") == derived_id
            ),
            None,
        )
        if entry is None:
            raise MissingInputError(
                f"node {source['id']} has no derived output: {derived_id}",
                code="missing_derived_output",
            )
        try:
            _validate_asset(entry.get("asset"), f"derived output {source['id']}:{derived_id}.asset")
        except GraphValidationError as exc:
            raise MissingInputError(str(exc), code="invalid_derived_output") from exc
        asset = dict(entry["asset"])
        if source_run_id is not None:
            if entry.get("source_run_id") != source_run_id:
                raise MissingInputError(
                    "衍生素材未绑定指定的来源版本", code="derived_source_mismatch"
                )
            asset["source_run_id"] = source_run_id
        if require_accept:
            assert selected_run is not None
            digest = asset.get("sha256")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise MissingInputError(
                    "衍生素材缺少文件摘要，请先导入实际文件", code="derived_digest_missing"
                )
            asset["accepted_sha256"] = digest
            asset["accepted_source"] = {
                key: selected_run["review"][key] for key in ("output_path", "output_sha256")
            }
        return [asset]

    succeeded = [
        run
        for run in runs
        if run.get("node_id") == source["id"]
        and run.get("status") in OUTPUT_STATUSES
        and (source_run_id is None or run.get("id") == source_run_id)
    ]
    if succeeded:
        succeeded.sort(key=_run_sort_key)
        if require_accept:
            assert selected_run is not None
            review = selected_run["review"]
            outputs = [{"path": review["output_path"], "kind": source_type}]
        else:
            outputs = succeeded[-1].get("outputs", [])
        if isinstance(outputs, Mapping):
            outputs = [outputs]
        if not _is_sequence(outputs) or not outputs:
            raise MissingInputError(
                f"run for node {source['id']} has no usable outputs",
                code="missing_upstream_result",
            )
        assets: list[dict[str, Any]] = []
        for index, output in enumerate(outputs):
            try:
                _validate_asset(output, f"run output {source['id']}[{index}]")
            except GraphValidationError as exc:
                raise MissingInputError(str(exc), code="invalid_run_output") from exc
            asset = dict(output)
            if source_run_id is not None:
                asset["source_run_id"] = source_run_id
            if require_accept:
                assert selected_run is not None
                review = selected_run["review"]
                if review["output_path"] != asset["path"]:
                    continue
                asset["accepted_sha256"] = review["output_sha256"]
            assets.append(asset)
        if not assets:
            raise MissingInputError("没有与采用记录一致的上游产物", code="accepted_output_missing")
        return assets

    asset = source["data"].get("asset")
    if asset is None:
        raise MissingInputError(
            f"node {source['id']} has no succeeded run or embedded asset",
            code="missing_upstream_result",
        )
    try:
        _validate_asset(asset, f"node {source['id']}.data.asset")
    except GraphValidationError as exc:
        raise MissingInputError(str(exc), code="invalid_asset") from exc
    return [dict(asset)]


def _run_sort_key(run: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(run.get("created_at") or run.get("updated_at") or ""),
        str(run.get("id") or ""),
    )


def _select_assets(assets: Sequence[Mapping[str, Any]], target_handle: str) -> list[dict[str, Any]]:
    if target_handle in {"first_frame", "last_frame", "reference_image"}:
        return [dict(asset) for asset in assets if asset.get("kind") == "image"]
    if target_handle == "reference_video":
        return [dict(asset) for asset in assets if asset.get("kind") == "video"]
    if target_handle == "reference_audio":
        return [dict(asset) for asset in assets if asset.get("kind") == "audio"]
    return [dict(asset) for asset in assets]


def _connection_is_possible(
    source_type: str, target_type: str, target_handle: str, *, derived_id: str | None
) -> bool:
    if target_handle == "related":
        return derived_id is None and source_type != "section" and target_type != "section"
    if target_handle in MEDIA_INPUT_HANDLES:
        if target_type not in GENERATION_NODE_TYPES:
            return False
        if source_type not in {"asset", "image", "video"}:
            return False
        return derived_id is None or source_type in GENERATION_NODE_TYPES
    return False


def _parse_source_handle(value: Any, field: str) -> str | None:
    if not isinstance(value, str):
        raise GraphValidationError(f"{field} must be a string", code="source_handle")
    if value == OUTPUT_HANDLE:
        return None
    if value.startswith(OUTPUT_HANDLE_PREFIX) and value[len(OUTPUT_HANDLE_PREFIX) :].strip():
        derived_id = value[len(OUTPUT_HANDLE_PREFIX) :]
        if any(char.isspace() for char in derived_id):
            raise GraphValidationError(
                f"{field} derived output id must not contain whitespace", code="source_handle"
            )
        return derived_id
    raise GraphValidationError(
        f"{field} must be output or output:<derived_id>", code="source_handle"
    )


def _reject_cycles(adjacency: Mapping[str, Sequence[str]]) -> None:
    states: dict[str, int] = {node_id: 0 for node_id in adjacency}

    def visit(node_id: str) -> None:
        states[node_id] = 1
        for target in adjacency[node_id]:
            if states[target] == 1:
                raise GraphValidationError("graph contains a cycle", code="graph_cycle")
            if states[target] == 0:
                visit(target)
        states[node_id] = 2

    for node_id in adjacency:
        if states[node_id] == 0:
            visit(node_id)


def _find_node(nodes: Sequence[Mapping[str, Any]], node_id: str) -> Mapping[str, Any]:
    for node in nodes:
        if node["id"] == node_id:
            return node
    raise SnapshotResolutionError(f"unknown node: {node_id}", code="unknown_node")


def _node_type(nodes: Sequence[Mapping[str, Any]], node_id: str) -> str:
    for node in nodes:
        if node["id"] == node_id:
            return str(node["type"])
    raise GraphValidationError(f"unknown node: {node_id}", code="unknown_node")


def _as_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SnapshotResolutionError(f"{field} must be an object", code="graph_type")
    return value


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GraphValidationError(f"{field} must be an object", code="object_type")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraphValidationError(f"{field} must be a non-empty string", code="string_type")
    return value


def _require_number(value: Any, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GraphValidationError(f"{field} must be a finite number", code="number_type")
    return value


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
