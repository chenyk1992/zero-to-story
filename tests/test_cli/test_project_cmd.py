"""Tests for project init CLI command."""
from __future__ import annotations

import os
import tempfile

import pytest

from lfo.cli.project_cmd import cmd_project_init


@pytest.fixture
def db_file():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


def test_project_init_creates_project_and_profile(db_file):
    result = cmd_project_init(db_file, "new_proj")
    assert result["project_id"] == "new_proj"
    assert "profile_revision_id" in result
    assert result["visual_input_policy"] == "allow_t2va_fallback"


def test_project_init_with_custom_policy(db_file):
    result = cmd_project_init(db_file, "custom_proj", visual_input_policy="visual_required")
    assert result["visual_input_policy"] == "visual_required"


def test_project_init_idempotent(db_file):
    """Initializing twice doesn't fail (project already exists)."""
    cmd_project_init(db_file, "dup_proj")
    result = cmd_project_init(db_file, "dup_proj")
    assert result["project_id"] == "dup_proj"
    assert "profile_revision_id" in result


def test_project_init_activates_profile(db_file):
    """After init, the profile should be active."""
    cmd_project_init(db_file, "active_proj")
    from lfo.application.visual_profile_service import VisualProfileService
    from lfo.core.database import Database
    db = Database(db_file)
    db.init_schema()
    svc = VisualProfileService(db)
    active = svc.get_active("active_proj")
    db.close()
    assert active is not None
    assert active["status"] == "active"
