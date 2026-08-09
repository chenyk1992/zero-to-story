"""Logical URI resolution — project://, comfy-input://, model://, etc."""
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfo.config.machine_profile import MachineProfile


def normalize_windows_path(path: str) -> str:
    """Normalize Windows path separators and case.

    Converts backslashes to forward slashes and lowercases drive letters.
    """
    # Convert backslashes to forward slashes
    normalized = path.replace("\\", "/")
    # Lowercase drive letter if present
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        normalized = normalized[0].lower() + normalized[1:]
    return normalized


class PathResolver:
    """Resolve logical URIs to absolute paths.

    Supported schemes:
    - project://          -> project_root/...
    - comfy-input://      -> machine_profile.storage.comfy_input/...
    - comfy-output://     -> machine_profile.storage.comfy_output/...
    - cache://            -> machine_profile.storage.lfo_cache/...
    - model://<model_id>  -> resolved via ModelResolver
    """

    def __init__(
        self,
        project_root: pathlib.Path,
        machine_profile: MachineProfile,
    ) -> None:
        self.project_root = project_root.resolve()
        self.profile = machine_profile

    def resolve(self, uri: str) -> pathlib.Path:
        """Resolve a logical URI to an absolute path.

        Raises:
            ValueError: For path traversal (..) attempts or unknown schemes.
        """
        # Split URI into scheme and path
        scheme, sep, rest = uri.partition("://")
        if not sep:
            raise ValueError(
                f"Invalid URI (no scheme): {uri}. "
                "Expected format: scheme://path"
            )

        if scheme == "project":
            return self._safe_resolve(rest, self.project_root)
        elif scheme == "comfy-input":
            base = pathlib.Path(self.profile.storage.comfy_input).resolve()
            return self._safe_resolve(rest, base)
        elif scheme == "comfy-output":
            base = pathlib.Path(self.profile.storage.comfy_output).resolve()
            return self._safe_resolve(rest, base)
        elif scheme == "cache":
            base = pathlib.Path(self.profile.storage.lfo_cache).resolve()
            return self._safe_resolve(rest, base)
        elif scheme == "model":
            raise ValueError(
                f"model:// URIs must be resolved via ModelResolver: {uri}"
            )
        else:
            raise ValueError(
                f"Unknown URI scheme: {scheme}. "
                "Supported: project://, comfy-input://, comfy-output://, cache://"
            )

    def _safe_resolve(self, rel: str, base: pathlib.Path) -> pathlib.Path:
        """Resolve a relative path against a base, with traversal protection."""
        # Remove leading slashes
        while rel.startswith("/"):
            rel = rel[1:]

        # Check for path traversal
        parts = rel.split("/")
        if ".." in parts:
            raise ValueError(f"Path traversal forbidden: {rel}")

        # Join path segments one by one to avoid issues with multi-segment strings
        result = base
        for part in parts:
            if part:  # skip empty segments
                result = result / part

        # Verify containment
        resolved = result.resolve()
        try:
            resolved.relative_to(base.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Resolved path {resolved} is outside base {base}"
            ) from exc

        return resolved

    def to_project_relative(self, path: pathlib.Path) -> str:
        """Convert absolute path back to project:// URI if under project root.

        Returns the original path as string if not under project root.
        """
        try:
            rel = path.resolve().relative_to(self.project_root)
            return f"project://{rel.as_posix()}"
        except ValueError:
            return str(path)

    def to_comfy_input_relative(self, path: pathlib.Path) -> str:
        """Convert absolute path back to comfy-input:// URI if under input dir."""
        base = pathlib.Path(self.profile.storage.comfy_input).resolve()
        try:
            rel = path.resolve().relative_to(base)
            return f"comfy-input://{rel.as_posix()}"
        except ValueError:
            return str(path)

    def to_comfy_output_relative(self, path: pathlib.Path) -> str:
        """Convert absolute path back to comfy-output:// URI if under output dir."""
        base = pathlib.Path(self.profile.storage.comfy_output).resolve()
        try:
            rel = path.resolve().relative_to(base)
            return f"comfy-output://{rel.as_posix()}"
        except ValueError:
            return str(path)
