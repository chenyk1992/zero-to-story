"""Workspace path resolution — the single source of truth for user data.

The Runtime owns project-scoped media under
``<workspace>/projects/<project_id>/``.  The SQLite database and CAS remain
global workspace services; generated media must never be routed through
workspace-level ``runs`` or ``exports`` directories.
"""
from __future__ import annotations

import os
from pathlib import Path

from lfo.services.artifact_layout import safe_component

#: Environment variable that overrides the default workspace location.
#: Set this to point LFO at a different drive or parent directory.
ENV_VAR = "LFO_WORKSPACE"


def _repo_root() -> Path:
    """Absolute path to the LFO project root.

    In the src layout this file lives at ``<repo>/src/lfo/services/workspace.py``,
    so we walk up three parents to reach the repo root (the directory
    containing ``pyproject.toml``).
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def resolve_workspace_root() -> Path:
    """Return the workspace root directory as an absolute Path.

    Priority:
        1. ``$LFO_WORKSPACE`` — resolved to absolute if relative.
        2. ``<repo_root>/workspace/`` (default).

    The function never creates the directory. Callers that need a
    guaranteed-on-disk path should call ``.mkdir(parents=True)``
    themselves so the policy is explicit.
    """
    env_val = os.environ.get(ENV_VAR)
    if env_val:
        path = Path(env_val).resolve()
        return path
    return _repo_root() / "workspace"


def project_dir(project_id: str) -> Path:
    """Return ``<workspace>/projects/<project_id>`` as an absolute path."""
    return resolve_workspace_root() / "projects" / safe_component(project_id, field="project_id")


def project_outputs_dir(project_id: str, run_id: str) -> Path:
    """Return the managed output root for one project Run."""
    return project_dir(project_id) / "outputs" / safe_component(run_id, field="run_id")


def project_final_dir(project_id: str, publication_directory: str) -> Path:
    """Return the versioned final directory for one project."""
    return project_dir(project_id) / "final" / safe_component(
        publication_directory, field="output.directory"
    )


def runtime_db_path() -> Path:
    """Return the Runtime v1 database path under the active workspace."""
    return resolve_workspace_root() / "db" / "runtime-v1.sqlite3"


def novel_dir(novel_id: str) -> Path:
    """``<workspace>/<novel_id>/``

    The novel root holds novel source files (chapter_*.md, notes.md),
    novel-wide reference images, and per-chapter video project
    subdirectories.
    """
    return resolve_workspace_root() / novel_id


def novel_ref_images_dir(novel_id: str) -> Path:
    """``<workspace>/<novel_id>/ref_images/``"""
    return novel_dir(novel_id) / "ref_images"


def novel_spikes_dir(novel_id: str) -> Path:
    """``<workspace>/<novel_id>/spikes/``"""
    return novel_dir(novel_id) / "spikes"


def orphans_dir() -> Path:
    """``<workspace>/_orphans/``

    Catch-all for user assets and experiment data that have not yet
    been assigned to a specific novel. Move files into the right
    novel's subtree when you decide where they belong.
    """
    return resolve_workspace_root() / "_orphans"


def orphans_ref_images_dir() -> Path:
    """``<workspace>/_orphans/ref_images/``"""
    return orphans_dir() / "ref_images"


def orphans_spikes_dir() -> Path:
    """``<workspace>/_orphans/spikes/``"""
    return orphans_dir() / "spikes"


def db_path() -> Path:
    """``<workspace>/db/lfo.db``"""
    return resolve_workspace_root() / "db" / "lfo.db"
