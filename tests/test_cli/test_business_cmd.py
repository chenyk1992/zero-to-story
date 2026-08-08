"""Tests for Wave 3: business commands."""
from __future__ import annotations

from lfo.cli.business_cmd import cmd_attempts_list, cmd_continuity_inspect, cmd_recover, cmd_retry
from lfo.cli.edit_cmd import cmd_edit_select


class TestEditSelect:
    def test_requires_args(self):
        result = cmd_edit_select("", "", "")
        assert not result["success"]

    def test_invalid_asset(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        result = cmd_edit_select("proj-1", "shot-1", "nonexistent", db_path=str(tmp_path / "test.db"))
        assert not result["success"]


class TestRetry:
    def test_requires_task_id(self):
        result = cmd_retry("")
        assert not result["success"]

    def test_classifies_transient(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, error) VALUES (?, ?, ?, ?, ?)",
                   ("task-1", "proj-1", "video", "FAILED_RETRYABLE", "Connection timeout"))
        result = cmd_retry("task-1", str(tmp_path / "test.db"))
        assert result["success"]
        assert result["classification"] == "transient"
        assert result["action"] == "retry_transient"

    def test_classifies_persistent(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, error) VALUES (?, ?, ?, ?, ?)",
                   ("task-1", "proj-1", "video", "FAILED_TERMINAL", "Asset not found"))
        result = cmd_retry("task-1", str(tmp_path / "test.db"))
        assert result["success"]
        assert result["classification"] == "persistent"


class TestRecover:
    def test_requires_project_id(self):
        result = cmd_recover("")
        assert not result["success"]

    def test_finds_failed_tasks(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, error) VALUES (?, ?, ?, ?, ?)",
                   ("task-1", "proj-1", "video", "FAILED_RETRYABLE", "Timeout"))
        result = cmd_recover("proj-1", str(tmp_path / "test.db"))
        assert result["success"]
        assert result["failed_count"] == 1
        assert len(result["plans"]) == 1


class TestContinuityInspect:
    def test_requires_project_id(self):
        result = cmd_continuity_inspect("")
        assert not result["success"]

    def test_empty_project(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
        result = cmd_continuity_inspect("proj-1", str(tmp_path / "test.db"))
        assert result["success"]
        assert result["pending_count"] == 0


class TestAttemptsList:
    def test_requires_task_id(self):
        result = cmd_attempts_list("")
        assert not result["success"]

    def test_no_attempts(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.init_schema()
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("task-1", "proj-1", "video", "PLANNED"))
        result = cmd_attempts_list("task-1", str(tmp_path / "test.db"))
        assert result["success"]
        assert result["attempt_count"] == 0
