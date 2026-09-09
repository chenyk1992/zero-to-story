"""Import a prepared story graph through the same API as the canvas page.

The caller decides which story assets belong together. This helper only reads
selected documents, registers media, and saves that graph; it never generates.
"""

from __future__ import annotations

# Ruff's confusable-punctuation rule does not apply to Chinese user messages.
# ruff: noqa: RUF001
import argparse
import copy
import json
from pathlib import Path
from typing import Any

from lfo.canvas.client import CanvasClient
from lfo.canvas.graph import validate_graph
from lfo.canvas.media import media_kind
from lfo.canvas.settings import CanvasSettings


def prepare_workspace(manifest: dict[str, Any], base: Path) -> dict[str, Any]:
    """Resolve all selected files before the first media import or DB write."""
    prepared = copy.deepcopy(manifest)
    name = prepared.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("工作空间需要名称")
    graph = prepared.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("清单需要 graph")
    for node in graph.get("nodes", []):
        data = node.setdefault("data", {})
        is_document = node["type"] == "document"
        source_key = "source_path" if is_document else "prompt_source_path"
        source = data.get(source_key)
        field = "content" if is_document else "prompt"
        if node["type"] in {"document", "image", "video"} and source and field not in data:
            path = _path(source, base)
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f"文档过大，请选取相关章节：{path.name}")
            data[field] = path.read_text(encoding="utf-8-sig")
            data[source_key] = str(path)
        for owner in _asset_owners(data):
            asset = owner["asset"]
            path = _path(asset["path"], base)
            if path.stat().st_size == 0:
                raise ValueError(f"素材为空：{path.name}")
            actual_kind = media_kind(path)
            if asset.get("kind") not in {None, actual_kind}:
                raise ValueError(f"素材类型不符：{path.name}")
            asset.update(path=str(path), kind=actual_kind)
            asset.setdefault("name", owner.get("label") or data.get("label") or path.name)
            owner.setdefault("source_path", str(path))
    prepared["graph"] = validate_graph(graph)
    # Same payload bound as the HTTP service; fail before copying any assets.
    if len(json.dumps(prepared, ensure_ascii=False).encode("utf-8")) > 3900 * 1024:
        raise ValueError("章节内容过大，请缩小导入范围")
    return prepared


def _path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else base / path).resolve()
    if not path.is_file():
        raise ValueError(f"所选文件不存在：{path}")
    return path


def _asset_owners(data: dict[str, Any]) -> list[dict[str, Any]]:
    owners = [data]
    for field in ("history", "derived_outputs"):
        values = data.get(field, [])
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(f"{field} 需要素材记录数组")
        owners.extend(values)
    return [
        owner
        for owner in owners
        if isinstance(owner.get("asset"), dict) and owner["asset"].get("path")
    ]


def import_workspace(client: CanvasClient, prepared: dict[str, Any]) -> dict[str, Any]:
    """Create one workspace without creating or completing generation runs."""
    body = copy.deepcopy(prepared)
    media_cache: dict[str, dict[str, str]] = {}
    for node in body["graph"]["nodes"]:
        data = node.get("data", {})
        for owner in _asset_owners(data):
            asset = owner["asset"]
            path = asset["path"]
            if path not in media_cache:
                media_cache[path] = client.request("POST", "/api/assets/import", {"path": path})
            owner["asset"] = {
                **asset,
                **media_cache[path],
                "name": asset.get("name") or media_cache[path]["name"],
            }
    return client.request("POST", "/api/canvases", {"name": body["name"], "graph": body["graph"]})


def main() -> int:
    parser = argparse.ArgumentParser(description="把已整理的故事资料清单放入项目画布，不生成媒体")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    prepared = prepare_workspace(manifest, project)
    if args.dry_run:
        graph = prepared["graph"]
        print(
            json.dumps(
                {
                    "name": prepared["name"],
                    "nodes": len(graph["nodes"]),
                    "edges": len(graph["edges"]),
                    "validated": True,
                },
                ensure_ascii=False,
            )
        )
        return 0
    client = CanvasClient(CanvasSettings.resolve(project))
    client.ensure_server()
    created = import_workspace(client, prepared)
    print(
        json.dumps(
            {
                "name": created["name"],
                "canvas_id": created["id"],
                "url": f"{client.url}/?canvas={created['id']}",
                "generation_submissions": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
