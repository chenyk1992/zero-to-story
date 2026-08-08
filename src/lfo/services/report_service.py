"""ReportService — generate and export project delivery reports.

Generates:
- execution_summary.json / .md
- asset_lineage.json
- qc_summary.json
- environment_summary.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lfo.core.database import Database
from lfo.services.lineage_service import LineageService


@dataclass
class ExecutionSummary:
    """Aggregated execution report."""

    project_id: str
    project_name: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    success_rate: float = 0.0
    total_assets: int = 0
    total_attempts: int = 0
    generated_at: str = ""


@dataclass
class QCSummary:
    """Aggregated QC report."""

    project_id: str
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    reports: list[dict] = field(default_factory=list)


class ReportService:
    """Generate structured project reports."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.lineage = LineageService(db)

    def execution_summary(self, project_id: str) -> dict:
        """Generate execution summary."""
        proj = db_fetchone(self.db, "SELECT name, status FROM projects WHERE project_id = ?", (project_id,))
        project_name = proj[0] if proj else ""

        task_rows = self.db.fetchall(
            "SELECT status, COUNT(*) FROM tasks WHERE project_id = ? GROUP BY status",
            (project_id,),
        )
        by_status = {s: c for s, c in task_rows}
        total = sum(by_status.values())
        completed = by_status.get("SUCCEEDED", 0) + by_status.get("APPROVED", 0)
        failed = sum(c for s, c in by_status.items() if "FAILED" in s)
        rate = (completed / total * 100) if total > 0 else 0

        assets = db_fetchone(self.db, "SELECT COUNT(*) FROM assets a JOIN tasks t ON a.task_id = t.task_id WHERE t.project_id = ?", (project_id,))
        attempts = db_fetchone(self.db, "SELECT COUNT(*) FROM attempts a JOIN tasks t ON a.task_id = t.task_id WHERE t.project_id = ?", (project_id,))

        return {
            "project_id": project_id,
            "project_name": project_name,
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": round(rate, 1),
            "total_assets": assets[0] if assets else 0,
            "total_attempts": attempts[0] if attempts else 0,
            "tasks_by_status": by_status,
            "generated_at": _utc_now(),
        }

    def asset_lineage_report(self, project_id: str) -> dict:
        """Generate asset lineage report for all export assets."""
        export_assets = self.db.fetchall(
            """SELECT a.asset_id, a.file_path FROM assets a
               JOIN tasks t ON a.task_id = t.task_id
               WHERE t.project_id = ? AND a.asset_type = 'video'
               ORDER BY a.created_at DESC LIMIT 20""",
            (project_id,),
        )

        lineages = {}
        for asset_id, file_path in export_assets:
            flat = self.lineage.get_lineage_flat(asset_id)
            lineages[asset_id] = {
                "file_path": file_path,
                "upstream_count": len(flat) - 1,
                "lineage": flat,
            }

        return {
            "project_id": project_id,
            "export_assets": lineages,
            "generated_at": _utc_now(),
        }

    def qc_summary(self, project_id: str) -> dict:
        """Generate QC summary across all reports."""
        rows = self.db.fetchall(
            """SELECT qc.status, COUNT(*), GROUP_CONCAT(qc.issues)
               FROM qc_reports qc
               JOIN tasks t ON qc.task_id = t.task_id
               WHERE t.project_id = ?
               GROUP BY qc.status""",
            (project_id,),
        )

        total = 0
        passed = 0
        failed = 0
        for status, count, _ in rows:
            total += count
            if status == "PASS":
                passed += count
            else:
                failed += count

        rate = (passed / total * 100) if total > 0 else 0

        return {
            "project_id": project_id,
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(rate, 1),
            "by_status": {s: c for s, c, _ in rows},
            "generated_at": _utc_now(),
        }

    def environment_summary(self, project_id: str) -> dict:
        """Generate environment snapshot summary."""
        snapshots = self.db.fetchall(
            "SELECT snapshot_id, machine_id, captured_at FROM environment_snapshots ORDER BY captured_at DESC LIMIT 5",
        )

        return {
            "project_id": project_id,
            "snapshots": [
                {"snapshot_id": s[0], "machine_id": s[1], "captured_at": s[2]}
                for s in snapshots
            ],
            "generated_at": _utc_now(),
        }

    def generate_all(self, project_id: str) -> dict:
        """Generate all reports as a single bundle."""
        return {
            "execution_summary": self.execution_summary(project_id),
            "asset_lineage": self.asset_lineage_report(project_id),
            "qc_summary": self.qc_summary(project_id),
            "environment_summary": self.environment_summary(project_id),
        }

    def execution_summary_md(self, project_id: str) -> str:
        """Generate human-readable Markdown execution summary."""
        summary = self.execution_summary(project_id)
        lines = [
            f"# Execution Summary: {summary['project_name']}",
            "",
            f"**Project ID:** {summary['project_id']}",
            f"**Generated:** {summary['generated_at']}",
            "",
            "## Overview",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tasks | {summary['total_tasks']} |",
            f"| Completed | {summary['completed_tasks']} |",
            f"| Failed | {summary['failed_tasks']} |",
            f"| Success Rate | {summary['success_rate']}% |",
            f"| Total Assets | {summary['total_assets']} |",
            f"| Total Attempts | {summary['total_attempts']} |",
            "",
            "## Task Breakdown",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]
        for status, count in sorted(summary.get("tasks_by_status", {}).items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")
        return "\n".join(lines)

    def export_to_disk(self, project_id: str, output_dir: str) -> dict:
        """Generate all reports and write them to disk.

        Args:
            project_id: The project to report on.
            output_dir: Directory path where reports will be written.

        Returns:
            dict with file paths written and status.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        reports = self.generate_all(project_id)
        files_written = {}

        # Write JSON reports
        for report_name, report_data in reports.items():
            file_path = out_path / f"{report_name}.json"
            file_path.write_text(
                json.dumps(report_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            files_written[report_name] = str(file_path)

        # Write Markdown execution summary
        md_content = self.execution_summary_md(project_id)
        md_path = out_path / "execution_summary.md"
        md_path.write_text(md_content, encoding="utf-8")
        files_written["execution_summary_md"] = str(md_path)

        return {
            "success": True,
            "project_id": project_id,
            "output_dir": str(out_path.absolute()),
            "files_written": files_written,
            "file_count": len(files_written),
        }

    def export_pdf(self, project_id: str, output_path: str) -> dict:
        """Generate a PDF report."""
        from lfo.services.report_renderer import render_pdf

        reports = self.generate_all(project_id)
        written = render_pdf(reports, output_path)
        return {
            "success": True,
            "project_id": project_id,
            "output_file": written,
        }

    def export_html(self, project_id: str, output_path: str) -> dict:
        """Generate an HTML report."""
        from lfo.services.report_renderer import render_html

        reports = self.generate_all(project_id)
        written = render_html(reports, output_path)
        return {
            "success": True,
            "project_id": project_id,
            "output_file": written,
        }


def db_fetchone(db: Database, sql: str, params: tuple = ()):
    """Helper to fetch one row."""
    return db.fetchone(sql, params)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
