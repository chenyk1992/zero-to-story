"""Workspace path resolution — single source of truth for user-data paths.

LFO has a strict two-layer layout:

- **System space** (git-tracked): the project root, containing
  ``src/lfo/``, ``templates/``, ``tests/``, ``docs/``, and
  ``pyproject.toml``. The user touches this only when upgrading or
  debugging the tool itself.

- **Workspace** (git-ignored): ``<repo_root>/workspace/`` by default,
  overridable via the ``LFO_WORKSPACE`` environment variable. Holds
  user novels, storyboards, run outputs, and the SQLite database.

The workspace itself is novel-centric: every novel is a subtree under
the workspace root, and every chapter of a novel is one LFO video
project (one intake.json, one storyboard.json, one set of outputs).

    workspace/
    ├── <novel_id>/
    │   ├── chapter_01.md           # novel source text (per chapter)
    │   ├── chapter_02.md
    │   ├── notes.md                # character / world / style notes
    │   ├── ref_images/             # per-novel reference images
    │   ├── <chapter_id>/           # one chapter = one video project
    │   │   ├── intake.json
    │   │   ├── storyboard.json
    │   │   ├── inputs/             # manual first frames / per-novel ref copies
    │   │   ├── outputs/            # raw ComfyUI outputs, normalized MP4, end frames
    │   │   ├── final/              # final MP4 + SRT
    │   │   └── notes.md
    │   └── spikes/                 # per-novel experimental data
    ├── _orphans/                   # user assets / experiments not yet assigned to a novel
    │   ├── ref_images/
    │   └── spikes/
    ├── db/
    │   └── lfo.db
    └── README.md

This module centralises path derivation so the rest of the codebase
never hardcodes ``cwd / "pipeline_output"`` or similar. Everything
returns absolute paths.
"""
from __future__ import annotations

import os
from pathlib import Path

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


def novel_dir(novel_id: str) -> Path:
    """``<workspace>/<novel_id>/``

    The novel root holds novel source files (chapter_*.md, notes.md),
    novel-wide reference images, and per-chapter video project
    subdirectories.
    """
    return resolve_workspace_root() / novel_id


def project_dir(novel_id: str, chapter_id: str) -> Path:
    """``<workspace>/<novel_id>/<chapter_id>/``

    A chapter is one LFO video project — owns its own intake.json,
    storyboard.json, inputs/, outputs/, and final/.
    """
    return novel_dir(novel_id) / chapter_id


def project_inputs_dir(novel_id: str, chapter_id: str) -> Path:
    """``<workspace>/<novel_id>/<chapter_id>/inputs/``"""
    return project_dir(novel_id, chapter_id) / "inputs"


def project_output_dir(novel_id: str, chapter_id: str) -> Path:
    """``<workspace>/<novel_id>/<chapter_id>/outputs/``

    LFO's pipeline drops raw ComfyUI output, normalized MP4s, end
    frames, and assembly intermediates here.
    """
    return project_dir(novel_id, chapter_id) / "outputs"


def project_final_dir(novel_id: str, chapter_id: str) -> Path:
    """``<workspace>/<novel_id>/<chapter_id>/final/``

    Where the final MP4 + SRT land after the assembly step.
    """
    return project_dir(novel_id, chapter_id) / "final"


def project_panels_dir(novel_id: str, chapter_id: str) -> Path:
    """``<workspace>/<novel_id>/<chapter_id>/panels/``

    Per-panel ``panel_{nn:02d}_pack.json`` files for r2v reference binding.
    """
    return project_dir(novel_id, chapter_id) / "panels"


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
