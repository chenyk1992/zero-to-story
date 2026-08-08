"""Tests for StoryboardGraphService."""
from __future__ import annotations

import pytest

from lfo.core.database import Database
from lfo.services.storyboard_graph_service import MODE_TO_WORKFLOW, StoryboardGraphService
from lfo.storyboard.panel_plan import derive_panels_from_beats
from lfo.storyboard.storyboard import (
    Beat,
    CharacterAppearance,
    Panel,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)


def make_storyboard_with_panels(num_panels: int = 3) -> Storyboard:
    """Create a test storyboard with the given number of panels."""
    beats = [
        Beat(
            beat_id=f"beat_{i:03d}",
            sequence=i,
            scene_id="scene_001",
            description=f"Beat {i} description",
            characters=[CharacterAppearance(character_id="char_001")],
        )
        for i in range(1, num_panels * 4 + 1)
    ]
    panels = [
        Panel(
            panel_id=f"panel_{i:03d}",
            sequence=i,
            beat_range=(max(1, (i - 1) * 4 + 1), min(i * 4, len(beats))),
            beat_ids=[b.beat_id for b in beats[max(0, (i - 1) * 4): min(i * 4, len(beats))]],
            desired_duration_ms=15_000,
            bw_asset_id=f"asset_bw_{i:03d}",
        )
        for i in range(1, num_panels + 1)
    ]
    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        style=StyleGuide(medium_lock="Medium: 3D rendered suspense."),
        beats=beats,
        panels=panels,
    )


def make_15_beat_2_panel_storyboard() -> Storyboard:
    """15 beats / 2 panels acceptance fixture."""
    beats = [
        Beat(
            beat_id=f"beat_{i:03d}",
            sequence=i,
            scene_id="scene_001",
            description=f"Beat {i}",
            characters=[CharacterAppearance(character_id="char_001")],
        )
        for i in range(1, 16)
    ]
    panels = derive_panels_from_beats(beats, total_duration_ms=30_000)
  # normalize panel ids for stable assertions
    for i, panel in enumerate(panels, start=1):
        panel.panel_id = f"panel_{i:03d}"
        panel.bw_asset_id = f"asset_bw_{i:03d}"

    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        style=StyleGuide(medium_lock="Medium: 3D rendered suspense."),
        beats=beats,
        panels=panels,
    )


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


class TestBuildGraph:
    """Test storyboard → task graph conversion."""

    def test_15_beats_2_panels_creates_panel_video_tasks_only(self, db):
        """Acceptance: 15 beats / 2 panels → 2 video/panel_* tasks, 0 video/shot_*."""
        service = StoryboardGraphService(db)
        storyboard = make_15_beat_2_panel_storyboard()
        graph = service.build_graph(storyboard)

        panel_tasks = [t for t in graph.tasks if t.logical_task_key.startswith("video/panel_")]
        shot_tasks = [t for t in graph.tasks if "shot" in t.logical_task_key]

        assert len(panel_tasks) == 2
        assert len(shot_tasks) == 0
        assert len(graph.tasks) == 2

    def test_creates_tasks_for_all_panels(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        assert len(graph.tasks) == 3

    def test_first_panel_has_no_dependencies(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        assert len(graph.tasks[0].depends_on) == 0

    def test_panels_depend_on_previous_in_order(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        assert graph.tasks[1].depends_on == [graph.tasks[0].task_id]
        assert graph.tasks[2].depends_on == [graph.tasks[1].task_id]

    def test_panel_logical_task_keys(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(2)
        graph = service.build_graph(storyboard)

        assert graph.tasks[0].logical_task_key == "video/panel_001"
        assert graph.tasks[1].logical_task_key == "video/panel_002"

    def test_task_ids_are_stable(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(2)
        graph = service.build_graph(storyboard)

        assert graph.tasks[0].task_id == "task_panel_001"
        assert graph.tasks[1].task_id == "task_panel_002"

    def test_no_visual_generate_tasks(self, db):
        """Happy path: no visual_{shot}_start_frame tasks."""
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        visual_tasks = [t for t in graph.tasks if t.task_type == "visual.generate"]
        assert visual_tasks == []

    def test_materializes_to_db(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        rows = db.fetchall("SELECT * FROM tasks WHERE project_id = ?", ("proj-test",))
        assert len(rows) == 3

    def test_materialization_summary(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
        graph = service.build_graph(storyboard)

        assert graph.materialization_summary["inserted"] == 3
        assert graph.materialization_summary["total"] == 3

    def test_empty_storyboard(self, db):
        service = StoryboardGraphService(db)
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-empty"),
            panels=[],
        )
        graph = service.build_graph(storyboard)

        assert len(graph.tasks) == 0

    def test_no_start_frame_asset_requirements(self, db):
        """Panel path does not require start_frame from previous shot."""
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(2)
        graph = service.build_graph(storyboard)

        for task in graph.tasks:
            roles = [r.asset_role for r in task.asset_requirements]
            assert "start_frame" not in roles

    def test_serial_group_set(self, db):
        service = StoryboardGraphService(db)
        storyboard = make_storyboard_with_panels(3)
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
