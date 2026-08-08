"""Tests for visual CLI commands."""
from __future__ import annotations

import os
import tempfile

import pytest

from lfo.cli.visual_cmd import (
    cmd_visual_profile_activate,
    cmd_visual_profile_clone,
    cmd_visual_profile_create,
    cmd_visual_profile_show,
    cmd_visual_provider_create,
    cmd_visual_provider_disable,
    cmd_visual_provider_list,
    cmd_visual_route_dry_run,
    cmd_visual_task_list,
)


@pytest.fixture
def db_file():
    """Create a temp DB file for the test module."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


def test_profile_show_not_found(db_file):
    result = cmd_visual_profile_show(db_file, "nonexistent")
    assert result["found"] is False


def test_profile_create_and_show(db_file):
    result = cmd_visual_profile_create(db_file, "proj1", {"visual_input_policy": "visual_required"})
    assert "revision_id" in result
    # Activate so get_active finds it
    cmd_visual_profile_activate(db_file, result["revision_id"])
    show = cmd_visual_profile_show(db_file, "proj1")
    assert show["found"] is True


def test_profile_activate(db_file):
    create_result = cmd_visual_profile_create(db_file, "proj2", {"visual_input_policy": "allow_t2va_fallback"})
    rev_id = create_result["revision_id"]
    activate_result = cmd_visual_profile_activate(db_file, rev_id)
    assert activate_result["activated"] == rev_id


def test_profile_clone(db_file):
    create_result = cmd_visual_profile_create(db_file, "proj3", {"visual_input_policy": "visual_required"})
    rev_id = create_result["revision_id"]
    clone_result = cmd_visual_profile_clone(db_file, rev_id)
    assert clone_result["parent_revision_id"] == rev_id
    assert clone_result["clone_revision_id"] != rev_id


def test_provider_list_empty(db_file):
    result = cmd_visual_provider_list(db_file)
    assert result["providers"] == []


def test_provider_create_and_list(db_file):
    result = cmd_visual_provider_create(
        db_file, "p1", "global", "*", "managed",
        {"endpoint": "http://fake"},
        {"text_to_image": True},
    )
    assert "revision_id" in result
    list_result = cmd_visual_provider_list(db_file)
    assert len(list_result["providers"]) == 1
    assert list_result["providers"][0]["provider_id"] == "p1"


def test_provider_disable(db_file):
    create_result = cmd_visual_provider_create(
        db_file, "p2", "global", "*", "manual", {}, {},
    )
    rev_id = create_result["revision_id"]
    # Activate the provider first (disable requires active state)
    from lfo.application.visual_provider_service import VisualProviderService
    from lfo.core.database import Database
    db = Database(db_file)
    db.init_schema()
    psvc = VisualProviderService(db)
    psvc.activate(rev_id)
    db.close()
    disable_result = cmd_visual_provider_disable(db_file, rev_id)
    assert disable_result["disabled"] == rev_id


def test_task_list_empty(db_file):
    result = cmd_visual_task_list(db_file)
    assert result["tasks"] == []


def test_route_dry_run_no_provider(db_file):
    result = cmd_visual_route_dry_run(db_file, "proj1", "character_reference", ["text_to_image"])
    assert result["routed"] is False
