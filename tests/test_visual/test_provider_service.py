"""Tests for VisualProviderService."""
from __future__ import annotations

import pytest

from lfo.application.visual_provider_service import VisualProviderService
from lfo.core.database import Database
from lfo.visual.capabilities import VisualCapabilities
from lfo.visual.errors import VisualProviderError


def _svc(db: Database) -> VisualProviderService:
    return VisualProviderService(db)


def test_create_draft_returns_id():
    db = Database()
    db.init_schema()
    svc = _svc(db)
    rid = svc.create_draft(
        provider_id="openai-dall-e",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://api.openai.com/v1/images/generations"},
        capabilities={"text_to_image": True, "reference_to_image": True},
    )
    assert rid is not None
    assert len(rid) > 0
    db.close()


def test_activate_then_resolve_active():
    db = Database()
    db.init_schema()
    svc = _svc(db)
    rid = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://x.com"},
        capabilities={"text_to_image": True},
    )
    svc.activate(rid)
    result = svc.resolve_active("p1", project_id="any")
    assert result is not None
    assert result["revision_id"] == rid
    assert result["provider_id"] == "p1"
    db.close()


def test_one_active_per_scope():
    """Activating a new draft supersedes the old active in the same scope."""
    db = Database()
    db.init_schema()
    svc = _svc(db)
    rid1 = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://x.com/v1"},
        capabilities={"text_to_image": True},
    )
    svc.activate(rid1)
    rid2 = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://x.com/v2"},
        capabilities={"text_to_image": True, "reference_to_image": True},
    )
    svc.activate(rid2)
    result = svc.resolve_active("p1", project_id="proj1")
    assert result is not None
    assert result["revision_id"] == rid2
    # Old active is now superseded
    old = db.fetchone(
        "SELECT status FROM visual_provider_revisions WHERE revision_id = ?",
        (rid1,),
    )
    assert old[0] == "superseded"
    db.close()


def test_project_scope_beats_global():
    """Project-scoped active provider resolves before global."""
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    svc = _svc(db)
    global_rid = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://global.com"},
        capabilities={"text_to_image": True},
    )
    svc.activate(global_rid)
    project_rid = svc.create_draft(
        provider_id="p1",
        scope_type="project",
        scope_id="proj1",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://project.com"},
        capabilities={"text_to_image": True, "reference_to_image": True},
    )
    svc.activate(project_rid)
    result = svc.resolve_active("p1", project_id="proj1")
    assert result is not None
    assert result["revision_id"] == project_rid
    db.close()


def test_resolve_active_none_when_no_active():
    db = Database()
    db.init_schema()
    svc = _svc(db)
    result = svc.resolve_active("nonexistent", project_id="proj1")
    assert result is None
    db.close()


def test_disable_sets_status_disabled():
    db = Database()
    db.init_schema()
    svc = _svc(db)
    rid = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://x.com"},
        capabilities={"text_to_image": True},
    )
    svc.activate(rid)
    svc.disable(rid)
    row = db.fetchone(
        "SELECT status FROM visual_provider_revisions WHERE revision_id = ?",
        (rid,),
    )
    assert row[0] == "disabled"
    # After disable, resolve returns None
    assert svc.resolve_active("p1", project_id="any") is None
    db.close()


def test_create_draft_validates_config():
    """Invalid config raises at create time."""
    db = Database()
    db.init_schema()
    svc = _svc(db)
    with pytest.raises(VisualProviderError):
        svc.create_draft(
            provider_id="p1",
            scope_type="global",
            scope_id="*",
            provider_type="managed",
            adapter_name="http_post",
            config={},  # missing endpoint
            capabilities={"text_to_image": True},
        )
    db.close()


def test_create_draft_stores_capabilities():
    db = Database()
    db.init_schema()
    svc = _svc(db)
    caps = VisualCapabilities(
        text_to_image=True,
        reference_to_image=True,
        multi_reference=True,
    )
    rid = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://x.com"},
        capabilities={
            "text_to_image": caps.text_to_image,
            "reference_to_image": caps.reference_to_image,
            "multi_reference": caps.multi_reference,
        },
    )
    svc.activate(rid)
    result = svc.resolve_active("p1", project_id="any")
    assert result is not None
    assert result["config"]["endpoint"] == "https://x.com"
    db.close()


def test_different_providers_independent():
    """Two providers in the same scope activate independently."""
    db = Database()
    db.init_schema()
    svc = _svc(db)
    rid1 = svc.create_draft(
        provider_id="p1",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://p1.com"},
        capabilities={"text_to_image": True},
    )
    rid2 = svc.create_draft(
        provider_id="p2",
        scope_type="global",
        scope_id="*",
        provider_type="managed",
        adapter_name="http_post",
        config={"endpoint": "https://p2.com"},
        capabilities={"text_to_image": True},
    )
    svc.activate(rid1)
    svc.activate(rid2)
    r1 = svc.resolve_active("p1", project_id="any")
    r2 = svc.resolve_active("p2", project_id="any")
    assert r1["revision_id"] == rid1
    assert r2["revision_id"] == rid2
    db.close()
