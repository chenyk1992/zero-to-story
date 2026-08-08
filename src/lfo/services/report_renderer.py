"""ReportRenderer — generate PDF and HTML reports from report data.

Uses reportlab for PDF composition and a built-in HTML template for web viewing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def render_pdf(report_data: dict, output_path: str) -> str:
    """Render a full project report as a PDF file.

    Args:
        report_data: Bundle from ReportService.generate_all()
        output_path: File path for the PDF output.

    Returns:
        Absolute path to the written PDF.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], spaceAfter=12,
        textColor=colors.HexColor("#1a1a2e"),
    )
    heading_style = ParagraphStyle(
        "Heading", parent=styles["Heading2"], spaceAfter=6, spaceBefore=12,
        textColor=colors.HexColor("#16213e"),
    )
    body_style = styles["BodyText"]

    story = []

    # Title
    exec_summary = report_data.get("execution_summary", {})
    project_name = exec_summary.get("project_name", "Project")
    story.append(Paragraph(f"Project Report: {project_name}", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        body_style,
    ))
    story.append(Spacer(1, 12))

    # Execution Summary
    story.append(Paragraph("Execution Summary", heading_style))
    summary_table = _build_summary_table(exec_summary)
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # Task Breakdown
    tasks_by_status = exec_summary.get("tasks_by_status", {})
    if tasks_by_status:
        story.append(Paragraph("Task Breakdown", heading_style))
        task_data = [["Status", "Count"]]
        for status, count in sorted(tasks_by_status.items()):
            task_data.append([status, str(count)])
        task_table = Table(task_data, colWidths=[150, 80])
        task_table.setStyle(_table_style())
        story.append(task_table)

    story.append(PageBreak())

    # QC Summary
    qc = report_data.get("qc_summary", {})
    if qc.get("total_checks", 0) > 0:
        story.append(Paragraph("Quality Control", heading_style))
        qc_data = [
            ["Metric", "Value"],
            ["Total Checks", str(qc.get("total_checks", 0))],
            ["Passed", str(qc.get("passed", 0))],
            ["Failed", str(qc.get("failed", 0))],
            ["Pass Rate", f"{qc.get('pass_rate', 0)}%"],
        ]
        qc_table = Table(qc_data, colWidths=[150, 80])
        qc_table.setStyle(_table_style())
        story.append(qc_table)
        story.append(Spacer(1, 12))

    # Asset Lineage
    lineage = report_data.get("asset_lineage", {})
    export_assets = lineage.get("export_assets", {})
    if export_assets:
        story.append(Paragraph("Asset Lineage", heading_style))
        for asset_id, info in list(export_assets.items())[:10]:
            story.append(Paragraph(
                f"<b>{asset_id[:12]}...</b> — {info.get('upstream_count', 0)} upstream assets",
                body_style,
            ))
            story.append(Paragraph(
                f"File: {info.get('file_path', '?')}", body_style,
            ))
            story.append(Spacer(1, 4))

    # Environment
    env = report_data.get("environment_summary", {})
    snapshots = env.get("snapshots", [])
    if snapshots:
        story.append(Paragraph("Environment", heading_style))
        for snap in snapshots[:5]:
            story.append(Paragraph(
                f"Machine: {snap.get('machine_id', '?')} — {snap.get('captured_at', '?')}",
                body_style,
            ))

    doc.build(story)
    return str(output.absolute())


def render_html(report_data: dict, output_path: str) -> str:
    """Render a full project report as an HTML file.

    Args:
        report_data: Bundle from ReportService.generate_all()
        output_path: File path for the HTML output.

    Returns:
        Absolute path to the written HTML.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    exec_summary = report_data.get("execution_summary", {})
    qc = report_data.get("qc_summary", {})
    lineage = report_data.get("asset_lineage", {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Project Report: {_esc(exec_summary.get('project_name', 'Project'))}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
h2 {{ color: #16213e; margin-top: 32px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
th {{ background: #f5f5f5; font-weight: 600; }}
.metric {{ display: inline-block; margin: 8px 16px 8px 0; padding: 12px 16px; background: #f0f4ff; border-radius: 6px; }}
.metric-value {{ font-size: 24px; font-weight: 700; color: #1a1a2e; }}
.metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
.section {{ margin: 24px 0; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
.tag-pass {{ background: #e6f4ea; color: #137333; }}
.tag-fail {{ background: #fce8e6; color: #c5221f; }}
</style>
</head>
<body>
<h1>Project Report: {_esc(exec_summary.get('project_name', 'Project'))}</h1>
<p>Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="section">
<h2>Overview</h2>
<div class="metric"><div class="metric-value">{exec_summary.get('total_tasks', 0)}</div><div class="metric-label">Total Tasks</div></div>
<div class="metric"><div class="metric-value">{exec_summary.get('completed_tasks', 0)}</div><div class="metric-label">Completed</div></div>
<div class="metric"><div class="metric-value">{exec_summary.get('success_rate', 0)}%</div><div class="metric-label">Success Rate</div></div>
<div class="metric"><div class="metric-value">{exec_summary.get('total_assets', 0)}</div><div class="metric-label">Assets</div></div>
</div>

<div class="section">
<h2>Task Breakdown</h2>
{_html_task_table(exec_summary.get('tasks_by_status', {}))}
</div>
"""

    if qc.get("total_checks", 0) > 0:
        html += f"""
<div class="section">
<h2>Quality Control</h2>
<p>
<span class="tag tag-pass">Passed: {qc.get('passed', 0)}</span>
<span class="tag tag-fail">Failed: {qc.get('failed', 0)}</span>
 — Pass Rate: <b>{qc.get('pass_rate', 0)}%</b>
</p>
</div>
"""

    export_assets = lineage.get("export_assets", {})
    if export_assets:
        html += """
<div class="section">
<h2>Asset Lineage</h2>
<table>
<tr><th>Asset ID</th><th>File</th><th>Upstream</th></tr>
"""
        for asset_id, info in list(export_assets.items())[:20]:
            html += f"<tr><td>{asset_id[:16]}...</td><td>{_esc(info.get('file_path', '?'))}</td><td>{info.get('upstream_count', 0)}</td></tr>\n"
        html += "</table></div>\n"

    html += "</body></html>"

    output.write_text(html, encoding="utf-8")
    return str(output.absolute())


def _build_summary_table(exec_summary: dict):
    """Build the execution summary metrics table."""
    from reportlab.platypus import Table
    data = [
        ["Metric", "Value"],
        ["Total Tasks", str(exec_summary.get("total_tasks", 0))],
        ["Completed", str(exec_summary.get("completed_tasks", 0))],
        ["Failed", str(exec_summary.get("failed_tasks", 0))],
        ["Success Rate", f"{exec_summary.get('success_rate', 0)}%"],
        ["Total Assets", str(exec_summary.get("total_assets", 0))],
        ["Total Attempts", str(exec_summary.get("total_attempts", 0))],
    ]
    table = Table(data, colWidths=[150, 80])
    table.setStyle(_table_style())
    return table


def _table_style():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
    ])


def _html_task_table(tasks_by_status: dict) -> str:
    """Build HTML task breakdown table."""
    if not tasks_by_status:
        return "<p>No tasks</p>"
    rows = "".join(
        f"<tr><td>{_esc(status)}</td><td>{count}</td></tr>"
        for status, count in sorted(tasks_by_status.items())
    )
    return f"<table><tr><th>Status</th><th>Count</th></tr>{rows}</table>"


def _esc(text: str) -> str:
    """Escape HTML entities."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
