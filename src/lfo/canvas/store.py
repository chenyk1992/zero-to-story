"""SQLite persistence for canvas drafts, run snapshots and run hand-off data.

The store is deliberately small.  A confirmed run keeps the exact snapshot
that was confirmed, while the extra columns on ``node_runs`` record execution
progress, local attention and (when requested) production review.  Run events
are written in the same transaction as the mutation which produced them, so a
consumer can resume from a durable cursor without creating a second task
database.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .graph import (
    GENERATION_NODE_TYPES,
    CanvasError,
    GraphValidationError,
    empty_graph,
    validate_graph,
)

__all__ = [
    "CanvasError",
    "CanvasNotFoundError",
    "CanvasStore",
    "CanvasStoreError",
    "ContinuationNotFoundError",
    "ContinuationRevisionError",
    "ContinuationRevisionRequiredError",
    "EventNotFoundError",
    "RequestConflictError",
    "RunNotFoundError",
    "RunStateError",
    "VersionConflictError",
]


class CanvasStoreError(CanvasError):
    """Base error for persistence operations."""

    def __init__(self, message: str, *, code: str, status: int = 400):
        super().__init__(message, code=code, status=status)


class CanvasNotFoundError(CanvasStoreError):
    def __init__(self, canvas_id: str):
        super().__init__(f"canvas not found: {canvas_id}", code="canvas_not_found", status=404)


class RunNotFoundError(CanvasStoreError):
    def __init__(self, run_id: str):
        super().__init__(f"run not found: {run_id}", code="run_not_found", status=404)


class EventNotFoundError(CanvasStoreError):
    def __init__(self, event_id: int):
        super().__init__(f"run event not found: {event_id}", code="event_not_found", status=404)


class VersionConflictError(CanvasStoreError):
    def __init__(self, canvas_id: str, expected: int, actual: int):
        super().__init__(
            f"canvas version conflict for {canvas_id}: expected {expected}, actual {actual}",
            code="version_conflict",
            status=409,
        )
        self.canvas_id = canvas_id
        self.expected_version = expected
        self.actual_version = actual


class RequestConflictError(CanvasStoreError):
    def __init__(self, request_id: str):
        super().__init__(
            f"request_id already belongs to a different run intent: {request_id}",
            code="request_id_conflict",
            status=409,
        )
        self.request_id = request_id


class RunStateError(CanvasStoreError):
    def __init__(self, message: str, *, code: str = "run_state_conflict"):
        super().__init__(message, code=code, status=409)


class ContinuationNotFoundError(CanvasStoreError):
    """A requested opt-in continuation plan does not exist."""

    def __init__(self, continuation_id: str):
        super().__init__(
            f"continuation not found: {continuation_id}",
            code="continuation_not_found",
            status=404,
        )


class ContinuationRevisionError(CanvasStoreError):
    """A continuation mutation lost its compare-and-swap race."""

    def __init__(self, continuation_id: str, expected: int, actual: int):
        super().__init__(
            f"continuation revision conflict for {continuation_id}: "
            f"expected {expected}, actual {actual}",
            code="continuation_revision_conflict",
            status=409,
        )
        self.continuation_id = continuation_id
        self.expected_revision = expected
        self.actual_revision = actual


class ContinuationRevisionRequiredError(CanvasStoreError):
    """A configuration attempted to change an existing plan implicitly."""

    def __init__(self, continuation_id: str):
        super().__init__(
            f"continuation {continuation_id} already exists; revision is required to change it",
            code="continuation_revision_required",
            status=409,
        )


_UNSET = object()
_SCHEMA_VERSION = 2
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "unknown", "cancelled"})
_CLAIMABLE_STATUSES = frozenset({"queued", "pending_agent"})
_BLOCKING_STATUSES = frozenset({"running", "unknown"})
_ATTENTION_STATES = frozenset({"active", "paused", "abandoned"})
_REVIEW_DECISIONS = frozenset({"ACCEPT", "REJECT", "INCONCLUSIVE"})
_CANCEL_MESSAGE = "用户取消了尚未开始的执行"
_UNKNOWN_RESOURCE_KEY = "legacy:unknown"
_DEFAULT_RESOURCE_CAPACITY = 1
_MAX_IMAGE_CAPACITY = 2
_CONTINUATION_STATES = frozenset({"active", "paused"})
_CONTINUATION_UNIT_STATES = frozenset({"dispatched", "result_ready", "handled", "blocked"})
_MAX_CONTINUATION_NODE_IDS = 256
_MAX_CONTINUATION_UNITS = 512
_MAX_CONTINUATION_SESSION_LENGTH = 256
_MAX_CONTINUATION_AUTHORIZATION_LENGTH = 8192
_MAX_CONTINUATION_REASON_LENGTH = 2000


class CanvasStore:
    """Persist canvas drafts and confirmed run snapshots in SQLite.

    Version 2 is an additive migration of the original two-table store.  Old
    ``node_runs`` rows retain their status, snapshot, outputs, provider task
    number, owner and error; fields introduced by this version receive
    conservative defaults.  A missing resource key is treated as an unknown
    shared resource and therefore continues to block admission until the
    request is terminal.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self.db_path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._initialize()

    @property
    def schema_version(self) -> int:
        """Return the current additive schema version."""

        with self._lock:
            row = (
                self._conn()
                .execute("SELECT version FROM canvas_schema_meta WHERE singleton = 1")
                .fetchone()
            )
        return _SCHEMA_VERSION if row is None else int(row["version"])

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def __enter__(self) -> CanvasStore:
        return self

    def __exit__(self, _exc_type: Any, _exc_value: Any, _traceback: Any) -> None:
        self.close()

    def list_canvases(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = (
                self._conn()
                .execute(
                    "SELECT id, name, version, graph_json, created_at, updated_at "
                    "FROM canvases ORDER BY updated_at DESC, id DESC"
                )
                .fetchall()
            )
            return [self._canvas_from_row(row) for row in rows]

    def create_canvas(self, name: str, graph: Mapping[str, Any] | None = None) -> dict[str, Any]:
        name = _require_name(name)
        normalized_graph = validate_graph(graph if graph is not None else empty_graph())
        canvas_id = str(uuid4())
        now = _now()
        with self._lock, self._transaction():
            self._conn().execute(
                "INSERT INTO canvases "
                "(id, name, version, graph_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (canvas_id, name, 1, _dump(normalized_graph), now, now),
            )
            row = (
                self._conn()
                .execute(
                    "SELECT id, name, version, graph_json, created_at, updated_at "
                    "FROM canvases WHERE id = ?",
                    (canvas_id,),
                )
                .fetchone()
            )
        assert row is not None
        return self._canvas_from_row(row)

    def get_canvas(self, canvas_id: str) -> dict[str, Any]:
        with self._lock:
            row = (
                self._conn()
                .execute(
                    "SELECT id, name, version, graph_json, created_at, updated_at "
                    "FROM canvases WHERE id = ?",
                    (canvas_id,),
                )
                .fetchone()
            )
        if row is None:
            raise CanvasNotFoundError(canvas_id)
        return self._canvas_from_row(row)

    def save_canvas(
        self,
        canvas_id: str,
        expected_version: int,
        graph: Mapping[str, Any],
        name: str | None = None,
    ) -> dict[str, Any]:
        expected_version = _require_version(expected_version)
        normalized_graph = validate_graph(graph)
        if name is not None:
            name = _require_name(name)
        with self._lock, self._transaction():
            row = (
                self._conn()
                .execute(
                    "SELECT id, name, version, graph_json, created_at, updated_at "
                    "FROM canvases WHERE id = ?",
                    (canvas_id,),
                )
                .fetchone()
            )
            if row is None:
                raise CanvasNotFoundError(canvas_id)
            actual_version = int(row["version"])
            if actual_version != expected_version:
                raise VersionConflictError(canvas_id, expected_version, actual_version)
            new_version = actual_version + 1
            now = _now()
            values: tuple[Any, ...]
            if name is None:
                values = (_dump(normalized_graph), new_version, now, canvas_id, expected_version)
                cursor = self._conn().execute(
                    "UPDATE canvases SET graph_json = ?, version = ?, updated_at = ? "
                    "WHERE id = ? AND version = ?",
                    values,
                )
            else:
                values = (
                    name,
                    _dump(normalized_graph),
                    new_version,
                    now,
                    canvas_id,
                    expected_version,
                )
                cursor = self._conn().execute(
                    "UPDATE canvases SET name = ?, graph_json = ?, version = ?, updated_at = ? "
                    "WHERE id = ? AND version = ?",
                    values,
                )
            if cursor.rowcount != 1:
                # A second connection can only win here when the caller uses
                # more than one CanvasStore instance for the same database.
                actual = self._current_canvas_version(canvas_id)
                raise VersionConflictError(canvas_id, expected_version, actual)
            updated = (
                self._conn()
                .execute(
                    "SELECT id, name, version, graph_json, created_at, updated_at "
                    "FROM canvases WHERE id = ?",
                    (canvas_id,),
                )
                .fetchone()
            )
        assert updated is not None
        return self._canvas_from_row(updated)

    def get_run_by_request(self, request_id: str) -> dict[str, Any] | None:
        request_id = _require_request_id(request_id)
        with self._lock:
            row = (
                self._conn()
                .execute("SELECT * FROM node_runs WHERE request_id = ?", (request_id,))
                .fetchone()
            )
        return None if row is None else self._run_from_row(row)

    def create_run(
        self,
        canvas_id: str,
        node_id: str,
        expected_version: int,
        request_id: str,
        snapshot: Mapping[str, Any],
        status: str = "queued",
        *,
        resource_key: str | None = None,
        resource_capacity: int | None = None,
    ) -> dict[str, Any]:
        """Create one immutable run intent, idempotently by ``request_id``.

        Resource information is part of the run intent.  Repeating a request
        with a changed resource declaration still returns the original run;
        it never mutates the frozen intent behind that request id.
        """

        expected_version = _require_version(expected_version)
        request_id = _require_request_id(request_id)
        node_id = _require_id(node_id, "node_id")
        status = _require_status(status)
        snapshot_json = _dump_snapshot(snapshot)
        resolved_resource_key, resolved_capacity = _resolve_resource(
            resource_key, resource_capacity
        )
        run_id = str(uuid4())
        now = _now()
        stage = _default_stage(status)
        with self._lock, self._transaction():
            existing = (
                self._conn()
                .execute("SELECT * FROM node_runs WHERE request_id = ?", (request_id,))
                .fetchone()
            )
            if existing is not None:
                if (
                    existing["canvas_id"] == canvas_id
                    and existing["node_id"] == node_id
                    and int(existing["canvas_version"]) == expected_version
                    and existing["snapshot"] == snapshot_json
                ):
                    return self._run_from_row(existing)
                raise RequestConflictError(request_id)

            canvas_row = (
                self._conn().execute("SELECT * FROM canvases WHERE id = ?", (canvas_id,)).fetchone()
            )
            if canvas_row is None:
                raise CanvasNotFoundError(canvas_id)
            actual_version = int(canvas_row["version"])
            if actual_version != expected_version:
                raise VersionConflictError(canvas_id, expected_version, actual_version)
            try:
                graph = validate_graph(_load(canvas_row["graph_json"], "graph_json"))
            except GraphValidationError as exc:
                raise CanvasStoreError(str(exc), code="invalid_canvas_graph", status=400) from exc
            if not any(node["id"] == node_id for node in graph["nodes"]):
                raise CanvasStoreError(
                    f"node not found in canvas: {node_id}", code="node_not_found", status=400
                )
            self._conn().execute(
                "INSERT INTO node_runs "
                "(id, request_id, canvas_id, node_id, canvas_version, status, snapshot, "
                "outputs, provider_task_id, owner_token, error, created_at, updated_at, "
                "stage, stage_updated_at, evidence, attention_state, attention_reason, "
                "attention_updated_at, resource_key, resource_capacity, review, "
                "review_owner_token, reviewed_at, recovery_token, recovery_reason, "
                "recovery_claimed_at, recovery_resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    request_id,
                    canvas_id,
                    node_id,
                    expected_version,
                    status,
                    snapshot_json,
                    "[]",
                    None,
                    None,
                    None,
                    now,
                    now,
                    stage,
                    now,
                    "[]",
                    "active",
                    None,
                    now,
                    resolved_resource_key,
                    resolved_capacity,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            assert row is not None
            self._emit_event(row, "run.created", {"status": status, "stage": stage}, now)
        assert row is not None
        return self._run_from_row(row)

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return self._run_from_row(row)

    def list_runs(self, canvas_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if canvas_id is None:
                rows = (
                    self._conn()
                    .execute("SELECT * FROM node_runs ORDER BY created_at ASC, id ASC")
                    .fetchall()
                )
            else:
                rows = (
                    self._conn()
                    .execute(
                        "SELECT * FROM node_runs WHERE canvas_id = ? "
                        "ORDER BY created_at ASC, id ASC",
                        (canvas_id,),
                    )
                    .fetchall()
                )
        return [self._run_from_row(row) for row in rows]

    def claim_run(
        self,
        run_id: str,
        owner_token: str | None = None,
        *,
        resource_key: str | None = None,
        resource_capacity: int | None = None,
    ) -> dict[str, Any]:
        """Atomically claim one pending run if its resource has capacity.

        ``running`` and ``unknown`` rows occupy their declared resource.  An
        unknown resource key is a wildcard: it conservatively blocks every
        other resource because the store cannot prove that the remote work
        ended or which provider resource it used.
        """

        if owner_token is not None:
            _require_owner_token(owner_token)
        if resource_key is not None:
            resource_key = _require_resource_key(resource_key)
        if resource_capacity is not None:
            resource_capacity = _require_resource_capacity(resource_capacity, resource_key)

        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["status"] not in _CLAIMABLE_STATUSES:
                raise RunStateError(
                    f"run {run_id} cannot be claimed from status {row['status']}",
                    code="run_not_claimable",
                )
            if row["attention_state"] != "active":
                raise RunStateError(
                    f"run {run_id} is {row['attention_state']} and cannot be claimed",
                    code="attention_inactive",
                )

            stored_key = row["resource_key"] or _UNKNOWN_RESOURCE_KEY
            stored_capacity = int(row["resource_capacity"] or _DEFAULT_RESOURCE_CAPACITY)
            if resource_key is not None and resource_key != stored_key:
                raise RunStateError(
                    f"run {run_id} has resource {stored_key}, not {resource_key}",
                    code="resource_mismatch",
                )
            if resource_capacity is not None and resource_capacity != stored_capacity:
                raise RunStateError(
                    f"run {run_id} has resource capacity {stored_capacity}, "
                    f"not {resource_capacity}",
                    code="resource_mismatch",
                )

            blockers = (
                self._conn()
                .execute(
                    "SELECT resource_key, resource_capacity, status, stage, evidence FROM node_runs "
                    "WHERE id <> ? AND status IN ('running', 'unknown')",
                    (run_id,),
                )
                .fetchall()
            )
            occupied = [
                blocking
                for blocking in blockers
                if _run_holds_generation_resource(blocking)
                and _resource_conflicts(stored_key, blocking["resource_key"])
            ]
            if occupied:
                capacities = [
                    stored_capacity,
                    *[
                        int(blocking["resource_capacity"] or _DEFAULT_RESOURCE_CAPACITY)
                        for blocking in occupied
                    ],
                ]
                capacity = max(1, min(capacities))
                if len(occupied) >= capacity:
                    blocking = occupied[0]
                    raise RunStateError(
                        f"resource {stored_key} is busy: {blocking['status']}", code="busy"
                    )

            now = _now()
            cursor = self._conn().execute(
                "UPDATE node_runs SET status = 'running', owner_token = ?, updated_at = ? "
                "WHERE id = ? AND status IN ('queued', 'pending_agent')",
                (owner_token, now, run_id),
            )
            if cursor.rowcount != 1:
                raise RunStateError(f"run {run_id} was claimed concurrently", code="busy")
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(updated, "run.claimed", {"status": "running"}, now)
        assert updated is not None
        return self._run_from_row(updated)

    def cancel_pending(self, run_id: str) -> dict[str, Any]:
        """Atomically cancel work that has not been claimed by a worker yet."""

        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["status"] not in _CLAIMABLE_STATUSES:
                raise RunStateError(
                    f"run {run_id} is no longer pending (status: {row['status']})",
                    code="run_not_pending",
                )
            now = _now()
            evidence = _append_evidence(
                _load(row["evidence"], "evidence"),
                {"kind": "cancelled", "reason": _CANCEL_MESSAGE},
                "cancelled",
                now,
            )
            cursor = self._conn().execute(
                "UPDATE node_runs SET status = 'cancelled', owner_token = NULL, error = ?, "
                "stage = 'cancelled', stage_updated_at = ?, evidence = ?, updated_at = ? "
                "WHERE id = ? AND status IN ('queued', 'pending_agent')",
                (_dump(_CANCEL_MESSAGE), now, _dump(evidence), now, run_id),
            )
            if cursor.rowcount != 1:
                raise RunStateError(
                    f"run {run_id} is no longer pending (status: {row['status']})",
                    code="run_not_pending",
                )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(updated, "run.cancelled", {"status": "cancelled"}, now)
        assert updated is not None
        return self._run_from_row(updated)

    def claim_recovery(self, run_id: str, reason: str) -> str:
        """Atomically acquire a one-time recovery token for a recoverable run.

        A failed run is recoverable only when the provider has already been
        confirmed as finished and the local failure happened while collecting
        or validating its result.  This permits collecting the same result
        again without making an ordinary failed run mutable.
        """

        if not isinstance(reason, str) or not reason.strip():
            raise CanvasStoreError(
                "a reason is required to claim recovery",
                code="recovery_reason_required",
                status=400,
            )
        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if not _is_recoverable_row(row):
                raise RunStateError(
                    f"run {run_id} has no bounded provider-result recovery path",
                    code="run_not_recoverable",
                )
            if row["recovery_token"] is not None:
                raise RunStateError(
                    f"run {run_id} already has a recovery claimant", code="recovery_busy"
                )
            if row["recovery_resolved_at"] is not None:
                raise RunStateError(
                    f"run {run_id} has already completed recovery", code="run_terminal"
                )
            token = uuid4().hex
            now = _now()
            evidence = _append_evidence(
                _load(row["evidence"], "evidence"),
                {"kind": "recovery_claimed", "reason": reason},
                "reconcile",
                now,
            )
            self._conn().execute(
                "UPDATE node_runs SET recovery_token = ?, recovery_reason = ?, "
                "recovery_claimed_at = ?, evidence = ?, updated_at = ? WHERE id = ? "
                "AND recovery_token IS NULL",
                (token, reason, now, _dump(evidence), now, run_id),
            )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(updated, "run.recovery_claimed", {"recovery_claimed": True}, now)
        return token

    def reconcile_run(
        self,
        run_id: str,
        status: str,
        evidence: Any,
        outputs: Sequence[Mapping[str, Any]] | None = None,
        provider_task_id: str | object | None = _UNSET,
        owner_token: str | None = None,
        *,
        recovery_token: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one unknown request using explicit, validated evidence.

        This is the only path that can close an ``unknown`` run.  It accepts a
        late result, confirmed provider failure, or confirmed cancellation;
        it never submits a new request.  Existing evidence and the original
        error are preserved and the reconciliation evidence is appended.
        File and media validation belongs to the service layer, while this
        method enforces identity, ownership and terminal-state rules.
        """

        status = _validate_reconcile_arguments(
            status,
            evidence,
            outputs,
            provider_task_id,
            owner_token,
            recovery_token,
        )
        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            _validate_reconcile_row(
                row,
                run_id,
                status,
                evidence,
                outputs,
                provider_task_id,
                owner_token,
                recovery_token,
            )
            now = _now()
            evidence_history = _append_evidence(
                _load(row["evidence"], "evidence"),
                {"kind": "reconcile", "status": status, "evidence": evidence},
                "reconcile",
                now,
            )
            assignments = [
                "status = ?",
                "owner_token = NULL",
                "recovery_token = NULL",
                "recovery_reason = NULL",
                "recovery_claimed_at = NULL",
                "recovery_resolved_at = ?",
                "evidence = ?",
                "stage = ?",
                "stage_updated_at = ?",
                "updated_at = ?",
            ]
            values: list[Any] = [
                status,
                now,
                _dump(evidence_history),
                "cancelled" if status == "cancelled" else "media_validation",
                now,
                now,
            ]
            if outputs is not None:
                assignments.append("outputs = ?")
                values.append(_dump(list(outputs)))
            if provider_task_id is not _UNSET:
                # ``None`` means "no new provider id".  Once a provider id is
                # known it is immutable across reconciliation attempts.
                if provider_task_id is not None and provider_task_id != row["provider_task_id"]:
                    assignments.append("provider_task_id = ?")
                    values.append(provider_task_id)
            values.append(run_id)
            cursor = self._conn().execute(
                f"UPDATE node_runs SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise RunStateError(f"run {run_id} was reconciled concurrently", code="busy")
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(
                updated,
                "run.reconciled",
                {"status": status, "evidence": True},
                now,
            )
        assert updated is not None
        return self._run_from_row(updated)

    def preflight_reconcile(
        self,
        run_id: str,
        status: str,
        evidence: Any,
        outputs: Sequence[Mapping[str, Any]] | None = None,
        provider_task_id: str | object | None = _UNSET,
        owner_token: str | None = None,
        *,
        recovery_token: str | None = None,
    ) -> dict[str, Any]:
        """Validate a reconciliation without changing durable state.

        The service uses this immediately before copying returned files into
        the run directory.  ``reconcile_run`` repeats the same checks inside
        its transaction, so a competing writer cannot turn a successful
        preflight into an unauthorized or stale commit.
        """

        status = _validate_reconcile_arguments(
            status,
            evidence,
            outputs,
            provider_task_id,
            owner_token,
            recovery_token,
        )
        with self._lock:
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            _validate_reconcile_row(
                row,
                run_id,
                status,
                evidence,
                outputs,
                provider_task_id,
                owner_token,
                recovery_token,
            )
            return self._run_from_row(row)

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        outputs: Sequence[Mapping[str, Any]] | None = None,
        provider_task_id: str | object | None = _UNSET,
        error: Any = _UNSET,
        stage: str | None = None,
        evidence: Any = _UNSET,
    ) -> dict[str, Any]:
        """Update mutable execution fields before a terminal state.

        A terminal execution result cannot be overwritten through this method.
        ``reconcile_run`` is intentionally separate so a late remote result is
        visibly an evidence-backed recovery operation.
        """

        if status is not None:
            status = _require_status(status)
        if stage is not None:
            stage = _require_stage(stage)
        if outputs is not None:
            _validate_outputs(outputs)
        if provider_task_id is not _UNSET and provider_task_id is not None:
            if not isinstance(provider_task_id, str):
                raise CanvasStoreError(
                    "provider_task_id must be a string or null",
                    code="provider_task_id_type",
                    status=400,
                )
        evidence_provided = evidence is not _UNSET and evidence is not None
        if evidence_provided:
            _validate_evidence_input(evidence)
        if (
            status is None
            and outputs is None
            and provider_task_id is _UNSET
            and error is _UNSET
            and stage is None
            and not evidence_provided
        ):
            return self.get_run(run_id)

        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["status"] in _TERMINAL_STATUSES:
                raise RunStateError(
                    f"terminal run cannot be updated: {run_id}", code="run_terminal"
                )

            now = _now()
            current_stage = row["stage"] or _default_stage(row["status"])
            next_stage = stage if stage is not None else current_stage
            assignments: list[str] = []
            values: list[Any] = []
            changed: dict[str, Any] = {}
            if status is not None and status != row["status"]:
                assignments.append("status = ?")
                values.append(status)
                changed["status"] = status
            current_outputs = _load(row["outputs"], "outputs")
            if outputs is not None and _canonical_json(list(outputs)) != _canonical_json(
                current_outputs
            ):
                assignments.append("outputs = ?")
                values.append(_dump(list(outputs)))
                changed["outputs"] = True
            if provider_task_id is not _UNSET and provider_task_id != row["provider_task_id"]:
                assignments.append("provider_task_id = ?")
                values.append(provider_task_id)
                changed["provider_task_id"] = provider_task_id is not None
            current_error = None if row["error"] is None else _load_error(row["error"])
            if error is not _UNSET and _canonical_json(error) != _canonical_json(current_error):
                assignments.append("error = ?")
                values.append(None if error is None else _dump(error))
                changed["error"] = error is not None
            if stage is not None and stage != current_stage:
                assignments.extend(["stage = ?", "stage_updated_at = ?"])
                values.extend([stage, now])
                changed["stage"] = stage
            if evidence_provided:
                evidence_history = _append_evidence(
                    _load(row["evidence"], "evidence"), evidence, next_stage, now
                )
                previous_history = _load(row["evidence"], "evidence")
                if not _evidence_duplicate(previous_history, evidence, next_stage):
                    assignments.append("evidence = ?")
                    values.append(_dump(evidence_history))
                    changed["evidence"] = True
            if not assignments:
                return self._run_from_row(row)
            assignments.append("updated_at = ?")
            values.extend([now, run_id])
            self._conn().execute(
                f"UPDATE node_runs SET {', '.join(assignments)} WHERE id = ?", values
            )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(updated, "run.updated", changed, now)
        assert updated is not None
        return self._run_from_row(updated)

    def set_attention(self, run_id: str, state: str, reason: str | None = None) -> dict[str, Any]:
        """Set local follow-up state independently of execution status."""

        state = _require_attention_state(state)
        if reason is not None:
            if not isinstance(reason, str) or not reason.strip():
                raise CanvasStoreError(
                    "attention reason must be a non-empty string or null",
                    code="attention_reason_type",
                    status=400,
                )
        if state != "active" and reason is None:
            raise CanvasStoreError(
                "paused or abandoned attention requires a reason",
                code="attention_reason_required",
                status=400,
            )
        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["attention_state"] == state and row["attention_reason"] == reason:
                return self._run_from_row(row)
            now = _now()
            self._conn().execute(
                "UPDATE node_runs SET attention_state = ?, attention_reason = ?, "
                "attention_updated_at = ?, updated_at = ? WHERE id = ?",
                (state, reason, now, now, run_id),
            )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(
                updated,
                "run.attention_changed",
                {"attention_state": state, "attention_reason": reason},
                now,
            )
        assert updated is not None
        return self._run_from_row(updated)

    def claim_review(self, run_id: str, owner_token: str | None = None) -> str:
        """Claim the separate production-review write slot for a run."""

        if owner_token is not None:
            _require_owner_token(owner_token)
        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["status"] != "succeeded":
                raise RunStateError(
                    f"only succeeded runs can be reviewed: {run_id}", code="review_not_ready"
                )
            existing_review = None if row["review"] is None else _load(row["review"], "review")
            if existing_review is not None:
                decision = _review_decision(existing_review)
                if decision in {"ACCEPT", "REJECT"}:
                    raise RunStateError(
                        f"run {run_id} already has a terminal production review",
                        code="review_terminal",
                    )
            claimed = row["review_owner_token"]
            if claimed is not None:
                if owner_token is not None and owner_token == claimed:
                    return str(claimed)
                raise RunStateError(
                    f"run {run_id} is already claimed for review", code="review_busy"
                )
            token = owner_token or uuid4().hex
            now = _now()
            self._conn().execute(
                "UPDATE node_runs SET review_owner_token = ?, updated_at = ? WHERE id = ?",
                (token, now, run_id),
            )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(updated, "review.claimed", {"review_claimed": True}, now)
        return token

    def review_run(
        self,
        run_id: str,
        review: Mapping[str, Any],
        owner_token: str | None = None,
    ) -> dict[str, Any]:
        """Persist a review bound to one exact output path and digest.

        The service is responsible for checking that the file exists and that
        its digest is correct.  This method requires the path and SHA-256
        fields, and stores them with the review, but deliberately does not
        require the path to already be in ``outputs``: a reviewed postprocessed
        file can be the adopted version even when the generated candidate list
        has not been rewritten.
        """

        normalized_review = _validate_review(review)
        if owner_token is None:
            raise CanvasStoreError(
                "claim the production review before recording it",
                code="review_owner_required",
                status=403,
            )
        _require_owner_token(owner_token)
        with self._lock, self._transaction():
            row = self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(run_id)
            if row["status"] != "succeeded":
                raise RunStateError(
                    f"only succeeded runs can be reviewed: {run_id}", code="review_not_ready"
                )
            previous = None if row["review"] is None else _load(row["review"], "review")
            if previous is not None:
                previous_decision = _review_decision(previous)
                if previous_decision in {"ACCEPT", "REJECT"}:
                    if _canonical_json(previous) == _canonical_json(normalized_review):
                        review_owner = row["review_owner_token"]
                        if review_owner != owner_token and row["owner_token"] != owner_token:
                            raise CanvasStoreError(
                                "a review owner is required to read back this review",
                                code="review_owner_required",
                                status=403,
                            )
                        return self._run_from_row(row)
                    raise RunStateError(
                        f"run {run_id} already has a terminal production review",
                        code="review_terminal",
                    )
                if not _same_review_binding(previous, normalized_review):
                    raise RunStateError(
                        "a review update must keep the same output binding",
                        code="review_output_mismatch",
                    )
            review_owner = row["review_owner_token"]
            if review_owner is not None and review_owner != owner_token:
                raise CanvasStoreError(
                    "this production review belongs to another reviewer",
                    code="review_owner_conflict",
                    status=403,
                )
            # A review claim is separate from execution ownership.  For a
            # caller that deliberately reuses the original execution token,
            # accepting it here is safe and makes script-run QC convenient.
            if review_owner is None and row["owner_token"] != owner_token:
                raise CanvasStoreError(
                    "claim the production review before recording it",
                    code="review_owner_required",
                    status=403,
                )
            now = _now()
            self._conn().execute(
                "UPDATE node_runs SET review = ?, review_owner_token = ?, "
                "reviewed_at = ?, updated_at = ? WHERE id = ?",
                (_dump(normalized_review), review_owner or owner_token, now, now, run_id),
            )
            updated = (
                self._conn().execute("SELECT * FROM node_runs WHERE id = ?", (run_id,)).fetchone()
            )
            assert updated is not None
            self._emit_event(
                updated,
                "review.recorded",
                {"decision": normalized_review["decision"], "output_sha256": True},
                now,
            )
        assert updated is not None
        return self._run_from_row(updated)

    def list_events(
        self, after: int = 0, canvas_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return durable events with ``event_id > after`` in sequence order."""

        after = _require_event_id(after, "after", allow_zero=True)
        limit = _require_limit(limit)
        if canvas_id is not None:
            canvas_id = _require_id(canvas_id, "canvas_id")
        with self._lock:
            if canvas_id is None:
                rows = (
                    self._conn()
                    .execute(
                        "SELECT * FROM run_events WHERE id > ? ORDER BY id ASC LIMIT ?",
                        (after, limit),
                    )
                    .fetchall()
                )
            else:
                rows = (
                    self._conn()
                    .execute(
                        "SELECT * FROM run_events WHERE id > ? AND canvas_id = ? "
                        "ORDER BY id ASC LIMIT ?",
                        (after, canvas_id, limit),
                    )
                    .fetchall()
                )
        return [self._event_from_row(row) for row in rows]

    def acknowledge_event(self, consumer_id: str, event_id: int) -> dict[str, Any]:
        """Advance one consumer cursor; repeated acknowledgments are harmless."""

        consumer_id = _require_consumer_id(consumer_id)
        event_id = _require_event_id(event_id, "event_id", allow_zero=False)
        with self._lock, self._transaction():
            event = (
                self._conn()
                .execute("SELECT id FROM run_events WHERE id = ?", (event_id,))
                .fetchone()
            )
            if event is None:
                raise EventNotFoundError(event_id)
            row = (
                self._conn()
                .execute("SELECT cursor FROM event_cursors WHERE consumer_id = ?", (consumer_id,))
                .fetchone()
            )
            current = 0 if row is None else int(row["cursor"])
            cursor = max(current, event_id)
            now = _now()
            self._conn().execute(
                "INSERT INTO event_cursors (consumer_id, cursor, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(consumer_id) DO UPDATE SET cursor = excluded.cursor, "
                "updated_at = excluded.updated_at",
                (consumer_id, cursor, now),
            )
        return {"consumer_id": consumer_id, "event_id": event_id, "cursor": cursor}

    def get_event_cursor(self, consumer_id: str) -> int:
        consumer_id = _require_consumer_id(consumer_id)
        with self._lock:
            row = (
                self._conn()
                .execute("SELECT cursor FROM event_cursors WHERE consumer_id = ?", (consumer_id,))
                .fetchone()
            )
        return 0 if row is None else int(row["cursor"])

    # ------------------------------------------------------------------
    # Opt-in production continuation
    # ------------------------------------------------------------------
    # Continuations intentionally live beside canvases and runs in this same
    # SQLite database.  They are a durable hand-off ledger only: none of the
    # methods below creates a run, claims an owner token or touches media.

    def get_continuation(self, continuation_id: str) -> dict[str, Any]:
        continuation_id = _require_continuation_id(continuation_id)
        with self._lock:
            row = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
        if row is None:
            raise ContinuationNotFoundError(continuation_id)
        return self._continuation_from_row(row)

    def get_continuation_for_scope(self, canvas_id: str, session_id: str) -> dict[str, Any] | None:
        canvas_id = _require_id(canvas_id, "canvas_id")
        session_id = _require_continuation_session(session_id)
        with self._lock:
            row = (
                self._conn()
                .execute(
                    "SELECT * FROM continuations WHERE canvas_id = ? AND session_id = ?",
                    (canvas_id, session_id),
                )
                .fetchone()
            )
        return None if row is None else self._continuation_from_row(row)

    def list_continuations(
        self,
        session_id: str | None = None,
        canvas_id: str | None = None,
        *,
        limit: int = 512,
    ) -> list[dict[str, Any]]:
        if session_id is not None:
            session_id = _require_continuation_session(session_id)
        if canvas_id is not None:
            canvas_id = _require_id(canvas_id, "canvas_id")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 512:
            raise CanvasStoreError(
                "continuation limit must be between 1 and 512",
                code="continuation_limit_type",
                status=400,
            )
        clauses: list[str] = []
        values: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            values.append(session_id)
        if canvas_id is not None:
            clauses.append("canvas_id = ?")
            values.append(canvas_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._lock:
            rows = (
                self._conn()
                .execute(
                    f"SELECT * FROM continuations{where} ORDER BY updated_at DESC, id DESC LIMIT ?",
                    [*values, limit],
                )
                .fetchall()
            )
        return [self._continuation_from_row(row) for row in rows]

    def configure_continuation(
        self,
        canvas_id: str,
        session_id: str,
        node_ids: Sequence[str],
        authorization: str,
        canvas_version: int,
        *,
        revision: int | None = None,
    ) -> dict[str, Any]:
        """Create or explicitly reconfigure one canvas/session plan.

        Repeating the exact configuration is idempotent.  Any change to the
        scope, authorization text or bound canvas version requires the current
        revision and is committed through a compare-and-swap update.
        """

        canvas_id = _require_id(canvas_id, "canvas_id")
        session_id = _require_continuation_session(session_id)
        node_ids = _require_continuation_node_ids(node_ids)
        authorization = _require_continuation_authorization(authorization)
        canvas_version = _require_version(canvas_version)
        if revision is not None:
            revision = _require_continuation_revision(revision)

        with self._lock, self._transaction():
            canvas_row = (
                self._conn()
                .execute("SELECT id, version, graph_json FROM canvases WHERE id = ?", (canvas_id,))
                .fetchone()
            )
            if canvas_row is None:
                raise CanvasNotFoundError(canvas_id)
            actual_version = int(canvas_row["version"])
            if actual_version != canvas_version:
                raise VersionConflictError(canvas_id, canvas_version, actual_version)
            graph = validate_graph(_load(canvas_row["graph_json"], "graph_json"))
            graph_nodes = {node["id"]: node for node in graph["nodes"]}
            graph_node_ids = set(graph_nodes)
            missing = [node_id for node_id in node_ids if node_id not in graph_node_ids]
            if missing:
                raise CanvasStoreError(
                    f"continuation scope contains unknown node: {missing[0]}",
                    code="continuation_node_not_found",
                    status=400,
                )
            non_media = [
                node_id
                for node_id in node_ids
                if graph_nodes[node_id].get("type") not in GENERATION_NODE_TYPES
            ]
            if non_media:
                raise CanvasStoreError(
                    "continuation scope may contain only image or video nodes",
                    code="continuation_node_type",
                    status=400,
                )

            existing = (
                self._conn()
                .execute(
                    "SELECT * FROM continuations WHERE canvas_id = ? AND session_id = ?",
                    (canvas_id, session_id),
                )
                .fetchone()
            )
            if existing is None:
                continuation_id = str(uuid4())
                now = _now()
                self._conn().execute(
                    "INSERT INTO continuations "
                    "(id, canvas_id, session_id, node_ids, authorization, canvas_version, "
                    "state, revision, units, stop_fingerprint, stop_count, stop_warning, "
                    "pause_reason, subagent_stops, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'active', 1, '[]', NULL, 0, NULL, NULL, '[]', ?, ?)",
                    (
                        continuation_id,
                        canvas_id,
                        session_id,
                        _dump(node_ids),
                        authorization,
                        canvas_version,
                        now,
                        now,
                    ),
                )
                row = (
                    self._conn()
                    .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                    .fetchone()
                )
                assert row is not None
                return self._continuation_from_row(row)

            current = self._continuation_from_row(existing)
            same = (
                current["canvas_id"] == canvas_id
                and current["session_id"] == session_id
                and set(current["node_ids"]) == set(node_ids)
                and current["authorization"] == authorization
                and current["canvas_version"] == canvas_version
            )
            if same:
                return current
            if revision is None:
                raise ContinuationRevisionRequiredError(current["id"])
            self._check_continuation_revision(current, revision)
            # Keep units that still belong to the explicitly selected scope.
            # Units without a node are plan-level hand-off records and remain.
            units = [
                unit
                for unit in current["units"]
                if not isinstance(unit, Mapping)
                or unit.get("node_id") is None
                or unit.get("node_id") in node_ids
            ]
            now = _now()
            cursor = self._conn().execute(
                "UPDATE continuations SET node_ids = ?, authorization = ?, "
                "canvas_version = ?, units = ?, stop_fingerprint = NULL, stop_count = 0, "
                "stop_warning = NULL, revision = revision + 1, updated_at = ? "
                "WHERE id = ? AND revision = ?",
                (
                    _dump(node_ids),
                    authorization,
                    canvas_version,
                    _dump(units),
                    now,
                    current["id"],
                    revision,
                ),
            )
            if cursor.rowcount != 1:
                actual = self._continuation_revision(current["id"])
                raise ContinuationRevisionError(current["id"], revision, actual)
            row = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (current["id"],))
                .fetchone()
            )
            assert row is not None
        return self._continuation_from_row(row)

    def update_continuation_state(
        self,
        continuation_id: str,
        revision: int,
        state: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        continuation_id = _require_continuation_id(continuation_id)
        revision = _require_continuation_revision(revision)
        state = _require_continuation_state(state)
        reason = _optional_continuation_reason(reason)
        if state == "paused" and reason is None:
            raise CanvasStoreError(
                "paused continuation requires a reason",
                code="continuation_reason_required",
                status=400,
            )
        with self._lock, self._transaction():
            row = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            if row is None:
                raise ContinuationNotFoundError(continuation_id)
            current = self._continuation_from_row(row)
            self._check_continuation_revision(current, revision)
            next_reason = reason if state == "paused" else None
            if current["state"] == state and current.get("pause_reason") == next_reason:
                return current
            now = _now()
            cursor = self._conn().execute(
                "UPDATE continuations SET state = ?, pause_reason = ?, "
                "stop_fingerprint = NULL, stop_count = 0, stop_warning = NULL, "
                "revision = revision + 1, updated_at = ? WHERE id = ? AND revision = ?",
                (state, next_reason, now, continuation_id, revision),
            )
            if cursor.rowcount != 1:
                actual = self._continuation_revision(continuation_id)
                raise ContinuationRevisionError(continuation_id, revision, actual)
            updated = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            assert updated is not None
        return self._continuation_from_row(updated)

    def update_continuation_unit(
        self,
        continuation_id: str,
        revision: int,
        unit_id: str,
        state: str,
        *,
        agent_id: str | None = None,
        node_id: str | None = None,
        run_id: str | None = None,
        turn_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        continuation_id = _require_continuation_id(continuation_id)
        revision = _require_continuation_revision(revision)
        unit_id = _require_continuation_unit_id(unit_id)
        state = _require_continuation_unit_state(state)
        agent_id = _optional_continuation_text(agent_id, "agent_id")
        node_id = _optional_continuation_text(node_id, "node_id")
        run_id = _optional_continuation_text(run_id, "run_id")
        turn_id = _optional_continuation_text(turn_id, "turn_id")
        reason = _optional_continuation_reason(reason)
        if state == "blocked" and reason is None:
            raise CanvasStoreError(
                "blocked unit requires a reason", code="continuation_reason_required", status=400
            )
        with self._lock, self._transaction():
            row = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            if row is None:
                raise ContinuationNotFoundError(continuation_id)
            current = self._continuation_from_row(row)
            self._check_continuation_revision(current, revision)
            if node_id is not None and node_id not in current["node_ids"]:
                raise CanvasStoreError(
                    "unit node_id must be inside the continuation scope",
                    code="continuation_scope_conflict",
                    status=400,
                )
            units = [dict(unit) for unit in current["units"] if isinstance(unit, Mapping)]
            existing_index = next(
                (index for index, unit in enumerate(units) if unit.get("unit_id") == unit_id),
                None,
            )
            now = _now()
            if existing_index is None:
                if len(units) >= _MAX_CONTINUATION_UNITS:
                    raise CanvasStoreError(
                        "continuation has too many units",
                        code="continuation_units_limit",
                        status=400,
                    )
                unit: dict[str, Any] = {
                    "unit_id": unit_id,
                    "agent_id": agent_id,
                    "node_id": node_id,
                    "run_id": run_id,
                    "turn_id": turn_id,
                    "state": state,
                    "reason": reason,
                    "created_at": now,
                    "updated_at": now,
                }
                units.append(unit)
                changed = True
            else:
                unit = units[existing_index]
                transitions = {
                    "dispatched": {"dispatched", "result_ready", "blocked"},
                    "result_ready": {"result_ready", "handled", "blocked"},
                    "blocked": {"blocked", "handled"},
                    "handled": {"handled"},
                }
                if state not in transitions.get(unit.get("state"), set()):
                    raise CanvasStoreError(
                        "unit state cannot move backwards; use a new unit for new work",
                        code="continuation_unit_transition",
                        status=409,
                    )
                for field, value in (
                    ("agent_id", agent_id),
                    ("node_id", node_id),
                    ("run_id", run_id),
                    ("turn_id", turn_id),
                ):
                    if value is not None and unit.get(field) not in {None, value}:
                        raise CanvasStoreError(
                            "unit bindings are immutable; use a new unit for new work",
                            code="continuation_unit_binding",
                            status=409,
                        )
                next_unit = dict(unit)
                next_unit.update(
                    {
                        "agent_id": agent_id if agent_id is not None else unit.get("agent_id"),
                        "node_id": node_id if node_id is not None else unit.get("node_id"),
                        "run_id": run_id if run_id is not None else unit.get("run_id"),
                        "turn_id": turn_id if turn_id is not None else unit.get("turn_id"),
                        "state": state,
                        "reason": reason if reason is not None else unit.get("reason"),
                    }
                )
                changed = any(next_unit.get(key) != unit.get(key) for key in next_unit)
                if changed:
                    next_unit["updated_at"] = now
                    units[existing_index] = next_unit
            if not changed:
                return current
            candidate = units[-1] if existing_index is None else units[existing_index]
            if candidate["state"] == "dispatched" and not (
                candidate.get("agent_id") or candidate.get("run_id")
            ):
                raise CanvasStoreError(
                    "dispatched unit requires an actual agent or run binding",
                    code="continuation_unit_binding",
                    status=400,
                )
            if candidate.get("run_id"):
                bound_run = (
                    self._conn()
                    .execute(
                        "SELECT canvas_id, node_id FROM node_runs WHERE id = ?",
                        (candidate["run_id"],),
                    )
                    .fetchone()
                )
                if (
                    bound_run is None
                    or bound_run["canvas_id"] != current["canvas_id"]
                    or bound_run["node_id"] not in current["node_ids"]
                    or candidate.get("node_id") not in {None, bound_run["node_id"]}
                ):
                    raise CanvasStoreError(
                        "unit run must belong to its canvas and scoped node",
                        code="continuation_scope_conflict",
                        status=400,
                    )
                candidate["node_id"] = bound_run["node_id"]
            if candidate.get("agent_id") and candidate.get("turn_id"):
                peers = (
                    self._conn()
                    .execute(
                        "SELECT id, units FROM continuations WHERE session_id = ?",
                        (current["session_id"],),
                    )
                    .fetchall()
                )
                for peer in peers:
                    for other in _load(peer["units"], "continuation_units"):
                        if peer["id"] == continuation_id and other.get("unit_id") == unit_id:
                            continue
                        if (
                            other.get("agent_id") == candidate["agent_id"]
                            and other.get("turn_id") == candidate["turn_id"]
                        ):
                            raise CanvasStoreError(
                                "agent turn already belongs to another unit",
                                code="continuation_unit_binding",
                                status=409,
                            )
            cursor = self._conn().execute(
                "UPDATE continuations SET units = ?, revision = revision + 1, updated_at = ? "
                "WHERE id = ? AND revision = ?",
                (_dump(units), now, continuation_id, revision),
            )
            if cursor.rowcount != 1:
                actual = self._continuation_revision(continuation_id)
                raise ContinuationRevisionError(continuation_id, revision, actual)
            updated = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            assert updated is not None
        return self._continuation_from_row(updated)

    def record_continuation_stop(
        self,
        continuation_id: str,
        revision: int,
        fingerprint: str,
    ) -> dict[str, Any]:
        """Count a hook Stop only after a read-only summary was computed."""

        continuation_id = _require_continuation_id(continuation_id)
        revision = _require_continuation_revision(revision)
        if not isinstance(fingerprint, str) or not fingerprint.strip() or len(fingerprint) > 128:
            raise CanvasStoreError(
                "continuation stop fingerprint is invalid",
                code="continuation_fingerprint_type",
                status=400,
            )
        with self._lock, self._transaction():
            row = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            if row is None:
                raise ContinuationNotFoundError(continuation_id)
            current = self._continuation_from_row(row)
            self._check_continuation_revision(current, revision)
            previous_count = int(current.get("stop_count") or 0)
            if current.get("stop_fingerprint") == fingerprint and previous_count >= 3:
                # Once the bounded warning has been emitted, repeated Stop
                # hooks are a no-op.  The plan stays visibly unfinished while
                # its revision and counter cannot grow without limit.
                return current
            count = previous_count + 1 if current.get("stop_fingerprint") == fingerprint else 1
            warning = (
                "接续摘要连续 3 次无进展，需要人工接手；计划未标记完成" if count >= 3 else None
            )
            now = _now()
            cursor = self._conn().execute(
                "UPDATE continuations SET stop_fingerprint = ?, stop_count = ?, "
                "stop_warning = ?, revision = revision + 1, updated_at = ? "
                "WHERE id = ? AND revision = ?",
                (fingerprint, count, warning, now, continuation_id, revision),
            )
            if cursor.rowcount != 1:
                actual = self._continuation_revision(continuation_id)
                raise ContinuationRevisionError(continuation_id, revision, actual)
            updated = (
                self._conn()
                .execute("SELECT * FROM continuations WHERE id = ?", (continuation_id,))
                .fetchone()
            )
            assert updated is not None
        return self._continuation_from_row(updated)

    def mark_subagent_result_ready(
        self,
        session_id: str,
        agent_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Idempotently advance matching dispatched units after SubagentStop."""

        session_id = _require_continuation_session(session_id)
        agent_id = _optional_continuation_text(agent_id, "agent_id")
        turn_id = _optional_continuation_text(turn_id, "turn_id")
        # A lifecycle event without its agent binding is only a hint.  It must
        # never guess which child unit ended, even when the plan happens to
        # contain one dispatched unit today.
        # The host's turn binding is equally required: without it a late event
        # from an earlier child turn could be mistaken for a newer unit owned
        # by the same agent.  Manual canvas_continuation_unit updates remain
        # available when a host cannot provide lifecycle identifiers.
        if agent_id is None or turn_id is None:
            return []
        with self._lock, self._transaction():
            rows = (
                self._conn()
                .execute(
                    "SELECT * FROM continuations WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                )
                .fetchall()
            )
            updated_rows: list[sqlite3.Row] = []
            matches = [
                (row["id"], unit.get("unit_id"))
                for row in rows
                for unit in _load(row["units"], "continuation_units")
                if unit.get("state") == "dispatched"
                and unit.get("agent_id") == agent_id
                and unit.get("turn_id") == turn_id
            ]
            # A lifecycle event identifies an exact child turn. Unbound units
            # are reconciled by the parent after inspecting the actual result.
            if len(matches) != 1:
                return []
            for row in rows:
                if row["id"] != matches[0][0]:
                    continue
                current = self._continuation_from_row(row)
                units = [dict(unit) for unit in current["units"] if isinstance(unit, Mapping)]
                dispatched = [unit for unit in units if unit.get("state") == "dispatched"]
                targets = [unit for unit in dispatched if unit.get("unit_id") == matches[0][1]]
                if turn_id is not None:
                    stop_key = f"{agent_id}:{turn_id}"
                    seen_stops = [
                        value
                        for value in current.get("subagent_stops", [])
                        if isinstance(value, str)
                    ]
                    if stop_key in seen_stops:
                        continue
                # A reused agent may own several outstanding units.  Without
                # an explicit turn binding the event cannot identify one
                # safely, so the missing-turn case returned above.
                if len(targets) != 1:
                    continue
                target_ids = {targets[0].get("unit_id")}
                now = _now()
                changed = False
                for unit in units:
                    if unit.get("unit_id") not in target_ids:
                        continue
                    unit["state"] = "result_ready"
                    unit["reason"] = "SubagentStop 已记录，等待主会话处理结果"
                    unit["updated_at"] = now
                    changed = True
                if not changed:
                    continue
                seen_stops.append(stop_key)
                seen_stops = seen_stops[-_MAX_CONTINUATION_UNITS:]
                cursor = self._conn().execute(
                    "UPDATE continuations SET units = ?, subagent_stops = ?, "
                    "stop_fingerprint = NULL, stop_count = 0, "
                    "stop_warning = NULL, revision = revision + 1, updated_at = ? "
                    "WHERE id = ? AND revision = ?",
                    (_dump(units), _dump(seen_stops), now, current["id"], current["revision"]),
                )
                if cursor.rowcount != 1:
                    actual = self._continuation_revision(current["id"])
                    raise ContinuationRevisionError(current["id"], current["revision"], actual)
                updated = (
                    self._conn()
                    .execute("SELECT * FROM continuations WHERE id = ?", (current["id"],))
                    .fetchone()
                )
                assert updated is not None
                updated_rows.append(updated)
        return [self._continuation_from_row(row) for row in updated_rows]

    def pause_continuations_for_session(self, session_id: str, reason: str) -> list[dict[str, Any]]:
        """Pause active plans for an Interrupt hook through CAS updates."""

        session_id = _require_continuation_session(session_id)
        reason = _require_continuation_reason(reason)
        with self._lock, self._transaction():
            rows = (
                self._conn()
                .execute(
                    "SELECT * FROM continuations WHERE session_id = ? AND state = 'active' "
                    "ORDER BY id ASC",
                    (session_id,),
                )
                .fetchall()
            )
            updated_rows: list[sqlite3.Row] = []
            for row in rows:
                current = self._continuation_from_row(row)
                now = _now()
                cursor = self._conn().execute(
                    "UPDATE continuations SET state = 'paused', pause_reason = ?, "
                    "stop_fingerprint = NULL, stop_count = 0, stop_warning = NULL, "
                    "revision = revision + 1, updated_at = ? WHERE id = ? AND revision = ?",
                    (reason, now, current["id"], current["revision"]),
                )
                if cursor.rowcount != 1:
                    actual = self._continuation_revision(current["id"])
                    raise ContinuationRevisionError(current["id"], current["revision"], actual)
                updated = (
                    self._conn()
                    .execute("SELECT * FROM continuations WHERE id = ?", (current["id"],))
                    .fetchone()
                )
                assert updated is not None
                updated_rows.append(updated)
        return [self._continuation_from_row(row) for row in updated_rows]

    @staticmethod
    def _check_continuation_revision(plan: Mapping[str, Any], expected: int) -> None:
        actual = int(plan["revision"])
        if actual != expected:
            raise ContinuationRevisionError(str(plan["id"]), expected, actual)

    def _continuation_revision(self, continuation_id: str) -> int:
        row = (
            self._conn()
            .execute("SELECT revision FROM continuations WHERE id = ?", (continuation_id,))
            .fetchone()
        )
        if row is None:
            raise ContinuationNotFoundError(continuation_id)
        return int(row["revision"])

    def _initialize(self) -> None:
        with self._lock, self._transaction():
            had_node_runs = self._table_exists("node_runs")
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS canvases ("
                "id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "version INTEGER NOT NULL, "
                "graph_json TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")"
            )
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS node_runs ("
                "id TEXT PRIMARY KEY, "
                "request_id TEXT NOT NULL UNIQUE, "
                "canvas_id TEXT NOT NULL REFERENCES canvases(id), "
                "node_id TEXT NOT NULL, "
                "canvas_version INTEGER NOT NULL, "
                "status TEXT NOT NULL, "
                "snapshot TEXT NOT NULL, "
                "outputs TEXT NOT NULL, "
                "provider_task_id TEXT, "
                "owner_token TEXT, "
                "error TEXT, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "stage TEXT NOT NULL DEFAULT 'legacy', "
                "stage_updated_at TEXT NOT NULL DEFAULT '', "
                "evidence TEXT NOT NULL DEFAULT '[]', "
                "attention_state TEXT NOT NULL DEFAULT 'active', "
                "attention_reason TEXT, "
                "attention_updated_at TEXT NOT NULL DEFAULT '', "
                "resource_key TEXT NOT NULL DEFAULT 'legacy:unknown', "
                "resource_capacity INTEGER NOT NULL DEFAULT 1, "
                "review TEXT, "
                "review_owner_token TEXT, "
                "reviewed_at TEXT, "
                "recovery_token TEXT, "
                "recovery_reason TEXT, "
                "recovery_claimed_at TEXT, "
                "recovery_resolved_at TEXT"
                ")"
            )
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS canvas_schema_meta ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                "version INTEGER NOT NULL"
                ")"
            )
            meta = (
                self._conn()
                .execute("SELECT version FROM canvas_schema_meta WHERE singleton = 1")
                .fetchone()
            )
            if meta is None:
                initial_version = 1 if had_node_runs else _SCHEMA_VERSION
                self._conn().execute(
                    "INSERT INTO canvas_schema_meta(singleton, version) VALUES (1, ?)",
                    (initial_version,),
                )
            self._migrate_node_runs()
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS run_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "run_id TEXT NOT NULL REFERENCES node_runs(id), "
                "canvas_id TEXT NOT NULL REFERENCES canvases(id), "
                "event_type TEXT NOT NULL, "
                "payload TEXT NOT NULL, "
                "created_at TEXT NOT NULL"
                ")"
            )
            self._conn().execute(
                "CREATE INDEX IF NOT EXISTS idx_run_events_canvas_id_id "
                "ON run_events(canvas_id, id)"
            )
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS event_cursors ("
                "consumer_id TEXT PRIMARY KEY, "
                "cursor INTEGER NOT NULL DEFAULT 0, "
                "updated_at TEXT NOT NULL"
                ")"
            )
            self._conn().execute(
                "CREATE TABLE IF NOT EXISTS continuations ("
                "id TEXT PRIMARY KEY, "
                "canvas_id TEXT NOT NULL REFERENCES canvases(id), "
                "session_id TEXT NOT NULL, "
                "node_ids TEXT NOT NULL, "
                "authorization TEXT NOT NULL, "
                "canvas_version INTEGER NOT NULL, "
                "state TEXT NOT NULL DEFAULT 'active', "
                "revision INTEGER NOT NULL DEFAULT 1, "
                "units TEXT NOT NULL DEFAULT '[]', "
                "stop_fingerprint TEXT, "
                "stop_count INTEGER NOT NULL DEFAULT 0, "
                "stop_warning TEXT, "
                "pause_reason TEXT, "
                "subagent_stops TEXT NOT NULL DEFAULT '[]', "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "UNIQUE(canvas_id, session_id)"
                ")"
            )
            self._migrate_continuations()
            self._conn().execute(
                "CREATE INDEX IF NOT EXISTS idx_continuations_session "
                "ON continuations(session_id, updated_at)"
            )
            self._conn().execute(
                "CREATE INDEX IF NOT EXISTS idx_node_runs_resource_status "
                "ON node_runs(resource_key, status)"
            )
            self._conn().execute(
                "UPDATE canvas_schema_meta SET version = ? WHERE singleton = 1",
                (_SCHEMA_VERSION,),
            )
            self._conn().execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def _migrate_continuations(self) -> None:
        """Add continuation columns without rewriting existing canvas data."""

        columns = {
            str(row["name"])
            for row in self._conn().execute("PRAGMA table_info(continuations)").fetchall()
        }
        additions: tuple[tuple[str, str], ...] = (
            ("session_id", "TEXT NOT NULL DEFAULT ''"),
            ("node_ids", "TEXT NOT NULL DEFAULT '[]'"),
            ("authorization", "TEXT NOT NULL DEFAULT ''"),
            ("canvas_version", "INTEGER NOT NULL DEFAULT 1"),
            ("state", "TEXT NOT NULL DEFAULT 'active'"),
            ("revision", "INTEGER NOT NULL DEFAULT 1"),
            ("units", "TEXT NOT NULL DEFAULT '[]'"),
            ("stop_fingerprint", "TEXT"),
            ("stop_count", "INTEGER NOT NULL DEFAULT 0"),
            ("stop_warning", "TEXT"),
            ("pause_reason", "TEXT"),
            ("subagent_stops", "TEXT NOT NULL DEFAULT '[]'"),
            ("created_at", "TEXT NOT NULL DEFAULT ''"),
            ("updated_at", "TEXT NOT NULL DEFAULT ''"),
        )
        for name, definition in additions:
            if name not in columns:
                self._conn().execute(f"ALTER TABLE continuations ADD COLUMN {name} {definition}")
        self._conn().execute(
            "UPDATE continuations SET state = CASE WHEN state IN ('active', 'paused') "
            "THEN state ELSE 'active' END, revision = CASE WHEN revision < 1 THEN 1 "
            "ELSE revision END, units = CASE WHEN units IS NULL OR units = '' "
            "THEN '[]' ELSE units END, stop_count = CASE WHEN stop_count < 0 THEN 0 "
            "ELSE stop_count END"
        )

    def _migrate_node_runs(self) -> None:
        """Add version-2 fields without rewriting historical execution data."""

        columns = {
            str(row["name"])
            for row in self._conn().execute("PRAGMA table_info(node_runs)").fetchall()
        }
        additions: tuple[tuple[str, str], ...] = (
            ("stage", "TEXT NOT NULL DEFAULT 'legacy'"),
            ("stage_updated_at", "TEXT NOT NULL DEFAULT ''"),
            ("evidence", "TEXT NOT NULL DEFAULT '[]'"),
            ("attention_state", "TEXT NOT NULL DEFAULT 'active'"),
            ("attention_reason", "TEXT"),
            ("attention_updated_at", "TEXT NOT NULL DEFAULT ''"),
            ("resource_key", "TEXT NOT NULL DEFAULT 'legacy:unknown'"),
            ("resource_capacity", "INTEGER NOT NULL DEFAULT 1"),
            ("review", "TEXT"),
            ("review_owner_token", "TEXT"),
            ("reviewed_at", "TEXT"),
            ("recovery_token", "TEXT"),
            ("recovery_reason", "TEXT"),
            ("recovery_claimed_at", "TEXT"),
            ("recovery_resolved_at", "TEXT"),
        )
        for name, definition in additions:
            if name not in columns:
                self._conn().execute(f"ALTER TABLE node_runs ADD COLUMN {name} {definition}")
        self._conn().execute(
            "UPDATE node_runs SET stage = CASE "
            "WHEN stage IS NULL OR stage = '' THEN 'legacy' ELSE stage END, "
            "stage_updated_at = CASE WHEN stage_updated_at IS NULL OR stage_updated_at = '' "
            "THEN updated_at ELSE stage_updated_at END, "
            "evidence = CASE WHEN evidence IS NULL OR evidence = '' THEN '[]' ELSE evidence END, "
            "attention_state = CASE WHEN attention_state IS NULL OR attention_state = '' "
            "THEN 'active' ELSE attention_state END, "
            "attention_updated_at = CASE WHEN attention_updated_at IS NULL OR attention_updated_at = '' "
            "THEN updated_at ELSE attention_updated_at END, "
            "resource_key = CASE WHEN resource_key IS NULL OR resource_key = '' "
            "THEN 'legacy:unknown' ELSE resource_key END, "
            "resource_capacity = CASE WHEN resource_capacity IS NULL OR resource_capacity < 1 "
            "THEN 1 ELSE resource_capacity END"
        )

    def _emit_event(
        self,
        row: sqlite3.Row,
        event_type: str,
        changes: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> int:
        timestamp = timestamp or _now()
        payload: dict[str, Any] = {
            "run_id": row["id"],
            "canvas_id": row["canvas_id"],
            "status": row["status"],
            "stage": row["stage"],
        }
        if changes:
            payload["changed"] = dict(changes)
        cursor = self._conn().execute(
            "INSERT INTO run_events(run_id, canvas_id, event_type, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (row["id"], row["canvas_id"], event_type, _dump(payload), timestamp),
        )
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn().execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._conn().rollback()
            raise
        else:
            self._conn().commit()

    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            raise CanvasStoreError("canvas store is closed", code="store_closed", status=500)
        return self._connection

    def _table_exists(self, name: str) -> bool:
        row = (
            self._conn()
            .execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
            .fetchone()
        )
        return row is not None

    def _current_canvas_version(self, canvas_id: str) -> int:
        row = (
            self._conn()
            .execute("SELECT version FROM canvases WHERE id = ?", (canvas_id,))
            .fetchone()
        )
        if row is None:
            raise CanvasNotFoundError(canvas_id)
        return int(row["version"])

    @staticmethod
    def _canvas_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "version": int(row["version"]),
            "graph": _load(row["graph_json"], "graph_json"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
        stage = row["stage"] or _default_stage(row["status"])
        stage_updated_at = row["stage_updated_at"] or row["updated_at"]
        attention_state = row["attention_state"] or "active"
        attention_updated_at = row["attention_updated_at"] or row["updated_at"]
        review = None if row["review"] is None else _load(row["review"], "review")
        return {
            "id": row["id"],
            "request_id": row["request_id"],
            "canvas_id": row["canvas_id"],
            "node_id": row["node_id"],
            "canvas_version": int(row["canvas_version"]),
            "status": row["status"],
            "snapshot": _load(row["snapshot"], "snapshot"),
            "outputs": _load(row["outputs"], "outputs"),
            "provider_task_id": row["provider_task_id"],
            "owner_token": row["owner_token"],
            # Early development databases occasionally stored a plain text
            # error instead of JSON encoding it.  Keep that historical text
            # readable while all new writes remain JSON encoded.
            "error": None if row["error"] is None else _load_error(row["error"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "stage": stage,
            "stage_updated_at": stage_updated_at,
            "evidence": _load(row["evidence"] or "[]", "evidence"),
            "attention_state": attention_state,
            "attention_reason": row["attention_reason"],
            "attention_updated_at": attention_updated_at,
            "resource_key": row["resource_key"] or _UNKNOWN_RESOURCE_KEY,
            "resource_capacity": int(row["resource_capacity"] or _DEFAULT_RESOURCE_CAPACITY),
            "review": review,
            "review_owner_token": row["review_owner_token"],
            "reviewed_at": row["reviewed_at"],
            "recovery_token": row["recovery_token"],
            "recovery_reason": row["recovery_reason"],
            "recovery_claimed_at": row["recovery_claimed_at"],
            "recovery_resolved_at": row["recovery_resolved_at"],
        }

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
        event_id = int(row["id"])
        event_type = row["event_type"]
        return {
            "id": event_id,
            "run_id": row["run_id"],
            "canvas_id": row["canvas_id"],
            "event_type": event_type,
            "payload": _load(row["payload"], "event_payload"),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _continuation_from_row(row: sqlite3.Row) -> dict[str, Any]:
        units_value = _load(row["units"] or "[]", "continuation_units")
        units = list(units_value) if isinstance(units_value, list) else []
        node_ids_value = _load(row["node_ids"] or "[]", "continuation_node_ids")
        node_ids = list(node_ids_value) if isinstance(node_ids_value, list) else []
        stops_value = _load(row["subagent_stops"] or "[]", "subagent_stops")
        subagent_stops = list(stops_value) if isinstance(stops_value, list) else []
        return {
            "id": row["id"],
            "canvas_id": row["canvas_id"],
            "session_id": row["session_id"],
            "node_ids": node_ids,
            "authorization": row["authorization"],
            "canvas_version": int(row["canvas_version"]),
            "state": row["state"],
            "revision": int(row["revision"]),
            "units": units,
            "stop_fingerprint": row["stop_fingerprint"],
            "stop_count": int(row["stop_count"] or 0),
            "stop_warning": row["stop_warning"],
            "pause_reason": row["pause_reason"],
            "subagent_stops": subagent_stops,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _require_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise CanvasStoreError(
            "canvas name must be a non-empty string", code="name_type", status=400
        )
    return name


def _require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanvasStoreError(f"{field} must be a non-empty string", code="id_type", status=400)
    return value


def _require_version(version: Any) -> int:
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CanvasStoreError(
            "expected_version must be a positive integer", code="version_type", status=400
        )
    return version


def _require_request_id(request_id: Any) -> str:
    if not isinstance(request_id, str) or not request_id.strip():
        raise CanvasStoreError(
            "request_id must be a non-empty string", code="request_id_type", status=400
        )
    return request_id


def _require_status(status: Any) -> str:
    if not isinstance(status, str) or not status.strip():
        raise CanvasStoreError("status must be a non-empty string", code="status_type", status=400)
    return status


def _require_stage(stage: Any) -> str:
    if not isinstance(stage, str) or not stage.strip():
        raise CanvasStoreError("stage must be a non-empty string", code="stage_type", status=400)
    return stage


def _require_attention_state(state: Any) -> str:
    if not isinstance(state, str) or state not in _ATTENTION_STATES:
        raise CanvasStoreError(
            "attention state must be active, paused or abandoned",
            code="attention_state_type",
            status=400,
        )
    return state


def _require_owner_token(token: Any) -> str:
    if not isinstance(token, str) or not token.strip():
        raise CanvasStoreError(
            "owner_token must be a non-empty string or null",
            code="owner_token_type",
            status=400,
        )
    return token


def _require_resource_key(resource_key: Any) -> str:
    if not isinstance(resource_key, str) or not resource_key.strip():
        raise CanvasStoreError(
            "resource_key must be a non-empty string or null",
            code="resource_key_type",
            status=400,
        )
    return resource_key


def _require_resource_capacity(capacity: Any, resource_key: str | None = None) -> int:
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise CanvasStoreError(
            "resource_capacity must be a positive integer or null",
            code="resource_capacity_type",
            status=400,
        )
    if (
        resource_key is not None
        and resource_key.startswith("image:")
        and capacity > _MAX_IMAGE_CAPACITY
    ):
        raise CanvasStoreError(
            "external image resource capacity cannot exceed 2",
            code="resource_capacity_limit",
            status=400,
        )
    return capacity


def _resolve_resource(resource_key: str | None, resource_capacity: int | None) -> tuple[str, int]:
    key = _UNKNOWN_RESOURCE_KEY if resource_key is None else _require_resource_key(resource_key)
    capacity = (
        _DEFAULT_RESOURCE_CAPACITY
        if resource_capacity is None
        else _require_resource_capacity(resource_capacity, key)
    )
    return key, capacity


def _resource_conflicts(left: str | None, right: str | None) -> bool:
    left = left or _UNKNOWN_RESOURCE_KEY
    right = right or _UNKNOWN_RESOURCE_KEY
    return left in (right, _UNKNOWN_RESOURCE_KEY) or right == _UNKNOWN_RESOURCE_KEY


def _default_stage(status: str) -> str:
    if status in {"queued", "pending_agent"}:
        return "input_validation"
    if status == "running":
        return "generation"
    if status == "succeeded":
        return "media_validation"
    return status


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise CanvasStoreError(
            f"value is not JSON serializable: {exc}", code="json_type", status=400
        ) from exc


def _dump_snapshot(snapshot: Any) -> str:
    if not isinstance(snapshot, Mapping):
        raise CanvasStoreError("snapshot must be an object", code="snapshot_type", status=400)
    return _dump(dict(snapshot))


def _load(value: str, field: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CanvasStoreError(
            f"stored {field} is invalid JSON", code="database_corrupt", status=500
        ) from exc


def _load_error(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _canonical_json(value: Any) -> str:
    return _dump(value)


def _validate_outputs(outputs: Any) -> None:
    if isinstance(outputs, (str, bytes, bytearray)) or not isinstance(outputs, Sequence):
        raise CanvasStoreError("outputs must be an array", code="outputs_type", status=400)
    for output in outputs:
        if not isinstance(output, Mapping):
            raise CanvasStoreError("each output must be an object", code="output_type", status=400)
    _dump(list(outputs))


def _validate_evidence_input(evidence: Any) -> None:
    if evidence is _UNSET or evidence is None:
        raise CanvasStoreError(
            "evidence must be a non-null JSON value", code="evidence_type", status=400
        )
    if isinstance(evidence, str) and not evidence.strip():
        raise CanvasStoreError("evidence must not be empty", code="evidence_required", status=400)
    if (
        isinstance(evidence, (Mapping, Sequence))
        and not isinstance(evidence, (str, bytes, bytearray))
        and len(evidence) == 0
    ):
        raise CanvasStoreError("evidence must not be empty", code="evidence_required", status=400)
    _dump(evidence)


def _validate_reconcile_evidence(evidence: Any, request_id: str, status: str) -> None:
    """Validate the identity and provenance required for late-result closure."""

    if not isinstance(evidence, Mapping):
        raise CanvasStoreError(
            "reconciliation evidence must be an object",
            code="reconcile_evidence_type",
            status=400,
        )
    if evidence.get("request_id") != request_id:
        raise CanvasStoreError(
            "reconciliation evidence belongs to a different request",
            code="reconcile_request_mismatch",
            status=400,
        )
    if evidence.get("remote_status") != status:
        raise CanvasStoreError(
            "reconciliation evidence status does not match the requested result",
            code="reconcile_status_mismatch",
            status=400,
        )
    source = evidence.get("source")
    if source not in {"provider_history", "provider_response", "operator_confirmation"}:
        raise CanvasStoreError(
            "reconciliation evidence source is not permitted",
            code="reconcile_source_type",
            status=400,
        )
    reason = evidence.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise CanvasStoreError(
            "reconciliation evidence requires a non-empty reason",
            code="reconcile_reason_required",
            status=400,
        )


def _validate_reconcile_arguments(
    status: Any,
    evidence: Any,
    outputs: Any,
    provider_task_id: Any,
    owner_token: Any,
    recovery_token: Any,
) -> str:
    """Validate request-shaped reconciliation values before reading a row."""

    status = _require_status(status)
    if status not in {"succeeded", "failed", "cancelled"}:
        raise CanvasStoreError(
            "reconciliation status must be succeeded, failed or cancelled",
            code="reconcile_status",
            status=400,
        )
    _validate_evidence_input(evidence)
    if outputs is not None:
        _validate_outputs(outputs)
    if provider_task_id is not _UNSET and provider_task_id is not None:
        if not isinstance(provider_task_id, str):
            raise CanvasStoreError(
                "provider_task_id must be a string or null",
                code="provider_task_id_type",
                status=400,
            )
    if owner_token is not None:
        _require_owner_token(owner_token)
    if recovery_token is not None:
        _require_owner_token(recovery_token)
    return status


def _validate_reconcile_row(
    row: Mapping[str, Any],
    run_id: str,
    status: str,
    evidence: Any,
    outputs: Sequence[Mapping[str, Any]] | None,
    provider_task_id: str | object | None,
    owner_token: str | None,
    recovery_token: str | None,
) -> None:
    """Apply row-dependent reconciliation rules for preflight and commit."""

    if not _is_recoverable_row(row):
        raise RunStateError(
            f"run {run_id} has no bounded provider-result recovery path",
            code="run_not_recoverable",
        )
    _validate_reconcile_evidence(evidence, row["request_id"], status)
    authorized = (owner_token is not None and row["owner_token"] == owner_token) or (
        recovery_token is not None and row["recovery_token"] == recovery_token
    )
    if not authorized:
        raise CanvasStoreError(
            "the original owner or a recovery token is required to reconcile this run",
            code="recovery_access_required",
            status=403,
        )
    current_outputs = _load(row["outputs"], "outputs")
    effective_outputs = current_outputs if outputs is None else list(outputs)
    if status == "succeeded" and not effective_outputs:
        raise CanvasStoreError(
            "a succeeded reconciliation must include a non-empty output list",
            code="outputs_required",
            status=400,
        )
    if (
        provider_task_id is not _UNSET
        and provider_task_id is not None
        and row["provider_task_id"] is not None
        and provider_task_id != row["provider_task_id"]
    ):
        raise RunStateError(
            "reconciliation cannot replace the original provider task id",
            code="provider_task_conflict",
        )


def _append_evidence(
    existing: Any, evidence: Any, stage: str | None, timestamp: str
) -> list[dict[str, Any]]:
    if isinstance(existing, list):
        history = list(existing)
    elif existing is None:
        history = []
    else:
        history = [{"recorded_at": timestamp, "stage": stage, "data": existing}]
    if isinstance(evidence, Sequence) and not isinstance(
        evidence, (str, bytes, bytearray, Mapping)
    ):
        items = list(evidence)
    else:
        items = [evidence]
    for item in items:
        if isinstance(item, Mapping):
            entry = dict(item)
            entry.setdefault("recorded_at", timestamp)
            if stage is not None:
                entry.setdefault("stage", stage)
        else:
            entry = {"recorded_at": timestamp, "stage": stage, "data": item}
        history.append(entry)
    return history


def _evidence_duplicate(existing: Any, evidence: Any, stage: str | None) -> bool:
    """Return whether ``evidence`` is already the most recent entry.

    Progress writers often observe the same provider line more than once.
    Treating that write as a no-op keeps the event stream compact while still
    preserving genuinely new evidence entries.
    """

    if not isinstance(existing, list) or not existing:
        return False
    if isinstance(evidence, Sequence) and not isinstance(
        evidence, (str, bytes, bytearray, Mapping)
    ):
        items = list(evidence)
    else:
        items = [evidence]
    if len(items) != 1:
        return False
    item = items[0]
    last = existing[-1]
    if isinstance(item, Mapping) and isinstance(last, Mapping):
        previous = dict(last)
        previous.pop("recorded_at", None)
        previous.pop("stage", None)
        return _canonical_json(previous) == _canonical_json(dict(item))
    return isinstance(last, Mapping) and last.get("data") == item


def _is_recoverable_row(row: Mapping[str, Any]) -> bool:
    """Check the narrow late-result recovery exception for a failed run."""

    status = row["status"]
    if status == "unknown":
        return True
    if status != "failed" or row["stage"] not in {"collection", "media_validation"}:
        return False
    try:
        history = _load(row["evidence"] or "[]", "evidence")
    except CanvasStoreError:
        return False
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes, bytearray)):
        return False
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("remote_finished") is True:
            return True
        nested = entry.get("evidence")
        if isinstance(nested, Mapping) and nested.get("remote_finished") is True:
            return True
    return False


def _run_holds_generation_resource(row: Mapping[str, Any]) -> bool:
    """Return whether a live run still occupies its generation resource.

    An unknown run always occupies its resource because the store cannot prove
    that remote work ended.  A running run releases the generation resource
    only after it has entered collection or media validation and durable
    evidence records that the provider finished.  Parse failures remain
    conservative and keep the resource occupied.
    """

    status = row["status"]
    if status == "unknown":
        return True
    if status != "running":
        return False
    if row["stage"] not in {"collection", "media_validation"}:
        return True
    try:
        history = _load(row["evidence"] or "[]", "evidence")
    except CanvasStoreError:
        return True
    if isinstance(history, Mapping):
        history = [history]
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes, bytearray)):
        return True
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("remote_finished") is True:
            return False
        nested = entry.get("evidence")
        if isinstance(nested, Mapping) and nested.get("remote_finished") is True:
            return False
    return True


def _review_decision(review: Mapping[str, Any]) -> str:
    raw = review.get("decision")
    return raw.upper() if isinstance(raw, str) else ""


def _review_binding(review: Mapping[str, Any]) -> tuple[str | None, str | None]:
    path = review.get("output_path")
    digest = review.get("output_sha256")
    return (
        path if isinstance(path, str) else None,
        digest if isinstance(digest, str) else None,
    )


def _validate_review(review: Any) -> dict[str, Any]:
    if not isinstance(review, Mapping):
        raise CanvasStoreError("review must be an object", code="review_type", status=400)
    normalized = dict(review)
    unknown_fields = set(normalized).difference(
        {"decision", "output_path", "output_sha256", "evidence", "end_state", "unverified"}
    )
    if unknown_fields:
        raise CanvasStoreError(
            f"review contains unsupported fields: {sorted(unknown_fields)}",
            code="review_field_type",
            status=400,
        )
    decision = _review_decision(normalized)
    if decision not in _REVIEW_DECISIONS:
        raise CanvasStoreError(
            "review decision must be ACCEPT, REJECT or INCONCLUSIVE",
            code="review_decision_type",
            status=400,
        )
    # Keep the public schema stable even if a caller supplied status as an alias.
    normalized["decision"] = decision
    path, digest = _review_binding(normalized)
    if not path or not digest:
        raise CanvasStoreError(
            "review must bind output_path and output_sha256",
            code="review_output_binding_required",
            status=400,
        )
    evidence = normalized.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
        raise CanvasStoreError(
            "review evidence must be an array", code="review_evidence_type", status=400
        )
    if len(evidence) == 0:
        raise CanvasStoreError(
            "review evidence must not be empty", code="review_evidence_required", status=400
        )
    if "end_state" in normalized and not isinstance(normalized["end_state"], Mapping):
        raise CanvasStoreError(
            "review end_state must be an object", code="review_end_state_type", status=400
        )
    unverified = normalized.get("unverified", [])
    if not isinstance(unverified, Sequence) or isinstance(unverified, (str, bytes, bytearray)):
        raise CanvasStoreError(
            "review unverified must be an array", code="review_unverified_type", status=400
        )
    if decision == "ACCEPT" and len(unverified) > 0:
        raise CanvasStoreError(
            "ACCEPT cannot contain unverified review items",
            code="review_unverified",
            status=400,
        )
    _dump(normalized)
    return normalized


def _same_review_binding(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    l_path, l_digest = _review_binding(left)
    r_path, r_digest = _review_binding(right)
    return l_path == r_path and (l_digest or "").lower() == (r_digest or "").lower()


def _require_event_id(value: Any, field: str, *, allow_zero: bool) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise CanvasStoreError(
            f"{field} must be a {'non-negative' if allow_zero else 'positive'} integer",
            code="event_id_type",
            status=400,
        )
    return value


def _require_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 1000:
        raise CanvasStoreError(
            "limit must be an integer from 1 to 1000", code="limit_type", status=400
        )
    return value


def _require_consumer_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanvasStoreError(
            "consumer_id must be a non-empty string", code="consumer_id_type", status=400
        )
    return value


def _require_continuation_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanvasStoreError(
            "continuation_id must be a non-empty string",
            code="continuation_id_type",
            status=400,
        )
    return value


def _require_continuation_session(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_CONTINUATION_SESSION_LENGTH
    ):
        raise CanvasStoreError(
            "session_id must be a non-empty string no longer than 256 characters",
            code="continuation_session_type",
            status=400,
        )
    return value


def _require_continuation_authorization(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_CONTINUATION_AUTHORIZATION_LENGTH
    ):
        raise CanvasStoreError(
            "authorization must be a non-empty string no longer than 8192 characters",
            code="continuation_authorization_type",
            status=400,
        )
    return value


def _require_continuation_node_ids(value: Any) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise CanvasStoreError(
            "node_ids must be a non-empty array",
            code="continuation_node_ids_type",
            status=400,
        )
    if not 0 < len(value) <= _MAX_CONTINUATION_NODE_IDS:
        raise CanvasStoreError(
            "node_ids must contain between 1 and 256 items",
            code="continuation_node_ids_type",
            status=400,
        )
    result: list[str] = []
    seen: set[str] = set()
    for node_id in value:
        if not isinstance(node_id, str) or not node_id.strip():
            raise CanvasStoreError(
                "node_ids must contain non-empty strings",
                code="continuation_node_ids_type",
                status=400,
            )
        node_id = node_id.strip()
        if node_id in seen:
            raise CanvasStoreError(
                "node_ids must not contain duplicates",
                code="continuation_node_ids_duplicate",
                status=400,
            )
        seen.add(node_id)
        result.append(node_id)
    return result


def _require_continuation_revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CanvasStoreError(
            "continuation revision must be a positive integer",
            code="continuation_revision_type",
            status=400,
        )
    return value


def _require_continuation_state(value: Any) -> str:
    if not isinstance(value, str) or value not in _CONTINUATION_STATES:
        raise CanvasStoreError(
            "continuation state must be active or paused",
            code="continuation_state_type",
            status=400,
        )
    return value


def _require_continuation_unit_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise CanvasStoreError(
            "unit_id must be a non-empty string no longer than 256 characters",
            code="continuation_unit_id_type",
            status=400,
        )
    return value


def _require_continuation_unit_state(value: Any) -> str:
    if not isinstance(value, str) or value not in _CONTINUATION_UNIT_STATES:
        raise CanvasStoreError(
            "unit state must be dispatched, result_ready, handled or blocked",
            code="continuation_unit_state_type",
            status=400,
        )
    return value


def _optional_continuation_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise CanvasStoreError(
            f"{field} must be a non-empty string or null",
            code="continuation_field_type",
            status=400,
        )
    return value.strip()


def _optional_continuation_reason(value: Any) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_CONTINUATION_REASON_LENGTH
    ):
        raise CanvasStoreError(
            "continuation reason must be a non-empty string or null",
            code="continuation_reason_type",
            status=400,
        )
    return value.strip()


def _require_continuation_reason(value: Any) -> str:
    reason = _optional_continuation_reason(value)
    if reason is None:
        raise CanvasStoreError(
            "continuation reason must be a non-empty string",
            code="continuation_reason_required",
            status=400,
        )
    return reason


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
