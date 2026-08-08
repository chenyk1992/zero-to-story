"""Tests for VisualResultService — import + approve."""
from __future__ import annotations

import hashlib

import pytest

from lfo.application.visual_result_service import VisualResultService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.visual.errors import VisualResultError


def _setup(db: Database) -> tuple[str, VisualTaskService]:
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = VisualTaskService(db)
    task_id = svc.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id="s1",
        references=[],
        prompt={"text": "hero"},
    )
    return task_id, svc


def test_import_manifest_creates_asset_and_manifest():
    db = Database()
    db.init_schema()
    task_id, _ = _setup(db)
    rs = VisualResultService(db)
    file_bytes = b"fake png bytes"
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    asset_id = rs.import_manifest(
        {
            "task_id": task_id,
            "content": {"file_path": "hero.png", "width": 1024, "height": 1024},
            "file_hash": file_hash,
        },
        source_root="/tmp/import",
    )
    assert asset_id is not None
    # Task status should be QC_PENDING + RESULT_IMPORTED
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "QC_PENDING"
    assert contract["visual_stage"] == "RESULT_IMPORTED"
    db.close()


def test_import_manifest_idempotent():
    """Re-importing same manifest (same task_id) raises."""
    db = Database()
    db.init_schema()
    task_id, _ = _setup(db)
    rs = VisualResultService(db)
    manifest = {
        "task_id": task_id,
        "content": {"file_path": "hero.png"},
        "file_hash": "a" * 64,
    }
    rs.import_manifest(manifest, source_root="/tmp")
    with pytest.raises(VisualResultError):
        rs.import_manifest(manifest, source_root="/tmp")
    db.close()


def test_approve_creates_binding_and_approves():
    db = Database()
    db.init_schema()
    task_id, _ = _setup(db)
    rs = VisualResultService(db)
    from lfo.services.visual_technical_qc_service import VisualTechnicalQCService
    file_hash = hashlib.sha256(b"img").hexdigest()
    asset_id = rs.import_manifest(
        {
            "task_id": task_id,
            "content": {"file_path": "hero.png", "width": 1024, "height": 1024},
            "file_hash": file_hash,
        },
        source_root="/tmp",
    )
    # Run technical QC to advance to WAITING_USER + AWAITING_REVIEW
    qc = VisualTechnicalQCService(db)
    qc.run(task_id, asset_id)
    rs.approve(
        task_id,
        asset_id=asset_id,
        entity_type="character",
        entity_id="char1",
        asset_role="reference",
        reviewer="human",
    )
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "APPROVED"
    assert contract["visual_stage"] == "APPROVED"
    db.close()


def test_import_never_leaves_succeeded():
    """Import must never leave task on SUCCEEDED."""
    db = Database()
    db.init_schema()
    task_id, _ = _setup(db)
    rs = VisualResultService(db)
    rs.import_manifest(
        {
            "task_id": task_id,
            "content": {"file_path": "hero.png"},
            "file_hash": "b" * 64,
        },
        source_root="/tmp",
    )
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    assert task["status"] != "SUCCEEDED"
    assert task["status"] == "QC_PENDING"
    db.close()
