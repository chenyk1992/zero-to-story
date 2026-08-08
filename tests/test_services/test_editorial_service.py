"""Tests for EditorialService."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from lfo.core.database import Database
from lfo.services.editorial_service import EditorialService
from lfo.services.media_service import MediaService, SelectedClipAsset
from lfo.services.technical_qc_service import QCResult, TechnicalQCService


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
        "INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, frame_count, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "norm-1", "task-1", "video", "/tmp/norm.mp4", "fh", "ch", 120,
            json.dumps({"fps": 24.0, "codec": "h264", "has_audio": True}),
        ),
    )
    return db


@pytest.fixture
def service(db: Database) -> EditorialService:
    media_svc = MediaService(db, ffmpeg_path="/usr/bin/ffmpeg", ffprobe_path="/usr/bin/ffprobe")
    qc_svc = TechnicalQCService(db)
    return EditorialService(db, media_service=media_svc, qc_service=qc_svc)


class TestCreateSelection:
    def test_creates_draft_with_full_range(self, service: EditorialService, db: Database):
        clip = service.create_selection(
            project_id="proj-1",
            shot_id="shot-1",
            normalized_asset_id="norm-1",
        )
        assert clip.status == "draft"
        assert clip.selected_in_frame == 0
        assert clip.selected_out_frame_exclusive == 120
        assert clip.revision == 1
        assert clip.content_hash != ""
        assert clip.dependency_hash != ""

    def test_creates_draft_with_explicit_range(self, service: EditorialService):
        clip = service.create_selection(
            project_id="proj-1",
            shot_id="shot-1",
            normalized_asset_id="norm-1",
            in_frame=10,
            out_frame_exclusive=80,
        )
        assert clip.selected_in_frame == 10
        assert clip.selected_out_frame_exclusive == 80
        assert clip.fps_num == 24
        assert clip.fps_den == 1

    def test_invalid_frame_range_raises(self, service: EditorialService):
        with pytest.raises(ValueError, match="must be > in_frame"):
            service.create_selection(
                project_id="proj-1",
                shot_id="shot-1",
                normalized_asset_id="norm-1",
                in_frame=50,
                out_frame_exclusive=20,
            )

    def test_asset_not_found_raises(self, service: EditorialService):
        with pytest.raises(ValueError, match="not found"):
            service.create_selection(
                project_id="proj-1",
                shot_id="shot-1",
                normalized_asset_id="nonexistent",
            )

    def test_revision_increments(self, service: EditorialService):
        clip1 = service.create_selection("proj-1", "shot-1", "norm-1")
        clip2 = service.create_selection("proj-1", "shot-1", "norm-1")
        assert clip1.revision == 1
        assert clip2.revision == 2


class TestRenderSelectedClip:
    def test_render_produces_output_asset(
        self, service: EditorialService, db: Database, tmp_path
    ):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)

        fake_output = tmp_path / "clip_output.mp4"
        fake_output.write_bytes(b"fake_clip_data")

        with patch.object(
            MediaService, "create_selected_clip",
            return_value=SelectedClipAsset(
                asset_id="clip-asset-id",
                file_path=str(fake_output),
                in_frame=0,
                out_frame_exclusive=50,
                duration_sec=2.08,
                frame_count=50,
            ),
        ), patch.object(
            TechnicalQCService, "check_asset",
            return_value=QCResult(asset_id="x", task_id="task-1", status="PASS"),
        ):
            result = service.render_selected_clip(clip.selected_clip_id)

        assert result.status == "awaiting_review"
        assert result.output_asset_id != ""

        # Verify asset was registered
        asset_row = db.fetchone(
            "SELECT asset_id, asset_type, file_path FROM assets WHERE asset_id = ?",
            (result.output_asset_id,),
        )
        assert asset_row is not None
        assert asset_row[1] == "video"
        assert str(fake_output) == asset_row[2]

        # Verify asset_relation was created
        rel = db.fetchone(
            "SELECT relation_type FROM asset_relations WHERE source_asset_id = ?",
            ("norm-1",),
        )
        assert rel is not None
        assert rel[0] == "selected_from"

    def test_render_qc_failure_marks_technical_failed(
        self, service: EditorialService, db: Database, tmp_path
    ):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)

        fake_output = tmp_path / "clip_output.mp4"
        fake_output.write_bytes(b"fake_clip_data")

        with patch.object(
            MediaService, "create_selected_clip",
            return_value=SelectedClipAsset(
                asset_id="clip-asset-id",
                file_path=str(fake_output),
                in_frame=0,
                out_frame_exclusive=50,
                duration_sec=2.08,
                frame_count=50,
            ),
        ), patch.object(
            TechnicalQCService, "check_asset",
            return_value=QCResult(
                asset_id="x", task_id="task-1", status="FAIL",
                issues=["no audio"],
            ),
        ):
            result = service.render_selected_clip(clip.selected_clip_id)

        assert result.status == "technical_failed"

    def test_render_extraction_failure_marks_technical_failed(
        self, service: EditorialService, db: Database
    ):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)

        with patch.object(
            MediaService, "create_selected_clip",
            side_effect=RuntimeError("FFmpeg failed"),
        ):
            with pytest.raises(RuntimeError, match="FFmpeg failed"):
                service.render_selected_clip(clip.selected_clip_id)

        row = db.fetchone(
            "SELECT status FROM selected_clips WHERE selected_clip_id = ?",
            (clip.selected_clip_id,),
        )
        assert row[0] == "technical_failed"


class TestApproveSelectedClip:
    def test_approve_marks_approved(
        self, service: EditorialService, db: Database, tmp_path
    ):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        fake_output = tmp_path / "clip.mp4"
        fake_output.write_bytes(b"data")

        with patch.object(
            MediaService, "create_selected_clip",
            return_value=SelectedClipAsset(
                asset_id="x", file_path=str(fake_output),
                in_frame=0, out_frame_exclusive=50,
                duration_sec=2.0, frame_count=50,
            ),
        ), patch.object(
            TechnicalQCService, "check_asset",
            return_value=QCResult(asset_id="x", task_id="task-1", status="PASS"),
        ):
            service.render_selected_clip(clip.selected_clip_id)

        result = service.approve_selected_clip(clip.selected_clip_id)
        assert result.status == "approved"
        assert result.approved_at != ""

    def test_approve_supersedes_old_revision(
        self, service: EditorialService, db: Database, tmp_path
    ):
        fake_output = tmp_path / "clip.mp4"
        fake_output.write_bytes(b"data")

        with patch.object(
            MediaService, "create_selected_clip",
            return_value=SelectedClipAsset(
                asset_id="x", file_path=str(fake_output),
                in_frame=0, out_frame_exclusive=50,
                duration_sec=2.0, frame_count=50,
            ),
        ), patch.object(
            TechnicalQCService, "check_asset",
            return_value=QCResult(asset_id="x", task_id="task-1", status="PASS"),
        ):
            clip1 = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
            service.render_selected_clip(clip1.selected_clip_id)
            service.approve_selected_clip(clip1.selected_clip_id)

            clip2 = service.create_selection("proj-1", "shot-1", "norm-1", 10, 60)
            service.render_selected_clip(clip2.selected_clip_id)
            service.approve_selected_clip(clip2.selected_clip_id)

        # Old revision should be superseded
        old = db.fetchone(
            "SELECT status, superseded_by FROM selected_clips WHERE selected_clip_id = ?",
            (clip1.selected_clip_id,),
        )
        assert old[0] == "superseded"
        assert old[1] == clip2.selected_clip_id

        # New revision should be approved
        new = db.fetchone(
            "SELECT status FROM selected_clips WHERE selected_clip_id = ?",
            (clip2.selected_clip_id,),
        )
        assert new[0] == "approved"

    def test_approve_wrong_status_raises(self, service: EditorialService):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        with pytest.raises(ValueError, match="Cannot approve"):
            service.approve_selected_clip(clip.selected_clip_id)


class TestRejectSelectedClip:
    def test_reject_marks_rejected(self, service: EditorialService, db: Database, tmp_path):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        fake_output = tmp_path / "clip.mp4"
        fake_output.write_bytes(b"data")

        with patch.object(
            MediaService, "create_selected_clip",
            return_value=SelectedClipAsset(
                asset_id="x", file_path=str(fake_output),
                in_frame=0, out_frame_exclusive=50,
                duration_sec=2.0, frame_count=50,
            ),
        ), patch.object(
            TechnicalQCService, "check_asset",
            return_value=QCResult(asset_id="x", task_id="task-1", status="PASS"),
        ):
            service.render_selected_clip(clip.selected_clip_id)

        result = service.reject_selected_clip(clip.selected_clip_id, "bad framing")
        assert result.status == "rejected"

    def test_reject_wrong_status_raises(self, service: EditorialService):
        clip = service.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_selected_clip(clip.selected_clip_id, "reason")
