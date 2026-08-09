"""Tests for v1 runtime CLI commands."""
from __future__ import annotations

import json
import pathlib

from lfo.cli.runtime_cmd import (
    cmd_cancel,
    cmd_execute,
    cmd_export,
    cmd_plan,
    cmd_retry,
    cmd_runtime_status,
    cmd_validate,
)


def _package_json(tmp_path: pathlib.Path) -> pathlib.Path:
    data = {
        "schema": "lfo.video-execution.v1",
        "package_id": "test-pkg",
        "revision": 1,
        "project": {"title": "Test"},
        "assets": [],
        "clips": [
            {
                "clip_id": "clip-001",
                "sequence": 1,
                "duration_ms": 5000,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "A sunset",
                    "requirements": {},
                },
            }
        ],
        "output": {},
    }
    p = tmp_path / "package.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestCmdValidate:
    def test_valid(self, tmp_path: pathlib.Path) -> None:
        result = cmd_validate(str(_package_json(tmp_path)))
        assert result["valid"]

    def test_missing_path(self) -> None:
        result = cmd_validate("")
        assert not result["success"]

    def test_missing_file(self) -> None:
        result = cmd_validate("/nonexistent.json")
        assert not result["valid"]


class TestCmdPlan:
    def test_plan(self, tmp_path: pathlib.Path) -> None:
        result = cmd_plan(str(_package_json(tmp_path)))
        assert result["success"]
        assert len(result["clips"]) == 1

    def test_plan_missing_path(self) -> None:
        result = cmd_plan("")
        assert not result["success"]


class TestCmdExecute:
    def test_execute(self, tmp_path: pathlib.Path) -> None:
        result = cmd_execute(str(_package_json(tmp_path)))
        assert result["success"]
        assert result["status"] == "COMPLETED"
        assert result["clip_count"] == 1

    def test_execute_missing_path(self) -> None:
        result = cmd_execute("")
        assert not result["success"]


class TestCmdCancel:
    def test_cancel(self) -> None:
        result = cmd_cancel("run-123")
        assert result["success"]

    def test_cancel_missing_id(self) -> None:
        result = cmd_cancel("")
        assert not result["success"]


class TestCmdExport:
    def test_export_missing_id(self) -> None:
        result = cmd_export("")
        assert not result["success"]


class TestCmdRetry:
    def test_retry_missing_id(self) -> None:
        result = cmd_retry("")
        assert not result["success"]
