"""Tests for DAG integration, dual gate, and panel-only graph (Task 8).

Covers:
- check_visual_assets_ready with allow_t2va_fallback / visual_required policies
- Graph service emits only video/panel_* tasks (no shot video path)
- Dual gate: video READY requires visual deps in APPROVED
"""
from __future__ import annotations

import hashlib

import pytest

from lfo.application.visual_profile_service import VisualProfileService
from lfo.core.database import Database
from lfo.planning.panel_pack import build_panel_pack
from lfo.planning.workflow_selector import select_workflow_for_panel
from lfo.services.storyboard_graph_service import StoryboardGraphService
from lfo.services.task_readiness_service import TaskReadinessService
from lfo.storyboard.storyboard import (
    Beat,
    CharacterAppearance,
    Panel,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def _make_panel_storyboard(num_panels: int = 3) -> Storyboard:
    panels = [
        Panel(
            panel_id=f"panel_{i:03d}",
            sequence=i,
            beat_range=(1, 8),
            beat_ids=[f"beat_{j:03d}" for j in range(1, 9)],
            desired_duration_ms=15_000,
            bw_asset_id=f"asset_bw_{i:03d}",
        )
        for i in range(1, num_panels + 1)
    ]
    beats = [
        Beat(
            beat_id=f"beat_{i:03d}",
            sequence=i,
            scene_id="scene_001",
            description=f"Beat {i}",
            characters=[CharacterAppearance(character_id="char_001")],
        )
        for i in range(1, 9)
    ]
    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        style=StyleGuide(medium_lock="Medium: 3D rendered suspense."),
        beats=beats,
        panels=panels,
    )


def _make_profile(db: Database, project_id: str, policy: str = "allow_t2va_fallback") -> str:
    service = VisualProfileService(db)
    revision_id = service.create_draft(project_id, {"visual_input_policy": policy})
    service.activate(revision_id)
    return revision_id


def _create_project(db: Database, project_id: str = "proj-test") -> None:
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (project_id, "Test"),
    )


def _create_approved_asset(
    db: Database,
    tmp_path,
    *,
    asset_id: str = "asset-1",
    project_id: str = "proj-test",
    entity_type: str = "shot",
    entity_id: str = "shot_002",
    asset_role: str = "start_frame",
) -> str:
    import uuid
    test_file = str(tmp_path / f"{asset_id}.png")
    with open(test_file, "wb") as f:
        f.write(b"test image content")
    file_hash = hashlib.sha256(b"test image content").hexdigest()

    db.execute(
        """INSERT INTO tasks
           (task_id, project_id, task_type, status, dependencies,
            content_hash, dependency_hash, params_hash, idempotency_key)
           VALUES (?, ?, 'visual.generate', 'APPROVED', '[]', '', '', '', ?)""",
        (asset_id, project_id, uuid.uuid4().hex),
    )
    db.execute(
        """INSERT INTO assets
           (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
           VALUES (?, ?, 'image', ?, ?, ?)""",
        (asset_id, asset_id, test_file, file_hash, file_hash),
    )
    db.execute(
        """INSERT INTO asset_bindings
           (binding_id, asset_id, project_id, entity_type, entity_id,
            asset_role, revision, validity)
           VALUES (?, ?, ?, ?, ?, ?, 1, 'current')""",
        (f"bind-{asset_id}", asset_id, project_id, entity_type, entity_id, asset_role),
    )
    db.execute(
        """INSERT INTO asset_reviews
           (review_id, asset_id, dependency_hash, technical_status,
            manual_review_status, review_source, reviewer)
           VALUES (?, ?, ?, 'passed', 'approved', 'manual', 'tester')""",
        (f"review-{asset_id}", asset_id, file_hash),
    )
    return test_file


class TestCheckVisualAssetsReady:
    def test_allow_t2va_fallback_missing_visuals_ready(self, db, tmp_path):
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)
        _make_profile(db, "proj-test", "allow_t2va_fallback")

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=["start_frame"],
        )

        assert result.ready is True
        assert "start_frame" in result.missing_roles

    def test_visual_required_missing_visuals_not_ready(self, db, tmp_path):
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=["start_frame"],
        )

        assert result.ready is False
        assert "start_frame" in result.missing_roles

    def test_visual_required_all_visuals_ready(self, db, tmp_path):
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")
        _create_approved_asset(db, tmp_path, entity_id="shot_002", asset_role="start_frame")

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=["start_frame"],
        )

        assert result.ready is True
        assert len(result.missing_roles) == 0

    def test_no_profile_defaults_to_allow_t2va_fallback(self, db, tmp_path):
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=["start_frame"],
        )

        assert result.ready is True

    def test_required_roles_empty_always_ready(self, db, tmp_path):
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=[],
        )

        assert result.ready is True
        assert len(result.missing_roles) == 0


class TestGraphServicePanelIntegration:
    """Panel-only graph: video/panel_* tasks, no shot video or visual.generate."""

    def test_only_panel_video_tasks(self, db):
        _create_project(db)
        service = StoryboardGraphService(db)
        graph = service.build_graph(_make_panel_storyboard(3))

        panel_tasks = [t for t in graph.tasks if t.logical_task_key.startswith("video/panel_")]
        shot_tasks = [t for t in graph.tasks if "shot" in t.logical_task_key]
        visual_tasks = [t for t in graph.tasks if t.task_type == "visual.generate"]

        assert len(panel_tasks) == 3
        assert len(shot_tasks) == 0
        assert len(visual_tasks) == 0

    def test_sequential_panel_dependencies(self, db):
        _create_project(db)
        service = StoryboardGraphService(db)
        graph = service.build_graph(_make_panel_storyboard(3))

        assert graph.tasks[0].depends_on == []
        assert graph.tasks[1].depends_on == [graph.tasks[0].task_id]
        assert graph.tasks[2].depends_on == [graph.tasks[1].task_id]

    def test_materialized_to_db(self, db):
        _create_project(db)
        service = StoryboardGraphService(db)
        graph = service.build_graph(_make_panel_storyboard(3))

        rows = db.fetchall(
            "SELECT task_id, task_type FROM tasks WHERE project_id = ?",
            ("proj-test",),
        )
        assert len(rows) == 3
        assert all(r[1] == "video.h3" for r in rows)


class TestDualGate:
    def _create_task(
        self,
        db: Database,
        task_id: str = "task-video-1",
        project_id: str = "proj-test",
        status: str = "WAITING_ASSETS",
        task_type: str = "video.h3",
        depends_on: str = "[]",
    ) -> None:
        import uuid
        db.execute(
            """INSERT INTO tasks
               (task_id, project_id, task_type, status, dependencies,
                content_hash, dependency_hash, params_hash, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, project_id, task_type, status, depends_on, "", "", "", uuid.uuid4().hex),
        )

    def _create_snapshot(self, db: Database) -> None:
        import uuid
        db.execute(
            """INSERT INTO environment_snapshots
               (snapshot_id, machine_id, captured_at, snapshot_json,
                execution_environment_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex, "local", "2026-01-01T00:00:00.000000Z", "{}", "env-hash"),
        )

    def test_visual_dep_approved_allows_promotion(self, db, tmp_path):
        _create_project(db)
        self._create_snapshot(db)

        self._create_task(db, task_id="task-visual-1", task_type="visual.generate", status="APPROVED")
        self._create_task(
            db, task_id="task-video-1", task_type="video.h3",
            status="WAITING_ASSETS", depends_on='["task-visual-1"]',
        )

        service = TaskReadinessService(db)
        result = service.promote_to_ready(
            task_id="task-video-1",
            asset_requirements=[],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test"},
        )

        assert result.success is True
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-video-1",))
        assert row[0] == "READY"

    def test_visual_dep_not_approved_blocks_promotion(self, db, tmp_path):
        _create_project(db)
        self._create_snapshot(db)

        self._create_task(db, task_id="task-visual-1", task_type="visual.generate", status="PLANNED")
        self._create_task(
            db, task_id="task-video-1", task_type="video.h3",
            status="WAITING_ASSETS", depends_on='["task-visual-1"]',
        )

        service = TaskReadinessService(db)
        result = service.promote_to_ready(
            task_id="task-video-1",
            asset_requirements=[],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test"},
        )

        assert result.success is False

    def test_no_visual_dep_allows_promotion(self, db, tmp_path):
        _create_project(db)
        self._create_snapshot(db)

        self._create_task(
            db, task_id="task-video-1", task_type="video.h3",
            status="WAITING_ASSETS", depends_on="[]",
        )

        service = TaskReadinessService(db)
        result = service.promote_to_ready(
            task_id="task-video-1",
            asset_requirements=[],
            workflow_id="h3_standard_t2v",
            params={"prompt": "test"},
        )

        assert result.success is True


class TestWorkflowSelectorForPanel:
    def test_valid_pack_selects_r2v(self):
        pack = build_panel_pack(
            panel_id="panel_01",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[("char_a", "asset_a")],
            max_ref_images=3,
        )
        result = select_workflow_for_panel(pack)
        assert result.workflow_mode == "r2v"
        assert result.selection_status == "confirmed"

    def test_incomplete_pack_blocked(self):
        pack = build_panel_pack(
            panel_id="panel_01",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[],
            max_ref_images=3,
        )
        result = select_workflow_for_panel(pack)
        assert result.selection_status == "blocked"
        assert result.workflow_mode == "r2v"
