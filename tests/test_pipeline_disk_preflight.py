"""Integration: PipelineService must surface disk-preflight warnings.

The pipeline should not start a 5-shot batch if the disk is too full
to hold the results. We don't block (the user might have cleaned up
manually) but we do log a clear warning. These tests pin that behavior.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from lfo.core.database import Database
from lfo.core.disk_guard import DiskSpaceStatus
from lfo.services.pipeline_service import PipelineService
from lfo.storyboard.storyboard import ProjectInfo, Storyboard


def _make_storyboard() -> Storyboard:
    return Storyboard(
        project=ProjectInfo(project_id="proj-disk-test", title="Test"),
        shots=[],
    )


def _ok_status() -> DiskSpaceStatus:
    return DiskSpaceStatus(
        path=".",
        free_bytes=500 * 1024**3,
        total_bytes=1000 * 1024**3,
        level="ok",
        should_warn=False,
        should_block=False,
    )


def _critical_status() -> DiskSpaceStatus:
    return DiskSpaceStatus(
        path=".",
        free_bytes=2 * 1024**3,
        total_bytes=1000 * 1024**3,
        level="critical",
        should_warn=True,
        should_block=True,
    )


class TestPipelineDiskPreflight:
    def test_pipeline_init_logs_warning_when_disk_critical(
        self, caplog: pytest.LogCaptureFixture, tmp_path,
    ):
        """When the output dir is on a near-full disk, log a warning at init time."""
        db = Database(tmp_path / "test.db")
        db.init_schema()
        output_dir = tmp_path / "out"

        with patch("lfo.services.pipeline_service.check_disk_space",
            return_value=_critical_status(),
        ):
            with caplog.at_level(logging.WARNING):
                PipelineService(
                    db,
                    comfy_url="http://127.0.0.1:8188",
                    output_dir=str(output_dir),
                )

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("disk" in r.getMessage().lower() for r in warnings), (
            f"expected a disk warning, got: {[r.getMessage() for r in warnings]}"
        )

    def test_pipeline_init_silent_when_disk_ok(self, caplog, tmp_path):
        """When disk is fine, init must not log a warning."""
        db = Database(tmp_path / "test.db")
        db.init_schema()
        output_dir = tmp_path / "out"

        with patch("lfo.services.pipeline_service.check_disk_space",
            return_value=_ok_status(),
        ):
            with caplog.at_level(logging.WARNING):
                PipelineService(
                    db,
                    comfy_url="http://127.0.0.1:8188",
                    output_dir=str(output_dir),
                )

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings == [], f"expected no warnings, got: {[r.getMessage() for r in warnings]}"

    def test_pipeline_init_continues_when_disk_check_raises(self, tmp_path):
        """If check_disk_space itself blows up, init must still succeed."""
        db = Database(tmp_path / "test.db")
        db.init_schema()
        output_dir = tmp_path / "out"

        with patch("lfo.services.pipeline_service.check_disk_space",
            side_effect=Exception("boom"),
        ):
            # Should NOT raise
            service = PipelineService(
                db,
                comfy_url="http://127.0.0.1:8188",
                output_dir=str(output_dir),
            )

        assert service is not None
