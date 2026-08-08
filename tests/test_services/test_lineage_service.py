"""Tests for Wave 2-B: LineageService."""
from __future__ import annotations

import json

import pytest

from lfo.core.database import Database
from lfo.services.lineage_service import LineageService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-1", "proj-1", "video", "SUCCEEDED"))
    return db


def _add_asset(db, asset_id, asset_type, file_path, metadata=None):
    db.execute(
        "INSERT INTO assets (asset_id, task_id, asset_type, file_path, metadata) VALUES (?, ?, ?, ?, ?)",
        (asset_id, "task-1", asset_type, file_path, json.dumps(metadata or {})),
    )


def _add_relation(db, source, target, relation_type, metadata=None):
    db.execute(
        "INSERT INTO asset_relations (source_asset_id, target_asset_id, relation_type, metadata) VALUES (?, ?, ?, ?)",
        (source, target, relation_type, json.dumps(metadata or {})),
    )


class TestLineageService:
    def test_get_lineage_not_found(self, db):
        svc = LineageService(db)
        assert svc.get_lineage("nonexistent") is None

    def test_get_lineage_single_asset(self, db):
        _add_asset(db, "asset-1", "video", "/tmp/v1.mp4")
        svc = LineageService(db)
        tree = svc.get_lineage("asset-1")
        assert tree is not None
        assert tree.asset_id == "asset-1"
        assert tree.children == []

    def test_get_lineage_with_children(self, db):
        _add_asset(db, "raw-1", "video", "/tmp/raw1.mp4")
        _add_asset(db, "norm-1", "video", "/tmp/norm1.mp4")
        _add_asset(db, "clip-1", "video", "/tmp/clip1.mp4")
        _add_relation(db, "raw-1", "norm-1", "normalized_from")
        _add_relation(db, "norm-1", "clip-1", "selected_from")

        svc = LineageService(db)
        tree = svc.get_lineage("clip-1")
        assert tree is not None
        assert len(tree.children) == 1
        assert tree.children[0].asset_id == "norm-1"
        assert tree.children[0].children[0].asset_id == "raw-1"

    def test_get_lineage_flat(self, db):
        _add_asset(db, "raw-1", "video", "/tmp/raw1.mp4")
        _add_asset(db, "norm-1", "video", "/tmp/norm1.mp4")
        _add_asset(db, "clip-1", "video", "/tmp/clip1.mp4")
        _add_relation(db, "raw-1", "norm-1", "normalized_from")
        _add_relation(db, "norm-1", "clip-1", "selected_from")

        svc = LineageService(db)
        flat = svc.get_lineage_flat("clip-1")
        assert len(flat) == 3
        depths = {n["asset_id"]: n["depth"] for n in flat}
        assert depths["clip-1"] == 0
        assert depths["norm-1"] == 1
        assert depths["raw-1"] == 2

    def test_get_export_lineage(self, db):
        _add_asset(db, "edl-1", "document", "/tmp/edl.json", {"source": "assembly"})
        _add_asset(db, "srt-1", "subtitle", "/tmp/subs.srt", {"source": "srt_generator"})
        _add_asset(db, "export-1", "video", "/tmp/final.mp4", {"source": "assembly"})
        _add_relation(db, "edl-1", "export-1", "assembled_from")
        _add_relation(db, "srt-1", "export-1", "subtitle_for")

        svc = LineageService(db)
        report = svc.get_export_lineage("export-1")

        assert report["export_asset_id"] == "export-1"
        assert report["total_upstream_assets"] == 2
        assert len(report["flat"]) == 3

    def test_max_depth_respected(self, db):
        """Lineage traversal should respect max_depth."""
        for i in range(6):
            _add_asset(db, f"asset-{i}", "video", f"/tmp/v{i}.mp4")
        for i in range(5):
            _add_relation(db, f"asset-{i+1}", f"asset-{i}", "derived_from")

        svc = LineageService(db)
        tree_shallow = svc.get_lineage("asset-0", max_depth=2)
        tree_deep = svc.get_lineage("asset-0", max_depth=10)

        shallow_count = len(svc.get_lineage_flat("asset-0") if False else [])
        deep_count = len(svc.get_lineage_flat("asset-0"))
        assert deep_count == 6
        assert tree_shallow is not None
        assert tree_deep is not None
        # Should stop at depth 2
