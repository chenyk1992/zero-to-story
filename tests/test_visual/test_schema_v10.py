"""Tests for schema v10 — visual production tables + attempt_kind."""
from __future__ import annotations

from lfo.core.database import SCHEMA_VERSION, Database

VISUAL_TABLES = (
    "visual_provider_revisions",
    "visual_generation_profile_revisions",
    "visual_task_contracts",
    "visual_result_manifests",
    "visual_provider_executions",
    "visual_exchange_executions",
)


def test_schema_version_is_10():
    assert SCHEMA_VERSION == 10


def test_fresh_has_visual_tables_and_provider_jobs():
    db = Database()
    db.init_schema()
    names = {r[0] for r in db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for t in VISUAL_TABLES:
        assert t in names
    assert "provider_jobs" in names
    db.close()


def test_attempt_kind_default_workflow():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('p1', 'n')")
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) "
        "VALUES ('t1', 'p1', 'video.h3', 'PLANNED')"
    )
    db.execute(
        """INSERT INTO attempts
           (attempt_id, task_id, idempotency_key, workflow_id,
            content_hash, dependency_hash, params_hash)
           VALUES ('a1', 't1', 'k', 'wf', 'c', 'd', 'p')"""
    )
    row = db.fetchone("SELECT attempt_kind FROM attempts WHERE attempt_id='a1'")
    assert row[0] == "workflow"
    db.close()


def test_visual_managed_attempt_requires_null_workflow_id():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('p1', 'n')")
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) "
        "VALUES ('t1', 'p1', 'visual.generate', 'PLANNED')"
    )
    try:
        db.execute(
            """INSERT INTO attempts
               (attempt_id, task_id, idempotency_key, workflow_id, attempt_kind,
                content_hash, dependency_hash, params_hash)
               VALUES ('a2', 't1', 'k2', 'wf', 'visual_managed', 'c', 'd', 'p')"""
        )
        raised = False
    except Exception:
        raised = True
    assert raised
    db.close()
