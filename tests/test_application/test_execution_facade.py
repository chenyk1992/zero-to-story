"""Tests for ExecutionFacade."""
from __future__ import annotations

import uuid

import pytest

from lfo.application.execution_facade import ExecutionFacade
from lfo.core.database import Database
from lfo.core.state_machine import SubmissionState, TaskStatus


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def facade(db: Database) -> ExecutionFacade:
    return ExecutionFacade(db)


def _create_project(db: Database, project_id: str = "proj-1") -> None:
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (project_id, "Test Project"),
    )


def _create_ready_task(db: Database, task_id: str = "task-1") -> None:
    """Create a task in READY state with all required fields."""
    _create_project(db)
    db.execute(
        """INSERT INTO tasks
           (task_id, project_id, task_type, status, params_hash, idempotency_key,
            dependency_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, "proj-1", "h3_i2v", TaskStatus.READY.value,
         "params-hash-123", "idem-key-456", "dep-hash-789"),
    )


def _create_materialization(
    db: Database,
    task_id: str = "task-1",
    env_hash: str = "env-hash-abc",
) -> str:
    """Create a task materialization. Returns snapshot_id."""
    snapshot_id = uuid.uuid4().hex
    # Create snapshot
    db.execute(
        """INSERT INTO environment_snapshots
           (snapshot_id, machine_id, captured_at, snapshot_json,
            execution_environment_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (snapshot_id, "local", "2026-01-01T00:00:00.000000Z",
         "{}", env_hash),
    )
    # Create materialization
    mat_id = uuid.uuid4().hex
    db.execute(
        """INSERT INTO task_materializations
           (materialization_id, task_id, project_id, workflow_id,
            params, params_hash, idempotency_key,
            environment_snapshot_id, environment_execution_hash,
            binding_snapshot, prompt_snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (mat_id, task_id, "proj-1", "h3_standard_i2v",
         '{"prompt": "test"}', "params-hash-123", "idem-key-456",
         snapshot_id, env_hash, "{}", "{}"),
    )
    return snapshot_id


class TestRunReadyTask:
    def test_successful_submission(self, facade: ExecutionFacade, db: Database):
        """Full flow: READY task → RUNNING with attempt + journal."""
        _create_ready_task(db)
        _create_materialization(db)

        result = facade.run_ready_task("task-1")

        assert result.success
        assert result.task_id == "task-1"
        assert result.attempt_id != ""
        assert result.prompt_id != ""
        assert result.status == SubmissionState.SUBMITTED.value

        # Verify task is now RUNNING
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-1",))
        assert row[0] == TaskStatus.RUNNING.value

        # Verify attempt was created
        attempt = db.fetchone(
            "SELECT status, workflow_id FROM attempts WHERE task_id = ?",
            ("task-1",),
        )
        assert attempt is not None
        assert attempt[0] == SubmissionState.SUBMITTED.value
        assert attempt[1] == "h3_standard_i2v"

        # Verify journal entry
        journal = db.fetchone(
            "SELECT state, provider_job_id FROM submission_journal WHERE task_id = ?",
            ("task-1",),
        )
        assert journal is not None
        assert journal[0] == SubmissionState.SUBMITTED.value

    def test_task_not_found(self, facade: ExecutionFacade):
        result = facade.run_ready_task("nonexistent")
        assert not result.success
        assert "not found" in result.message

    def test_task_not_ready(self, facade: ExecutionFacade, db: Database):
        _create_project(db)
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
            ("task-1", "proj-1", "h3_i2v", TaskStatus.PLANNED.value),
        )
        result = facade.run_ready_task("task-1")
        assert not result.success
        assert "expected READY" in result.message

    def test_no_materialization(self, facade: ExecutionFacade, db: Database):
        _create_ready_task(db)
        # No materialization created
        result = facade.run_ready_task("task-1")
        assert not result.success
        assert "No materialization" in result.message

    def test_environment_changed(self, facade: ExecutionFacade, db: Database):
        """Task is marked STALE when environment hash doesn't match."""
        _create_ready_task(db)
        _create_materialization(db, env_hash="old-env-hash")
        # Update snapshot with different hash
        db.execute(
            "UPDATE environment_snapshots SET execution_environment_hash = ? WHERE snapshot_id = (SELECT environment_snapshot_id FROM task_materializations WHERE task_id = ?)",
            ("new-env-hash", "task-1"),
        )
        # Also update materialization to have old hash
        db.execute(
            "UPDATE task_materializations SET environment_execution_hash = ? WHERE task_id = ?",
            ("old-env-hash", "task-1"),
        )

        result = facade.run_ready_task("task-1")
        assert not result.success
        assert "ENVIRONMENT_CHANGED" in result.message

        # Verify task is now STALE
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-1",))
        assert row[0] == TaskStatus.STALE.value


class TestRecoverAttempt:
    def test_recover_uncertain_with_prompt_id(self, facade: ExecutionFacade, db: Database):
        """Recover an uncertain attempt that has a prompt_id."""
        _create_ready_task(db)
        snapshot_id = _create_materialization(db)

        # Create an attempt
        attempt_id = uuid.uuid4().hex
        db.execute(
            """INSERT INTO attempts
               (attempt_id, task_id, idempotency_key, workflow_id, params,
                content_hash, dependency_hash, params_hash, status,
                environment_snapshot_id, execution_environment_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (attempt_id, "task-1", "idem", "wf1", "{}", "ch", "dh", "ph",
             SubmissionState.PREPARED.value, snapshot_id, "env-hash"),
        )

        # Create uncertain journal entry with prompt_id
        journal_id = uuid.uuid4().hex
        prompt_id = "recoverable-prompt-123"
        db.execute(
            """INSERT INTO submission_journal
               (journal_id, attempt_id, task_id, state, from_state,
                provider_job_id, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (journal_id, attempt_id, "task-1",
             SubmissionState.SUBMISSION_UNCERTAIN.value,
             SubmissionState.PREPARED.value, prompt_id,
             "2026-01-01T00:00:00.000000Z"),
        )

        result = facade.recover_attempt(attempt_id)
        assert result.success
        assert result.prompt_id == prompt_id
        assert result.details.get("recovered") is True

    def test_recover_non_recoverable(self, facade: ExecutionFacade, db: Database):
        """Cannot recover an attempt without uncertain state."""
        _create_ready_task(db)
        snapshot_id = _create_materialization(db)

        attempt_id = uuid.uuid4().hex
        db.execute(
            """INSERT INTO attempts
               (attempt_id, task_id, idempotency_key, workflow_id, params,
                content_hash, dependency_hash, params_hash, status,
                environment_snapshot_id, execution_environment_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (attempt_id, "task-1", "idem", "wf1", "{}", "ch", "dh", "ph",
             SubmissionState.FAILED.value, snapshot_id, "env-hash"),
        )

        result = facade.recover_attempt(attempt_id)
        assert not result.success
        assert "cannot be recovered" in result.message

    def test_recover_nonexistent_attempt(self, facade: ExecutionFacade):
        result = facade.recover_attempt("nonexistent")
        assert not result.success
        assert "not found" in result.message
