"""Tests for planning.segmenter."""
from lfo.planning.segmenter import _make_task_id, segment_storyboard
from lfo.storyboard.storyboard import (
    ContinuityChain,
    Panel,
    ProjectInfo,
    Storyboard,
)


class TestMakeTaskId:
    def test_basic(self):
        assert _make_task_id("video/panel_003") == "task_video_panel_003"

    def test_no_slash(self):
        assert _make_task_id("video_panel_003") == "task_video_panel_003"

    def test_nested(self):
        assert _make_task_id("video/panel_001/extra") == "task_video_panel_001_extra"


class TestSegmentStoryboard:
    def _make_storyboard(self, panels=None, chains=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001", title="Test"),
            panels=panels or [],
            continuity_chains=chains or [],
        )

    def test_empty_storyboard(self):
        sb = self._make_storyboard()
        tasks = segment_storyboard(sb)
        assert tasks == []

    def test_single_panel(self):
        sb = self._make_storyboard(
            panels=[Panel(panel_id="panel_001", sequence=1)],
        )
        tasks = segment_storyboard(sb)
        assert len(tasks) == 1
        assert tasks[0].logical_task_key == "video/panel_001"
        assert tasks[0].task_id == "task_video_panel_001"
        assert tasks[0].task_type == "video.h3"
        assert tasks[0].target_ids == ["panel_001"]
        assert tasks[0].project_id == "proj_001"

    def test_multiple_panels_ordered(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
            ],
        )
        tasks = segment_storyboard(sb)
        assert len(tasks) == 3
        assert [t.task_id for t in tasks] == [
            "task_video_panel_001", "task_video_panel_002", "task_video_panel_003",
        ]
        assert [t.target_ids[0] for t in tasks] == ["panel_001", "panel_002", "panel_003"]

    def test_project_id_override(self):
        sb = self._make_storyboard(
            panels=[Panel(panel_id="panel_001", sequence=1)],
        )
        tasks = segment_storyboard(sb, project_id="custom_proj")
        assert tasks[0].project_id == "custom_proj"

    def test_serial_group_from_continuity_chain(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
            ],
            chains=[
                ContinuityChain(chain_id="chain_abc", shot_ids=["panel_001", "panel_003"]),
            ],
        )
        tasks = segment_storyboard(sb)
        assert tasks[0].serial_group == "chain_abc"
        assert tasks[1].serial_group == ""
        assert tasks[2].serial_group == "chain_abc"

    def test_default_priority_class(self):
        sb = self._make_storyboard(
            panels=[Panel(panel_id="panel_001", sequence=1)],
        )
        tasks = segment_storyboard(sb)
        assert tasks[0].priority_class == 30

    def test_determinism(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
            ],
        )
        tasks1 = segment_storyboard(sb)
        tasks2 = segment_storyboard(sb)
        assert [t.task_id for t in tasks1] == [t.task_id for t in tasks2]
        assert [t.logical_task_key for t in tasks1] == [t.logical_task_key for t in tasks2]
