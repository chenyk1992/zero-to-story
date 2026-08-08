"""Tests for ``lfo run`` crash-recovery integration.

The ``run`` command must invoke ``recover_project`` on startup so an
interrupted batch resumes automatically. The recovery call must:
- be best-effort: a failure to recover must not abort the run
- be a no-op for in-memory databases (nothing to recover)
- log a summary so the user can see what was reset
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from lfo.core.database import Database
from lfo.core.runtime import (
    create_task,
    update_task_hashes,
    update_task_status,
)
from lfo.core.state_machine import TaskStatus

MINIMAL_STORYBOARD = {
    "project": {"project_id": "proj-recover-test", "title": "Recover Test"},
    "beats": [],
    "panels": [],
}


def _write_storyboard(tmp_path: Path) -> Path:
    """Create a minimal on-disk storyboard so cmd_run will accept it."""
    import json
    p = tmp_path / "storyboard.json"
    p.write_text(json.dumps(MINIMAL_STORYBOARD), encoding="utf-8")
    return p


class TestRunCmdRecovery:
    def test_run_invokes_recover_project_for_on_disk_db(
        self, tmp_path, caplog: pytest.LogCaptureFixture,
    ):
        """When the DB is on disk, run must call recover_project with the loaded project_id."""
        from lfo.cli.run_cmd import cmd_run

        sb = _write_storyboard(tmp_path)
        db_file = tmp_path / "lfo.db"
        Database(str(db_file)).close()

        with patch("lfo.cli.run_cmd.recover_project") as mock_recover:
            with caplog.at_level(logging.INFO):
                cmd_run(
                    storyboard_path=str(sb),
                    db_path=str(db_file),
                    comfy_url="http://127.0.0.1:1",  # no ComfyUI; will fail later
                )

        mock_recover.assert_called_once()
        args, kwargs = mock_recover.call_args
        # Either positional or keyword for project_id
        passed_proj = args[1] if len(args) > 1 else kwargs.get("project_id", "")
        assert passed_proj == "proj-recover-test"

    def test_run_skips_recovery_for_in_memory_db(self, tmp_path):
        """When DB is in-memory, recover is meaningless and must be skipped."""
        from lfo.cli.run_cmd import cmd_run

        sb = _write_storyboard(tmp_path)

        with patch("lfo.cli.run_cmd.recover_project") as mock_recover:
            cmd_run(
                storyboard_path=str(sb),
                db_path="",  # -> :memory:
                comfy_url="http://127.0.0.1:1",
            )

        mock_recover.assert_not_called()

    def test_run_continues_even_if_recovery_fails(self, tmp_path):
        """A recovery failure must not abort the run — only log a warning."""
        from lfo.cli.run_cmd import cmd_run

        sb = _write_storyboard(tmp_path)
        db_file = tmp_path / "lfo.db"
        Database(str(db_file)).close()

        with patch("lfo.cli.run_cmd.recover_project",
            side_effect=Exception("recovery blew up"),
        ):
            # Should NOT raise even though recovery exploded
            result = cmd_run(
                storyboard_path=str(sb),
                db_path=str(db_file),
                comfy_url="http://127.0.0.1:1",
            )

        # We don't care if pipeline itself succeeded; only that cmd_run
        # returned normally rather than propagating the recovery error.
        assert isinstance(result, dict)
        assert "success" in result

    def test_recovery_summary_is_logged(self, tmp_path, caplog):
        """The recovery summary dict should be surfaced to the user via log."""
        from lfo.cli.run_cmd import cmd_run

        sb = _write_storyboard(tmp_path)
        db_file = tmp_path / "lfo.db"
        # Pre-populate a RUNNING task so the recovery summary is non-trivial
        seed_db = Database(str(db_file))
        seed_db.init_schema()
        seed_db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            ("proj-recover-test", "t"),
        )
        tid = create_task(seed_db, "proj-recover-test", "h3_t2va")
        update_task_hashes(
            seed_db, tid,
            content_hash="ch", dependency_hash="dh",
            params_hash="ph", idempotency_key="ik",
        )
        update_task_status(seed_db, tid, TaskStatus.RUNNING)
        seed_db.close()

        with caplog.at_level(logging.INFO):
            cmd_run(
                storyboard_path=str(sb),
                db_path=str(db_file),
                comfy_url="http://127.0.0.1:1",
            )

        # The recovery ran in our actual recover_project (not mocked),
        # so the summary line should mention the reset count.
        summary_logs = [r for r in caplog.records if "recovery" in r.getMessage().lower()]
        assert summary_logs, "expected a recovery summary line in the log"
