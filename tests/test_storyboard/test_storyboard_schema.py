"""Tests for LFO Storyboard Schema."""
from lfo.storyboard.panel_plan import derive_panels_from_beats
from lfo.storyboard.storyboard import (
    REVIEW_PENDING,
    ActionBeat,
    Beat,
    Camera,
    Character,
    CharacterAppearance,
    ContinuityInfo,
    Panel,
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


class TestBeat:
    def test_auto_id(self):
        b = Beat()
        assert b.beat_id.startswith("beat_")

    def test_with_scene(self):
        b = Beat(beat_id="beat_001", scene_id="scene_001", sequence=1, description="Walks in")
        assert b.beat_id == "beat_001"
        assert b.scene_id == "scene_001"

    def test_round_trip(self):
        b = Beat(
            beat_id="beat_001",
            sequence=1,
            scene_id="scene_001",
            description="Enters frame",
            dialogue="Hello",
            sound="footsteps",
            characters=[
                CharacterAppearance(
                    character_id="char_001",
                    screen_position="center",
                    action="walks forward",
                )
            ],
            framing="close_up",
        )
        d = b.to_dict()
        restored = Beat.from_dict(d)
        assert restored.beat_id == "beat_001"
        assert restored.framing == "close_up"
        assert len(restored.characters) == 1
        assert restored.characters[0].character_id == "char_001"


class TestShot:
    """Shot remains for LLM decompose intermediate; not on Storyboard."""

    def test_auto_id(self):
        s = Shot()
        assert s.shot_id.startswith("shot_")

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
        assert len(restored.action_beats) == 2


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
        assert sb.beats == []
        assert sb.panels == []
        assert sb.review.status == REVIEW_PENDING

    def test_total_duration(self):
        sb = Storyboard(
            panels=[
                Panel(panel_id="p1", desired_duration_ms=5000),
                Panel(panel_id="p2", desired_duration_ms=3000),
                Panel(panel_id="p3", desired_duration_ms=7000),
            ],
        )
        assert sb.total_duration_ms() == 15000

    def test_total_duration_empty(self):
        sb = Storyboard()
        assert sb.total_duration_ms() == 0

    def test_panel_by_id(self):
        sb = Storyboard(
            panels=[Panel(panel_id="p1"), Panel(panel_id="p2")],
        )
        found = sb.panel_by_id("p2")
        assert found is not None
        assert found.panel_id == "p2"

    def test_panel_by_id_missing(self):
        sb = Storyboard()
        assert sb.panel_by_id("nonexistent") is None

    def test_beat_by_id(self):
        sb = Storyboard()
        sb.beats = [Beat(beat_id="b1"), Beat(beat_id="b2")]
        found = sb.beat_by_id("b1")
        assert found is not None
        assert found.beat_id == "b1"

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

    def test_display_index_for_panel(self):
        sb = Storyboard(
            panels=[Panel(panel_id="p1"), Panel(panel_id="p2"), Panel(panel_id="p3")],
        )
        assert sb.display_index_for_panel("p1") == 1
        assert sb.display_index_for_panel("p2") == 2
        assert sb.display_index_for_panel("p3") == 3

    def test_display_index_missing(self):
        sb = Storyboard()
        assert sb.display_index_for_panel("nonexistent") == 0

    def test_full_round_trip(self):
        beats = [
            Beat(
                beat_id="beat_001",
                sequence=1,
                scene_id="scene_001",
                description="Walks down the street",
                framing="wide",
                characters=[
                    CharacterAppearance(
                        character_id="char_001",
                        screen_position="center",
                        action="walks",
                    )
                ],
            ),
        ]
        panels = derive_panels_from_beats(beats, 5000)
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
            beats=beats,
            panels=panels,
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
        assert len(restored.beats) == 1
        assert restored.beats[0].beat_id == "beat_001"
        assert restored.beats[0].framing == "wide"
        assert len(restored.panels) == 1
