"""Tests for LFO Storyboard Schema."""
from lfo.storyboard.storyboard import (
    REVIEW_PENDING,
    ActionBeat,
    Camera,
    Character,
    CharacterAppearance,
    ContinuityInfo,
    ProjectInfo,
    ReviewStatus,
    Scene,
    Shot,
    Story,
    Storyboard,
    StyleGuide,
)


class TestProjectInfo:
    def test_create(self):
        p = ProjectInfo(project_id="proj_001", title="My Film")
        assert p.project_id == "proj_001"
        assert p.schema_version == "lfo.storyboard.v1"
        assert p.revision == 1

    def test_round_trip(self):
        p = ProjectInfo(project_id="proj_001", title="Test", revision=3)
        d = p.to_dict()
        restored = ProjectInfo.from_dict(d)
        assert restored.project_id == "proj_001"
        assert restored.revision == 3


class TestCharacter:
    def test_auto_id(self):
        c = Character(name="Mira")
        assert c.character_id.startswith("char_")

    def test_with_id(self):
        c = Character(character_id="char_protagonist", name="Mira", role="protagonist")
        assert c.character_id == "char_protagonist"
        assert c.role == "protagonist"

    def test_new_fields_round_trip(self):
        """New fields (signature_action, key_prop, ref_asset_id, ref_image_path) round-trip."""
        c = Character(
            character_id="char_chenmo",
            name="Chen Mo",
            signature_action="leans against counter",
            key_prop="steel-pipe scanner gun",
            ref_asset_id="asset_001",
            ref_image_path="workspace/proj/ref_images/char_chenmo.png",
        )
        d = c.to_dict()
        assert d["signature_action"] == "leans against counter"
        assert d["key_prop"] == "steel-pipe scanner gun"
        assert d["ref_asset_id"] == "asset_001"
        assert d["ref_image_path"] == "workspace/proj/ref_images/char_chenmo.png"
        c2 = Character.from_dict(d)
        assert c2.signature_action == "leans against counter"
        assert c2.key_prop == "steel-pipe scanner gun"
        assert c2.ref_asset_id == "asset_001"
        assert c2.ref_image_path == "workspace/proj/ref_images/char_chenmo.png"


class TestStyleGuide:
    def test_new_fields_round_trip(self):
        """medium_lock and style_keywords round-trip through to_dict/from_dict."""
        sg = StyleGuide(
            visual_style="2d_anime",
            medium_lock="Medium: 2D hand-drawn animation. NOT 3D render.",
            style_keywords=["cinematic", "neon-lit"],
        )
        d = sg.to_dict()
        assert d["medium_lock"] == "Medium: 2D hand-drawn animation. NOT 3D render."
        assert d["style_keywords"] == ["cinematic", "neon-lit"]
        sg2 = StyleGuide.from_dict(d)
        assert sg2.medium_lock == "Medium: 2D hand-drawn animation. NOT 3D render."
        assert sg2.style_keywords == ["cinematic", "neon-lit"]
    def test_auto_id(self):
        s = Scene(name="Rainy Street")
        assert s.scene_id.startswith("scene_")


class TestShot:
    def test_auto_id(self):
        s = Shot()
        assert s.shot_id.startswith("shot_")

    def test_with_scene(self):
        s = Shot(shot_id="shot_001", scene_id="scene_001", desired_duration_ms=5000)
        assert s.shot_id == "shot_001"
        assert s.desired_duration_ms == 5000

    def test_camera_defaults(self):
        s = Shot()
        assert s.camera.shot_size == "medium"
        assert s.camera.angle == "eye_level"
        assert s.camera.movement == "static"

    def test_round_trip(self):
        s = Shot(
            shot_id="shot_001",
            scene_id="scene_001",
            desired_duration_ms=4000,
            camera=Camera(shot_size="close_up", angle="low", movement="slow_push_in"),
            characters=[
                CharacterAppearance(
                    character_id="char_001",
                    screen_position="center",
                    action="walks forward",
                )
            ],
            action_beats=[
                ActionBeat(sequence=1, description="Enters frame", duration_ms=2000),
                ActionBeat(sequence=2, description="Stops", duration_ms=2000),
            ],
        )
        d = s.to_dict()
        restored = Shot.from_dict(d)
        assert restored.shot_id == "shot_001"
        assert restored.camera.shot_size == "close_up"
        assert len(restored.characters) == 1
        assert restored.characters[0].character_id == "char_001"
        assert len(restored.action_beats) == 2
        assert restored.action_beats[0].description == "Enters frame"


class TestContinuityInfo:
    def test_references(self):
        c = ContinuityInfo(
            start_state="standing left",
            end_state="sitting right",
            previous_shot_id="shot_001",
            next_shot_id="shot_003",
            priority="high",
        )
        assert c.previous_shot_id == "shot_001"
        assert c.next_shot_id == "shot_003"

    def test_round_trip(self):
        c = ContinuityInfo(
            start_state="rain",
            end_state="sun",
            continuity_elements=["costume:blue_jacket"],
        )
        d = c.to_dict()
        restored = ContinuityInfo.from_dict(d)
        assert restored.continuity_elements == ["costume:blue_jacket"]


class TestStoryboard:
    def test_create_empty(self):
        sb = Storyboard()
        assert sb.project.project_id == ""
        assert sb.shots == []
        assert sb.review.status == REVIEW_PENDING

    def test_total_duration(self):
        sb = Storyboard()
        sb.shots = [
            Shot(shot_id="s1", desired_duration_ms=5000),
            Shot(shot_id="s2", desired_duration_ms=3000),
            Shot(shot_id="s3", desired_duration_ms=7000),
        ]
        assert sb.total_duration_ms() == 15000

    def test_total_duration_empty(self):
        sb = Storyboard()
        assert sb.total_duration_ms() == 0

    def test_shot_by_id(self):
        sb = Storyboard()
        sb.shots = [Shot(shot_id="s1"), Shot(shot_id="s2")]
        found = sb.shot_by_id("s2")
        assert found is not None
        assert found.shot_id == "s2"

    def test_shot_by_id_missing(self):
        sb = Storyboard()
        assert sb.shot_by_id("nonexistent") is None

    def test_character_by_id(self):
        sb = Storyboard()
        sb.characters = [Character(character_id="c1", name="Mira")]
        found = sb.character_by_id("c1")
        assert found is not None
        assert found.name == "Mira"

    def test_scene_by_id(self):
        sb = Storyboard()
        sb.scenes = [Scene(scene_id="sc1", name="Lab")]
        found = sb.scene_by_id("sc1")
        assert found is not None
        assert found.name == "Lab"

    def test_display_index(self):
        sb = Storyboard()
        sb.shots = [Shot(shot_id="s1"), Shot(shot_id="s2"), Shot(shot_id="s3")]
        assert sb.display_index_for("s1") == 1
        assert sb.display_index_for("s2") == 2
        assert sb.display_index_for("s3") == 3

    def test_display_index_missing(self):
        sb = Storyboard()
        assert sb.display_index_for("nonexistent") == 0

    def test_full_round_trip(self):
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_001", title="Test Film"),
            story=Story(logline="A robot remembers.", synopsis="Long story."),
            style=StyleGuide(visual_style="cyberpunk"),
            characters=[
                Character(character_id="char_001", name="Mira", role="protagonist"),
            ],
            scenes=[
                Scene(scene_id="scene_001", name="Rainy Street", environment="exterior"),
            ],
            shots=[
                Shot(
                    shot_id="shot_001",
                    display_index=1,
                    scene_id="scene_001",
                    desired_duration_ms=5000,
                    camera=Camera(shot_size="wide", movement="static"),
                    characters=[
                        CharacterAppearance(
                            character_id="char_001",
                            screen_position="center",
                            action="walks",
                        )
                    ],
                ),
            ],
            review=ReviewStatus(status=REVIEW_PENDING),
        )

        d = sb.to_dict()
        restored = Storyboard.from_dict(d)

        assert restored.project.project_id == "proj_001"
        assert restored.story.logline == "A robot remembers."
        assert len(restored.characters) == 1
        assert restored.characters[0].name == "Mira"
        assert len(restored.scenes) == 1
        assert restored.scenes[0].name == "Rainy Street"
        assert len(restored.shots) == 1
        assert restored.shots[0].shot_id == "shot_001"
        assert restored.shots[0].desired_duration_ms == 5000
        assert restored.shots[0].camera.shot_size == "wide"
