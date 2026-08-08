"""Tests for CLI color output."""
from __future__ import annotations

import os
from unittest.mock import patch

from lfo.cli import color
from lfo.cli.output import CommandResult, format_output


class TestColorModule:
    def test_colorize_when_disabled(self):
        color.disable_colors()
        assert color.colorize("hello", "\033[32m") == "hello"
        color.enable_colors()

    def test_colorize_when_enabled(self):
        color.enable_colors()
        result = color.colorize("hello", "\033[32m")
        assert "\033[32m" in result
        assert "hello" in result
        assert "\033[0m" in result

    def test_green(self):
        color.enable_colors()
        assert "\033[32m" in color.green("test")

    def test_red(self):
        color.enable_colors()
        assert "\033[31m" in color.red("test")

    def test_yellow(self):
        color.enable_colors()
        assert "\033[33m" in color.yellow("test")

    def test_no_color_env(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            # Force re-evaluation
            result = color._supports_color() if not os.environ.get("FORCE_COLOR") else True
            assert result is False or os.environ.get("FORCE_COLOR")


class TestColoredOutput:
    def test_error_is_red(self):
        color.enable_colors()
        result = CommandResult(ok=False, command="test",
                               error={"code": "E_FAIL", "message": "Broken"})
        output = format_output(result, json_mode=False)
        assert "\033[31m" in output
        assert "Broken" in output

    def test_warnings_are_yellow(self):
        color.enable_colors()
        result = CommandResult(ok=True, command="test", warnings=["low disk"])
        output = format_output(result, json_mode=False)
        assert "\033[33m" in output
        assert "low disk" in output

    def test_status_panel_has_colors(self):
        color.enable_colors()
        result = CommandResult(ok=True, command="status", data={
            "success": True,
            "project_name": "Test",
            "project_id": "p1",
            "phase": "running",
            "completed": 2,
            "total_tasks": 5,
            "completion_pct": 40.0,
            "tasks_by_status": {"RUNNING": 1, "SUCCEEDED": 2},
            "blockers": [],
            "next_actions": [],
            "clip_reviews_pending": [],
        })
        output = format_output(result, json_mode=False)
        # Should contain ANSI codes
        assert "\033[" in output
        assert "Test" in output

    def test_json_mode_no_colors(self):
        result = CommandResult(ok=True, command="status", data={
            "success": True, "project_name": "Test", "project_id": "p1",
            "phase": "running", "completed": 2, "total_tasks": 5,
            "completion_pct": 40.0, "tasks_by_status": {},
            "blockers": [], "next_actions": [], "clip_reviews_pending": [],
        })
        output = format_output(result, json_mode=True)
        assert "\033[" not in output

    def test_colors_disabled(self):
        color.disable_colors()
        result = CommandResult(ok=False, command="test",
                               error={"code": "E_FAIL", "message": "Broken"})
        output = format_output(result, json_mode=False)
        assert "\033[" not in output
        color.enable_colors()
