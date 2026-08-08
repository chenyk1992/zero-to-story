"""Tests for planning.dag."""
from lfo.planning.dag import build_task_dependencies
from lfo.planning.schema import PlannedTask
from lfo.storyboard.storyboard import ContinuityChain, ProjectInfo, Shot, Storyboard


class TestBuildTaskDependencies:
    def _make_storyboard(self, shots=None, chains=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
            continuity_chains=chains or [],
        )

    def _make_tasks(self, shot_ids):
        return [
            PlannedTask(
                logical_task_key=f"video/{sid}",
                task_id=f"task_video_{sid}",
                project_id="proj_001",
                target_ids=[sid],
            )
            for sid in shot_ids
        ]

    def test_empty_tasks(self):
        sb = self._make_storyboard()
        result = build_task_dependencies([], sb)
        assert result == []

    def test_single_task_no_deps(self):
        sb = self._make_storyboard()
        tasks = self._make_tasks(["shot_001"])
        result = build_task_dependencies(tasks, sb)
        assert result[0].depends_on == []

    def test_chain_creates_sequential_deps(self):
        """Tasks in a continuity chain should have sequential dependencies."""
        sb = self._make_storyboard(
            shots=[
                Shot(shot_id="shot_001"),
                Shot(shot_id="shot_002"),
                Shot(shot_id="shot_003"),
            ],
            chains=[
                ContinuityChain(chain_id="chain_1", shot_ids=["shot_001", "shot_002", "shot_003"]),
            ],
        )
        tasks = self._make_tasks(["shot_001", "shot_002", "shot_003"])
        result = build_task_dependencies(tasks, sb)

        task_map = {t.task_id: t for t in result}
        assert task_map["task_video_shot_001"].depends_on == []
        assert task_map["task_video_shot_002"].depends_on == ["task_video_shot_001"]
        assert task_map["task_video_shot_003"].depends_on == ["task_video_shot_002"]

    def test_no_chain_no_deps(self):
        """Tasks not in any chain have no dependencies."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001"), Shot(shot_id="shot_002")],
        )
        tasks = self._make_tasks(["shot_001", "shot_002"])
        result = build_task_dependencies(tasks, sb)
        assert all(t.depends_on == [] for t in result)

    def test_chain_with_gap(self):
        """Chain with shots not in the task list should skip gracefully."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001"), Shot(shot_id="shot_002")],
            chains=[
                ContinuityChain(
                    chain_id="chain_1",
                    shot_ids=["shot_001", "shot_003", "shot_002"],
                ),
            ],
        )
        # Only shot_001 and shot_002 have tasks, shot_003 doesn't
        tasks = self._make_tasks(["shot_001", "shot_002"])
        result = build_task_dependencies(tasks, sb)
        task_map = {t.task_id: t for t in result}
        # shot_001 → shot_002 (skipping shot_003 which has no task)
        assert task_map["task_video_shot_001"].depends_on == []
        assert task_map["task_video_shot_002"].depends_on == ["task_video_shot_001"]

    def test_multiple_chains(self):
        """Multiple independent chains should each have their own ordering."""
        sb = self._make_storyboard(
            shots=[
                Shot(shot_id="shot_001"),
                Shot(shot_id="shot_002"),
                Shot(shot_id="shot_003"),
                Shot(shot_id="shot_004"),
            ],
            chains=[
                ContinuityChain(chain_id="chain_a", shot_ids=["shot_001", "shot_002"]),
                ContinuityChain(chain_id="chain_b", shot_ids=["shot_003", "shot_004"]),
            ],
        )
        tasks = self._make_tasks(["shot_001", "shot_002", "shot_003", "shot_004"])
        result = build_task_dependencies(tasks, sb)
        task_map = {t.task_id: t for t in result}

        assert task_map["task_video_shot_001"].depends_on == []
        assert task_map["task_video_shot_002"].depends_on == ["task_video_shot_001"]
        assert task_map["task_video_shot_003"].depends_on == []
        assert task_map["task_video_shot_004"].depends_on == ["task_video_shot_003"]

    def test_does_not_duplicate_deps(self):
        """Same dependency should not be added twice."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001"), Shot(shot_id="shot_002")],
            chains=[
                ContinuityChain(chain_id="chain_1", shot_ids=["shot_001", "shot_002"]),
            ],
        )
        tasks = self._make_tasks(["shot_001", "shot_002"])
        # Run twice to check idempotency
        result = build_task_dependencies(tasks, sb)
        result = build_task_dependencies(result, sb)
        task_map = {t.task_id: t for t in result}
        assert len(task_map["task_video_shot_002"].depends_on) == 1

    def test_preserves_order(self):
        """Output should preserve the input task order."""
        sb = self._make_storyboard()
        tasks = self._make_tasks(["shot_001", "shot_002", "shot_003"])
        result = build_task_dependencies(tasks, sb)
        assert [t.task_id for t in result] == [
            "task_video_shot_001", "task_video_shot_002", "task_video_shot_003",
        ]

    def test_determinism(self):
        """Same inputs → same dependencies."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001"), Shot(shot_id="shot_002")],
            chains=[
                ContinuityChain(chain_id="chain_1", shot_ids=["shot_001", "shot_002"]),
            ],
        )
        tasks = self._make_tasks(["shot_001", "shot_002"])
        r1 = build_task_dependencies(tasks, sb)
        r2 = build_task_dependencies(tasks, sb)
        assert [t.depends_on for t in r1] == [t.depends_on for t in r2]
