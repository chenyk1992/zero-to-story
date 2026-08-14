"""Project-scoped artifact layout for Runtime v1.

Every new run resolves its complete on-disk layout once and passes the
resolved paths through the immutable run snapshot.  Handlers consume those
paths; they never reconstruct ``runs`` or ``exports`` locations themselves.
"""
from __future__ import annotations

import hashlib
import pathlib
import tempfile
from dataclasses import dataclass
from typing import Any

from lfo.contracts.package import VideoExecutionPackage

LAYOUT_VERSION = "project-v1"
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ArtifactLayoutError(ValueError):
    """Raised when a project or artifact path is unsafe or incomplete."""


def managed_path(raw_path: object, layout: object) -> pathlib.Path:
    """Resolve a task path and require it to stay in its project root."""
    if not isinstance(raw_path, str) or not raw_path:
        raise ArtifactLayoutError("Task is missing its project-managed output_path")
    if not isinstance(layout, dict):
        raise ArtifactLayoutError("Task is missing its project artifact_layout")
    project_root_raw = layout.get("project_root")
    workspace_root_raw = layout.get("workspace_root")
    if not isinstance(project_root_raw, str) or not isinstance(workspace_root_raw, str):
        raise ArtifactLayoutError("Task artifact_layout has no project/workspace root")
    workspace_projects = pathlib.Path(workspace_root_raw).resolve(strict=False) / "projects"
    project_root = pathlib.Path(project_root_raw).resolve(strict=False)
    try:
        project_root.relative_to(workspace_projects.resolve(strict=False))
    except ValueError as exc:
        raise ArtifactLayoutError(f"Project root escapes workspace projects: {project_root}") from exc
    path = pathlib.Path(raw_path).resolve(strict=False)
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ArtifactLayoutError(f"Managed output escapes project root: {path}") from exc
    return path


def safe_component(value: str, *, field: str) -> str:
    """Validate one path component without silently rewriting it."""
    if not isinstance(value, str) or not value.strip():
        raise ArtifactLayoutError(f"{field} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ArtifactLayoutError(f"{field} must be a single path component")
    if len(value) >= 2 and value[1] == ":":
        raise ArtifactLayoutError(f"{field} must not contain a drive prefix")
    if "\x00" in value:
        raise ArtifactLayoutError(f"{field} contains a NUL character")
    if value.rstrip(" .") != value:
        raise ArtifactLayoutError(f"{field} must not end with a dot or space")
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        raise ArtifactLayoutError(f"{field} uses a reserved Windows name")
    return value


def _inside(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    """Resolve *path* and require it to remain inside *root*."""
    resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ArtifactLayoutError(f"Artifact path escapes workspace: {resolved}") from exc
    return resolved


def _suffix(container: str) -> str:
    return f".{container.lower().lstrip('.') or 'mp4'}"


@dataclass(frozen=True)
class RunArtifactLayout:
    """Resolved project/run paths shared by all execution handlers."""

    workspace_root: pathlib.Path
    project_id: str
    project_root: pathlib.Path
    run_id: str
    package_id: str
    package_revision: int
    publication_directory: str
    container: str

    @classmethod
    def from_package(
        cls,
        *,
        workspace_root: pathlib.Path,
        run_id: str,
        package: VideoExecutionPackage,
    ) -> "RunArtifactLayout":
        project_id = package.project.project_id
        if project_id is None:
            raise ArtifactLayoutError(
                "project.project_id is required for execution; add the stable project directory name"
            )
        project_id = safe_component(project_id, field="project.project_id")
        package_id = safe_component(package.package_id, field="package_id")
        publication = package.output.directory or package.package_id
        publication = safe_component(publication, field="output.directory")
        workspace = workspace_root.resolve(strict=False)
        project_root = _inside(workspace / "projects" / project_id, workspace / "projects")
        safe_component(run_id, field="run_id")
        return cls(
            workspace_root=workspace,
            project_id=project_id,
            project_root=project_root,
            run_id=run_id,
            package_id=package_id,
            package_revision=package.revision,
            publication_directory=publication,
            container=package.output.container,
        )

    @property
    def run_root(self) -> pathlib.Path:
        return self.project_root / "outputs" / self.run_id

    @property
    def clips_root(self) -> pathlib.Path:
        return self.run_root / "clips"

    @property
    def global_root(self) -> pathlib.Path:
        return self.run_root / "global"

    @property
    def final_directory(self) -> pathlib.Path:
        return self.project_root / "final" / self.publication_directory

    @property
    def final_path(self) -> pathlib.Path:
        return self.final_directory / f"{self.package_id}-{self.run_id}{_suffix(self.container)}"

    @property
    def manifest_path(self) -> pathlib.Path:
        return pathlib.Path(f"{self.final_path}.manifest.json")

    @property
    def subtitles_path(self) -> pathlib.Path:
        return self.final_path.with_suffix(".srt")

    def clip_path(self, clip_id: str, artifact_name: str, suffix: str | None = None) -> pathlib.Path:
        clip = safe_component(clip_id, field="clip_id")
        name = safe_component(artifact_name, field="artifact_name")
        return self.clips_root / clip / f"{name}{suffix or _suffix(self.container)}"

    def global_path(self, artifact_name: str, suffix: str | None = None) -> pathlib.Path:
        name = safe_component(artifact_name, field="artifact_name")
        return self.global_root / f"{name}{suffix or _suffix(self.container)}"

    def task_output_path(self, task_type: str, clip_id: str | None = None) -> pathlib.Path:
        if task_type == "video.generate":
            if clip_id is None:
                raise ArtifactLayoutError("video.generate requires clip_id")
            return self.clip_path(clip_id, "generated", ".mp4")
        if task_type == "video.upscale":
            if clip_id is None:
                raise ArtifactLayoutError("video.upscale requires clip_id")
            return self.clip_path(clip_id, "upscaled", ".mp4")
        if task_type == "media.normalize":
            if clip_id is None:
                raise ArtifactLayoutError("media.normalize requires clip_id")
            return self.clip_path(clip_id, "normalized")
        if task_type == "audio.mix":
            if clip_id is None:
                raise ArtifactLayoutError("audio.mix requires clip_id")
            return self.clip_path(clip_id, "mixed")
        if task_type == "subtitle.render":
            if clip_id is None:
                raise ArtifactLayoutError("subtitle.render requires clip_id")
            return self.clip_path(clip_id, "subtitles", ".srt")
        if task_type == "timeline.assemble":
            return self.global_path("timeline")
        if task_type == "export.finalize":
            return self.final_path
        raise ArtifactLayoutError(f"No managed output path for task type {task_type!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout_version": LAYOUT_VERSION,
            "project_id": self.project_id,
            "workspace_root": str(self.workspace_root),
            "project_root": str(self.project_root),
            "run_id": self.run_id,
            "run_root": str(self.run_root),
            "clips_root": str(self.clips_root),
            "global_root": str(self.global_root),
            "final_directory": str(self.final_directory),
            "final_path": str(self.final_path),
            "manifest_path": str(self.manifest_path),
            "subtitles_path": str(self.subtitles_path),
            "package_id": self.package_id,
            "package_revision": self.package_revision,
            "publication_directory": self.publication_directory,
            "container": self.container,
        }

    def hash_payload(self) -> dict[str, Any]:
        """Return path-independent routing data for materialization hashes."""
        return {
            "layout_version": LAYOUT_VERSION,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "package_id": self.package_id,
            "package_revision": self.package_revision,
            "publication_directory": self.publication_directory,
            "container": self.container,
        }

    def prepare(self) -> None:
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.final_directory.mkdir(parents=True, exist_ok=True)


def atomic_copy_verified(source: pathlib.Path, destination: pathlib.Path) -> tuple[str, int]:
    """Copy a provider file atomically and return its SHA-256 and byte size."""
    source = source.resolve(strict=True)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = destination.resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(prefix=".lfo-copy-", dir=destination.parent, delete=False) as tmp:
        temp_path = pathlib.Path(tmp.name)
        with source.open("rb") as src:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                tmp.write(chunk)
        tmp.flush()
    try:
        if destination.exists():
            existing_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing_hash != digest.hexdigest():
                raise ArtifactLayoutError(f"Destination already exists with a different hash: {destination}")
            temp_path.unlink(missing_ok=True)
            return digest.hexdigest(), size
        temp_path.replace(destination)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return digest.hexdigest(), size
