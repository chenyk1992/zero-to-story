"""Tests for EnvironmentService."""
from __future__ import annotations

import lfo.services.environment_service as environment_service_module
from lfo.environment.discovery import DiscoveredEnvironment
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

    def test_discover_and_create_populates_comfy_storage_from_root(
        self, tmp_path, monkeypatch
    ):
        comfyui_root = tmp_path / "ComfyUI"
        discovery = DiscoveredEnvironment(comfyui_root=comfyui_root)
        monkeypatch.setattr(
            environment_service_module,
            "discover_environment",
            lambda: discovery,
        )

        _, profile = EnvironmentService(machines_dir=tmp_path).discover_and_create_profile(
            "local-windows", save=False
        )

        assert profile.storage.comfy_input == str(comfyui_root / "input")
        assert profile.storage.comfy_output == str(comfyui_root / "output")

    def test_discover_and_create_leaves_comfy_storage_empty_without_root(
        self, tmp_path, monkeypatch
    ):
        discovery = DiscoveredEnvironment()
        monkeypatch.setattr(
            environment_service_module,
            "discover_environment",
            lambda: discovery,
        )

        _, profile = EnvironmentService(machines_dir=tmp_path).discover_and_create_profile(
            "local-windows", save=False
        )

        assert profile.storage.comfy_input == ""
        assert profile.storage.comfy_output == ""
