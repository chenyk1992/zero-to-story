"""Tests for Wave 2-A: ContinuityService."""
from __future__ import annotations

import pytest

from lfo.core.database import Database
from lfo.services.continuity_service import ContinuityService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"))
    db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path) VALUES (?, ?, ?, ?)",
               ("frame-1", "task-1", "image", "/tmp/frame1.png"))
    db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path) VALUES (?, ?, ?, ?)",
               ("frame-2", "task-1", "image", "/tmp/frame2.png"))
    return db


@pytest.fixture
def service(db) -> ContinuityService:
    return ContinuityService(db)


class TestBindEndFrame:
    def test_bind_creates_ready_state(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        assert rec.status == "ready"
        assert rec.source_shot_id == "shot-1"
        assert rec.shot_id == "shot-2"
        assert rec.end_frame_asset_id == "frame-1"

    def test_bind_with_state_json(self, service):
        state = {"character": "samurai", "costume": "blue", "pose": "standing"}
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1", state)
        assert rec.state_json == state

    def test_bind_multiple_shots(self, service):
        r1 = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        r2 = service.bind_end_frame_to_shot("proj-1", "shot-2", "shot-3", "frame-2")
        assert r1.continuity_id != r2.continuity_id
        assert r1.shot_id == "shot-2"
        assert r2.shot_id == "shot-3"


class TestApproveReject:
    def test_approve(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        approved = service.approve_continuity(rec.continuity_id, "director")
        assert approved.status == "approved"
        assert approved.approved_by == "director"
        assert approved.approved_at != ""

    def test_reject(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        rejected = service.reject_continuity(rec.continuity_id)
        assert rejected.status == "rejected"

    def test_approve_wrong_status_raises(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        service.approve_continuity(rec.continuity_id)
        with pytest.raises(ValueError, match="Cannot approve"):
            service.approve_continuity(rec.continuity_id)

    def test_reject_wrong_status_raises(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        service.reject_continuity(rec.continuity_id)
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_continuity(rec.continuity_id)


class TestQuery:
    def test_get_for_shot(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        service.approve_continuity(rec.continuity_id)
        found = service.get_continuity_for_shot("proj-1", "shot-2")
        assert found is not None
        assert found.continuity_id == rec.continuity_id

    def test_get_pending(self, service):
        service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        service.bind_end_frame_to_shot("proj-1", "shot-2", "shot-3", "frame-2")
        pending = service.get_pending_for_project("proj-1")
        assert len(pending) == 2

    def test_update_state(self, service):
        rec = service.bind_end_frame_to_shot("proj-1", "shot-1", "shot-2", "frame-1")
        updated = service.update_state_json(rec.continuity_id, {"prop": "sword"})
        assert updated.state_json == {"prop": "sword"}
