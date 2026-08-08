"""Tests for services.workspace — workspace path resolution.

LFO has a strict two-layer layout: the system (code + templates) is in
the git-tracked project root, the user workspace (novels, storyboards,
run outputs) lives in ``<repo>/workspace/`` and is git-ignored.

The workspace itself is novel-centric: each novel gets a subtree, and
each chapter within a novel is one LFO video project.

    workspace/<novel_id>/<chapter_id>/{inputs,outputs,final}/

This module centralises path derivation so we have one place to look up
the workspace root, per-novel / per-chapter subdirs, the DB path, etc.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestResolveWorkspaceRoot:
    """The LFO_WORKSPACE env var wins; otherwise the default is used."""

    def test_env_var_overrides_default(self, monkeypatch, tmp_path):
        from lfo.services.workspace import resolve_workspace_root

        custom = tmp_path / "my-custom-workspace"
        monkeypatch.setenv("LFO_WORKSPACE", str(custom))

        result = resolve_workspace_root()

        assert result == custom

    def test_default_is_repo_workspace_dir(self, monkeypatch):
        from lfo.services.workspace import resolve_workspace_root

        monkeypatch.delenv("LFO_WORKSPACE", raising=False)

        result = resolve_workspace_root()

        # Default location: <repo_root>/workspace/ — sibling of src/
        repo_root = Path(__file__).resolve().parent.parent
        assert result == repo_root / "workspace"

    def test_env_var_must_be_absolute(self, monkeypatch):
        """A relative env var should be resolved relative to the project root
        and returned as an absolute path. We never return a relative path —
        downstream callers assume absolute."""
        from lfo.services.workspace import resolve_workspace_root

        monkeypatch.setenv("LFO_WORKSPACE", "relative/path/ws")

        result = resolve_workspace_root()

        assert result.is_absolute()


class TestNovelLayoutPaths:
    """Path derivation for a given novel_id (the novel root)."""

    def test_novel_dir(self):
        from lfo.services.workspace import novel_dir

        result = novel_dir("midnight_train")

        assert result.name == "midnight_train"
        assert result.parent.name == "workspace"

    def test_novel_ref_images_dir(self):
        from lfo.services.workspace import novel_ref_images_dir

        result = novel_ref_images_dir("midnight_train")

        assert result.name == "ref_images"
        assert result.parent.name == "midnight_train"

    def test_novel_spikes_dir(self):
        from lfo.services.workspace import novel_spikes_dir

        result = novel_spikes_dir("midnight_train")

        assert result.name == "spikes"
        assert result.parent.name == "midnight_train"


class TestProjectLayoutPaths:
    """Path derivation for a given (novel_id, chapter_id) — one chapter = one project."""

    def test_project_dir(self):
        from lfo.services.workspace import project_dir

        result = project_dir("midnight_train", "chapter_01")

        # <workspace>/<novel>/<chapter>
        assert result.name == "chapter_01"
        assert result.parent.name == "midnight_train"
        assert result.parent.parent.name == "workspace"

    def test_project_output_dir(self):
        from lfo.services.workspace import project_output_dir

        result = project_output_dir("midnight_train", "chapter_01")

        assert result.name == "outputs"
        assert result.parent.name == "chapter_01"
        assert result.parent.parent.name == "midnight_train"

    def test_project_final_dir(self):
        from lfo.services.workspace import project_final_dir

        result = project_final_dir("midnight_train", "chapter_01")

        assert result.name == "final"
        assert result.parent.name == "chapter_01"
        assert result.parent.parent.name == "midnight_train"

    def test_project_inputs_dir(self):
        from lfo.services.workspace import project_inputs_dir

        result = project_inputs_dir("midnight_train", "chapter_01")

        assert result.name == "inputs"
        assert result.parent.name == "chapter_01"
        assert result.parent.parent.name == "midnight_train"

    def test_chapter_ids_can_contain_dashes(self):
        """A chapter_id like 'chapter-01-special' should not be split again;
        the novel_id / chapter_id split is the caller's responsibility."""
        from lfo.services.workspace import project_dir

        result = project_dir("midnight_train", "chapter-01-special")

        assert result.name == "chapter-01-special"
        assert result.parent.name == "midnight_train"


class TestDbPath:
    """The SQLite database path lives at the workspace root, not under any novel."""

    def test_db_path(self):
        from lfo.services.workspace import db_path

        result = db_path()

        assert result.name == "lfo.db"
        assert result.parent.name == "db"
        assert result.parent.parent.name == "workspace"


class TestOrphansPaths:
    """The _orphans/ subtree is a catch-all for unassigned assets and spikes."""

    def test_orphans_dir(self):
        from lfo.services.workspace import orphans_dir

        result = orphans_dir()

        assert result.name == "_orphans"
        assert result.parent.name == "workspace"

    def test_orphans_ref_images_dir(self):
        from lfo.services.workspace import orphans_ref_images_dir

        result = orphans_ref_images_dir()

        assert result.name == "ref_images"
        assert result.parent.name == "_orphans"
        assert result.parent.parent.name == "workspace"

    def test_orphans_spikes_dir(self):
        from lfo.services.workspace import orphans_spikes_dir

        result = orphans_spikes_dir()

        assert result.name == "spikes"
        assert result.parent.name == "_orphans"
        assert result.parent.parent.name == "workspace"


class TestAllPathsUnderWorkspaceRoot:
    """Setting LFO_WORKSPACE shifts every derived path accordingly."""

    def test_all_paths_under_workspace_root(self, monkeypatch, tmp_path):
        from lfo.services.workspace import (
            db_path,
            novel_dir,
            novel_ref_images_dir,
            novel_spikes_dir,
            orphans_dir,
            orphans_ref_images_dir,
            orphans_spikes_dir,
            project_dir,
            project_final_dir,
            project_inputs_dir,
            project_output_dir,
            resolve_workspace_root,
        )

        custom = tmp_path / "alt-ws"
        monkeypatch.setenv("LFO_WORKSPACE", str(custom))

        ws = resolve_workspace_root()
        # All derived paths must live under the workspace root
        for p in (
            novel_dir("n1"),
            novel_ref_images_dir("n1"),
            novel_spikes_dir("n1"),
            project_dir("n1", "chapter_01"),
            project_output_dir("n1", "chapter_01"),
            project_final_dir("n1", "chapter_01"),
            project_inputs_dir("n1", "chapter_01"),
            orphans_dir(),
            orphans_ref_images_dir(),
            orphans_spikes_dir(),
            db_path(),
        ):
            assert p.is_absolute()
            try:
                p.relative_to(ws)
            except ValueError:
                pytest.fail(f"{p} is not under workspace root {ws}")
