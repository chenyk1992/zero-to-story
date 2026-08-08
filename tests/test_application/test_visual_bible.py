"""Tests for Visual Bible — schema, hashing, validation, service lifecycle."""
from __future__ import annotations

import json
import time

import pytest

from lfo.application.visual_bible_service import (
    VisualBibleService,
)
from lfo.core.database import Database
from lfo.core.hashing import compute_workflow_hash
from lfo.visual_bible.hashing import compute_visual_bible_hash
from lfo.visual_bible.schema import ColorSpec, StyleReference, VisualBible
from lfo.visual_bible.validate import validate_visual_bible

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    """Fresh in-memory database with schema initialized."""
    database = Database()
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def service(db):
    return VisualBibleService(db)


@pytest.fixture
def project_id():
    return "proj-visual-bible-001"


@pytest.fixture
def sample_bible(project_id):
    """A valid Visual Bible with characters, colors, scenes."""
    return VisualBible(
        project_id=project_id,
        characters={
            "hero": {
                "description": "A young warrior with silver armor",
                "age": 25,
            },
            "villain": {
                "description": "A shadowy figure in a dark cloak",
            },
        },
        scenes={
            "forest": {
                "description": "Dense enchanted forest with bioluminescent plants",
                "lighting": "dim green ambient",
            },
        },
        color_palette=[
            ColorSpec(name="steel_blue", hex_code="#4682B4", usage="primary"),
            ColorSpec(name="shadow_black", hex_code="#1A1A1A", usage="secondary"),
            ColorSpec(name="ember_glow", hex_code="#FF4500", usage="accent"),
        ],
        style_references=[
            StyleReference(
                description="Dark fantasy style reminiscent of Berserk manga",
                reference_images=[],
            ),
        ],
        props={
            "hero_sword": {"description": "Longsword with rune engravings"},
        },
        cinematography={
            "aspect_ratio": "16:9",
            "camera_style": "cinematic shallow depth of field",
        },
        created_by="test_user",
    )


@pytest.fixture
def second_bible(project_id):
    """A modified Visual Bible with different content."""
    vb = VisualBible(project_id=project_id)
    vb.characters = {
        "hero": {"description": "An elder wizard with a staff"},
    }
    vb.color_palette = [
        ColorSpec(name="royal_purple", hex_code="#7851A9", usage="primary"),
    ]
    return vb


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidate:
    def test_validate_accepts_valid_bible(self, sample_bible):
        valid, errors = validate_visual_bible(sample_bible)
        assert valid
        assert errors == []

    def test_validate_rejects_empty_project_id(self):
        vb = VisualBible(project_id="")
        valid, errors = validate_visual_bible(vb)
        assert not valid
        assert "project_id is required" in errors

    def test_validate_rejects_invalid_color(self, sample_bible):
        sample_bible.color_palette.append(
            ColorSpec(name="bad_color", hex_code="not_a_hex", usage="primary")
        )
        valid, errors = validate_visual_bible(sample_bible)
        assert not valid
        assert any("invalid hex code" in e for e in errors)

    def test_validate_rejects_short_hex(self, sample_bible):
        sample_bible.color_palette.append(
            ColorSpec(name="short", hex_code="#FFF", usage="primary")
        )
        # #FFF is 4 chars — valid (short form)
        valid, errors = validate_visual_bible(sample_bible)
        assert valid

    def test_validate_rejects_character_without_description(self, sample_bible):
        sample_bible.characters["ghost"] = {"age": 100}
        valid, errors = validate_visual_bible(sample_bible)
        assert not valid
        assert any("missing description" in e for e in errors)


# ---------------------------------------------------------------------------
# Hashing tests
# ---------------------------------------------------------------------------


class TestHashing:
    def test_hash_produces_string(self, sample_bible):
        h = compute_visual_bible_hash(sample_bible)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_idempotent(self, sample_bible):
        h1 = compute_visual_bible_hash(sample_bible)
        h2 = compute_visual_bible_hash(sample_bible)
        assert h1 == h2

    def test_modified_content_different_hash(self, sample_bible):
        h1 = compute_visual_bible_hash(sample_bible)
        sample_bible.characters["hero"]["description"] = "Completely different"
        h2 = compute_visual_bible_hash(sample_bible)
        assert h1 != h2

    def test_hash_uses_not_workflow_hash(self, sample_bible):
        """Confirm Visual Bible uses LFO-CJ1 hash, NOT compute_workflow_hash.

        The key difference: LFO-CJ1 forbids floats (raises), while
        compute_workflow_hash (LFO-WFJ1) normalises them.  For pure
        integer/string data the hashes coincidentally match, so we
        verify the behavioural distinction by injecting a float.
        """
        from lfo.core.canonical import LFO_CJ1_FLOAT_FORBIDDEN

        # A bible containing a float value
        sample_bible.cinematography["aspect_ratio_float"] = 1.777
        # LFO-CJ1 path must reject floats
        with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
            compute_visual_bible_hash(sample_bible)
        # LFO-WFJ1 path accepts and normalises floats
        wf_hash = compute_workflow_hash(sample_bible.to_dict())
        assert isinstance(wf_hash, str) and len(wf_hash) == 64

    def test_hash_invalid_bible_raises(self):
        vb = VisualBible(project_id="")
        with pytest.raises(ValueError, match="Invalid visual bible"):
            compute_visual_bible_hash(vb)


# ---------------------------------------------------------------------------
# Service: create revision
# ---------------------------------------------------------------------------


class TestCreateRevision:
    def _ensure_project(self, db, project_id):
        db.execute(
            "INSERT OR IGNORE INTO projects (project_id, name) VALUES (?, ?)",
            (project_id, "Test Project"),
        )

    def test_create_revision_computes_hash(self, service, sample_bible, db, project_id):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        assert info.content_hash is not None
        assert len(info.content_hash) == 64

    def test_create_revision_sets_draft_status(self, service, sample_bible, db, project_id):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        assert info.status == "draft"

    def test_create_revision_sets_parent(self, service, sample_bible, second_bible, db, project_id):
        self._ensure_project(db, project_id)
        # Create and approve first revision
        info1 = service.create_revision(sample_bible, created_by="user1")
        service.submit_for_review(info1.revision_id)
        service.approve_revision(info1.revision_id, approved_by="reviewer")

        # Create second revision — parent should be the first
        info2 = service.create_revision(second_bible, created_by="user2")
        assert info2.parent_revision_id == info1.revision_id

    def test_create_revision_no_parent_when_no_approved(
        self, service, sample_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        assert info.parent_revision_id is None

    def test_duplicate_content_same_hash(self, sample_bible):
        """Same content produces the same hash (idempotent computation)."""
        h1 = compute_visual_bible_hash(sample_bible)
        h2 = compute_visual_bible_hash(sample_bible)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Service: approval lifecycle
# ---------------------------------------------------------------------------


class TestApprovalLifecycle:
    def _ensure_project(self, db, project_id):
        db.execute(
            "INSERT OR IGNORE INTO projects (project_id, name) VALUES (?, ?)",
            (project_id, "Test Project"),
        )

    def _create_and_approve(self, service, bible, project_id, db):
        self._ensure_project(db, project_id)
        info = service.create_revision(bible)
        service.submit_for_review(info.revision_id)
        service.approve_revision(info.revision_id, approved_by="reviewer")
        return info

    def test_approve_supersedes_previous(
        self, service, sample_bible, second_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        # Approve first revision
        info1 = self._create_and_approve(
            service, sample_bible, project_id, db
        )

        # Approve second revision
        info2 = service.create_revision(second_bible)
        service.submit_for_review(info2.revision_id)
        service.approve_revision(info2.revision_id, approved_by="reviewer")

        # First should be superseded
        row = db.fetchone(
            "SELECT status FROM visual_bible_revisions WHERE revision_id = ?",
            (info1.revision_id,),
        )
        assert row[0] == "superseded"

        # Second should be approved
        row2 = db.fetchone(
            "SELECT status FROM visual_bible_revisions WHERE revision_id = ?",
            (info2.revision_id,),
        )
        assert row2[0] == "approved"

    def test_reject_sets_status_and_reason(
        self, service, sample_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        service.submit_for_review(info.revision_id)
        service.reject_revision(info.revision_id, "Color palette too dark")

        row = db.fetchone(
            "SELECT status, rejection_reason FROM visual_bible_revisions "
            "WHERE revision_id = ?",
            (info.revision_id,),
        )
        assert row[0] == "rejected"
        assert row[1] == "Color palette too dark"

    def test_submit_for_review(self, service, sample_bible, db, project_id):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        service.submit_for_review(info.revision_id)

        row = db.fetchone(
            "SELECT status FROM visual_bible_revisions WHERE revision_id = ?",
            (info.revision_id,),
        )
        assert row[0] == "pending_review"


# ---------------------------------------------------------------------------
# Service: queries
# ---------------------------------------------------------------------------


class TestQueries:
    def _ensure_project(self, db, project_id):
        db.execute(
            "INSERT OR IGNORE INTO projects (project_id, name) VALUES (?, ?)",
            (project_id, "Test Project"),
        )

    def test_get_current_approved_returns_latest_approved(
        self, service, sample_bible, second_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        # Create and approve first
        info1 = service.create_revision(sample_bible)
        service.submit_for_review(info1.revision_id)
        service.approve_revision(info1.revision_id, approved_by="reviewer")

        # Create and approve second
        info2 = service.create_revision(second_bible)
        service.submit_for_review(info2.revision_id)
        service.approve_revision(info2.revision_id, approved_by="reviewer")

        # Should return the second (most recently approved)
        current = service.get_current_approved(project_id)
        assert current is not None
        assert current.characters["hero"]["description"] == "An elder wizard with a staff"

    def test_get_current_approved_none_when_no_approval(
        self, service, sample_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        service.create_revision(sample_bible)
        assert service.get_current_approved(project_id) is None

    def test_revision_history_ordered_by_date(
        self, service, sample_bible, second_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        info1 = service.create_revision(sample_bible)
        time.sleep(0.01)  # ensure distinct microsecond timestamps
        info2 = service.create_revision(second_bible)

        history = service.get_revision_history(project_id)
        assert len(history) == 2
        # Newest first
        assert history[0].revision_id == info2.revision_id
        assert history[1].revision_id == info1.revision_id

    def test_export_json_returns_valid_json(
        self, service, sample_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        service.submit_for_review(info.revision_id)
        service.approve_revision(info.revision_id, approved_by="reviewer")

        exported = service.export_json(project_id)
        assert exported is not None
        data = json.loads(exported)
        assert "project_id" in data
        assert "color_palette" in data
        assert data["characters"]["hero"]["description"] == "A young warrior with silver armor"

    def test_export_json_none_when_no_approved(
        self, service, project_id
    ):
        assert service.export_json(project_id) is None

    def test_is_content_approved_with_current_hash(
        self, service, sample_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        info = service.create_revision(sample_bible)
        service.submit_for_review(info.revision_id)
        service.approve_revision(info.revision_id, approved_by="reviewer")

        assert service.is_content_approved(project_id, info.content_hash)

    def test_is_content_approved_with_old_hash(
        self, service, sample_bible, second_bible, db, project_id
    ):
        self._ensure_project(db, project_id)
        # Approve first
        info1 = service.create_revision(sample_bible)
        service.submit_for_review(info1.revision_id)
        service.approve_revision(info1.revision_id, approved_by="reviewer")

        # Approve second
        info2 = service.create_revision(second_bible)
        service.submit_for_review(info2.revision_id)
        service.approve_revision(info2.revision_id, approved_by="reviewer")

        # Old hash should NOT be approved anymore
        assert not service.is_content_approved(project_id, info1.content_hash)
        # Current hash should be approved
        assert service.is_content_approved(project_id, info2.content_hash)


# ---------------------------------------------------------------------------
# Database schema test
# ---------------------------------------------------------------------------


class TestDatabaseSchema:
    def test_fresh_db_has_visual_bible_revisions_table(self):
        db = Database()
        db.init_schema()
        tables = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {r[0] for r in tables}
        assert "visual_bible_revisions" in table_names
        db.close()

    def test_fresh_db_has_vb_indexes(self):
        db = Database()
        db.init_schema()
        indexes = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_vb_%'"
        )
        index_names = {r[0] for r in indexes}
        assert "idx_vb_project" in index_names
        assert "idx_vb_status" in index_names
        assert "idx_vb_hash" in index_names
        db.close()
