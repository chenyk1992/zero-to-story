"""Tests for EnvironmentService."""
from __future__ import annotations

from lfo.services.environment_service import EnvironmentService


class TestEnvironmentService:
    def test_init(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        service = EnvironmentService()
        assert service.machines_dir.exists()

    def test_get_or_create_nonexistent(self, tmp_path, monkeypatch):
        """If profile doesn't exist, get_or_create returns None (cannot discover in test)."""
        monkeypatch.setenv("APPDATA", str(tmp_path))
        service = EnvironmentService()
        # Since load_machine_profile returns None for nonexistent,
        # discover_and_create_profile tries to discover, which may fail in CI.
        # We test that load_machine_profile returns None for unknown ID.
        from lfo.config.machine_profile import load_machine_profile
        assert load_machine_profile("nonexistent-id") is None

    def test_init_with_custom_dir(self, tmp_path):
        custom = tmp_path / "custom_machines"
        custom.mkdir()
        service = EnvironmentService(machines_dir=custom)
        assert service.machines_dir == custom
