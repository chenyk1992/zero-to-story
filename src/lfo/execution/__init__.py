"""LFO Runtime v1 — SQLite store.

New database for the v1 runtime. No migration from older schemas.

Tables:
- packages / package_revisions
- blobs / assets / asset_revisions
- reviews
- runs / run_snapshots
- tasks / task_dependencies
- attempts / task_leases
- artifacts / lineage_edges
- invalidations
- exports
- transition_journal
"""
from __future__ import annotations

import pathlib
import sqlite3
from contextlib import contextmanager

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- ===========================================================================
-- Packages
-- ===========================================================================

CREATE TABLE IF NOT EXISTS packages (
    package_id      TEXT PRIMARY KEY,
    project_title   TEXT NOT NULL,
    locale          TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS package_revisions (
    revision_id     TEXT PRIMARY KEY,
    package_id      TEXT NOT NULL REFERENCES packages(package_id),
    revision        INTEGER NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,
    raw_json        TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (package_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_rev_package ON package_revisions(package_id);
CREATE INDEX IF NOT EXISTS idx_rev_hash ON package_revisions(content_hash);

-- ===========================================================================
-- Blobs (CAS) and assets
-- ===========================================================================

CREATE TABLE IF NOT EXISTS blobs (
    blob_hash       TEXT PRIMARY KEY,
    size            INTEGER NOT NULL,
    blob_path       TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id        TEXT PRIMARY KEY,
    asset_key       TEXT NOT NULL,
    media_type      TEXT NOT NULL
        CHECK (media_type IN ('image', 'video', 'audio', 'subtitle', 'document')),
    provenance      TEXT NOT NULL DEFAULT '{}',
    review_required INTEGER NOT NULL DEFAULT 1,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS asset_revisions (
    asset_revision_id TEXT PRIMARY KEY,
    asset_id        TEXT NOT NULL REFERENCES assets(asset_id),
    blob_hash       TEXT NOT NULL REFERENCES blobs(blob_hash),
    file_hash       TEXT NOT NULL,
    metadata_hash   TEXT,
    probe_result    TEXT NOT NULL DEFAULT '{}',
    source_uri      TEXT,
    original_filename TEXT,
    imported_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ar_asset ON asset_revisions(asset_id);
CREATE INDEX IF NOT EXISTS idx_ar_blob ON asset_revisions(blob_hash);

-- ===========================================================================
-- Reviews
-- ===========================================================================

CREATE TABLE IF NOT EXISTS reviews (
    review_id       TEXT PRIMARY KEY,
    target_type     TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'INVALIDATED')),
    content_hash    TEXT,
    file_hash       TEXT,
    metadata_hash   TEXT,
    bindings        TEXT NOT NULL DEFAULT '{}',
    decided_at      TEXT,
    decided_by      TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_target ON reviews(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);

-- ===========================================================================
-- Runs
-- ===========================================================================

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    package_id      TEXT NOT NULL REFERENCES packages(package_id),
    revision_id     TEXT NOT NULL REFERENCES package_revisions(revision_id),
    status          TEXT NOT NULL DEFAULT 'ACCEPTED',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS run_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    snapshot_hash   TEXT NOT NULL UNIQUE,
    snapshot_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_package ON runs(package_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_run ON run_snapshots(run_id);

-- ===========================================================================
-- Tasks and dependencies
-- ===========================================================================

CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    task_type       TEXT NOT NULL,
    logical_key     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'BLOCKED',
    content_hash    TEXT,
    params_hash     TEXT,
    idempotency_key TEXT UNIQUE,
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    depends_on      TEXT NOT NULL REFERENCES tasks(task_id),
    PRIMARY KEY (task_id, depends_on)
);

CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key);

-- ===========================================================================
-- Attempts and leases
-- ===========================================================================

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id      TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    idempotency_key TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'CREATED',
    provider_job_id TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS task_leases (
    lease_id        TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    worker_id       TEXT NOT NULL,
    acquired_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at      TEXT NOT NULL,
    released        INTEGER NOT NULL DEFAULT 0,
    released_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
CREATE INDEX IF NOT EXISTS idx_leases_task ON task_leases(task_id);
CREATE INDEX IF NOT EXISTS idx_leases_expires ON task_leases(expires_at);

-- ===========================================================================
-- Artifacts and lineage
-- ===========================================================================

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id     TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    attempt_id      TEXT REFERENCES attempts(attempt_id),
    artifact_type   TEXT NOT NULL,
    blob_hash       TEXT REFERENCES blobs(blob_hash),
    file_path       TEXT,
    file_hash       TEXT,
    media_type      TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS lineage_edges (
    edge_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    target_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    relation_type   TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage_edges(source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_lineage_target ON lineage_edges(target_artifact_id);

-- ===========================================================================
-- Invalidations
-- ===========================================================================

CREATE TABLE IF NOT EXISTS invalidations (
    invalidation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    source_task_id  TEXT NOT NULL REFERENCES tasks(task_id),
    target_task_id  TEXT NOT NULL REFERENCES tasks(task_id),
    reason          TEXT NOT NULL,
    scope_json      TEXT NOT NULL DEFAULT '{}',
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_inval_target ON invalidations(target_task_id);
CREATE INDEX IF NOT EXISTS idx_inval_run ON invalidations(run_id);

-- ===========================================================================
-- Exports
-- ===========================================================================

CREATE TABLE IF NOT EXISTS exports (
    export_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    status          TEXT NOT NULL DEFAULT 'PENDING',
    container       TEXT,
    video_encoder   TEXT,
    audio_encoder   TEXT,
    width           INTEGER,
    height          INTEGER,
    fps             INTEGER,
    file_path       TEXT,
    file_hash       TEXT,
    subtitles_path  TEXT,
    manifest_path   TEXT,
    provenance_path TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_exports_run ON exports(run_id);

-- ===========================================================================
-- Transition journal (CAS audit log)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS transition_journal (
    journal_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL,  -- 'run' | 'task' | 'attempt' | 'review' | 'export'
    entity_id       TEXT NOT NULL,
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_entity ON transition_journal(entity_type, entity_id);
"""


class ExecutionStore:
    """SQLite-backed store for the LFO v1 runtime."""

    def __init__(self, db_path: pathlib.Path | str) -> None:
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Get or create the SQLite connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=30,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Create all tables if they don't exist."""
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()

    @contextmanager
    def transaction(self):
        """Context manager for a transaction."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    @property
    def schema_version(self) -> int:
        conn = self.connect()
        row = conn.execute("PRAGMA user_version").fetchone()
        return row[0] if row else 0
