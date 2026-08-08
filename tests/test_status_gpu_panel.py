"""Tests for the GPU resource panel in ``lfo status``."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lfo.core.database import Database


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Give each test a real on-disk DB so cmd_status and the fixture share state."""
    p = tmp_path / "lfo-test.db"
    database = Database(p)
    database.init_schema()
    return str(p)


def _seed_project(db_path: str, project_id: str) -> None:
    db = Database(db_path)
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (project_id, "test"),
    )
    db.close()


class TestStatusGpuPanel:
    def test_status_includes_gpu_status_key(self, db_path):
        """cmd_status should always include a 'gpu_status' key, even if null."""
        from lfo.cli.status_cmd import cmd_status

        _seed_project(db_path, "proj-1")

        with patch("lfo.comfy.gpu_guard.get_gpu_status", return_value=None):
            result = cmd_status(project_id="proj-1", db_path=db_path)

        assert "gpu_status" in result
        assert result["gpu_status"] is None

    def test_status_includes_gpu_snapshot_when_available(self, db_path):
        """When GPU info is available, surface used/total/free/used_ratio."""
        from lfo.cli import status_cmd

        _seed_project(db_path, "proj-2")

        fake_snapshot = {
            "device_index": 0,
            "used_bytes": 4 * 1024**3,
            "total_bytes": 16 * 1024**3,
            "free_bytes": 12 * 1024**3,
            "used_ratio": 0.25,
        }

        with patch.object(status_cmd, "get_gpu_status", return_value=fake_snapshot):
            result = status_cmd.cmd_status(project_id="proj-2", db_path=db_path)

        assert result["gpu_status"] == fake_snapshot

