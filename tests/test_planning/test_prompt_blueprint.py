"""Tests for planning.prompt_blueprint."""
from lfo.planning.prompt_blueprint import (
    compile_first_last_blueprint,
    compile_i2v_blueprint,
    compile_r2v_blueprint,
    compile_t2va_blueprint,
)
from lfo.planning.schema import ReferenceBinding
from lfo.storyboard.storyboard import (
    ActionBeat,
    AudioPolicy,
    Camera,
    CharacterAppearance,
    ContinuityInfo,
    ProjectInfo,
    Scene,
    Shot,
    Storyboard,
    StyleGuide,
)


class TestCompileT2vaBlueprint:
    def _make_storyboard(self, shots=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
        )

    def test_basic(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", description="A hero walks in rain")],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        assert bp.blueprint_id == "pb_t2va_shot_001"
        assert bp.workflow_mode == "t2va"
        assert bp.materialization_status == "complete"
        assert bp.symbolic_references == []

    def test_has_negative_part(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        negative_parts = [p for p in bp.parts if p.part_type == "negative"]
        assert len(negative_parts) == 1
        assert "blurry" in negative_parts[0].content

    def test_no_symbolic_refs(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        assert all(not r.is_symbolic for r in bp.symbolic_references)


class TestCompileI2vBlueprint:
    def _make_storyboard(self, shots=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
        )

    def test_symbolic_start_frame(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_i2v_blueprint(sb.shots[0], sb)
        assert bp.workflow_mode == "i2v"
        assert bp.materialization_status == "waiting_assets"
        assert len(bp.symbolic_references) == 1
        assert bp.symbolic_references[0].is_symbolic is True
        assert "start_frame" in bp.symbolic_references[0].asset_id

    def test_blueprint_id(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_i2v_blueprint(sb.shots[0], sb)
        assert bp.blueprint_id == "pb_i2v_shot_001"


class TestCompileFirstLastBlueprint:
    def _make_storyboard(self, shots=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
        )

    def test_symbolic_start_and_end(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_first_last_blueprint(sb.shots[0], sb)
        assert bp.workflow_mode == "first_last"
        assert len(bp.symbolic_references) == 2
        roles = [r.asset_id for r in bp.symbolic_references]
        assert any("start_frame" in r for r in roles)
        assert any("end_frame" in r for r in roles)

    def test_status_waiting(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_first_last_blueprint(sb.shots[0], sb)
        assert bp.materialization_status == "waiting_assets"


class TestCompileR2vBlueprint:
    def _make_storyboard(self, shots=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
        )

    def test_with_references(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        refs = [
            ReferenceBinding(slot=1, asset_id="asset_char", entity_id="char_001", role="character"),
            ReferenceBinding(slot=2, asset_id="asset_comp", entity_id="shot_001", role="composition"),
            ReferenceBinding(slot=3, asset_id="asset_scene", entity_id="scene_001", role="scene"),
        ]
        bp = compile_r2v_blueprint(sb.shots[0], sb, reference_bindings=refs)
        assert bp.workflow_mode == "r2v"
        assert len(bp.symbolic_references) == 3

    def test_with_pictures_in_subject(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        refs = [
            ReferenceBinding(slot=1, asset_id="a", entity_id="c", role="character"),
            ReferenceBinding(slot=2, asset_id="b", entity_id="s", role="composition"),
        ]
        bp = compile_r2v_blueprint(sb.shots[0], sb, reference_bindings=refs)
        # Should have picture references added
        subject_parts = [p for p in bp.parts if "Picture" in p.content]
        assert len(subject_parts) >= 1

    def test_no_references(self):
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_r2v_blueprint(sb.shots[0], sb)
        assert bp.materialization_status == "complete"

    def test_default_references_none(self):
        """Default reference_bindings=None should work."""
        sb = self._make_storyboard(shots=[Shot(shot_id="shot_001")])
        bp = compile_r2v_blueprint(sb.shots[0], sb)
        assert bp.symbolic_references == []


class TestBaseParts:
    """Test the common semantic extraction logic."""

    def _make_storyboard(self, shots=None, scenes=None, characters=None, audio=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
            scenes=scenes or [],
            characters=characters or [],
            audio_policy=audio or AudioPolicy(),
        )

    def test_subject_from_characters(self):
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    characters=[
                        CharacterAppearance(character_id="char_001", action="walks forward"),
                    ],
                ),
            ],
            characters=[],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        subject = [p for p in bp.parts if p.part_type == "subject"]
        assert len(subject) == 1
        assert "walks forward" in subject[0].content

    def test_scene_from_description(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", scene_id="scene_001")],
            scenes=[Scene(scene_id="scene_001", description="A rainy city street at night")],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        scene = [p for p in bp.parts if p.part_type == "scene"]
        assert len(scene) == 1
        assert "rainy city street" in scene[0].content

    def test_action_from_beats(self):
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    action_beats=[
                        ActionBeat(sequence=1, description="Enters frame"),
                        ActionBeat(sequence=2, description="Stops"),
                    ],
                ),
            ],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        action = [p for p in bp.parts if p.part_type == "action"]
        assert len(action) == 1
        assert "Enters frame" in action[0].content
        assert "Stops" in action[0].content

    def test_camera_parts(self):
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    camera=Camera(shot_size="close_up", movement="slow_push_in"),
                ),
            ],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        camera = [p for p in bp.parts if p.part_type == "camera"]
        assert len(camera) == 1
        assert "close_up" in camera[0].content
        assert "slow_push_in" in camera[0].content

    def test_end_state_from_continuity(self):
        sb = self._make_storyboard(
            shots=[
                Shot(
                    shot_id="shot_001",
                    continuity=ContinuityInfo(end_state="Character exits left"),
                ),
            ],
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        end = [p for p in bp.parts if p.part_type == "end_state"]
        assert len(end) == 1
        assert "exits left" in end[0].content

    def test_audio_from_policy(self):
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
            audio=AudioPolicy(mode="full", music="generated", sound_effects="auto"),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        audio = [p for p in bp.parts if p.part_type == "audio"]
        assert len(audio) == 1
        assert "music" in audio[0].content

    def test_determinism(self):
        """Same shot → same blueprint parts."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", description="Test scene")],
        )
        bp1 = compile_t2va_blueprint(sb.shots[0], sb)
        bp2 = compile_t2va_blueprint(sb.shots[0], sb)
        assert [p.content for p in bp1.parts] == [p.content for p in bp2.parts]
        assert [p.part_type for p in bp1.parts] == [p.part_type for p in bp2.parts]


class TestStyleParts:
    """Test that StyleGuide medium_lock and style_keywords appear in blueprints."""

    def _make_storyboard(self, shots=None, style=None):
        return Storyboard(
            project=ProjectInfo(project_id="proj_001"),
            shots=shots or [],
            style=style or StyleGuide(),
        )

    def test_medium_lock_in_parts(self):
        """medium_lock appears as a 'style' PromptPart."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", description="A hero walks")],
            style=StyleGuide(medium_lock="Medium: 3D rendered scene. NOT anime."),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        style_parts = [p for p in bp.parts if p.part_type == "style"]
        assert len(style_parts) == 1
        assert style_parts[0].content == "Medium: 3D rendered scene. NOT anime."
        assert style_parts[0].source == "storyboard.style.medium_lock"

    def test_style_keywords_in_parts(self):
        """style_keywords appear as a 'style_keywords' PromptPart."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001", description="A hero walks")],
            style=StyleGuide(style_keywords=["cinematic", "neon-lit"]),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        kw_parts = [p for p in bp.parts if p.part_type == "style_keywords"]
        assert len(kw_parts) == 1
        assert "cinematic" in kw_parts[0].content
        assert "neon-lit" in kw_parts[0].content

    def test_no_medium_lock_no_style_part(self):
        """Empty medium_lock → no 'style' part."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
            style=StyleGuide(),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        style_parts = [p for p in bp.parts if p.part_type == "style"]
        assert style_parts == []

    def test_no_keywords_no_style_keywords_part(self):
        """Empty style_keywords → no 'style_keywords' part."""
        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
            style=StyleGuide(),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        kw_parts = [p for p in bp.parts if p.part_type == "style_keywords"]
        assert kw_parts == []

    def test_both_medium_lock_and_keywords(self):
        """Both fields present → both parts appear."""
        from lfo.storyboard.storyboard import StyleGuide

        sb = self._make_storyboard(
            shots=[Shot(shot_id="shot_001")],
            style=StyleGuide(
                medium_lock="Medium: anime. NOT 3D.",
                style_keywords=["cinematic"],
            ),
        )
        bp = compile_t2va_blueprint(sb.shots[0], sb)
        style_parts = [p for p in bp.parts if p.part_type == "style"]
        kw_parts = [p for p in bp.parts if p.part_type == "style_keywords"]
        assert len(style_parts) == 1
        assert len(kw_parts) == 1
