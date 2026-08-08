"""Tests for VisualProfileService."""
from __future__ import annotations

import pytest

from lfo.application.visual_profile_service import VisualProfileService
from lfo.core.database import Database
from lfo.visual.errors import VisualContractError


def _svc(db: Database) -> VisualProfileService:
    return VisualProfileService(db)


def test_create_draft_returns_id():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    rid = svc.create_draft("proj1", {
        "visual_input_policy": "visual_required",
        "technical_checks": ["decodable", "hash"],
        "review_checklist": ["identity"],
    })
    assert rid is not None
    db.close()


def test_activate_and_get_active():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    rid = svc.create_draft("proj1", {"visual_input_policy": "allow_t2va_fallback"})
    svc.activate(rid)
    active = svc.get_active("proj1")
    assert active is not None
    assert active["revision_id"] == rid
    assert active["content"]["visual_input_policy"] == "allow_t2va_fallback"
    db.close()


def test_one_active_per_project():
    """Activating new profile supersedes old."""
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    rid1 = svc.create_draft("proj1", {"visual_input_policy": "allow_t2va_fallback"})
    svc.activate(rid1)
    rid2 = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid2)
    active = svc.get_active("proj1")
    assert active["revision_id"] == rid2
    old = db.fetchone(
        "SELECT status FROM visual_generation_profile_revisions WHERE revision_id = ?",
        (rid1,),
    )
    assert old[0] == "superseded"
    db.close()


def test_get_active_none_when_no_profile():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    assert svc.get_active("proj1") is None
    db.close()


def test_clone_creates_draft_with_parent():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    rid = svc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    svc.activate(rid)
    clone_rid = svc.clone(rid)
    row = db.fetchone(
        "SELECT parent_revision_id, status, project_id "
        "FROM visual_generation_profile_revisions WHERE revision_id = ?",
        (clone_rid,),
    )
    assert row[0] == rid  # parent = original
    assert row[1] == "draft"  # clone is a draft
    assert row[2] == "proj1"
    db.close()


def test_create_draft_validates_invalid_policy():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    with pytest.raises(VisualContractError):
        svc.create_draft("proj1", {"visual_input_policy": "invalid_value"})
    db.close()


def test_different_projects_independent():
    """Each project has its own active profile."""
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj2', 'n')")
    svc = _svc(db)
    rid1 = svc.create_draft("proj1", {"visual_input_policy": "allow_t2va_fallback"})
    rid2 = svc.create_draft("proj2", {"visual_input_policy": "visual_required"})
    svc.activate(rid1)
    svc.activate(rid2)
    a1 = svc.get_active("proj1")
    a2 = svc.get_active("proj2")
    assert a1["revision_id"] == rid1
    assert a2["revision_id"] == rid2
    assert a1["content"]["visual_input_policy"] == "allow_t2va_fallback"
    assert a2["content"]["visual_input_policy"] == "visual_required"
    db.close()
