"""Tests for the project-scoped workspace layout."""
from __future__ import annotations

from pathlib import Path


def test_workspace_root_resolution(monkeypatch, tmp_path: Path) -> None:
    from lfo.services.workspace import resolve_workspace_root

    custom = tmp_path / "custom-workspace"
    monkeypatch.setenv("LFO_WORKSPACE", str(custom))
    assert resolve_workspace_root() == custom

    monkeypatch.setenv("LFO_WORKSPACE", "relative/path")
    assert resolve_workspace_root().is_absolute()


def test_project_paths_are_stable_and_scoped(monkeypatch, tmp_path: Path) -> None:
    from lfo.services.workspace import (
        project_dir,
        project_final_dir,
        project_outputs_dir,
        resolve_workspace_root,
        runtime_db_path,
    )

    workspace = tmp_path / "workspace"
    monkeypatch.setenv("LFO_WORKSPACE", str(workspace))
    assert project_dir("midnight_train") == workspace / "projects" / "midnight_train"
    assert project_outputs_dir("midnight_train", "run-001") == (
        workspace / "projects" / "midnight_train" / "outputs" / "run-001"
    )
    assert project_final_dir("midnight_train", "revision-001") == (
        workspace / "projects" / "midnight_train" / "final" / "revision-001"
    )
    assert runtime_db_path() == workspace / "db" / "runtime-v1.sqlite3"
    for path in (
        project_dir("midnight_train"),
        project_outputs_dir("midnight_train", "run-001"),
        project_final_dir("midnight_train", "revision-001"),
        runtime_db_path(),
    ):
        path.relative_to(resolve_workspace_root())


def test_authoring_helpers_remain_workspace_scoped(monkeypatch, tmp_path: Path) -> None:
    from lfo.services.workspace import (
        novel_dir,
        novel_ref_images_dir,
        novel_spikes_dir,
        orphans_dir,
        orphans_ref_images_dir,
        orphans_spikes_dir,
    )

    workspace = tmp_path / "workspace"
    monkeypatch.setenv("LFO_WORKSPACE", str(workspace))
    assert novel_dir("story").name == "story"
    assert novel_ref_images_dir("story").name == "ref_images"
    assert novel_spikes_dir("story").name == "spikes"
    assert orphans_dir().name == "_orphans"
    assert orphans_ref_images_dir().name == "ref_images"
    assert orphans_spikes_dir().name == "spikes"
