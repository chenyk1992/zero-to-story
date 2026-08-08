"""Tests for planning.asset_requirements."""
from lfo.planning.asset_requirements import plan_asset_requirements
from lfo.planning.workflow_selector import WorkflowSelection
from lfo.storyboard.storyboard import CharacterAppearance, Shot


class TestPlanAssetRequirements:
    def _make_selection(self, mode):
        return WorkflowSelection(
            workflow_id="h3_standard_t2v",
            workflow_family="h3_fl2va",
            workflow_mode=mode,
            reason="test",
        )

    def test_t2va_no_requirements(self):
        shot = Shot(shot_id="shot_001")
        sel = self._make_selection("t2va")
        reqs = plan_asset_requirements(shot, sel)
        assert reqs == []

    def test_i2v_requires_start_frame(self):
        shot = Shot(shot_id="shot_001")
        sel = self._make_selection("i2v")
        reqs = plan_asset_requirements(shot, sel)
        assert len(reqs) == 1
        assert reqs[0].asset_role == "start_frame"
        assert reqs[0].target_id == "shot_001"
        assert reqs[0].required is True

    def test_first_last_requires_start_and_end(self):
        shot = Shot(shot_id="shot_001")
        sel = self._make_selection("first_last")
        reqs = plan_asset_requirements(shot, sel)
        roles = [r.asset_role for r in reqs]
        assert "start_frame" in roles
        assert "end_frame" in roles
        assert len(reqs) == 2

    def test_r2v_character_refs(self):
        shot = Shot(
            shot_id="shot_001",
            scene_id="scene_001",
            characters=[
                CharacterAppearance(character_id="char_001"),
                CharacterAppearance(character_id="char_002"),
            ],
        )
        sel = self._make_selection("r2v")
        reqs = plan_asset_requirements(shot, sel)
        roles = [r.asset_role for r in reqs]
        assert roles.count("character_ref") == 2
        assert "scene_ref" in roles
        assert "composition_ref" in roles

    def test_r2v_no_characters(self):
        """R2V with no characters still needs scene + composition refs."""
        shot = Shot(shot_id="shot_001", scene_id="scene_001")
        sel = self._make_selection("r2v")
        reqs = plan_asset_requirements(shot, sel)
        roles = [r.asset_role for r in reqs]
        assert "character_ref" not in roles
        assert "scene_ref" in roles
        assert "composition_ref" in roles

    def test_r2v_no_scene_id(self):
        """R2V with no scene_id skips scene_ref."""
        shot = Shot(shot_id="shot_001")
        sel = self._make_selection("r2v")
        reqs = plan_asset_requirements(shot, sel)
        roles = [r.asset_role for r in reqs]
        assert "scene_ref" not in roles
        assert "composition_ref" in roles

    def test_requirement_ids_unique(self):
        """Each requirement should have a unique ID."""
        shot = Shot(
            shot_id="shot_001",
            scene_id="scene_001",
            characters=[CharacterAppearance(character_id="char_001")],
        )
        sel = self._make_selection("r2v")
        reqs = plan_asset_requirements(shot, sel)
        ids = [r.requirement_id for r in reqs]
        assert len(ids) == len(set(ids))

    def test_all_missing_by_default(self):
        """All requirements should start as 'missing'."""
        shot = Shot(shot_id="shot_001")
        sel = self._make_selection("i2v")
        reqs = plan_asset_requirements(shot, sel)
        assert all(r.status == "missing" for r in reqs)

    def test_determinism(self):
        """Same shot + selection → same requirements."""
        shot = Shot(shot_id="shot_001", scene_id="scene_001")
        sel = self._make_selection("first_last")
        r1 = plan_asset_requirements(shot, sel)
        r2 = plan_asset_requirements(shot, sel)
        assert [r.requirement_id for r in r1] == [r.requirement_id for r in r2]
        assert [r.asset_role for r in r1] == [r.asset_role for r in r2]
