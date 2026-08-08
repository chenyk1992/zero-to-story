"""Tests for planning.dag."""
from lfo.planning.dag import build_task_dependencies
from lfo.planning.schema import PlannedTask
from lfo.storyboard.storyboard import ContinuityChain, Panel, ProjectInfo, Storyboard


class TestBuildTaskDependencies:
    def _make_storyboard(self, panels=None, chains=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            panels=panels or [],
            continuity_chains=chains or [],
        )

    def _make_tasks(self, panel_ids):
        return [
            PlannedTask(
                logical_task_key=f"video/{pid}",
                task_id=f"task_{pid}",
                project_id="proj_001",
                target_ids=[pid],
            )
            for pid in panel_ids
        ]

    def test_empty_tasks(self):
        sb = self._make_storyboard()
        result = build_task_dependencies([], sb)
        assert result == []

    def test_single_task_no_deps(self):
        sb = self._make_storyboard(
            panels=[Panel(panel_id="panel_001", sequence=1)],
        )
        tasks = self._make_tasks(["panel_001"])
        result = build_task_dependencies(tasks, sb)
        assert result[0].depends_on == []

    def test_sequential_panel_order_creates_deps(self):
        """Panels in narrative order get sequential dependencies."""
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002", "panel_003"])
        result = build_task_dependencies(tasks, sb)

        task_map = {t.task_id: t for t in result}
        assert task_map["task_panel_001"].depends_on == []
        assert task_map["task_panel_002"].depends_on == ["task_panel_001"]
        assert task_map["task_panel_003"].depends_on == ["task_panel_002"]

    def test_chain_creates_sequential_deps(self):
        """Continuity chain adds ordering (panel_ids stored in chain.shot_ids)."""
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
            ],
            chains=[
                ContinuityChain(
                    chain_id="chain_1",
                    shot_ids=["panel_001", "panel_002", "panel_003"],
                ),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002", "panel_003"])
        result = build_task_dependencies(tasks, sb)

        task_map = {t.task_id: t for t in result}
        assert task_map["task_panel_002"].depends_on == ["task_panel_001"]
        assert task_map["task_panel_003"].depends_on == ["task_panel_002"]

    def test_chain_with_gap(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
            ],
            chains=[
                ContinuityChain(
                    chain_id="chain_1",
                    shot_ids=["panel_001", "panel_003", "panel_002"],
                ),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002"])
        result = build_task_dependencies(tasks, sb)
        task_map = {t.task_id: t for t in result}
        assert task_map["task_panel_002"].depends_on == ["task_panel_001"]

    def test_multiple_chains(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
                Panel(panel_id="panel_004", sequence=4),
            ],
            chains=[
                ContinuityChain(chain_id="chain_a", shot_ids=["panel_001", "panel_002"]),
                ContinuityChain(chain_id="chain_b", shot_ids=["panel_003", "panel_004"]),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002", "panel_003", "panel_004"])
        result = build_task_dependencies(tasks, sb)
        task_map = {t.task_id: t for t in result}

        assert task_map["task_panel_002"].depends_on == ["task_panel_001"]
        assert task_map["task_panel_004"].depends_on == ["task_panel_003"]

    def test_does_not_duplicate_deps(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002"])
        result = build_task_dependencies(tasks, sb)
        result = build_task_dependencies(result, sb)
        task_map = {t.task_id: t for t in result}
        assert len(task_map["task_panel_002"].depends_on) == 1

    def test_preserves_order(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
                Panel(panel_id="panel_003", sequence=3),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002", "panel_003"])
        result = build_task_dependencies(tasks, sb)
        assert [t.task_id for t in result] == [
            "task_panel_001", "task_panel_002", "task_panel_003",
        ]

    def test_determinism(self):
        sb = self._make_storyboard(
            panels=[
                Panel(panel_id="panel_001", sequence=1),
                Panel(panel_id="panel_002", sequence=2),
            ],
        )
        tasks = self._make_tasks(["panel_001", "panel_002"])
        r1 = build_task_dependencies(tasks, sb)
        r2 = build_task_dependencies(tasks, sb)
        assert [t.depends_on for t in r1] == [t.depends_on for t in r2]
