"""Unified CLI output — human readable + --json mode + color support."""
from __future__ import annotations

import json
from typing import Any

from lfo.cli.color import bold, cyan, dim, green, red, yellow


class CommandResult:
    """Structured result from a command execution."""

    def __init__(
        self,
        ok: bool,
        command: str,
        data: Any = None,
        warnings: list[str] | None = None,
        error: dict[str, str] | None = None,
    ):
        self.ok = ok
        self.command = command
        self.data = data or {}
        self.warnings = warnings or []
        self.error = error


def format_output(result: CommandResult, json_mode: bool = False) -> str:
    """Format result for output. JSON mode for machines, human mode for humans."""
    if json_mode:
        return json.dumps(
            {
                "ok": result.ok,
                "command": result.command,
                "data": result.data,
                "warnings": result.warnings,
                "error": result.error,
            },
            ensure_ascii=False,
            indent=2,
        )
    if not result.ok:
        code = result.error.get("code", "UNKNOWN") if result.error else "UNKNOWN"
        msg = result.error.get("message", "Unknown error") if result.error else "Unknown error"
        return red(f"Error [{code}]: {msg}")
    return _format_human(result)


def _format_human(result: CommandResult) -> str:
    """Pretty human-readable output with tables for structured data."""
    lines = []

    # Special formatting for known commands
    data = result.data if isinstance(result.data, dict) else {}

    if result.command == "status" and data.get("success"):
        return _format_status_panel(data)

    # Generic header
    lines.append(f"[{result.command}]")

    # Render data as key-value or table
    if data:
        lines.extend(_render_data(data, indent=2))

    if result.warnings:
        lines.append("")
        for w in result.warnings:
            lines.append(f"  {yellow('⚠')} {yellow(w)}")

    return "\n".join(lines) if lines else green(f"[{result.command}] OK")


def _format_status_panel(data: dict) -> str:
    """Render the status panel with colors."""
    phase = data.get("phase", "?")
    phase_color = _phase_color(phase)

    lines = [
        "",
        bold(f"Project: {data.get('project_name', '?')} ({data.get('project_id', '?')})"),
        f"Phase: {phase_color(phase)}  |  Status: {data.get('project_status', '?')}",
        f"Tasks: {data.get('completed', 0)}/{data.get('total_tasks', 0)} completed ({green(str(data.get('completion_pct', 0))) + '%'})",
        "",
    ]

    # Tasks by status table
    tasks_by_status = data.get("tasks_by_status", {})
    if tasks_by_status:
        lines.append(bold("Tasks by Status:"))
        lines.append(f"  {'Status':<25} {'Count':>5}")
        lines.append(f"  {dim('-' * 25)} {dim('-' * 5)}")
        for status, count in sorted(tasks_by_status.items()):
            lines.append(f"  {status:<25} {count:>5}")
        lines.append("")

    progress = data.get("progress", {})
    if isinstance(progress, dict) and progress:
        lines.append(bold("Active Progress:"))
        for logical_key, event in progress.items():
            if not isinstance(event, dict):
                continue
            completed = event.get("completed_segments", 0)
            total = event.get("segment_count", 0)
            status = event.get("status", "unknown")
            lines.append(f"  {cyan('→')} {logical_key}: {status} ({completed}/{total} segments)")
        lines.append("")

    # Blockers
    blockers = data.get("blockers", [])
    if blockers:
        lines.append(red(f"Blockers ({len(blockers)}):"))
        for b in blockers:
            lines.append(f"  {red('✗')} {b.get('task_id', '?')}: {b.get('status', '?')} — {dim(b.get('error', '')[:60])}")
        lines.append("")

    # Next actions
    next_actions = data.get("next_actions", [])
    if next_actions:
        lines.append(cyan(f"Next Actions ({len(next_actions)}):"))
        for n in next_actions:
            lines.append(f"  {cyan('→')} {n.get('task_id', '?')}: {n.get('status', '?')}")
        lines.append("")

    # Clip reviews pending
    clips = data.get("clip_reviews_pending", [])
    if clips:
        lines.append(yellow(f"Clip Reviews Pending ({len(clips)}):"))
        for c in clips:
            lines.append(f"  ○ {c.get('shot_id', '?')}: {dim(c.get('selected_clip_id', '?')[:12] + '...')}")
        lines.append("")

    return "\n".join(lines)


def _phase_color(phase: str):
    """Return the color function for a given phase."""
    if phase == "complete":
        return green
    if phase in ("running", "in_progress"):
        return cyan
    if phase == "waiting":
        return yellow
    if phase == "failed":
        return red
    return dim


def _render_data(data: dict, indent: int = 2) -> list[str]:
    """Render a dict as formatted key-value lines."""
    lines = []
    prefix = " " * indent
    for key, value in data.items():
        if key == "success":
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_render_data(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: [{len(value)} items]")
            for item in value[:5]:
                if isinstance(item, dict):
                    parts = [f"{k}={v}" for k, v in list(item.items())[:3]]
                    lines.append(f"{prefix}  - {', '.join(parts)}")
                else:
                    lines.append(f"{prefix}  - {item}")
            if len(value) > 5:
                lines.append(f"{prefix}  ... and {len(value) - 5} more")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return lines


EXIT_SUCCESS = 0
EXIT_EXECUTION_FAILED = 1
EXIT_CLI_ERROR = 2
EXIT_PREFLIGHT_BLOCKED = 3
EXIT_WAITING_USER = 4
EXIT_PARTIAL_SUCCESS = 5
