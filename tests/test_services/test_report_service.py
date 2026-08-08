"""Tests for Wave 3: ReportService."""
from __future__ import annotations

import pytest

from lfo.core.database import Database
from lfo.services.report_service import ReportService


@pytest.fixture
def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name, status) VALUES (?, ?, ?)",
               ("proj-1", "Test Project", "active"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-1", "proj-1", "h3_t2va", "SUCCEEDED"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-2", "proj-1", "h3_i2v", "FAILED_RETRYABLE"))
    db.execute("INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, content_hash, dependency_hash, params_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
               ("att-1", "task-1", "ik-1", "COMPLETED", "ch", "dh", "ph"))
    db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path) VALUES (?, ?, ?, ?)",
               ("asset-1", "task-1", "video", "/tmp/v1.mp4"))
    db.execute("INSERT INTO qc_reports (report_id, task_id, asset_id, status, checks, issues) VALUES (?, ?, ?, ?, ?, ?)",
               ("qc-1", "task-1", "asset-1", "PASS", "{}", "[]"))
    return db


class TestExecutionSummary:
    def test_summary_structure(self, db):
        svc = ReportService(db)
        result = svc.execution_summary("proj-1")
        assert result["project_id"] == "proj-1"
        assert result["project_name"] == "Test Project"
        assert result["total_tasks"] == 2
        assert result["completed_tasks"] == 1
        assert result["failed_tasks"] == 1

    def test_success_rate(self, db):
        svc = ReportService(db)
        result = svc.execution_summary("proj-1")
        assert result["success_rate"] == 50.0

    def test_tasks_by_status(self, db):
        svc = ReportService(db)
        result = svc.execution_summary("proj-1")
        assert result["tasks_by_status"]["SUCCEEDED"] == 1
        assert result["tasks_by_status"]["FAILED_RETRYABLE"] == 1


class TestQCSummary:
    def test_qc_summary(self, db):
        svc = ReportService(db)
        result = svc.qc_summary("proj-1")
        assert result["total_checks"] == 1
        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["pass_rate"] == 100.0


class TestAssetLineageReport:
    def test_lineage_report(self, db):
        svc = ReportService(db)
        result = svc.asset_lineage_report("proj-1")
        assert "export_assets" in result


class TestEnvironmentSummary:
    def test_env_summary(self, db):
        svc = ReportService(db)
        result = svc.environment_summary("proj-1")
        assert result["project_id"] == "proj-1"


class TestMarkdown:
    def test_markdown_output(self, db):
        svc = ReportService(db)
        md = svc.execution_summary_md("proj-1")
        assert "# Execution Summary" in md
        assert "Test Project" in md
        assert "50.0%" in md
