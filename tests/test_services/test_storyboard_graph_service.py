"""Tests for StoryboardGraphService."""
from __future__ import annotations

import pytest

from lfo.core.database import Database
from lfo.services.storyboard_graph_service import MODE_TO_WORKFLOW, StoryboardGraphService
from lfo.storyboard.storyboard import (
    Camera,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Shot,
    Storyboard,
)


def make_storyboard(num_shots: int = 3) -> Storyboard:
    """Create a test storyboard with the given number of shots."""
    shots = []
    for i in range(num_shots):
        shot = Shot(
            shot_id=f"shot_{i + 1:03d}",
            display_index=i + 1,
            scene_id="scene_001",
            description=f"Shot {i + 1} description",
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(
                start_frame_needed=(i > 0),  # First shot doesn't need start frame
            ),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)

    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        shots=shots,
    )


@pytest.fixture
def db() -> Database:
    """Create a fresh in-memory database."""
    db = Database(":memory:")
    db.init_schema()
    return db


class TestBuildGraph:
    """Test storyboard → task graph conversion."""

    def test_creates_tasks_for_all_shots(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        assert len(graph.tasks) == 3

    def test_first_shot_has_no_dependencies(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        assert len(graph.tasks[0].depends_on) == 0

    def test_continuation_shots_depend_on_previous(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        # Shot 2 depends on shot 1
        assert len(graph.tasks[1].depends_on) == 1
        assert graph.tasks[1].depends_on[0] == graph.tasks[0].task_id

        # Shot 3 depends on shot 2
        assert len(graph.tasks[2].depends_on) == 1
        assert graph.tasks[2].depends_on[0] == graph.tasks[1].task_id

    def test_first_shot_is_t2v(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(2)
        graph = service.build_graph(storyboard)

        assert graph.tasks[0].workflow_mode == "t2va"
        assert graph.tasks[0].workflow_id == "h3_standard_t2v"

    def test_continuation_shot_is_i2v(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(2)
        graph = service.build_graph(storyboard)

        assert graph.tasks[1].workflow_mode == "i2v"
        assert graph.tasks[1].workflow_id == "h3_standard_i2v"

    def test_task_ids_are_stable(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(2)
        graph = service.build_graph(storyboard)

        assert graph.tasks[0].task_id == "task_shot_001"
        assert graph.tasks[1].task_id == "task_shot_002"

    def test_materializes_to_db(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        # Check tasks are in DB
        rows = db.fetchall("SELECT * FROM tasks WHERE project_id = ?", ("proj-test",))
        assert len(rows) == 3

    def test_materialization_summary(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        assert graph.materialization_summary["inserted"] == 3
        assert graph.materialization_summary["total"] == 3

    def test_empty_storyboard(self, db):
        service = StoryboardGraphService(db)
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-empty"),
            shots=[],
        )
        graph = service.build_graph(storyboard)

        assert len(graph.tasks) == 0

    def test_asset_requirements_for_continuation(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(2)
        graph = service.build_graph(storyboard)

        # First shot: no asset requirements
        assert len(graph.tasks[0].asset_requirements) == 0

        # Second shot: needs start_frame from previous
        assert len(graph.tasks[1].asset_requirements) == 1
        assert graph.tasks[1].asset_requirements[0].asset_role == "start_frame"

    def test_serial_group_set(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard(3)
        graph = service.build_graph(storyboard)

        for task in graph.tasks:
            assert task.serial_group == "proj-test"


class TestModeMapping:
    """Test workflow mode to workflow_id mapping."""

    def test_t2va_mapping(self):
        assert MODE_TO_WORKFLOW["t2va"] == "h3_standard_t2v"

    def test_i2v_mapping(self):
        assert MODE_TO_WORKFLOW["i2v"] == "h3_standard_i2v"

    def test_r2v_mapping(self):
        assert MODE_TO_WORKFLOW["r2v"] == "h3_standard_r2v"

    def test_first_last_mapping(self):
        assert MODE_TO_WORKFLOW["first_last"] == "h3_standard_i2v"
