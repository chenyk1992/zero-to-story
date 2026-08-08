"""Tests for report export to disk."""
from __future__ import annotations

import json

import pytest

from lfo.core.database import Database
from lfo.services.report_service import ReportService


@pytest.fixture
def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test Film"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-1", "proj-1", "h3_t2va", "SUCCEEDED"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-2", "proj-1", "h3_i2v", "RUNNING"))
    db.execute("INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, content_hash, dependency_hash, params_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
               ("att-1", "task-1", "ik-1", "COMPLETED", "ch", "dh", "ph"))
    db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path) VALUES (?, ?, ?, ?)",
               ("asset-1", "task-1", "video", "/tmp/v1.mp4"))
    db.execute("INSERT INTO qc_reports (report_id, task_id, asset_id, status, checks, issues) VALUES (?, ?, ?, ?, ?, ?)",
               ("qc-1", "task-1", "asset-1", "PASS", "{}", "[]"))
    return db


class TestExportToDisk:
    def test_export_creates_directory(self, db, tmp_path):
        svc = ReportService(db)
        output_dir = str(tmp_path / "reports" / "proj-1")
        result = svc.export_to_disk("proj-1", output_dir)
        assert result["success"]
        assert result["file_count"] == 5

    def test_export_writes_json_files(self, db, tmp_path):
        svc = ReportService(db)
        output_dir = str(tmp_path / "reports")
        result = svc.export_to_disk("proj-1", output_dir)

        for report_name in ["execution_summary", "asset_lineage", "qc_summary", "environment_summary"]:
            file_path = result["files_written"][report_name]
            assert os.path.exists(file_path)
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["project_id"] == "proj-1"

    def test_export_writes_markdown(self, db, tmp_path):
        svc = ReportService(db)
        output_dir = str(tmp_path / "reports")
        result = svc.export_to_disk("proj-1", output_dir)

        md_path = result["files_written"]["execution_summary_md"]
        assert os.path.exists(md_path)
        content = open(md_path, encoding="utf-8").read()
        assert "# Execution Summary" in content
        assert "Test Film" in content

    def test_export_returns_paths(self, db, tmp_path):
        svc = ReportService(db)
        output_dir = str(tmp_path / "reports")
        result = svc.export_to_disk("proj-1", output_dir)

        assert "output_dir" in result
        assert "files_written" in result
        assert result["file_count"] == 5

    def test_export_empty_project(self, db, tmp_path):
        db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("empty-proj", "Empty"))
        svc = ReportService(db)
        output_dir = str(tmp_path / "reports")
        result = svc.export_to_disk("empty-proj", output_dir)
        assert result["success"]
        assert result["file_count"] == 5


import os
