"""Shared Markdown utilities for LFO renderers.

Used by both storyboard/render.py and planning/render.py to avoid
duplication of common Markdown patterns.
"""
from __future__ import annotations


def md_heading(text: str, level: int = 1) -> str:
    """Render a Markdown heading.

    Args:
        text: Heading text.
        level: Heading level (1-6). Clamped to [1, 6].
    """
    level = max(1, min(level, 6))
    return f"{'#' * level} {text}"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table.

    Args:
        headers: Column header labels.
        rows: Table data rows. Each row must have len(headers) columns.

    Returns:
        A Markdown table string. Returns a message if headers are empty.
    """
    if not headers:
        return "*(no columns)*"

    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        # Pad or truncate row to match header count
        padded = list(row) + [""] * (len(headers) - len(row))
        padded = padded[: len(headers)]
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


def md_code_block(content: str, language: str = "") -> str:
    """Render a fenced code block."""
    return f"```{language}\n{content}\n```"


def md_blockquote(text: str) -> str:
    """Render a blockquote. Handles multi-line text."""
    lines = text.split("\n")
    return "\n".join(f"> {line}" if line.strip() else ">" for line in lines)


def md_warning(text: str) -> str:
    """Render a warning blockquote."""
    return f"> ⚠️ **Warning:** {text}"


def md_success(text: str) -> str:
    """Render a success blockquote."""
    return f"> ✅ {text}"


def md_error(text: str) -> str:
    """Render an error blockquote."""
    return f"> ❌ {text}"


def md_json_pointer(pointer: str) -> str:
    """Format a JSON Pointer for display.

    Prepends '/' if missing so the pointer reads as a proper JSON Pointer.
    """
    if not pointer.startswith("/"):
        pointer = "/" + pointer
    return f"`{pointer}`"


def md_task_id(task_id: str) -> str:
    """Format a task ID as inline code."""
    return f"`{task_id}`"
