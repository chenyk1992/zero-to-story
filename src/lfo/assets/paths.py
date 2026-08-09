"""Safe path resolution for Package-relative URIs.

Rules:
- Relative URIs are resolved against the Package directory.
- ``..``, symlinks, junctions and Windows drive escapes are rejected.
- No absolute paths, no device paths, no directory inputs.
"""
from __future__ import annotations

import pathlib

# Device paths and other forbidden prefixes.
_FORBIDDEN_PREFIXES = ("\\\\?\\", "\\\\.\\", "//?/", "//./")


class PathSecurityError(ValueError):
    """Raised when a path escapes the allowed root or is otherwise unsafe."""
    pass


def _normalise_separators(path: str) -> str:
    """Convert backslashes to forward slashes and collapse repeats."""
    p = path.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    return p


def _is_subpath(candidate: pathlib.Path, root: pathlib.Path) -> bool:
    """Return True if ``candidate`` is ``root`` or inside it.

    Resolves both paths to real paths (follows symlinks) before comparing.
    """
    try:
        real_candidate = candidate.resolve(strict=False)
        real_root = root.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    try:
        real_candidate.relative_to(real_root)
        return True
    except ValueError:
        return False


def resolve_package_uri(uri: str, package_dir: pathlib.Path) -> pathlib.Path:
    """Resolve a Package-relative URI to a real, safe path.

    Args:
        uri: The URI from an AssetSpec source (e.g. ``"assets/hero.png"``).
        package_dir: Absolute path to the directory containing the Package file.

    Returns:
        Absolute path to the referenced file.

    Raises:
        PathSecurityError: If the URI is absolute, contains ``..``, points to
            a directory, or escapes the package directory via symlink/junction.
    """
    if not isinstance(uri, str) or not uri:
        raise PathSecurityError("URI must be a non-empty string")

    # Reject forbidden prefixes.
    for prefix in _FORBIDDEN_PREFIXES:
        if uri.startswith(prefix):
            raise PathSecurityError(f"Forbidden path prefix: {prefix!r}")

    # Reject absolute paths.
    if uri.startswith("/") or (len(uri) >= 2 and uri[1] == ":" and uri[0].isalpha()):
        raise PathSecurityError(f"Absolute path forbidden: {uri!r}")

    # Normalise separators.
    uri = _normalise_separators(uri)

    # Reject ``..`` components before any filesystem access.
    parts = uri.split("/")
    if ".." in parts:
        raise PathSecurityError(f"Path contains forbidden '..' component: {uri!r}")
    # Reject empty components and current-dir noise.
    cleaned = [p for p in parts if p and p != "."]
    if not cleaned:
        raise PathSecurityError(f"Path is empty after normalisation: {uri!r}")

    # Resolve against package directory.
    package_dir = package_dir.resolve(strict=False)
    candidate = (package_dir / "/".join(cleaned)).resolve(strict=False)

    # Final safety: the resolved path must be inside the package directory.
    if not _is_subpath(candidate, package_dir):
        raise PathSecurityError(
            f"Path escapes package directory: {uri!r} -> {candidate}"
        )

    return candidate


def validate_readable_file(path: pathlib.Path) -> None:
    """Validate that ``path`` is a readable file (not a directory, not empty)."""
    if not path.exists():
        raise PathSecurityError(f"File does not exist: {path}")
    if path.is_dir():
        raise PathSecurityError(f"Path is a directory, not a file: {path}")
    if not path.is_file():
        raise PathSecurityError(f"Path is not a regular file: {path}")
    if path.stat().st_size == 0:
        raise PathSecurityError(f"File is empty: {path}")
