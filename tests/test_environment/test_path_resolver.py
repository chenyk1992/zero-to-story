"""Tests for logical URI path resolver."""
from __future__ import annotations

import pathlib

import pytest

from lfo.config.machine_profile import MachineProfile, StorageConfig
from lfo.environment.path_resolver import (
    PathResolver,
    normalize_windows_path,
)


@pytest.fixture
def tmp_profile(tmp_path):
    storage = StorageConfig(
        comfy_input=str(tmp_path / "input"),
        comfy_output=str(tmp_path / "output"),
        lfo_cache=str(tmp_path / "cache"),
    )
    profile = MachineProfile(
        machine_id="test",
        storage=storage,
    )
    # Create dirs
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "cache").mkdir()
    return profile


class TestNormalizeWindowsPath:
    def test_backslash_to_forward(self):
        assert normalize_windows_path("a\\b\\c") == "a/b/c"

    def test_lowercase_drive(self):
        result = normalize_windows_path("C:\\Windows")
        assert result[0] == "c"
        assert "/" in result  # backslashes converted

    def test_already_forward(self):
        assert normalize_windows_path("a/b/c") == "a/b/c"


class TestPathResolver:
    def test_resolve_project_uri(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        result = resolver.resolve("project://scenes/scene01.json")
        assert result == pathlib.Path(tmp_path / "scenes" / "scene01.json").resolve()

    def test_resolve_comfy_input(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        result = resolver.resolve("comfy-input://input_image.png")
        assert result == pathlib.Path(tmp_path / "input" / "input_image.png").resolve()

    def test_resolve_comfy_output(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        result = resolver.resolve("comfy-output://video.mp4")
        assert result == pathlib.Path(tmp_path / "output" / "video.mp4").resolve()

    def test_resolve_cache(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        result = resolver.resolve("cache://temp/file.tmp")
        assert result == pathlib.Path(tmp_path / "cache" / "temp" / "file.tmp").resolve()

    def test_model_uri_raises(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        with pytest.raises(ValueError, match="ModelResolver"):
            resolver.resolve("model://some_model")

    def test_unknown_scheme_raises(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        with pytest.raises(ValueError, match="Unknown URI scheme"):
            resolver.resolve("unknown://path")

    def test_path_traversal_blocked(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        with pytest.raises(ValueError, match="traversal"):
            resolver.resolve("project://../etc/passwd")

    def test_to_project_relative(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        abs_path = tmp_path / "subdir" / "file.txt"
        rel = resolver.to_project_relative(abs_path)
        assert rel.startswith("project://")

    def test_to_project_relative_outside(self, tmp_path, tmp_profile):
        resolver = PathResolver(tmp_path, tmp_profile)
        abs_path = pathlib.Path("/tmp/outside.txt")
        rel = resolver.to_project_relative(abs_path)
        # Should return the absolute path as string since it's outside project
        assert not rel.startswith("project://")
