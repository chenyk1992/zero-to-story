"""Tests for PDF/HTML report export."""
from __future__ import annotations

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


class TestPdfExport:
    def test_export_pdf(self, db, tmp_path):
        svc = ReportService(db)
        output_path = str(tmp_path / "report.pdf")
        result = svc.export_pdf("proj-1", output_path)

        assert result["success"]
        assert os.path.exists(result["output_file"])
        assert result["output_file"].endswith(".pdf")
        # PDF files start with %PDF
        with open(result["output_file"], "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_export_pdf_not_found(self, db, tmp_path):
        svc = ReportService(db)
        result = svc.export_pdf("nonexistent", str(tmp_path / "r.pdf"))
        assert result["success"]


class TestHtmlExport:
    def test_export_html(self, db, tmp_path):
        svc = ReportService(db)
        output_path = str(tmp_path / "report.html")
        result = svc.export_html("proj-1", output_path)

        assert result["success"]
        assert os.path.exists(result["output_file"])
        assert result["output_file"].endswith(".html")

        content = open(result["output_file"], encoding="utf-8").read()
        assert "<!DOCTYPE html>" in content
        assert "Test Film" in content
        assert "Overview" in content

    def test_export_html_escapes_content(self, db, tmp_path):
        db.execute("UPDATE projects SET name = ? WHERE project_id = ?",
                   ("<script>alert('xss')</script>", "proj-1"))
        svc = ReportService(db)
        output_path = str(tmp_path / "report.html")
        result = svc.export_html("proj-1", output_path)
        content = open(result["output_file"], encoding="utf-8").read()
        assert "<script>" not in content
        assert "&lt;script&gt;" in content


import os
