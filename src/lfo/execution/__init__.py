"""LFO Runtime v1 — SQLite store.

Schema v2 persists project identity and the resolved artifact layout. Existing
database rows may remain as audit history, but their deleted legacy file paths
are not used for new execution or export.

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

import json
import pathlib
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Any

SCHEMA_VERSION = 2

SCHEMA_SQL = """
-- ===========================================================================
-- Packages
-- ===========================================================================

CREATE TABLE IF NOT EXISTS packages (
    package_id      TEXT PRIMARY KEY,
    project_id      TEXT,
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
    layout_json     TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'ACCEPTED',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS run_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    snapshot_hash   TEXT NOT NULL,
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
    metadata        TEXT NOT NULL DEFAULT '{}',
    retry_count     INTEGER NOT NULL DEFAULT 0,
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
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Get or create the SQLite connection."""
        if self._conn is None:
            # Opening SQLite creates the database file.  Keep that write lazy
            # so constructing a runtime (or running validate/plan) remains
            # read-only until an operation explicitly needs durable state.
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        # v1 was initially published with the table but without task metadata.
        # Keep initialisation idempotent for databases created by that build.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "metadata" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
        if "retry_count" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
        package_columns = {row[1] for row in conn.execute("PRAGMA table_info(packages)")}
        if "project_id" not in package_columns:
            conn.execute("ALTER TABLE packages ADD COLUMN project_id TEXT")
        run_columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        if "layout_json" not in run_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN layout_json TEXT NOT NULL DEFAULT '{}'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_packages_project ON packages(project_id)")
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

    # The methods below are intentionally small, explicit persistence primitives.
    # The application facade owns orchestration; this store owns atomic database
    # changes and the corresponding audit trail.

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, object] | None:
        return dict(row) if row is not None else None

    def create_package_revision(
        self, *, package_id: str, project_id: str = "", project_title: str, revision: int,
        content_hash: str, raw_json: str, locale: str | None = None,
        revision_id: str | None = None,
    ) -> str:
        """Persist a package revision, returning its stable internal id.

        Repeating an identical package is idempotent; conflicting package ids
        or revision numbers are left to SQLite's uniqueness constraints.
        """
        self.init_schema()
        revision_id = revision_id or f"pkg-rev-{uuid.uuid4().hex}"
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT revision_id FROM package_revisions WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if existing is not None:
                return str(existing["revision_id"])
            conn.execute(
                "INSERT OR IGNORE INTO packages (package_id, project_id, project_title, locale) VALUES (?, ?, ?, ?)",
                (package_id, project_id, project_title, locale),
            )
            stored = conn.execute(
                "SELECT project_id FROM packages WHERE package_id = ?", (package_id,)
            ).fetchone()
            if stored is not None and stored["project_id"] not in (None, project_id):
                raise ValueError(
                    f"Package {package_id!r} is already bound to project {stored['project_id']!r}"
                )
            if stored is not None and stored["project_id"] is None:
                conn.execute(
                    "UPDATE packages SET project_id=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE package_id=?",
                    (project_id, package_id),
                )
            conn.execute(
                """INSERT INTO package_revisions
                   (revision_id, package_id, revision, content_hash, raw_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (revision_id, package_id, revision, content_hash, raw_json),
            )
        return revision_id

    def get_package_revision(self, revision_id: str) -> dict[str, object] | None:
        return self._row(self.connect().execute(
            "SELECT * FROM package_revisions WHERE revision_id = ?", (revision_id,)
        ).fetchone())

    def record_asset_revision(
        self,
        *,
        asset_id: str,
        asset_key: str,
        media_type: str,
        blob_hash: str,
        blob_size: int,
        blob_path: str,
        file_hash: str,
        probe_result: dict[str, object],
        source_uri: str,
        original_filename: str,
        provenance: dict[str, object],
        review_required: bool,
        metadata: dict[str, object] | None = None,
        asset_revision_id: str | None = None,
    ) -> str:
        """Persist one imported CAS blob and its logical asset revision idempotently."""
        asset_revision_id = asset_revision_id or f"asset-rev-{uuid.uuid4().hex}"
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blobs (blob_hash, size, blob_path) VALUES (?, ?, ?)",
                (blob_hash, blob_size, blob_path),
            )
            conn.execute(
                """INSERT OR IGNORE INTO assets
                   (asset_id, asset_key, media_type, provenance, review_required, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    asset_id,
                    asset_key,
                    media_type,
                    self._json(provenance),
                    int(review_required),
                    self._json(metadata or {}),
                ),
            )
            existing = conn.execute(
                "SELECT asset_revision_id FROM asset_revisions WHERE asset_id=? AND file_hash=?",
                (asset_id, file_hash),
            ).fetchone()
            if existing is not None:
                return str(existing["asset_revision_id"])
            conn.execute(
                """INSERT INTO asset_revisions
                   (asset_revision_id, asset_id, blob_hash, file_hash, probe_result,
                    source_uri, original_filename)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset_revision_id,
                    asset_id,
                    blob_hash,
                    file_hash,
                    self._json(probe_result),
                    source_uri,
                    original_filename,
                ),
            )
        return asset_revision_id

    def create_run(
        self, *, run_id: str, package_id: str, revision_id: str,
        layout_json: str = "{}", status: str = "ACCEPTED",
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, package_id, revision_id, layout_json, status) VALUES (?, ?, ?, ?, ?)",
                (run_id, package_id, revision_id, layout_json, status),
            )
            self._journal(conn, "run", run_id, None, status, "run created")

    def get_run(self, run_id: str) -> dict[str, object] | None:
        return self._row(self.connect().execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())

    def transition_run(self, run_id: str, from_state: str, to_state: str,
                       reason: str | None = None) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE runs SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE run_id = ? AND status = ?""", (to_state, run_id, from_state),
            )
            if cursor.rowcount != 1:
                return False
            self._journal(conn, "run", run_id, from_state, to_state, reason)
            return True

    def create_snapshot(self, *, snapshot_id: str, run_id: str,
                        snapshot_hash: str, snapshot_json: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO run_snapshots (snapshot_id, run_id, snapshot_hash, snapshot_json) VALUES (?, ?, ?, ?)",
                (snapshot_id, run_id, snapshot_hash, snapshot_json),
            )

    def persist_tasks(self, run_id: str, tasks: list[Any]) -> None:
        """Atomically persist a validated TaskGraph's nodes and dependencies."""
        with self.transaction() as conn:
            for task in tasks:
                conn.execute(
                    """INSERT INTO tasks (task_id, run_id, task_type, logical_key, status, metadata)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (task.task_id, run_id, task.task_type, task.logical_key,
                     "BLOCKED" if task.dependencies else "READY", self._json(task.metadata)),
                )
            for task in tasks:
                for dependency in task.dependencies:
                    conn.execute(
                        "INSERT INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
                        (task.task_id, dependency),
                    )

    def get_task(self, task_id: str) -> dict[str, object] | None:
        return self._row(self.connect().execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone())

    def update_task_metadata(self, task_id: str, metadata: dict[str, object]) -> bool:
        """Persist fully materialized task metadata without changing its state."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE tasks SET metadata=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE task_id=?""", (self._json(metadata), task_id),
            )
            return cursor.rowcount == 1

    def update_task_retry_count(self, task_id: str, retry_count: int) -> bool:
        """Persist the attempt budget consumed by one task.

        Retry count is kept outside the opaque metadata column because it is
        part of scheduler state and must survive a process restart.
        """
        if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
            raise ValueError("retry_count must be an integer >= 0")
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE tasks SET retry_count=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE task_id=?""",
                (retry_count, task_id),
            )
            return cursor.rowcount == 1

    def list_tasks(self, run_id: str) -> list[dict[str, object]]:
        rows = self.connect().execute(
            "SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at, task_id", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def list_attempts(self, run_id: str) -> list[dict[str, object]]:
        rows = self.connect().execute(
            """SELECT a.* FROM attempts a JOIN tasks t ON t.task_id=a.task_id
               WHERE t.run_id=? ORDER BY a.created_at, a.attempt_id""",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_artifacts(self, run_id: str) -> list[dict[str, object]]:
        rows = self.connect().execute(
            """SELECT a.* FROM artifacts a JOIN tasks t ON t.task_id=a.task_id
               WHERE t.run_id=? ORDER BY a.created_at, a.artifact_id""",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_reviews(self, *, target_id: str | None = None) -> list[dict[str, object]]:
        if target_id is None:
            rows = self.connect().execute("SELECT * FROM reviews ORDER BY created_at").fetchall()
        else:
            rows = self.connect().execute(
                "SELECT * FROM reviews WHERE target_id=? ORDER BY created_at", (target_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def transition_task(self, task_id: str, from_state: str, to_state: str,
                        reason: str | None = None, error: str | None = None) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE tasks SET status = ?, error = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE task_id = ? AND status = ?""",
                (to_state, error, task_id, from_state),
            )
            if cursor.rowcount != 1:
                return False
            self._journal(conn, "task", task_id, from_state, to_state, reason)
            return True

    def advance_ready_tasks(self, run_id: str) -> list[str]:
        """Advance only BLOCKED tasks whose *every* dependency succeeded."""
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT t.task_id FROM tasks t
                   WHERE t.run_id = ? AND t.status = 'BLOCKED'
                   AND NOT EXISTS (
                       SELECT 1 FROM task_dependencies d
                       JOIN tasks dep ON dep.task_id = d.depends_on
                       WHERE d.task_id = t.task_id AND dep.status != 'SUCCEEDED'
                   )""", (run_id,),
            ).fetchall()
            advanced: list[str] = []
            for row in rows:
                task_id = str(row["task_id"])
                cursor = conn.execute(
                    "UPDATE tasks SET status='READY', updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE task_id=? AND status='BLOCKED'",
                    (task_id,),
                )
                if cursor.rowcount == 1:
                    self._journal(conn, "task", task_id, "BLOCKED", "READY", "dependencies satisfied")
                    advanced.append(task_id)
            return advanced

    def create_attempt(self, *, attempt_id: str, task_id: str,
                       idempotency_key: str, status: str = "CREATED") -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO attempts (attempt_id, task_id, idempotency_key, status) VALUES (?, ?, ?, ?)",
                (attempt_id, task_id, idempotency_key, status),
            )
            self._journal(conn, "attempt", attempt_id, None, status, "attempt created")

    def transition_attempt(self, attempt_id: str, from_state: str, to_state: str,
                           reason: str | None = None, error: str | None = None,
                           provider_job_id: str | None = None) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE attempts SET status=?, error=?, provider_job_id=COALESCE(?, provider_job_id),
                   updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE attempt_id=? AND status=?""",
                (to_state, error, provider_job_id, attempt_id, from_state),
            )
            if cursor.rowcount != 1:
                return False
            self._journal(conn, "attempt", attempt_id, from_state, to_state, reason)
            return True

    def acquire_task_lease(self, *, task_id: str, worker_id: str, expires_at: str,
                           lease_id: str | None = None) -> str | None:
        """CAS READY→RUNNING and acquire one active lease in one transaction."""
        lease_id = lease_id or f"lease-{uuid.uuid4().hex}"
        with self.transaction() as conn:
            active = conn.execute(
                "SELECT 1 FROM task_leases WHERE task_id=? AND released=0 AND expires_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                (task_id,),
            ).fetchone()
            if active is not None:
                return None
            cursor = conn.execute("UPDATE tasks SET status='RUNNING' WHERE task_id=? AND status='READY'", (task_id,))
            if cursor.rowcount != 1:
                return None
            conn.execute(
                "INSERT INTO task_leases (lease_id, task_id, worker_id, expires_at) VALUES (?, ?, ?, ?)",
                (lease_id, task_id, worker_id, expires_at),
            )
            self._journal(conn, "task", task_id, "READY", "RUNNING", "lease acquired")
            return lease_id

    def release_task_lease(self, lease_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE task_leases SET released=1, released_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE lease_id=? AND released=0""", (lease_id,),
            )
            return cursor.rowcount == 1

    def recover_interrupted_tasks(self, run_id: str) -> list[str]:
        """Recover RUNNING tasks that no longer have a live worker lease.

        A live lease protects a task owned by another process.  Once the lease
        is absent or expired, the task is safe to retry after an interrupted
        local process, and any non-terminal attempt is closed for auditability.
        """
        recovered: list[str] = []
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT task_id FROM tasks WHERE run_id=? AND status='RUNNING'",
                (run_id,),
            ).fetchall()
            for row in rows:
                task_id = str(row["task_id"])
                live_lease = conn.execute(
                    """SELECT 1 FROM task_leases
                       WHERE task_id=? AND released=0
                         AND expires_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       LIMIT 1""",
                    (task_id,),
                ).fetchone()
                if live_lease is not None:
                    continue

                reason = "recovered interrupted task without a live worker lease"
                attempt = conn.execute(
                    """SELECT attempt_id, status FROM attempts
                       WHERE task_id=? ORDER BY created_at DESC LIMIT 1""",
                    (task_id,),
                ).fetchone()
                if attempt is not None and attempt["status"] not in {"SUCCEEDED", "FAILED"}:
                    conn.execute(
                        """UPDATE attempts SET status='FAILED', error=?,
                           updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                           WHERE attempt_id=?""",
                        (reason, attempt["attempt_id"]),
                    )
                    self._journal(
                        conn, "attempt", str(attempt["attempt_id"]),
                        str(attempt["status"]), "FAILED", reason,
                    )
                cursor = conn.execute(
                    """UPDATE tasks SET status='FAILED_RETRYABLE', error=?,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       WHERE task_id=? AND status='RUNNING'""",
                    (reason, task_id),
                )
                if cursor.rowcount != 1:
                    continue
                self._journal(conn, "task", task_id, "RUNNING", "FAILED_RETRYABLE", reason)
                conn.execute(
                    """UPDATE task_leases SET released=1,
                       released_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       WHERE task_id=? AND released=0""",
                    (task_id,),
                )
                recovered.append(task_id)
        return recovered

    def record_artifact(self, *, artifact_id: str, task_id: str, artifact_type: str,
                        attempt_id: str | None = None, file_path: str | None = None,
                        file_hash: str | None = None, media_type: str | None = None,
                        metadata: dict[str, object] | None = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO artifacts (artifact_id, task_id, attempt_id, artifact_type, file_path, file_hash, media_type, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (artifact_id, task_id, attempt_id, artifact_type, file_path, file_hash,
                 media_type, self._json(metadata or {})),
            )

    def create_review(self, *, review_id: str, target_type: str, target_id: str,
                      content_hash: str | None = None, file_hash: str | None = None,
                      metadata_hash: str | None = None, bindings: dict[str, object] | None = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO reviews (review_id, target_type, target_id, content_hash, file_hash, metadata_hash, bindings)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (review_id, target_type, target_id, content_hash, file_hash, metadata_hash,
                 self._json(bindings or {})),
            )
            self._journal(conn, "review", review_id, None, "PENDING", "review created")

    def transition_review(self, review_id: str, from_state: str, to_state: str,
                          reason: str | None = None, decided_by: str | None = None) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE reviews SET status=?, decided_by=?, decided_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), notes=?
                   WHERE review_id=? AND status=?""", (to_state, decided_by, reason, review_id, from_state),
            )
            if cursor.rowcount != 1:
                return False
            self._journal(conn, "review", review_id, from_state, to_state, reason)
            return True

    def record_invalidation(self, *, run_id: str, source_task_id: str,
                            target_task_id: str, reason: str,
                            scope: dict[str, object] | None = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO invalidations (run_id, source_task_id, target_task_id, reason, scope_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, source_task_id, target_task_id, reason, self._json(scope or {})),
            )

    def create_export(
        self,
        *,
        export_id: str,
        run_id: str,
        status: str,
        file_path: str | None = None,
        file_hash: str | None = None,
        manifest_path: str | None = None,
        subtitles_path: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO exports
                   (export_id, run_id, status, file_path, file_hash, manifest_path,
                    subtitles_path, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    export_id,
                    run_id,
                    status,
                    file_path,
                    file_hash,
                    manifest_path,
                    subtitles_path,
                    error,
                ),
            )
            self._journal(conn, "export", export_id, None, status, error)

    def latest_export(self, run_id: str) -> dict[str, object] | None:
        return self._row(
            self.connect().execute(
                "SELECT * FROM exports WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        )

    @staticmethod
    def _journal(conn: sqlite3.Connection, entity_type: str, entity_id: str,
                 from_state: str | None, to_state: str, reason: str | None) -> None:
        conn.execute(
            """INSERT INTO transition_journal (entity_type, entity_id, from_state, to_state, reason)
               VALUES (?, ?, ?, ?, ?)""", (entity_type, entity_id, from_state, to_state, reason),
        )
