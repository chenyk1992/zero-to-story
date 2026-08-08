"""Tests for CLI status command."""
from __future__ import annotations

from lfo.cli.status_cmd import cmd_status
from lfo.core.database import Database


def _seed_project(db: Database, project_id: str, num_tasks: int = 3):
    """Seed a project with tasks in various states."""
    db.execute(
        "INSERT OR IGNORE INTO projects (project_id, name) VALUES (?, ?)",
        (project_id, f"Project {project_id}"),
    )
    for i in range(num_tasks):
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
            (f"task_{i + 1}", project_id, "h3_t2va", "PLANNED"),
        )


class TestCmdStatus:
    """Test lfo status command."""

    def test_empty_project_id(self):
        result = cmd_status(project_id="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_no_tasks(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("empty-proj", "Empty"))
        result = cmd_status(project_id="empty-proj", db_path=db_path)
        assert result["success"] is True
        assert result["total_tasks"] == 0

    def test_with_tasks(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        db.init_schema()
        _seed_project(db, "proj-1", num_tasks=3)

        result = cmd_status(project_id="proj-1", db_path=db_path)

        assert result["success"] is True
        assert result["total_tasks"] == 3
        assert result["tasks_by_status"]["PLANNED"] == 3
        assert result["completion_pct"] == 0.0
        assert result["phase"] == "planned"

    def test_mixed_statuses(self, tmp_path):
        db_path = str(tmp_path / "test2.db")
        db = Database(db_path)
        db.init_schema()
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-2", "Test"))

        # Mix of statuses
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("t1", "proj-2", "h3_t2va", "SUCCEEDED"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("t2", "proj-2", "h3_t2va", "SUCCEEDED"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("t3", "proj-2", "h3_i2v", "RUNNING"))
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
                   ("t4", "proj-2", "h3_t2va", "PLANNED"))

        result = cmd_status(project_id="proj-2", db_path=db_path)

        assert result["total_tasks"] == 4
        assert result["completed"] == 2
        assert result["completion_pct"] == 50.0
        assert result["tasks_by_status"]["SUCCEEDED"] == 2
        assert result["tasks_by_status"]["RUNNING"] == 1
