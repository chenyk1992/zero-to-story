"""Tests for finding tasks that should be released from upstream blocking.

When a task's only ``stuck`` upstream becomes ``SUCCEEDED`` (e.g. after
a manual retry) the downstream stays in ``PLANNED`` forever because
``promote_task_to_ready`` rejects dependencies that aren't in
``TASK_TERMINAL_STATES``. ``FAILED_RETRYABLE`` is a "retryable" state,
not "terminal", so downstreams of it never get unblocked.

This helper identifies PLANNED tasks whose upstream chain is
"effectively unblocked" — i.e. all dependencies are in the OK set
(``SUCCEEDED`` / ``APPROVED`` / ``FAILED_RETRYABLE``).
"""
from __future__ import annotations

import json

import pytest

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.services.pipeline_service import find_unblocked_tasks


@pytest.fixture
def db() -> Database:
    d = Database()
    d.init_schema()
    return d


def _make_task(
    db: Database,
    project_id: str,
    task_id: str,
    deps: list[str] | None = None,
    status: TaskStatus = TaskStatus.PLANNED,
) -> None:
    """Bypass full create_task because we want explicit deps + status control.

    Note: ``task_id`` must be globally unique across all tests in this
    session because the tasks table has a UNIQUE(task_id) constraint.
    """
    deps_json = json.dumps(deps or [])
    db.execute(
        """INSERT INTO tasks
           (task_id, project_id, task_type, status, dependencies,
            serial_group, priority_class, priority_override,
            content_hash, dependency_hash, params_hash, idempotency_key,
            created_at, updated_at)
           VALUES (?, ?, 'h3_t2va', ?, ?, NULL, 30, NULL,
                   ?, ?, ?, ?, '2026-01-01T00:00:00.000Z',
                   '2026-01-01T00:00:00.000Z')""",
        (
            task_id, project_id, status.value, deps_json,
            f"ch_{task_id}", f"dh_{task_id}", f"ph_{task_id}", f"ik_{task_id}",
        ),
    )


class TestFindUnblockedTasks:
    def test_empty_project_returns_no_tasks(self, db):
        result = find_unblocked_tasks(db, "proj-empty")
        assert result == []

    def test_planned_task_with_no_dependencies_is_unblocked(self, db):
        """A task with no upstream is trivially unblocked (it just needs promote)."""
        _make_task(db, "proj-1", "t1", deps=[])

        result = find_unblocked_tasks(db, "proj-1")

        assert [t["task_id"] for t in result] == ["t1"]

    def test_planned_task_with_succeeded_upstream_is_unblocked(self, db):
        _make_task(db, "proj-1", "up", deps=[], status=TaskStatus.SUCCEEDED)
        _make_task(db, "proj-1", "down", deps=["up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert [t["task_id"] for t in result] == ["down"]

    def test_planned_task_with_retryable_upstream_is_unblocked(self, db):
        """FAILED_RETRYABLE upstream should NOT permanently block downstream."""
        _make_task(db, "proj-1", "up", deps=[], status=TaskStatus.FAILED_RETRYABLE)
        _make_task(db, "proj-1", "down", deps=["up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert [t["task_id"] for t in result] == ["down"]

    def test_planned_task_with_approved_upstream_is_unblocked(self, db):
        _make_task(db, "proj-1", "up", deps=[], status=TaskStatus.APPROVED)
        _make_task(db, "proj-1", "down", deps=["up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert [t["task_id"] for t in result] == ["down"]

    def test_planned_task_with_terminal_failure_upstream_still_blocked(self, db):
        """FAILED_TERMINAL upstream = real block. Do not release."""
        _make_task(db, "proj-1", "up", deps=[], status=TaskStatus.FAILED_TERMINAL)
        _make_task(db, "proj-1", "down", deps=["up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert result == []

    def test_planned_task_with_stale_upstream_still_blocked(self, db):
        """STALE = explicit user/action decision, must not be auto-released."""
        _make_task(db, "proj-1", "up", deps=[], status=TaskStatus.STALE)
        _make_task(db, "proj-1", "down", deps=["up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert result == []

    def test_planned_task_with_mixed_upstream_partial_ok_still_blocked(self, db):
        """One OK + one non-OK upstream = still blocked."""
        _make_task(db, "proj-1", "ok_up", deps=[], status=TaskStatus.SUCCEEDED)
        _make_task(db, "proj-1", "bad_up", deps=[], status=TaskStatus.FAILED_TERMINAL)
        _make_task(db, "proj-1", "down", deps=["ok_up", "bad_up"], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-1")

        assert result == []

    def test_task_in_terminal_state_is_not_returned(self, db):
        """find_unblocked_tasks only surfaces PLANNED — terminal tasks are out of scope."""
        _make_task(db, "proj-1", "t", deps=[], status=TaskStatus.SUCCEEDED)

        result = find_unblocked_tasks(db, "proj-1")

        assert result == []

    def test_other_projects_tasks_are_excluded(self, db):
        _make_task(db, "proj-A", "down_a", deps=[], status=TaskStatus.PLANNED)
        _make_task(db, "proj-B", "down_b", deps=[], status=TaskStatus.PLANNED)

        result = find_unblocked_tasks(db, "proj-A")

        assert [t["task_id"] for t in result] == ["down_a"]
