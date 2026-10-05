"""Bounded Agent projections; exact canvas data remains available explicitly."""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

from .graph import CanvasError


def _short(value: Any, limit: int = 160) -> str:
    return value[:limit] if isinstance(value, str) else ""


def canvas_view(
    canvas: dict[str, Any], *, view: str = "full", node_id: str | None = None,
    node_ids: list[str] | None = None, limit: int = 50, offset: int = 0,
    expected_version: int | None = None,
) -> dict[str, Any]:
    if view not in {"full", "overview"}:
        raise ValueError("view 只能是 overview 或 full")
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError("limit 需要在 1–100 之间，offset 需要是非负整数")
    if expected_version is not None and (type(expected_version) is not int or expected_version != canvas["version"]):
        raise CanvasError("画布版本已变化，请重新读取目录", code="version_conflict", status=409)
    graph = canvas["graph"]
    nodes, edges = graph["nodes"], graph["edges"]
    if node_id is not None or node_ids is not None:
        if node_id is not None and node_ids is not None:
            raise ValueError("node_id 与 node_ids 不能同时指定")
        requested = [node_id] if node_id is not None else node_ids
        if not isinstance(requested, list) or not 1 <= len(requested) <= 20 or any(not isinstance(i, str) or not i for i in requested) or len(set(requested)) != len(requested):
            raise ValueError("需要 1–20 个不重复的节点编号")
        targets = set(requested)
        if not targets <= {node["id"] for node in nodes}:
            raise ValueError("没有找到请求的组件")
        incoming = [edge for edge in edges if edge["target"] in targets]
        ids = targets | {edge["source"] for edge in incoming}
        return {"id": canvas["id"], "version": canvas["version"], "nodes": copy.deepcopy([node for node in nodes if node["id"] in ids]), "edges": copy.deepcopy(incoming)}
    if view == "full":
        return copy.deepcopy(canvas)
    if offset and expected_version is None:
        raise ValueError("后续分页必须携带 expected_version，避免混合版本")
    page = nodes[offset:offset + limit]
    summaries = []
    for node in page:
        data = node.get("data", {})
        summaries.append({
            "id": node["id"], "type": node["type"],
            "position": {key: node["position"][key] for key in ("x", "y")},
            "data": {
                **{key: _short(data.get(key)) for key in ("label", "panel_id", "category", "provider", "model", "mode")},
                "has_asset": bool(data.get("asset")),
                "prompt_chars": len(data.get("prompt") or ""),
                "content_chars": len(data.get("content") or ""),
            },
        })
    ids = {node["id"] for node in page}
    relevant = [edge for edge in edges if edge["source"] in ids or edge["target"] in ids]
    workspace = graph.get("workspace", {})
    return {
        "id": canvas["id"], "name": _short(canvas["name"]), "version": canvas["version"],
        "view": "overview", "partial": True,
        "omitted": ["prompt", "content", "description", "asset", "history", "generation_snapshot", "workspace_details"],
        "selection": list(graph.get("selection", []))[:100],
        "selection_count": len(graph.get("selection", [])),
        "selection_truncated": len(graph.get("selection", [])) > 100, "nodes": summaries,
        "edges": [{key: edge[key] for key in ("id", "source", "target", "sourceHandle", "targetHandle") if key in edge} for edge in relevant[:200]],
        "edges_truncated": len(relevant) > 200, "edge_count": len(edges),
        "workspace": {key: _short(workspace.get(key), 320) for key in ("story", "chapter", "summary") if key in workspace},
        "page": {"offset": offset, "limit": limit, "total": len(nodes), "next_offset": offset + limit if offset + limit < len(nodes) else None},
    }


def edit_receipt(
    canvas: dict[str, Any], operations: list[dict[str, Any]], *,
    affected_node_ids: Iterable[str] = (),
) -> dict[str, Any]:
    changed = set(affected_node_ids)
    for operation in operations:
        if operation.get("node_id"):
            changed.add(operation["node_id"])
        node = operation.get("node")
        if isinstance(node, dict) and node.get("id"):
            changed.add(node["id"])
        edge = operation.get("edge")
        if isinstance(edge, dict):
            changed.update(edge[key] for key in ("source", "target") if key in edge)
    return {
        "id": canvas["id"], "name": _short(canvas["name"]), "version": canvas["version"],
        "changed_node_ids": sorted(changed)[:20], "changed_node_count": len(changed),
        "changed_nodes_truncated": len(changed) > 20,
        "node_count": len(canvas["graph"]["nodes"]), "edge_count": len(canvas["graph"]["edges"]),
    }
