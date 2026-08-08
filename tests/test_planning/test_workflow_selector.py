"""Tests for planning.workflow_selector."""
from lfo.planning.workflow_selector import select_workflow
from lfo.storyboard.storyboard import (
    CharacterAppearance,
    ContinuityInfo,
    ProjectInfo,
    Shot,
    Storyboard,
)


class TestSelectWorkflow:
    def _make_storyboard(self, shots=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
        )

    def test_no_assets_t2va_fallback(self):
        """With no available assets, should fall back to t2va (provisional)."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        result = select_workflow(sb.shots[0], sb)
        assert result.workflow_id == "h3_standard_t2v"
        assert result.workflow_mode == "t2va"
        assert result.selection_status == "provisional"
        assert "start_frame" in result.missing_requirements

    def test_start_frame_only_i2v(self):
        """Approved start frame (no end) → i2v."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        assets = {"shot_001": {"start_frame": {"status": "approved"}}}
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_i2v"
        assert result.workflow_mode == "i2v"
        assert result.selection_status == "confirmed"

    def test_start_and_end_frame_first_last(self):
        """Approved start + end frame → first_last."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        assets = {
            "shot_001": {
                "start_frame": {"status": "approved"},
                "end_frame": {"status": "approved"},
            },
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_i2v"
        assert result.workflow_mode == "first_last"
        assert result.selection_status == "confirmed"

    def test_character_ref_and_composition_r2v(self):
        """1 identity char with ref + composition ref → r2v (continuation shot)."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                    continuity=ContinuityInfo(start_frame_needed=True),
                ),
            ],
        )
        assets = {
            "char_001": {"character_ref": {"status": "approved"}},
            "shot_001": {"composition_ref": {"status": "approved"}},
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_r2v"
        assert result.workflow_mode == "r2v"
        assert result.selection_status == "confirmed"

    def test_two_chars_with_refs_r2v(self):
        """2 identity chars with refs + scene ref → r2v (continuation shot)."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[
                        CharacterAppearance(character_id="char_001"),
                        CharacterAppearance(character_id="char_002"),
                    ],
                    continuity=ContinuityInfo(start_frame_needed=True),
                ),
            ],
        )
        assets = {
            "char_001": {"character_ref": {"status": "approved"}},
            "char_002": {"character_ref": {"status": "approved"}},
            "scene_001": {"scene_ref": {"status": "approved"}},
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_r2v"
        assert result.workflow_mode == "r2v"

    def test_r2v_priority_over_first_last(self):
        """R2V (rule 1/2) should take priority over first_last (rule 3).

        Requires start_frame_needed=True so the shot forces visual input;
        otherwise R2V is not eligible and first_last would be selected.
        """
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                    continuity=ContinuityInfo(start_frame_needed=True),
                ),
            ],
        )
        assets = {
            "char_001": {"character_ref": {"status": "approved"}},
            "shot_001": {
                "composition_ref": {"status": "approved"},
                "start_frame": {"status": "approved"},
                "end_frame": {"status": "approved"},
            },
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_r2v"
        assert result.workflow_mode == "r2v"

    def test_no_characters_t2va(self):
        """Shot with no characters and no assets → t2va."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        result = select_workflow(sb.shots[0], sb, available_assets={})
        assert result.workflow_id == "h3_standard_t2v"
        assert result.workflow_mode == "t2va"
        assert result.selection_status == "provisional"

    def test_character_without_ref_not_counted(self):
        """Character without approved ref doesn't count for R2V."""
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                ),
            ],
        )
        # No character_ref provided
        assets = {
            "shot_001": {"composition_ref": {"status": "approved"}},
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        # No character ref → not R2V → falls to T2VA
        assert result.workflow_id == "h3_standard_t2v"
        assert result.workflow_mode == "t2va"

    def test_refs_without_visual_input_falls_back_to_t2va(self):
        """Character + composition refs but no visual input requirement → t2va.

        R2V requires the shot to actually need visual input (continuity or
        explicit preference).  The first shot establishes the character
        look, so it should stay T2VA even with registered refs.
        """
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    scene_id="scene_001",
                    characters=[CharacterAppearance(character_id="char_001")],
                    # No start_frame_needed, no preferred_mode → first shot
                ),
            ],
        )
        assets = {
            "char_001": {"character_ref": {"status": "approved"}},
            "shot_001": {"composition_ref": {"status": "approved"}},
        }
        result = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert result.workflow_id == "h3_standard_t2v"
        assert result.workflow_mode == "t2va"

    def test_determinism(self):
        """Same inputs → same selection."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        assets = {"shot_001": {"start_frame": {"status": "approved"}}}
        r1 = select_workflow(sb.shots[0], sb, available_assets=assets)
        r2 = select_workflow(sb.shots[0], sb, available_assets=assets)
        assert r1.workflow_id == r2.workflow_id
        assert r1.workflow_mode == r2.workflow_mode
        assert r1.reason == r2.reason

    def test_workflow_family_populated(self):
        """Workflow family should come from manifest."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
        )
        result = select_workflow(sb.shots[0], sb)
        assert result.workflow_family == "h3_fl2va"

    def test_none_assets_treated_as_empty(self):
        """available_assets=None should be treated as empty."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
        )
        result = select_workflow(sb.shots[0], sb, available_assets=None)
        assert result.workflow_id == "h3_standard_t2v"
