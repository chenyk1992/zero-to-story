"""Tests for TaskReadinessService."""
from __future__ import annotations

import hashlib

import pytest

from lfo.application.asset_service import AssetBindingService
from lfo.core.database import Database
from lfo.services.environment_snapshot_service import EnvironmentSnapshotService
from lfo.services.task_readiness_service import (
    AssetRequirement,
    TaskReadinessService,
    _compute_idempotency_key,
    _compute_params_hash,
)


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def asset_service(db: Database) -> AssetBindingService:
    return AssetBindingService(db)


@pytest.fixture
def snapshot_service(db: Database) -> EnvironmentSnapshotService:
    return EnvironmentSnapshotService(db)


@pytest.fixture
def service(db: Database, asset_service: AssetBindingService, snapshot_service: EnvironmentSnapshotService) -> TaskReadinessService:
    return TaskReadinessService(db, asset_service, snapshot_service)


def _create_project(db: Database, project_id: str = "proj-1") -> None:
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (project_id, "Test Project"),
    )


def _create_task(
    db: Database,
    task_id: str = "task-1",
    project_id: str = "proj-1",
    status: str = "WAITING_ASSETS",
    task_type: str = "h3_i2v",
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


def _create_asset_with_approval(
    db: Database,
    tmp_path,
    asset_id: str = "asset-1",
    task_id: str = "task-1",
) -> str:
    """Create an asset with binding and approval. Returns file path."""
    test_file = str(tmp_path / f"{asset_id}.png")
    with open(test_file, "wb") as f:
        f.write(b"test image content")

    file_hash = hashlib.sha256(b"test image content").hexdigest()

    db.execute(
        """INSERT INTO assets
           (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
           VALUES (?, ?, 'image', ?, ?, ?)""",
        (asset_id, task_id, test_file, file_hash, file_hash),
    )
    db.execute(
        """INSERT INTO asset_bindings
           (binding_id, asset_id, project_id, entity_type, entity_id,
            asset_role, revision, validity)
           VALUES (?, ?, ?, ?, ?, ?, 1, 'current')""",
        (f"bind-{asset_id}", asset_id, "proj-1", "task", task_id, "first_frame"),
    )
    db.execute(
        """INSERT INTO asset_reviews
           (review_id, asset_id, dependency_hash, technical_status,
            manual_review_status, review_source, reviewer)
           VALUES (?, ?, ?, 'passed', 'approved', 'manual', 'tester')""",
        (f"review-{asset_id}", asset_id, file_hash),
    )
    return test_file


def _create_snapshot(db: Database, machine_id: str = "local") -> str:
    """Create an environment snapshot. Returns snapshot_id."""
    import uuid
    snapshot_id = uuid.uuid4().hex
    db.execute(
        """INSERT INTO environment_snapshots
           (snapshot_id, machine_id, captured_at, snapshot_json,
            execution_environment_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (snapshot_id, machine_id, "2026-01-01T00:00:00.000000Z",
         "{}", "env-hash-123"),
    )
    return snapshot_id


class TestPromoteToReady:
    def test_successful_promotion(
        self,
        service: TaskReadinessService,
        db: Database,
        tmp_path,
    ):
        """Full successful promotion from WAITING_ASSETS to READY."""
        _create_project(db)
        _create_task(db)
        _create_asset_with_approval(db, tmp_path)
        _create_snapshot(db)

        result = service.promote_to_ready(
            task_id="task-1",
            asset_requirements=[
                AssetRequirement("task", "task-1", "first_frame"),
            ],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test", "length": 124},
        )

        assert result.success
        assert result.task_id == "task-1"
        assert result.materialization_id != ""

        # Verify task is now READY
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-1",))
        assert row[0] == "READY"

        # Verify materialization was created
        mat = db.fetchone(
            "SELECT workflow_id, params_hash FROM task_materializations WHERE task_id = ?",
            ("task-1",),
        )
        assert mat is not None
        assert mat[0] == "h3_standard_i2v"

    def test_task_not_found(self, service: TaskReadinessService):
        result = service.promote_to_ready(
            task_id="nonexistent",
            asset_requirements=[],
            workflow_id="wf1",
            params={},
        )
        assert not result.success
        assert "not found" in result.message

    def test_task_not_in_waiting_assets(self, service: TaskReadinessService, db: Database):
        _create_project(db)
        _create_task(db, status="PLANNED")
        result = service.promote_to_ready(
            task_id="task-1",
            asset_requirements=[],
            workflow_id="wf1",
            params={},
        )
        assert not result.success
        assert "expected WAITING_ASSETS" in result.message

    def test_asset_not_ready(
        self,
        service: TaskReadinessService,
        db: Database,
        tmp_path,
    ):
        """Task stays WAITING_ASSETS when asset is not approved."""
        _create_project(db)
        _create_task(db)
        _create_snapshot(db)
        # Create asset WITHOUT approval
        test_file = str(tmp_path / "unapproved.png")
        with open(test_file, "wb") as f:
            f.write(b"unapproved content")
        file_hash = hashlib.sha256(b"unapproved content").hexdigest()
        db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
               VALUES (?, ?, 'image', ?, ?, ?)""",
            ("asset-2", "task-1", test_file, file_hash, file_hash),
        )
        db.execute(
            """INSERT INTO asset_bindings
               (binding_id, asset_id, project_id, entity_type, entity_id,
                asset_role, revision, validity)
               VALUES (?, ?, ?, ?, ?, ?, 1, 'current')""",
            ("bind-2", "asset-2", "proj-1", "task", "task-1", "first_frame"),
        )

        result = service.promote_to_ready(
            task_id="task-1",
            asset_requirements=[
                AssetRequirement("task", "task-1", "first_frame"),
            ],
            workflow_id="wf1",
            params={},
        )

        assert not result.success
        assert result.failed_asset == "first_frame"
        # Task should still be WAITING_ASSETS
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-1",))
        assert row[0] == "WAITING_ASSETS"

    def test_no_snapshot(self, service: TaskReadinessService, db: Database, tmp_path):
        """Promotion fails when no environment snapshot exists."""
        _create_project(db)
        _create_task(db)
        _create_asset_with_approval(db, tmp_path)
        # No snapshot created

        result = service.promote_to_ready(
            task_id="task-1",
            asset_requirements=[
                AssetRequirement("task", "task-1", "first_frame"),
            ],
            workflow_id="wf1",
            params={},
        )

        assert not result.success
        assert "No environment snapshot" in result.message

    def test_multiple_assets_all_required(
        self,
        service: TaskReadinessService,
        db: Database,
        tmp_path,
    ):
        """All assets must be approved for promotion."""
        _create_project(db)
        _create_task(db)
        _create_snapshot(db)

        # Create two assets
        for asset_id in ["asset-a", "asset-b"]:
            test_file = str(tmp_path / f"{asset_id}.png")
            with open(test_file, "wb") as f:
                f.write(f"content-{asset_id}".encode())
            file_hash = hashlib.sha256(f"content-{asset_id}".encode()).hexdigest()
            db.execute(
                """INSERT INTO assets
                   (asset_id, task_id, asset_type, file_path, file_hash, content_hash)
                   VALUES (?, ?, 'image', ?, ?, ?)""",
                (asset_id, "task-1", test_file, file_hash, file_hash),
            )
            db.execute(
                """INSERT INTO asset_bindings
                   (binding_id, asset_id, project_id, entity_type, entity_id,
                    asset_role, revision, validity)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 'current')""",
                (f"bind-{asset_id}", asset_id, "proj-1", "task", "task-1", f"ref_{asset_id}"),
            )
            db.execute(
                """INSERT INTO asset_reviews
                   (review_id, asset_id, dependency_hash, technical_status,
                    manual_review_status, review_source, reviewer)
                   VALUES (?, ?, ?, 'passed', 'approved', 'manual', 'tester')""",
                (f"review-{asset_id}", asset_id, file_hash),
            )

        result = service.promote_to_ready(
            task_id="task-1",
            asset_requirements=[
                AssetRequirement("task", "task-1", "ref_asset-a"),
                AssetRequirement("task", "task-1", "ref_asset-b"),
            ],
            workflow_id="h3_standard_r2v",
            params={"prompt": "test"},
        )

        assert result.success
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-1",))
        assert row[0] == "READY"


class TestComputeParamsHash:
    def test_deterministic(self):
        params = {"prompt": "test", "length": 124, "seed": 42}
        h1 = _compute_params_hash(params)
        h2 = _compute_params_hash(params)
        assert h1 == h2

    def test_order_independent(self):
        params1 = {"a": 1, "b": 2, "c": 3}
        params2 = {"c": 3, "a": 1, "b": 2}
        assert _compute_params_hash(params1) == _compute_params_hash(params2)

    def test_different_params_different_hash(self):
        h1 = _compute_params_hash({"prompt": "a"})
        h2 = _compute_params_hash({"prompt": "b"})
        assert h1 != h2


class TestComputeIdempotencyKey:
    def test_deterministic(self):
        k1 = _compute_idempotency_key("task-1", "params-hash", "env-hash")
        k2 = _compute_idempotency_key("task-1", "params-hash", "env-hash")
        assert k1 == k2

    def test_different_task_different_key(self):
        k1 = _compute_idempotency_key("task-1", "params-hash", "env-hash")
        k2 = _compute_idempotency_key("task-2", "params-hash", "env-hash")
        assert k1 != k2

    def test_different_env_different_key(self):
        k1 = _compute_idempotency_key("task-1", "params-hash", "env-1")
        k2 = _compute_idempotency_key("task-1", "params-hash", "env-2")
        assert k1 != k2


class TestDualGate:
    """Dual gate: video READY requires visual deps in APPROVED (spec §19)."""

    def test_visual_dep_approved_allows_promotion(
        self, service: TaskReadinessService, db: Database
    ):
        """Video task with visual dep in APPROVED → promote succeeds."""
        _create_project(db)
        _create_snapshot(db)
        # Visual dependency task in APPROVED
        _create_task(
            db, task_id="task-visual", task_type="visual.generate", status="APPROVED"
        )
        # Video task depends on visual task
        _create_task(
            db,
            task_id="task-video",
            task_type="video.h3",
            status="WAITING_ASSETS",
            depends_on='["task-visual"]',
        )

        result = service.promote_to_ready(
            task_id="task-video",
            asset_requirements=[],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test"},
        )

        assert result.success
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-video",))
        assert row[0] == "READY"

    def test_visual_dep_not_approved_blocks_promotion(
        self, service: TaskReadinessService, db: Database
    ):
        """Video task with visual dep in PLANNED → promote fails."""
        _create_project(db)
        _create_snapshot(db)
        # Visual dependency task NOT approved
        _create_task(
            db, task_id="task-visual", task_type="visual.generate", status="PLANNED"
        )
        _create_task(
            db,
            task_id="task-video",
            task_type="video.h3",
            status="WAITING_ASSETS",
            depends_on='["task-visual"]',
        )

        result = service.promote_to_ready(
            task_id="task-video",
            asset_requirements=[],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test"},
        )

        assert not result.success
        assert "visual" in result.message.lower()
        # Task should still be WAITING_ASSETS
        row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", ("task-video",))
        assert row[0] == "WAITING_ASSETS"

    def test_no_visual_dep_allows_promotion(
        self, service: TaskReadinessService, db: Database
    ):
        """Video task with no visual dep → promote succeeds (unchanged)."""
        _create_project(db)
        _create_snapshot(db)
        _create_task(
            db,
            task_id="task-video",
            task_type="video.h3",
            status="WAITING_ASSETS",
            depends_on="[]",
        )

        result = service.promote_to_ready(
            task_id="task-video",
            asset_requirements=[],
            workflow_id="h3_standard_t2v",
            params={"prompt": "test"},
        )

        assert result.success

    def test_visual_dep_qc_pending_blocks_promotion(
        self, service: TaskReadinessService, db: Database
    ):
        """Video task with visual dep in QC_PENDING → promote fails."""
        _create_project(db)
        _create_snapshot(db)
        _create_task(
            db, task_id="task-visual", task_type="visual.generate", status="QC_PENDING"
        )
        _create_task(
            db,
            task_id="task-video",
            task_type="video.h3",
            status="WAITING_ASSETS",
            depends_on='["task-visual"]',
        )

        result = service.promote_to_ready(
            task_id="task-video",
            asset_requirements=[],
            workflow_id="h3_standard_i2v",
            params={"prompt": "test"},
        )

        assert not result.success
        assert "APPROVED" in result.message
