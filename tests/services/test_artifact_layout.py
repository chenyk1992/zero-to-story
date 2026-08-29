from __future__ import annotations

from pathlib import Path

import pytest

from lfo.contracts.package import VideoExecutionPackage
from lfo.services.artifact_layout import (
    ArtifactLayoutError,
    RunArtifactLayout,
    atomic_copy_verified,
    managed_path,
)


def _package(project_id: str = "project-1", package_id: str = "package-1") -> VideoExecutionPackage:
    return VideoExecutionPackage.from_dict(
        {
            "schema": "lfo.video-execution.v1",
            "package_id": package_id,
            "revision": 2,
            "project": {"title": "Test", "project_id": project_id},
            "assets": [],
            "clips": [],
            "output": {"directory": "revision-002", "container": "mp4"},
        }
    )


def test_layout_is_project_scoped_and_versioned(tmp_path: Path) -> None:
    layout = RunArtifactLayout.from_package(
        workspace_root=tmp_path / "workspace",
        run_id="run-1",
        package=_package(),
    )
    layout.prepare()
    assert layout.final_path == (
        tmp_path / "workspace" / "projects" / "project-1" / "final" / "revision-002"
        / "package-1-run-1.mp4"
    )
    assert layout.task_output_path("video.generate", "clip-1").as_posix().endswith(
        "/outputs/run-1/clips/clip-1/generated.mp4"
    )
    assert layout.task_output_path("video.upscale", "clip-1").as_posix().endswith(
        "/outputs/run-1/clips/clip-1/upscaled.mp4"
    )
    assert layout.task_output_path(
        "media.boundary_evidence", "clip-1__clip-2"
    ).as_posix().endswith(
        "/outputs/run-1/global/boundaries/clip-1__clip-2"
    )
    assert layout.final_path.parent.is_dir()
    assert layout.run_root.is_dir()
    assert layout.to_dict()["layout_version"] == "project-v1"


def test_layout_rejects_missing_or_unsafe_project_identity(tmp_path: Path) -> None:
    package = _package(project_id="../escape")
    with pytest.raises(ArtifactLayoutError):
        RunArtifactLayout.from_package(
            workspace_root=tmp_path / "workspace", run_id="run-1", package=package
        )

    missing = _package()
    missing.project.project_id = None
    with pytest.raises(ArtifactLayoutError, match="project.project_id"):
        RunArtifactLayout.from_package(
            workspace_root=tmp_path / "workspace", run_id="run-1", package=missing
        )


def test_atomic_copy_verified_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "provider.mp4"
    destination = tmp_path / "workspace" / "projects" / "p" / "generated.mp4"
    source.write_bytes(b"provider-bytes")
    first = atomic_copy_verified(source, destination)
    second = atomic_copy_verified(source, destination)
    assert first == second
    assert destination.read_bytes() == b"provider-bytes"


def test_managed_path_cannot_escape_project_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project = workspace / "projects" / "p"
    layout = {"workspace_root": str(workspace), "project_root": str(project)}
    assert managed_path(str(project / "outputs" / "clip.mp4"), layout)
    with pytest.raises(ArtifactLayoutError, match="project root"):
        managed_path(str(workspace / "exports" / "clip.mp4"), layout)
