"""Tests for Wave 3: extended status panel."""
from __future__ import annotations

import pytest

from lfo.cli.status_cmd import _compute_phase, cmd_status


@pytest.fixture
def db(tmp_path):
    from lfo.core.database import Database
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name, status) VALUES (?, ?, ?)",
               ("proj-1", "Test Project", "active"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, priority_class) VALUES (?, ?, ?, ?, ?)",
               ("task-1", "proj-1", "h3_t2va", "SUCCEEDED", 30))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, priority_class) VALUES (?, ?, ?, ?, ?)",
               ("task-2", "proj-1", "h3_i2v", "RUNNING", 30))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, priority_class) VALUES (?, ?, ?, ?, ?)",
               ("task-3", "proj-1", "h3_i2v", "WAITING_ASSETS", 30))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, priority_class) VALUES (?, ?, ?, ?, ?)",
               ("task-4", "proj-1", "h3_i2v", "FAILED_TERMINAL", 30))
    return db


class TestComputePhase:
    def test_empty(self):
        assert _compute_phase({}, 0) == "empty"

    def test_complete(self):
        assert _compute_phase({"SUCCEEDED": 5}, 5) == "complete"

    def test_running(self):
        assert _compute_phase({"SUCCEEDED": 3, "RUNNING": 2}, 5) == "running"

    def test_planned(self):
        assert _compute_phase({"PLANNED": 5}, 5) == "planned"

    def test_waiting(self):
        assert _compute_phase({"SUCCEEDED": 2, "WAITING_ASSETS": 3}, 5) == "waiting"

    def test_in_progress(self):
        assert _compute_phase({"SUCCEEDED": 2, "PLANNED": 3}, 5) == "in_progress"


class TestStatusPanel:
    def test_requires_project_id(self):
        result = cmd_status("")
        assert not result["success"]

    def test_project_not_found(self, tmp_path):
        from lfo.core.database import Database
        db = Database(str(tmp_path / "empty.db"))
        db.init_schema()
        result = cmd_status("nonexistent", str(tmp_path / "empty.db"))
        assert result["success"]
        assert result["message"] == "Project not found"

    def test_status_breakdown(self, db):
        result = cmd_status("proj-1", str(db.path))
        assert result["success"]
        assert result["total_tasks"] == 4
        assert result["tasks_by_status"]["SUCCEEDED"] == 1
        assert result["tasks_by_status"]["RUNNING"] == 1

    def test_blockers(self, db):
        db.execute("UPDATE tasks SET error = 'OOM' WHERE task_id = 'task-4'")
        result = cmd_status("proj-1", str(db.path))
        assert len(result["blockers"]) == 1
        assert result["blockers"][0]["task_id"] == "task-4"

    def test_next_actions(self, db):
        result = cmd_status("proj-1", str(db.path))
        assert len(result["next_actions"]) > 0

    def test_waiting_assets(self, db):
        result = cmd_status("proj-1", str(db.path))
        assert "task-3" in result["waiting_assets"]

    def test_phase(self, db):
        result = cmd_status("proj-1", str(db.path))
        assert result["phase"] == "running"

    def test_completion_pct(self, db):
        result = cmd_status("proj-1", str(db.path))
        assert result["completion_pct"] == 25.0
