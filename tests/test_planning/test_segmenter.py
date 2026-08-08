"""Tests for planning.segmenter."""
from lfo.planning.segmenter import _make_task_id, segment_storyboard
from lfo.storyboard.storyboard import (
    ContinuityChain,
    ProjectInfo,
    Shot,
    Storyboard,
)


class TestMakeTaskId:
    def test_basic(self):
        assert _make_task_id("video/shot_003") == "task_video_shot_003"

    def test_no_slash(self):
        assert _make_task_id("video_shot_003") == "task_video_shot_003"

    def test_nested(self):
        assert _make_task_id("video/shot_001/extra") == "task_video_shot_001_extra"


class TestSegmentStoryboard:
    def _make_storyboard(self, shots=None, chains=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001", title="Test"),
            shots=shots or [],
            continuity_chains=chains or [],
        )

    def test_empty_storyboard(self):
        sb = self._make_storyboard()
        tasks = segment_storyboard(sb)
        assert tasks == []

    def test_single_shot(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", display_index=1)],
        )
        tasks = segment_storyboard(sb)
        assert len(tasks) == 1
        assert tasks[0].logical_task_key == "video/shot_001"
        assert tasks[0].task_id == "task_video_shot_001"
        assert tasks[0].task_type == "video.h3"
        assert tasks[0].target_ids == ["shot_001"]
        assert tasks[0].project_id == "proj_001"

    def test_multiple_shots_ordered(self):
        sb = self._make_storyboard(
            shots=[
                Shot(shot_id="shot_001", display_index=1),
                Shot(shot_id="shot_002", display_index=2),
                Shot(shot_id="shot_003", display_index=3),
            ],
        )
        tasks = segment_storyboard(sb)
        assert len(tasks) == 3
        assert [t.task_id for t in tasks] == [
            "task_video_shot_001", "task_video_shot_002", "task_video_shot_003",
        ]
        # Order is preserved
        assert [t.target_ids[0] for t in tasks] == ["shot_001", "shot_002", "shot_003"]

    def test_project_id_override(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
        )
        tasks = segment_storyboard(sb, project_id="custom_proj")
        assert tasks[0].project_id == "custom_proj"

    def test_serial_group_from_continuity_chain(self):
        sb = self._make_storyboard(
            shots=[
                Shot(shot_id="shot_001"),
                Shot(shot_id="shot_002"),
                Shot(shot_id="shot_003"),
            ],
            chains=[
                ContinuityChain(chain_id="chain_abc", shot_ids=["shot_001", "shot_003"]),
            ],
        )
        tasks = segment_storyboard(sb)
        assert tasks[0].serial_group == "chain_abc"
        assert tasks[1].serial_group == ""  # not in any chain
        assert tasks[2].serial_group == "chain_abc"

    def test_default_priority_class(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
        )
        tasks = segment_storyboard(sb)
        assert tasks[0].priority_class == 30

    def test_determinism(self):
        """Same storyboard → same task list."""
        sb = self._make_storyboard(
            shots=[
                Shot(shot_id="shot_001"),
                Shot(shot_id="shot_002"),
            ],
        )
        tasks1 = segment_storyboard(sb)
        tasks2 = segment_storyboard(sb)
        assert [t.task_id for t in tasks1] == [t.task_id for t in tasks2]
        assert [t.logical_task_key for t in tasks1] == [t.logical_task_key for t in tasks2]
