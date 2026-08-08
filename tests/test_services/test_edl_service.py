"""Tests for EDLService."""
from __future__ import annotations

import json

import pytest

from lfo.core.database import Database
from lfo.services.edl_service import CLIP_SELECTOR_CURRENT_APPROVED, EDLService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
        ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("norm-1", "task-1", "video", "/tmp/norm.mp4", "fh", "ch", 120),
    )
    db.execute(
        """INSERT INTO selected_clips
           (selected_clip_id, project_id, shot_id, normalized_asset_id,
            output_asset_id, selected_in_frame, selected_out_frame_exclusive,
            fps_num, fps_den, render_policy_id, revision, status,
            content_hash, dependency_hash, created_at, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "clip-1", "proj-1", "shot-1", "norm-1",
            "norm-1", 0, 120, 24, 1, "selected_clip_v1", 1, "approved",
            "ch", "dh", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
        ),
    )
    return db


@pytest.fixture
def service(db: Database) -> EDLService:
    return EDLService(db)


class TestCreateEDL:
    def test_creates_draft_with_shot_order(self, service: EDLService):
        edl = service.create_edl(
            project_id="proj-1",
            shot_ids=["shot-1", "shot-2", "shot-3"],
        )
        assert edl.status == "draft"
        assert edl.revision == 1
        assert edl.content_hash != ""

        doc = json.loads(edl.content_json)
        assert doc["shots"] == ["shot-1", "shot-2", "shot-3"]
        assert len(doc["video_track"]["clips"]) == 3
        assert doc["video_track"]["clips"][0]["clip_selector"] == CLIP_SELECTOR_CURRENT_APPROVED

    def test_revision_increments(self, service: EDLService):
        edl1 = service.create_edl("proj-1", ["shot-1"])
        edl2 = service.create_edl("proj-1", ["shot-1"])
        assert edl1.revision == 1
        assert edl2.revision == 2

    def test_default_export_profile(self, service: EDLService):
        edl = service.create_edl("proj-1", ["shot-1"])
        doc = json.loads(edl.content_json)
        assert doc["export_profile_id"] == "vertical_h264_v1"
        assert doc["transition"] == "hard_cut"


class TestResolveClips:
    def test_resolves_current_approved(self, service: EDLService, db: Database):
        edl = service.create_edl("proj-1", ["shot-1"])
        resolved = service.resolve_clips(edl.edl_id)
        assert len(resolved) == 1
        assert resolved[0].selected_clip_id == "clip-1"
        assert resolved[0].selected_clip_revision == 1

    def test_no_approved_clip_raises(self, service: EDLService):
        edl = service.create_edl("proj-1", ["shot-99"])
        with pytest.raises(ValueError, match="No approved clip"):
            service.resolve_clips(edl.edl_id)

    def test_edl_not_found_raises(self, service: EDLService):
        with pytest.raises(ValueError, match="not found"):
            service.resolve_clips("nonexistent")


class TestApproveEDL:
    def test_approve_marks_approved(self, service: EDLService):
        edl = service.create_edl("proj-1", ["shot-1"])
        result = service.approve_edl(edl.edl_id)
        assert result.status == "approved"
        assert result.approved_at != ""

    def test_approve_wrong_status_raises(self, service: EDLService):
        edl = service.create_edl("proj-1", ["shot-1"])
        service.approve_edl(edl.edl_id)
        with pytest.raises(ValueError, match="Cannot approve"):
            service.approve_edl(edl.edl_id)
