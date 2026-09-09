"""Tests for the LFO v1 ExecutionStore (SQLite schema and basic operations)."""
from __future__ import annotations

import pathlib
import sqlite3

import pytest

from lfo.execution import ExecutionStore


@pytest.fixture
def store(tmp_path: pathlib.Path) -> ExecutionStore:
    """Create an ExecutionStore with a temp DB."""
    db_path = tmp_path / "test.db"
    s = ExecutionStore(db_path)
    s.init_schema()
    return s


class TestSchemaInit:
    def test_creates_all_tables(self, store: ExecutionStore) -> None:
        conn = store.connect()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "packages",
            "package_revisions",
            "blobs",
            "assets",
            "asset_revisions",
            "reviews",
            "runs",
            "run_snapshots",
            "tasks",
            "task_dependencies",
            "attempts",
            "task_leases",
            "artifacts",
            "lineage_edges",
            "invalidations",
            "exports",
            "transition_journal",
        }
        assert expected.issubset(tables)

    def test_schema_version(self, store: ExecutionStore) -> None:
        assert store.schema_version == 2

    def test_wal_mode(self, store: ExecutionStore) -> None:
        conn = store.connect()
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_foreign_keys_on(self, store: ExecutionStore) -> None:
        conn = store.connect()
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


class TestConnection:
    def test_lazy_connect(self, tmp_path: pathlib.Path) -> None:
        s = ExecutionStore(tmp_path / "lazy.db")
        assert s._conn is None
        conn = s.connect()
        assert conn is not None
        assert s._conn is conn

    def test_reuses_connection(self, store: ExecutionStore) -> None:
        conn1 = store.connect()
        conn2 = store.connect()
        assert conn1 is conn2

    def test_close(self, store: ExecutionStore) -> None:
        store.connect()
        store.close()
        assert store._conn is None


class TestTransaction:
    def test_commits_on_success(self, store: ExecutionStore) -> None:
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
                ("pkg-1", "Test"),
            )
        # Verify commit
        conn = store.connect()
        row = conn.execute(
            "SELECT project_title FROM packages WHERE package_id = ?",
            ("pkg-1",),
        ).fetchone()
        assert row[0] == "Test"

    def test_rollback_on_failure(self, store: ExecutionStore) -> None:
        with pytest.raises(RuntimeError):
            with store.transaction() as conn:
                conn.execute(
                    "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
                    ("pkg-fail", "Should Not Exist"),
                )
                raise RuntimeError("intentional failure")
        # Verify rollback
        conn = store.connect()
        row = conn.execute(
            "SELECT project_title FROM packages WHERE package_id = ?",
            ("pkg-fail",),
        ).fetchone()
        assert row is None


class TestPackages:
    def test_insert_and_read(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            "INSERT INTO packages (package_id, project_title, locale) VALUES (?, ?, ?)",
            ("pkg-1", "Demo", "zh-CN"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT project_title, locale FROM packages WHERE package_id = ?",
            ("pkg-1",),
        ).fetchone()
        assert row[0] == "Demo"
        assert row[1] == "zh-CN"


class TestPackageRevisions:
    def test_insert_revision(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
            ("pkg-1", "Demo"),
        )
        conn.execute(
            """INSERT INTO package_revisions
               (revision_id, package_id, revision, content_hash, raw_json)
               VALUES (?, ?, ?, ?, ?)""",
            ("rev-1", "pkg-1", 1, "abc123", "{}"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT revision, content_hash FROM package_revisions WHERE revision_id = ?",
            ("rev-1",),
        ).fetchone()
        assert row[0] == 1
        assert row[1] == "abc123"

    def test_unique_content_hash(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
            ("pkg-1", "Demo"),
        )
        conn.commit()

        conn.execute(
            """INSERT INTO package_revisions
               (revision_id, package_id, revision, content_hash, raw_json)
               VALUES (?, ?, ?, ?, ?)""",
            ("rev-1", "pkg-1", 1, "samehash", "{}"),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO package_revisions
                   (revision_id, package_id, revision, content_hash, raw_json)
                   VALUES (?, ?, ?, ?, ?)""",
                ("rev-2", "pkg-1", 2, "samehash", "{}"),
            )
        conn.rollback()


class TestBlobsAndAssets:
    def test_insert_blob(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            "INSERT INTO blobs (blob_hash, size, blob_path) VALUES (?, ?, ?)",
            ("deadbeef", 1024, "/cas/sha256/de/deadbeef/file.png"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT size FROM blobs WHERE blob_hash = ?", ("deadbeef",)
        ).fetchone()
        assert row[0] == 1024

    def test_insert_asset_with_revision(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            "INSERT INTO blobs (blob_hash, size, blob_path) VALUES (?, ?, ?)",
            ("hash1", 2048, "/cas/path/file.png"),
        )
        conn.execute(
            "INSERT INTO assets (asset_id, asset_key, media_type) VALUES (?, ?, ?)",
            ("asset-1", "hero.png", "image"),
        )
        conn.execute(
            """INSERT INTO asset_revisions
               (asset_revision_id, asset_id, blob_hash, file_hash, source_uri)
               VALUES (?, ?, ?, ?, ?)""",
            ("ar-1", "asset-1", "hash1", "filehash1", "assets/hero.png"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT media_type FROM assets WHERE asset_key = ?", ("hero.png",)
        ).fetchone()
        assert row[0] == "image"


class TestTasksAndDependencies:
    def test_insert_task(self, store: ExecutionStore) -> None:
        conn = store.connect()
        # Need a run first
        conn.execute(
            "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
            ("pkg-1", "Demo"),
        )
        conn.execute(
            """INSERT INTO package_revisions
               (revision_id, package_id, revision, content_hash, raw_json)
               VALUES (?, ?, ?, ?, ?)""",
            ("rev-1", "pkg-1", 1, "hash", "{}"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, package_id, revision_id) VALUES (?, ?, ?)",
            ("run-1", "pkg-1", "rev-1"),
        )
        conn.execute(
            """INSERT INTO tasks
               (task_id, run_id, task_type, logical_key, status)
               VALUES (?, ?, ?, ?, ?)""",
            ("task-1", "run-1", "video.generate", "clip-001", "BLOCKED"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT task_type, status FROM tasks WHERE task_id = ?", ("task-1",)
        ).fetchone()
        assert row[0] == "video.generate"
        assert row[1] == "BLOCKED"

    def test_task_dependency(self, store: ExecutionStore) -> None:
        conn = store.connect()
        # Setup: package, revision, run, two tasks
        conn.execute(
            "INSERT INTO packages (package_id, project_title) VALUES (?, ?)",
            ("pkg-1", "Demo"),
        )
        conn.execute(
            """INSERT INTO package_revisions
               (revision_id, package_id, revision, content_hash, raw_json)
               VALUES (?, ?, ?, ?, ?)""",
            ("rev-1", "pkg-1", 1, "hash", "{}"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, package_id, revision_id) VALUES (?, ?, ?)",
            ("run-1", "pkg-1", "rev-1"),
        )
        conn.execute(
            """INSERT INTO tasks (task_id, run_id, task_type, logical_key)
               VALUES (?, ?, ?, ?)""",
            ("task-1", "run-1", "video.generate", "clip-001"),
        )
        conn.execute(
            """INSERT INTO tasks (task_id, run_id, task_type, logical_key)
               VALUES (?, ?, ?, ?)""",
            ("task-2", "run-1", "timeline.assemble", "timeline"),
        )
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
            ("task-2", "task-1"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT depends_on FROM task_dependencies WHERE task_id = ?",
            ("task-2",),
        ).fetchone()
        assert row[0] == "task-1"

class TestTransitionJournal:
    def test_insert_journal_entry(self, store: ExecutionStore) -> None:
        conn = store.connect()
        conn.execute(
            """INSERT INTO transition_journal
               (entity_type, entity_id, from_state, to_state, reason)
               VALUES (?, ?, ?, ?, ?)""",
            ("task", "task-1", "BLOCKED", "READY", "dependencies met"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT from_state, to_state FROM transition_journal WHERE entity_id = ?",
            ("task-1",),
        ).fetchone()
        assert row[0] == "BLOCKED"
        assert row[1] == "READY"


class TestForeignKeyConstraints:
    def test_cascade_violation(self, store: ExecutionStore) -> None:
        conn = store.connect()
        # Inserting a task without a run should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO tasks (task_id, run_id, task_type, logical_key)
                   VALUES (?, ?, ?, ?)""",
                ("orphan-task", "nonexistent-run", "video.generate", "clip"),
            )
        conn.rollback()


class TestRuntimePersistencePrimitives:
    def test_cas_task_transition_and_dependency_advancement(self, store: ExecutionStore) -> None:
        revision_id = store.create_package_revision(
            package_id="pkg", project_title="Demo", revision=1,
            content_hash="package-hash", raw_json="{}",
        )
        store.create_run(run_id="run", package_id="pkg", revision_id=revision_id)

        class Task:
            def __init__(self, task_id: str, dependencies: list[str]) -> None:
                self.task_id = task_id
                self.task_type = "video.generate"
                self.logical_key = task_id
                self.dependencies = dependencies
                self.metadata = {}

        store.persist_tasks("run", [Task("first", []), Task("second", ["first"])])
        first_task = store.get_task("first")
        assert first_task is not None and first_task["status"] == "READY"
        assert store.transition_task("first", "READY", "RUNNING")
        assert store.transition_task("first", "RUNNING", "SUCCEEDED")
        assert store.advance_ready_tasks("run") == ["second"]
        assert not store.transition_task("second", "BLOCKED", "RUNNING")

    def test_lease_is_compare_and_set(self, store: ExecutionStore) -> None:
        revision_id = store.create_package_revision(
            package_id="pkg", project_title="Demo", revision=1,
            content_hash="package-hash", raw_json="{}",
        )
        store.create_run(run_id="run", package_id="pkg", revision_id=revision_id)

        class Task:
            def __init__(self) -> None:
                self.task_id = "task"
                self.task_type = "video.generate"
                self.logical_key = "task"
                self.dependencies: list[str] = []
                self.metadata: dict[str, object] = {}

        store.persist_tasks("run", [Task()])
        assert store.acquire_task_lease(task_id="task", worker_id="one", expires_at="2999-01-01T00:00:00Z")
        assert store.acquire_task_lease(task_id="task", worker_id="two", expires_at="2999-01-01T00:00:00Z") is None
