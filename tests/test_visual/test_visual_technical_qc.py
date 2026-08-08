"""Tests for VisualTechnicalQCService."""
from __future__ import annotations

import hashlib

from lfo.application.visual_result_service import VisualResultService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.services.visual_technical_qc_service import VisualTechnicalQCService


def _import_result(db: Database, task_id: str) -> str:
    rs = VisualResultService(db)
    file_hash = hashlib.sha256(b"img").hexdigest()
    return rs.import_manifest(
        {
            "task_id": task_id,
            "content": {"file_path": "hero.png", "width": 1024, "height": 1024},
            "file_hash": file_hash,
        },
        source_root="/tmp",
    )


def test_qc_pass_transitions_to_awaiting_review():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    asset_id = _import_result(db, task_id)
    qc = VisualTechnicalQCService(db)
    result = qc.run(task_id, asset_id)
    assert result["overall"] == "pass"
    assert "decodable" in result["checks"]
    task = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    contract = db.fetchone(
        "SELECT visual_stage FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    assert task["status"] == "WAITING_USER"
    assert contract["visual_stage"] == "AWAITING_REVIEW"
    db.close()


def test_qc_fails_on_hash_mismatch():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    rs = VisualResultService(db)
    # Import with a file_hash that doesn't match content's declared hash
    asset_id = rs.import_manifest(
        {
            "task_id": task_id,
            "content": {"file_path": "hero.png", "declared_hash": "xyz"},
            "file_hash": "a" * 64,
        },
        source_root="/tmp",
    )
    qc = VisualTechnicalQCService(db)
    result = qc.run(task_id, asset_id)
    assert result["overall"] == "fail"
    assert result["checks"]["hash_match"] is False
    db.close()


def test_qc_checks_included():
    """QC runs the standard technical checks."""
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="scene_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    asset_id = _import_result(db, task_id)
    qc = VisualTechnicalQCService(db)
    result = qc.run(task_id, asset_id)
    checks = result["checks"]
    assert "decodable" in checks
    assert "hash_match" in checks
    assert "mime_type" in checks
    assert "dimensions" in checks
    db.close()
