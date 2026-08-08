"""Tests for DAG integration, dual gate, and T2VA policy (Task 10).

Covers:
- check_visual_assets_ready with allow_t2va_fallback / visual_required policies
- Graph service inserts visual.generate tasks when visual_required
- Dual gate: video READY requires visual deps in APPROVED
- Workflow selector T2VA fallback policy
"""
from __future__ import annotations

import hashlib

import pytest

from lfo.application.visual_profile_service import VisualProfileService
from lfo.core.database import Database
from lfo.planning.workflow_selector import select_workflow
from lfo.services.storyboard_graph_service import StoryboardGraphService
from lfo.services.task_readiness_service import TaskReadinessService
from lfo.storyboard.storyboard import (
    Camera,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Shot,
    Storyboard,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def _make_storyboard(num_shots: int = 3, preferred_mode: str | None = None) -> Storyboard:
    """Create a test storyboard where continuation shots need visual input."""
    shots = []
    for i in range(num_shots):
        hint = GenerationHint(preferred_mode=preferred_mode) if preferred_mode else GenerationHint()
        shot = Shot(
            shot_id=f"shot_{i + 1:03d}",
            display_index=i + 1,
            scene_id="scene_001",
            description=f"Shot {i + 1}",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=hint,
        )
        shots.append(shot)
    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        shots=shots,
    )


def _make_profile(db: Database, project_id: str, policy: str = "allow_t2va_fallback") -> str:
    """Create and activate a visual profile. Returns revision_id."""
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
    """Create an asset with binding + approval. Returns file path."""
    import uuid
    test_file = str(tmp_path / f"{asset_id}.png")
    with open(test_file, "wb") as f:
        f.write(b"test image content")
    file_hash = hashlib.sha256(b"test image content").hexdigest()

    # Create a dummy task row to satisfy FK (assets.task_id -> tasks.task_id)
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


# ---------------------------------------------------------------------------
# check_visual_assets_ready
# ---------------------------------------------------------------------------


class TestCheckVisualAssetsReady:
    """Tests for check_visual_assets_ready function."""

    def test_allow_t2va_fallback_missing_visuals_ready(self, db, tmp_path):
        """allow_t2va_fallback: missing visuals are OK (T2VA fallback)."""
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
        """visual_required: missing visuals block readiness."""
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
        """visual_required: all visuals present → ready."""
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
        """No active profile → defaults to allow_t2va_fallback → ready."""
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
        """Empty required_roles → always ready."""
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

    def test_details_contain_policy_and_role_info(self, db, tmp_path):
        """Result details include policy and per-role status."""
        from lfo.application.visual_readiness import check_visual_assets_ready

        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        result = check_visual_assets_ready(
            db,
            project_id="proj-test",
            shot_id="shot_002",
            required_roles=["start_frame"],
        )

        assert "policy" in result.details
        assert result.details["policy"] == "visual_required"
        assert "start_frame" in result.details.get("roles", {})


# ---------------------------------------------------------------------------
# Graph service integration
# ---------------------------------------------------------------------------


class TestGraphServiceVisualIntegration:
    """Tests for visual task insertion in the graph service."""

    def test_visual_required_inserts_visual_task(self, db):
        """visual_required: graph inserts visual.generate before video.h3."""
        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        service = StoryboardGraphService(db)
        storyboard = _make_storyboard(3)
        graph = service.build_graph(storyboard)

        # Should have visual tasks + video tasks
        task_types = [t.task_type for t in graph.tasks]
        assert "visual.generate" in task_types

        # Shot 2 and 3 should have visual tasks
        visual_tasks = [t for t in graph.tasks if t.task_type == "visual.generate"]
        assert len(visual_tasks) == 2  # shot_002 and shot_003

    def test_allow_t2va_fallback_no_visual_task(self, db):
        """allow_t2va_fallback: no visual tasks inserted."""
        _create_project(db)
        _make_profile(db, "proj-test", "allow_t2va_fallback")

        service = StoryboardGraphService(db)
        storyboard = _make_storyboard(3)
        graph = service.build_graph(storyboard)

        task_types = [t.task_type for t in graph.tasks]
        assert "visual.generate" not in task_types
        assert all(t.task_type == "video.h3" for t in graph.tasks)

    def test_visual_task_dependency_chain(self, db):
        """visual_required: video task depends on visual task."""
        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        service = StoryboardGraphService(db)
        storyboard = _make_storyboard(3)
        graph = service.build_graph(storyboard)

        # Find video task for shot_002
        video_task = next(
            t for t in graph.tasks
            if t.task_type == "video.h3" and "shot_002" in t.task_id
        )
        # Video task should depend on a visual task
        assert len(video_task.depends_on) > 0
        dep_id = video_task.depends_on[0]
        dep_task = next(t for t in graph.tasks if t.task_id == dep_id)
        assert dep_task.task_type == "visual.generate"

    def test_first_shot_no_visual_even_with_visual_required(self, db):
        """First shot (T2VA) doesn't get a visual task even with visual_required."""
        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        service = StoryboardGraphService(db)
        storyboard = _make_storyboard(3)
        graph = service.build_graph(storyboard)

        # First shot should be T2VA (no visual task)
        first_video = next(
            t for t in graph.tasks
            if t.task_type == "video.h3" and "shot_001" in t.task_id
        )
        assert len(first_video.depends_on) == 0

    def test_materialized_visual_tasks_in_db(self, db):
        """visual_required: visual tasks are materialized to DB."""
        _create_project(db)
        _make_profile(db, "proj-test", "visual_required")

        service = StoryboardGraphService(db)
        storyboard = _make_storyboard(3)
        graph = service.build_graph(storyboard)

        # Check DB has visual tasks
        rows = db.fetchall(
            "SELECT task_id, task_type FROM tasks WHERE project_id = ? AND task_type = ?",
            ("proj-test", "visual.generate"),
        )
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Dual gate
# ---------------------------------------------------------------------------


class TestDualGate:
    """Tests for the dual gate in TaskReadinessService."""

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
        """Video task with visual dep in APPROVED → promote succeeds."""

        _create_project(db)
        self._create_snapshot(db)

        # Create visual task in APPROVED
        self._create_task(db, task_id="task-visual-1", task_type="visual.generate", status="APPROVED")
        # Create video task depending on visual task
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
        """Video task with visual dep in PLANNED → promote fails."""
        _create_project(db)
        self._create_snapshot(db)

        # Create visual task in PLANNED (not approved)
        self._create_task(db, task_id="task-visual-1", task_type="visual.generate", status="PLANNED")
        # Create video task depending on visual task
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
        assert "visual" in result.message.lower() or "not approved" in result.message.lower()

    def test_no_visual_dep_allows_promotion(self, db, tmp_path):
        """Video task with no visual dep → promote succeeds (current behavior)."""
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


# ---------------------------------------------------------------------------
# Workflow selector T2VA policy
# ---------------------------------------------------------------------------


class TestWorkflowSelectorT2VAPolicy:
    """Tests for workflow selector T2VA fallback policy."""

    def test_visual_required_no_assets_blocked(self):
        """visual_required: shot without assets → blocked (no T2VA fallback)."""
        shot = Shot(
            shot_id="shot_001",
            display_index=1,
            scene_id="scene_001",
            description="Test",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=True),
            generation_hint=GenerationHint(),
        )
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-test", title="Test"),
            shots=[shot],
        )

        result = select_workflow(
            shot, storyboard, available_assets={},
            visual_input_policy="visual_required",
        )

        # With visual_required, no T2VA fallback
        assert result.workflow_mode == "i2v"
        assert result.selection_status == "blocked"

    def test_allow_t2va_fallback_no_assets_t2va(self):
        """allow_t2va_fallback: shot without assets → T2VA."""
        shot = Shot(
            shot_id="shot_001",
            display_index=1,
            scene_id="scene_001",
            description="Test",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=False),
            generation_hint=GenerationHint(),
        )
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-test", title="Test"),
            shots=[shot],
        )

        result = select_workflow(shot, storyboard, available_assets={})

        assert result.workflow_mode == "t2va"
        assert result.selection_status == "provisional"

    def test_visual_required_with_assets_i2v(self):
        """visual_required: shot with start frame asset → i2v confirmed."""
        shot = Shot(
            shot_id="shot_001",
            display_index=1,
            scene_id="scene_001",
            description="Test",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=True),
            generation_hint=GenerationHint(),
        )
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-test", title="Test"),
            shots=[shot],
        )
        assets = {"shot_001": {"start_frame": {"status": "approved"}}}

        result = select_workflow(shot, storyboard, available_assets=assets)

        assert result.workflow_mode == "i2v"
        assert result.selection_status == "confirmed"
