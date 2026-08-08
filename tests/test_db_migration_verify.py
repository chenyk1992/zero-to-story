"""Quick verification script for DB migration."""
import pathlib
import sqlite3
import tempfile

import pytest

from lfo.core.database import SCHEMA_VERSION, Database


def test_fresh_db():
    db = Database()
    db.init_schema()
    assert db.schema_version == SCHEMA_VERSION
    assert SCHEMA_VERSION == 10

    tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r[0] for r in tables}
    assert "environment_snapshots" in table_names
    assert "preflights" in table_names
    assert "task_materializations" in table_names
    assert "selected_clips" in table_names

    cols = db.fetchall("PRAGMA table_info(attempts)")
    col_names = {r[1] for r in cols}
    assert "machine_id" in col_names
    assert "environment_snapshot_id" in col_names
    assert "execution_environment_hash" in col_names

    db.close()
    print("Fresh DB: OK")


def test_migration_v2_to_v3():
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_path = tmp / "migrate_test.lfo.db"

    # Create a v2 database
    db = Database(db_path)
    db.init_schema()
    db.conn.execute("PRAGMA user_version = 2")
    db.close()

    # Reopen and migrate
    db2 = Database(db_path)
    db2.migrate()
    assert db2.schema_version == SCHEMA_VERSION

    tables = db2.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r[0] for r in tables}
    assert "environment_snapshots" in table_names
    assert "preflights" in table_names

    cols = db2.fetchall("PRAGMA table_info(attempts)")
    col_names = {r[1] for r in cols}
    assert "machine_id" in col_names
    assert "environment_snapshot_id" in col_names

    db2.close()
    print("Migration v2->v3: OK")


def test_migration_v9_to_v10():
    """v9 → v10: visual tables + attempt_kind column + assets CHECK."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_path = tmp / "migrate_v10_test.lfo.db"

    # Create a v9 database
    db = Database(db_path)
    db.init_schema()
    db.conn.execute("PRAGMA user_version = 9")
    db.close()

    # Reopen and migrate
    db2 = Database(db_path)
    db2.migrate()
    assert db2.schema_version == SCHEMA_VERSION
    assert SCHEMA_VERSION == 10

    tables = db2.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r[0] for r in tables}
    for visual_tbl in (
        "visual_provider_revisions",
        "visual_generation_profile_revisions",
        "visual_task_contracts",
        "visual_result_manifests",
        "visual_provider_executions",
        "visual_exchange_executions",
    ):
        assert visual_tbl in table_names
    # provider_jobs must be retained
    assert "provider_jobs" in table_names

    # attempt_kind column exists with default 'workflow'
    cols = db2.fetchall("PRAGMA table_info(attempts)")
    col_names = {r[1] for r in cols}
    assert "attempt_kind" in col_names

    db2.close()
    print("Migration v9->v10: OK")


# ---------------------------------------------------------------------------
# Environment-column equivalence tests (Phase 4.6A)
# ---------------------------------------------------------------------------

EXPECTED_ENV_COLUMNS = {"machine_id", "environment_snapshot_id", "execution_environment_hash"}


def test_fresh_v3_attempts_has_environment_columns():
    """Fresh DB created by init_schema() must include the three v3 env columns."""
    db = Database()
    db.init_schema()
    cols = db.fetchall("PRAGMA table_info(attempts)")
    col_names = {r[1] for r in cols}
    assert EXPECTED_ENV_COLUMNS.issubset(col_names), (
        f"Missing env columns: {EXPECTED_ENV_COLUMNS - col_names}"
    )
    db.close()


def test_migrated_v3_attempts_has_environment_columns():
    """Migrated DB (v2 → v3) must also include the three v3 env columns."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_path = tmp / "migrate_env_test.lfo.db"

    db = Database(db_path)
    db.init_schema()
    db.conn.execute("PRAGMA user_version = 2")
    db.close()

    db2 = Database(db_path)
    db2.migrate()
    assert db2.schema_version == SCHEMA_VERSION

    cols = db2.fetchall("PRAGMA table_info(attempts)")
    col_names = {r[1] for r in cols}
    assert EXPECTED_ENV_COLUMNS.issubset(col_names), (
        f"Missing env columns after migration: {EXPECTED_ENV_COLUMNS - col_names}"
    )
    db2.close()


def test_fresh_and_migrated_schema_are_equivalent():
    """Fresh DB and Migrated DB must produce identical schema metadata."""

    # --- Fresh DB ---
    db_fresh = Database()
    db_fresh.init_schema()
    fresh_version = db_fresh.schema_version
    fresh_tables = _get_table_names(db_fresh)
    fresh_meta = {t: _get_table_meta(db_fresh, t) for t in fresh_tables}
    db_fresh.close()

    # --- Migrated DB (v2 → v3) ---
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_path = tmp / "equiv_test.lfo.db"
    db_old = Database(db_path)
    db_old.init_schema()
    db_old.conn.execute("PRAGMA user_version = 2")
    db_old.close()

    db_new = Database(db_path)
    db_new.migrate()
    migrated_version = db_new.schema_version
    migrated_tables = _get_table_names(db_new)
    migrated_meta = {t: _get_table_meta(db_new, t) for t in migrated_tables}
    db_new.close()

    # Same user_version
    assert fresh_version == migrated_version == SCHEMA_VERSION

    # Same table set
    assert fresh_tables == migrated_tables, (
        f"Table mismatch: fresh={fresh_tables}, migrated={migrated_tables}"
    )

    # Same columns, types, notnull, defaults for every table
    for table in fresh_tables:
        fresh_cols = fresh_meta[table]["columns"]
        migrated_cols = migrated_meta[table]["columns"]
        assert fresh_cols == migrated_cols, (
            f"Column mismatch in '{table}':\n  fresh={fresh_cols}\n  migrated={migrated_cols}"
        )

    # Same indexes
    for table in fresh_tables:
        fresh_idxs = fresh_meta[table]["indexes"]
        migrated_idxs = migrated_meta[table]["indexes"]
        assert fresh_idxs == migrated_idxs, (
            f"Index mismatch in '{table}':\n  fresh={fresh_idxs}\n  migrated={migrated_idxs}"
        )


def test_init_schema_sets_user_version_only_after_success():
    """init_schema() must not set user_version if SCHEMA_SQL fails.

    Uses a Database subclass whose _connect() returns a real in-memory
    connection wrapped so executescript() raises on the first call,
    simulating a DDL failure before user_version is set.
    """
    class _FailingConnection:
        """Wrapper around a real sqlite3 connection that fails on executescript."""

        def __init__(self, real):
            self._real = real

        def executescript(self, sql):
            raise sqlite3.OperationalError("simulated DDL failure")

        def __getattr__(self, name):
            return getattr(self._real, name)

    class FailingDb(Database):
        def _connect(self):
            real = super()._connect()
            return _FailingConnection(real)

    db = FailingDb()
    assert db.schema_version == 0

    with pytest.raises(sqlite3.OperationalError):
        db.init_schema()

    # user_version must still be 0 — the pragma assignment must not have run
    assert db.schema_version == 0, (
        f"user_version should be 0 after failed init, got {db.schema_version}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_table_names(db: Database) -> set[str]:
    """Return set of user-defined table names."""
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {r[0] for r in rows}


def _get_table_meta(db: Database, table: str) -> dict:
    """Return column and index metadata for a given table."""
    # PRAGMA table_info returns: (cid, name, type, notno, dflt_value, pk)
    col_rows = db.fetchall(f"PRAGMA table_info({table})")
    columns = [
        (name, ctype, notnull, dflt, pk)
        for cid, name, ctype, notnull, dflt, pk in col_rows
    ]

    # PRAGMA index_list returns: (seq, name, unique, origin, partial)
    idx_rows = db.fetchall(f"PRAGMA index_list({table})")
    indexes = sorted(idx_name for seq, idx_name, unique, origin, partial in idx_rows)

    return {"columns": columns, "indexes": indexes}


if __name__ == "__main__":
    test_fresh_db()
    test_migration_v2_to_v3()
    test_fresh_v3_attempts_has_environment_columns()
    test_migrated_v3_attempts_has_environment_columns()
    test_fresh_and_migrated_schema_are_equivalent()
    test_init_schema_sets_user_version_only_after_success()
    print("All DB migration checks passed!")
