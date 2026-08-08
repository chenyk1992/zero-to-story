"""Tests for environment discovery."""
from __future__ import annotations

from lfo.environment.discovery import (
    DiscoveredEnvironment,
    detect_gpu,
    discover_environment,
    find_python,
)


class TestDiscoveredEnvironment:
    def test_defaults(self):
        d = DiscoveredEnvironment()
        assert d.comfyui_running is False
        assert d.comfyui_pid is None
        assert d.gpu_name == ""
        assert d.has_ffmpeg is False


class TestDiscoverEnvironment:
    def test_returns_discovered_env(self):
        result = discover_environment()
        assert isinstance(result, DiscoveredEnvironment)


class TestFindPython:
    def test_none_input(self):
        # Should not crash with None
        result = find_python(None)
        # On a system with python in PATH, this returns a path
        # On a minimal CI env, it may return None
        # Either is acceptable for this test
        assert result is None or hasattr(result, "exists")

    def test_with_nonexistent_root(self):
        import pathlib
        result = find_python(pathlib.Path("/nonexistent/path"))
        # Falls back to system python or None
        assert result is None or isinstance(result, pathlib.Path)


class TestDetectGpu:
    def test_returns_tuple(self):
        name, vram = detect_gpu()
        assert isinstance(name, str)
        assert isinstance(vram, int)
        assert vram >= 0
