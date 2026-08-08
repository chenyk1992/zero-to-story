"""Tests for AssetBindingService."""
from __future__ import annotations

import os
import sqlite3

import pytest

from lfo.application.asset_service import (
    ApprovedAsset,
    AssetBindingService,
    AssetNotReadyError,
    BindingRevision,
)
from lfo.core.database import SCHEMA_VERSION, Database

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Fresh in-memory database with v4 schema."""
    database = Database()
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def service(db):
    """AssetBindingService backed by a fresh DB."""
    return AssetBindingService(db)


@pytest.fixture
def populated_db(db):
    """DB with a project, task, and asset ready for binding tests."""
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, 'PLANNED')",
        ("task-1", "proj-1", "keyframe"),
    )
    db.execute(
        """INSERT INTO assets
           (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
           VALUES (?, ?, 'image', '/tmp/test.png', 'abc123', 'dep-hash-1')""",
        ("asset-1", "task-1"),
    )
    return db


# ---------------------------------------------------------------------------
# Schema version tests
# ---------------------------------------------------------------------------

def test_fresh_db_has_v10_schema():
    """Fresh DB initialized with init_schema() must be at SCHEMA_VERSION=10."""
    db = Database()
    db.init_schema()
    assert db.schema_version == 10
    assert SCHEMA_VERSION == 10

    tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r[0] for r in tables}
    assert "projects" in table_names
    assert "asset_bindings" in table_names
    assert "asset_reviews" in table_names
    assert "task_materializations" in table_names
    assert "selected_clips" in table_names
    assert "edit_decision_lists" in table_names
    assert "continuity_states" in table_names
    # v10 visual tables
    assert "visual_task_contracts" in table_names
    assert "visual_provider_revisions" in table_names
    assert "visual_generation_profile_revisions" in table_names
    assert "visual_result_manifests" in table_names
    assert "visual_provider_executions" in table_names
    assert "visual_exchange_executions" in table_names
    db.close()


def test_migrated_v3_to_v10_has_new_tables():
    """A v3 database migrated to latest must have the new tables."""
    import pathlib
    import tempfile

    tmp = pathlib.Path(tempfile.mkdtemp())
    db_path = tmp / "migrate_v3_to_v10.lfo.db"

    # Create a v3 database
    db = Database(db_path)
    db.init_schema()
    db.conn.execute("PRAGMA user_version = 3")
    db.close()

    # Reopen and migrate (runs v3→...→v10)
    db2 = Database(db_path)
    db2.migrate()
    assert db2.schema_version == 10

    tables = db2.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r[0] for r in tables}
    assert "projects" in table_names
    assert "asset_bindings" in table_names
    assert "asset_reviews" in table_names
    assert "task_materializations" in table_names
    assert "selected_clips" in table_names
    assert "edit_decision_lists" in table_names
    assert "continuity_states" in table_names
    assert "visual_task_contracts" in table_names
    db2.close()


# ---------------------------------------------------------------------------
# Binding creation tests
# ---------------------------------------------------------------------------

def test_create_binding_returns_revision(service, populated_db):
    """Creating a binding returns a BindingRevision with revision=1."""
    result = service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    assert isinstance(result, BindingRevision)
    assert result.revision == 1
    assert result.validity == "current"
    assert result.asset_id == "asset-1"
    assert result.project_id == "proj-1"
    assert result.entity_type == "task"
    assert result.entity_id == "task-1"
    assert result.asset_role == "output"
    assert result.superseded_by is None
    assert result.binding_id is not None


def test_create_revision_supersedes_old(service, populated_db):
    """Creating a revision marks the old 'current' as 'superseded'."""
    # Create first binding
    v1 = service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )
    assert v1.revision == 1

    # Create second binding (revision)
    v2 = service.create_revision(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )
    assert v2.revision == 2
    assert v2.validity == "current"

    # Old binding should now be superseded
    row = populated_db.fetchone(
        "SELECT validity, superseded_by FROM asset_bindings WHERE binding_id = ?",
        (v1.binding_id,),
    )
    assert row[0] == "superseded"
    assert row[1] == v2.binding_id


def test_get_current_binding_returns_latest(service, populated_db):
    """get_current_binding returns the latest revision."""
    # Create two revisions
    service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )
    v2 = service.create_revision(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    # Get current should return v2
    current = service.get_current_binding(
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )
    assert current is not None
    assert current.binding_id == v2.binding_id
    assert current.revision == 2


def test_unique_constraint_blocks_duplicate_revision(service, populated_db):
    """Same (project, entity, role, revision) must violate UNIQUE constraint."""
    service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    # Manually inserting a duplicate revision should fail
    with pytest.raises(sqlite3.IntegrityError):
        populated_db.execute(
            """INSERT INTO asset_bindings
               (binding_id, asset_id, project_id, entity_type, entity_id,
                asset_role, revision, validity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 'current',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            ("dup-binding", "asset-1", "proj-1", "task", "task-1", "output"),
        )


# ---------------------------------------------------------------------------
# Partial unique index test
# ---------------------------------------------------------------------------

def test_partial_unique_index_only_one_current(service, populated_db):
    """Only one 'current' binding per (project, entity, role) is allowed."""
    service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    # Trying to insert another 'current' for the same key must fail
    with pytest.raises(sqlite3.IntegrityError):
        populated_db.execute(
            """INSERT INTO asset_bindings
               (binding_id, asset_id, project_id, entity_type, entity_id,
                asset_role, revision, validity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 3, 'current',
                       strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
            ("another-current", "asset-1", "proj-1", "task", "task-1", "output"),
        )


# ---------------------------------------------------------------------------
# Approval tests
# ---------------------------------------------------------------------------

def test_approve_asset_creates_review(service, populated_db):
    """Approving an asset creates an asset_reviews record."""
    review_id = service.approve_asset(
        asset_id="asset-1",
        reviewer="user@example.com",
    )
    assert review_id is not None

    row = populated_db.fetchone(
        """SELECT asset_id, manual_review_status, review_source, reviewer
           FROM asset_reviews WHERE review_id = ?""",
        (review_id,),
    )
    assert row[0] == "asset-1"
    assert row[1] == "approved"
    assert row[2] == "manual"
    assert row[3] == "user@example.com"


def test_reject_asset_creates_review(service, populated_db):
    """Rejecting an asset creates an asset_reviews record."""
    review_id = service.reject_asset(
        asset_id="asset-1",
        reviewer="user@example.com",
        reason="Quality too low",
    )
    assert review_id is not None

    row = populated_db.fetchone(
        """SELECT asset_id, manual_review_status, reviewer, rejection_reason
           FROM asset_reviews WHERE review_id = ?""",
        (review_id,),
    )
    assert row[0] == "asset-1"
    assert row[1] == "rejected"
    assert row[2] == "user@example.com"
    assert row[3] == "Quality too low"


def test_is_approved_returns_true_after_approve(service, populated_db):
    """is_approved returns True after approving an asset."""
    assert service.is_approved("asset-1") is False

    service.approve_asset(asset_id="asset-1", reviewer="user@example.com")
    assert service.is_approved("asset-1") is True


def test_is_approved_returns_false_after_reject(service, populated_db):
    """is_approved returns False after rejecting an asset."""
    service.reject_asset(
        asset_id="asset-1",
        reviewer="user@example.com",
        reason="Not good",
    )
    assert service.is_approved("asset-1") is False


# ---------------------------------------------------------------------------
# Cascade / RESTRICT tests
# ---------------------------------------------------------------------------

def test_cascade_delete_project_removes_bindings(service, populated_db):
    """Deleting a project cascades to remove its bindings."""
    service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    # Delete project
    populated_db.execute("DELETE FROM projects WHERE project_id = 'proj-1'")

    # Bindings should be gone
    row = populated_db.fetchone(
        "SELECT COUNT(*) FROM asset_bindings WHERE project_id = 'proj-1'",
    )
    assert row[0] == 0


def test_restrict_delete_asset_with_bindings(service, populated_db):
    """Deleting an asset that has bindings must be blocked by RESTRICT FK."""
    service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    with pytest.raises(sqlite3.IntegrityError):
        populated_db.execute("DELETE FROM assets WHERE asset_id = 'asset-1'")


# ---------------------------------------------------------------------------
# Transaction rollback test
# ---------------------------------------------------------------------------

def test_transaction_rollback_on_revision_failure(populated_db, monkeypatch):
    """If create_revision fails mid-transaction, the whole transaction rolls back.

    We simulate a failure by making db.execute raise on the INSERT step
    (the second execute call inside create_revision).
    """
    service = AssetBindingService(populated_db)

    # Create first binding
    v1 = service.create_binding(
        asset_id="asset-1",
        project_id="proj-1",
        entity_type="task",
        entity_id="task-1",
        asset_role="output",
    )

    # Monkeypatch execute to fail on the INSERT (2nd call in create_revision)
    call_count = 0
    original_execute = populated_db.execute

    def failing_execute(sql, params=()):
        nonlocal call_count
        call_count += 1
        # The INSERT is the 2nd execute in create_revision
        # (1st is fetchone via SELECT, but execute() is called for UPDATE then INSERT)
        if call_count == 2 and "INSERT" in sql:
            raise sqlite3.OperationalError("simulated INSERT failure")
        return original_execute(sql, params)

    monkeypatch.setattr(populated_db, "execute", failing_execute)

    with pytest.raises(sqlite3.OperationalError, match="simulated INSERT failure"):
        service.create_revision(
            asset_id="asset-1",
            project_id="proj-1",
            entity_type="task",
            entity_id="task-1",
            asset_role="output",
        )

    # The transaction should have rolled back — v1 should still be 'current'
    row = populated_db.fetchone(
        "SELECT validity FROM asset_bindings WHERE binding_id = ?",
        (v1.binding_id,),
    )
    assert row[0] == "current", "Transaction did not roll back — v1 was modified"


# ---------------------------------------------------------------------------
# get_current_approved_asset tests
# ---------------------------------------------------------------------------


@pytest.fixture
def approved_asset_db(tmp_path):
    """DB with a project, task, asset, binding, approval, and real file."""
    db = Database()
    db.init_schema()

    # Create project
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    # Create task
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, 'PLANNED')",
        ("task-1", "proj-1", "keyframe"),
    )
    # Create a real temp file
    test_file = str(tmp_path / "test_asset.png")
    with open(test_file, "wb") as f:
        f.write(b"fake image content for testing")

    # Compute hashes
    import hashlib
    file_hash = hashlib.sha256(b"fake image content for testing").hexdigest()
    content_hash = file_hash  # For simplicity, same hash

    # Create asset
    db.execute(
        """INSERT INTO assets
           (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
           VALUES (?, ?, 'image', ?, ?, ?)""",
        ("asset-1", "task-1", test_file, file_hash, content_hash),
    )

    # Create binding
    db.execute(
        """INSERT INTO asset_bindings
           (binding_id, asset_id, project_id, entity_type, entity_id,
            asset_role, revision, validity)
           VALUES (?, ?, ?, ?, ?, ?, 1, 'current')""",
        ("bind-1", "asset-1", "proj-1", "task", "task-1", "output"),
    )

    # Create approval
    db.execute(
        """INSERT INTO asset_reviews
           (review_id, asset_id, dependency_hash, technical_status,
            manual_review_status, review_source, reviewer)
           VALUES (?, ?, ?, 'passed', 'approved', 'manual', 'tester')""",
        ("review-1", "asset-1", content_hash),
    )

    return db, test_file, file_hash


class TestGetCurrentApprovedAsset:
    def test_returns_approved_asset_when_all_gates_pass(self, approved_asset_db):
        db, test_file, file_hash = approved_asset_db
        service = AssetBindingService(db)
        result = service.get_current_approved_asset(
            project_id="proj-1",
            entity_type="task",
            entity_id="task-1",
            asset_role="output",
        )
        assert isinstance(result, ApprovedAsset)
        assert result.asset_id == "asset-1"
        assert result.file_path == test_file
        assert result.file_hash == file_hash
        assert result.manual_review_status == "approved"
        assert result.technical_status == "passed"

    def test_raises_when_no_binding(self, approved_asset_db):
        db, _, _ = approved_asset_db
        service = AssetBindingService(db)
        with pytest.raises(AssetNotReadyError, match="No current binding"):
            service.get_current_approved_asset(
                project_id="proj-1",
                entity_type="task",
                entity_id="nonexistent",
                asset_role="output",
            )

    def test_raises_when_file_missing(self, approved_asset_db, tmp_path):
        db, test_file, _ = approved_asset_db
        # Delete the file
        os.remove(test_file)
        service = AssetBindingService(db)
        with pytest.raises(AssetNotReadyError, match="file missing"):
            service.get_current_approved_asset(
                project_id="proj-1",
                entity_type="task",
                entity_id="task-1",
                asset_role="output",
            )

    def test_raises_when_file_hash_mismatch(self, approved_asset_db, tmp_path):
        db, test_file, _ = approved_asset_db
        # Modify the file
        with open(test_file, "wb") as f:
            f.write(b"different content")
        service = AssetBindingService(db)
        with pytest.raises(AssetNotReadyError, match="file_hash mismatch"):
            service.get_current_approved_asset(
                project_id="proj-1",
                entity_type="task",
                entity_id="task-1",
                asset_role="output",
            )

    def test_raises_when_not_approved(self, approved_asset_db):
        db, _, _ = approved_asset_db
        # Update review to rejected
        db.execute(
            "UPDATE asset_reviews SET manual_review_status = 'rejected' WHERE review_id = ?",
            ("review-1",),
        )
        service = AssetBindingService(db)
        with pytest.raises(AssetNotReadyError, match="manual_review_status"):
            service.get_current_approved_asset(
                project_id="proj-1",
                entity_type="task",
                entity_id="task-1",
                asset_role="output",
            )

    def test_raises_when_content_changed(self, approved_asset_db):
        db, _, _ = approved_asset_db
        # Change content_hash without updating review
        db.execute(
            "UPDATE assets SET content_hash = ? WHERE asset_id = ?",
            ("new-content-hash", "asset-1"),
        )
        service = AssetBindingService(db)
        with pytest.raises(AssetNotReadyError, match="content changed"):
            service.get_current_approved_asset(
                project_id="proj-1",
                entity_type="task",
                entity_id="task-1",
                asset_role="output",
            )
