"""LineageService — trace asset provenance via asset_relations.

Walks the asset_relations graph backward from a final export asset to produce
a complete lineage tree: Final Export → EDL → Selected Clips → Raw Videos.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from lfo.core.database import Database


@dataclass
class LineageNode:
    """A node in the asset lineage tree."""

    asset_id: str
    asset_type: str
    file_path: str
    relation: str  # how this node connects to its parent
    children: list[LineageNode] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class LineageService:
    """Trace asset provenance through asset_relations."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_lineage(self, asset_id: str, max_depth: int = 10) -> LineageNode | None:
        """Build the full lineage tree for an asset."""
        row = self.db.fetchone(
            "SELECT asset_id, asset_type, file_path, metadata FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        if row is None:
            return None

        metadata = json.loads(row[3]) if row[3] else {}
        node = LineageNode(
            asset_id=row[0],
            asset_type=row[1],
            file_path=row[2],
            relation="root",
            metadata=metadata,
        )

        self._build_children(node, depth=0, max_depth=max_depth)
        return node

    def get_lineage_flat(self, asset_id: str) -> list[dict]:
        """Get a flat list of all upstream assets (BFS traversal)."""
        visited = set()
        result = []
        queue = [(asset_id, 0, "root")]

        while queue:
            aid, depth, relation = queue.pop(0)
            if aid in visited or depth > 10:
                continue
            visited.add(aid)

            row = self.db.fetchone(
                "SELECT asset_id, asset_type, file_path, metadata FROM assets WHERE asset_id = ?",
                (aid,),
            )
            if row is None:
                continue

            metadata = json.loads(row[3]) if row[3] else {}
            result.append({
                "asset_id": row[0],
                "asset_type": row[1],
                "file_path": row[2],
                "relation": relation,
                "depth": depth,
                "metadata": metadata,
            })

            # Find upstream assets (sources that target this asset)
            relations = self.db.fetchall(
                "SELECT source_asset_id, relation_type FROM asset_relations WHERE target_asset_id = ?",
                (aid,),
            )
            for src_id, rel_type in relations:
                if src_id not in visited:
                    queue.append((src_id, depth + 1, rel_type))

        return result

    def get_export_lineage(self, export_asset_id: str) -> dict:
        """Get a structured lineage report for a final export asset."""
        tree = self.get_lineage(export_asset_id)
        if tree is None:
            return {"error": f"Asset {export_asset_id} not found"}

        flat = self.get_lineage_flat(export_asset_id)

        edl_ids = [n for n in flat if n.get("metadata", {}).get("source") == "srt_generator"]
        srt_ids = [n["asset_id"] for n in flat if n["asset_type"] == "subtitle"]

        return {
            "export_asset_id": export_asset_id,
            "tree": _node_to_dict(tree),
            "flat": flat,
            "total_upstream_assets": len(flat) - 1,
            "edl_assets": edl_ids,
            "srt_assets": srt_ids,
        }

    # -- internal helpers -------------------------------------------------

    def _build_children(self, node: LineageNode, depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return

        relations = self.db.fetchall(
            "SELECT source_asset_id, relation_type, metadata FROM asset_relations WHERE target_asset_id = ?",
            (node.asset_id,),
        )
        for src_id, rel_type, _rel_meta in relations:
            src_row = self.db.fetchone(
                "SELECT asset_id, asset_type, file_path, metadata FROM assets WHERE asset_id = ?",
                (src_id,),
            )
            if src_row is None:
                continue

            metadata = json.loads(src_row[3]) if src_row[3] else {}
            child = LineageNode(
                asset_id=src_row[0],
                asset_type=src_row[1],
                file_path=src_row[2],
                relation=rel_type,
                metadata=metadata,
            )
            node.children.append(child)
            self._build_children(child, depth + 1, max_depth)


def _node_to_dict(node: LineageNode) -> dict:
    """Convert a LineageNode tree to a dict."""
    return {
        "asset_id": node.asset_id,
        "asset_type": node.asset_type,
        "file_path": node.file_path,
        "relation": node.relation,
        "metadata": node.metadata,
        "children": [_node_to_dict(c) for c in node.children],
    }
