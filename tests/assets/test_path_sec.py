"""Tests for safe path resolution."""
from __future__ import annotations

import pathlib

import pytest

from lfo.assets.paths import (
    PathSecurityError,
    resolve_package_uri,
    validate_readable_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_package(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a package directory with an assets subdirectory."""
    pkg = tmp_path / "package"
    assets = pkg / "assets"
    assets.mkdir(parents=True)
    # Create test files.
    (assets / "hero.png").write_bytes(b"fake image data")
    (assets / "deep" / "nested").mkdir(parents=True, exist_ok=True)
    (assets / "deep" / "nested" / "file.txt").write_bytes(b"deep")
    (pkg / "root_file.txt").write_bytes(b"root")
    return pkg


# ---------------------------------------------------------------------------
# Valid paths
# ---------------------------------------------------------------------------


class TestValidPaths:
    def test_simple_relative(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("assets/hero.png", tmp_package)
        assert p == (tmp_package / "assets" / "hero.png").resolve()

    def test_backslash_converted(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("assets\\hero.png", tmp_package)
        assert p == (tmp_package / "assets" / "hero.png").resolve()

    def test_deep_nested(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("assets/deep/nested/file.txt", tmp_package)
        assert p == (tmp_package / "assets" / "deep" / "nested" / "file.txt").resolve()

    def test_root_file(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("root_file.txt", tmp_package)
        assert p == (tmp_package / "root_file.txt").resolve()

    def test_dot_prefix(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("./assets/hero.png", tmp_package)
        assert p == (tmp_package / "assets" / "hero.png").resolve()

    def test_double_slash_collapsed(self, tmp_package: pathlib.Path) -> None:
        p = resolve_package_uri("assets//hero.png", tmp_package)
        assert p == (tmp_package / "assets" / "hero.png").resolve()


# ---------------------------------------------------------------------------
# Path traversal attacks
# ---------------------------------------------------------------------------


class TestPathTraversalBlocked:
    def test_dotdot_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match=r"\.\."):
            resolve_package_uri("../etc/passwd", tmp_package)

    def test_dotdot_middle_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match=r"\.\."):
            resolve_package_uri("assets/../../etc/passwd", tmp_package)

    def test_absolute_unix_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="Absolute"):
            resolve_package_uri("/etc/passwd", tmp_package)

    def test_absolute_windows_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="Absolute"):
            resolve_package_uri("C:\\Windows\\System32\\config\\SAM", tmp_package)

    def test_device_path_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="Forbidden"):
            resolve_package_uri("\\\\?\\C:\\autoexec.bat", tmp_package)

    def test_device_path_dot_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="Forbidden"):
            resolve_package_uri("\\\\.\\C:\\autoexec.bat", tmp_package)


# ---------------------------------------------------------------------------
# Empty / invalid URIs
# ---------------------------------------------------------------------------


class TestInvalidUris:
    def test_empty_string(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="non-empty"):
            resolve_package_uri("", tmp_package)

    def test_none_rejected(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="non-empty"):
            resolve_package_uri(None, tmp_package)  # type: ignore[arg-type]

    def test_only_dots(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="empty after normalisation"):
            resolve_package_uri("./", tmp_package)

    def test_slash_only(self, tmp_package: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="Absolute"):
            resolve_package_uri("/", tmp_package)


# ---------------------------------------------------------------------------
# validate_readable_file
# ---------------------------------------------------------------------------


class TestValidateReadableFile:
    def test_valid_file(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "ok.txt"
        f.write_bytes(b"content")
        validate_readable_file(f)  # should not raise

    def test_missing(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(PathSecurityError, match="does not exist"):
            validate_readable_file(tmp_path / "missing.txt")

    def test_directory(self, tmp_path: pathlib.Path) -> None:
        d = tmp_path / "subdir"
        d.mkdir()
        with pytest.raises(PathSecurityError, match="directory"):
            validate_readable_file(d)

    def test_empty_file(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        with pytest.raises(PathSecurityError, match="empty"):
            validate_readable_file(f)
