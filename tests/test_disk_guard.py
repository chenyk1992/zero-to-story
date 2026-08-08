"""Tests for core.disk_guard — disk-space preflight for batch runs.

The guard warns when free space falls below sane thresholds so the user
sees the warning BEFORE the pipeline starts grinding on huge videos.
"""
from __future__ import annotations

from unittest.mock import patch


class TestDiskSpaceCheck:
    def test_ok_when_ample_free_space(self):
        from lfo.core.disk_guard import DiskSpaceStatus, check_disk_space

        with patch("lfo.core.disk_guard.shutil.disk_usage",
            return_value=_make_usage(free_gb=500, total_gb=1000),
        ):
            result = check_disk_space("/some/path")

        assert isinstance(result, DiskSpaceStatus)
        assert result.level == "ok"
        assert result.should_warn is False
        assert result.should_block is False

    def test_warn_when_free_space_below_warn_threshold(self):
        from lfo.core.disk_guard import check_disk_space

        with patch("lfo.core.disk_guard.shutil.disk_usage",
            return_value=_make_usage(free_gb=30, total_gb=1000),
        ):
            result = check_disk_space("/some/path", warn_threshold_gb=50, critical_threshold_gb=5)

        assert result.level == "warn"
        assert result.should_warn is True
        assert result.should_block is False

    def test_critical_when_free_space_below_critical_threshold(self):
        from lfo.core.disk_guard import check_disk_space

        with patch("lfo.core.disk_guard.shutil.disk_usage",
            return_value=_make_usage(free_gb=2, total_gb=1000),
        ):
            result = check_disk_space("/some/path", warn_threshold_gb=50, critical_threshold_gb=5)

        assert result.level == "critical"
        assert result.should_warn is True
        assert result.should_block is True

    def test_returns_status_without_raising_on_oserror(self):
        """A failed disk_usage call (e.g. path deleted) must not raise — fail open."""
        from lfo.core.disk_guard import check_disk_space

        with patch("lfo.core.disk_guard.shutil.disk_usage", side_effect=OSError("no such path")):
            result = check_disk_space("/nonexistent")

        assert result.level == "unknown"
        assert result.should_block is False
        assert result.error == "no such path"


def _make_usage(free_gb: int, total_gb: int) -> object:
    """Mimic shutil.disk_usage named tuple: (total, used, free)."""
    total = total_gb * 1024**3
    free = free_gb * 1024**3
    used = total - free
    nt = type("Usage", (), {"total": total, "used": used, "free": free})
    return nt()
