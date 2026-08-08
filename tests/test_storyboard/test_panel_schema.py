"""Tests for Beat + Panel schema and panel derivation."""
from __future__ import annotations

from lfo.planning.panel_pack import (
    PanelPack,
    PanelPackRef,
    build_panel_pack,
    panel_pack_from_dict,
    panel_pack_to_dict,
)
from lfo.storyboard.panel_plan import derive_panels_from_beats
from lfo.storyboard.storyboard import (
    Beat,
    CharacterAppearance,
    Panel,
    ProjectInfo,
    Storyboard,
)


def _sample_beats(n: int = 8) -> list[Beat]:
    return [
        Beat(
            beat_id=f"beat_{i:03d}",
            sequence=i,
            scene_id="scene_001",
            description=f"Beat {i} action",
            dialogue=f"Line {i}" if i % 3 == 0 else "",
            sound=f"SFX {i}" if i % 2 == 0 else "",
            characters=[
                CharacterAppearance(
                    character_id="char_001",
                    action=f"action {i}",
                )
            ],
            framing="medium" if i % 2 else "wide",
        )
        for i in range(1, n + 1)
    ]


class TestBeatRoundTrip:
    def test_minimal(self):
        beat = Beat(beat_id="beat_001", sequence=1, scene_id="scene_001", description="Hello")
        restored = Beat.from_dict(beat.to_dict())
        assert restored.beat_id == "beat_001"
        assert restored.sequence == 1
        assert restored.description == "Hello"

    def test_with_characters(self):
        beat = Beat(
            beat_id="beat_002",
            sequence=2,
            scene_id="scene_001",
            characters=[CharacterAppearance(character_id="char_001", action="walks")],
            framing="close_up",
        )
        restored = Beat.from_dict(beat.to_dict())
        assert len(restored.characters) == 1
        assert restored.characters[0].action == "walks"
        assert restored.framing == "close_up"


class TestPanelRoundTrip:
    def test_minimal(self):
        panel = Panel(
            panel_id="panel_001",
            sequence=1,
            beat_range=(1, 8),
            beat_ids=[f"beat_{i:03d}" for i in range(1, 9)],
            desired_duration_ms=15_000,
        )
        restored = Panel.from_dict(panel.to_dict())
        assert restored.panel_id == "panel_001"
        assert restored.beat_range == (1, 8)
        assert restored.desired_duration_ms == 15_000

    def test_with_pack(self):
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw_001",
            character_assets=[("char_001", "asset_char")],
        )
        panel = Panel(
            panel_id="panel_001",
            sequence=1,
            beat_range=(1, 8),
            beat_ids=["beat_001"],
            desired_duration_ms=15_000,
            bw_asset_id="bw_001",
            pack=pack,
            prompt_text="承接上段…",
        )
        d = panel.to_dict()
        assert d["pack"]["panel_id"] == "panel_001"
        assert d["prompt_text"] == "承接上段…"
        restored = Panel.from_dict(d)
        assert restored.pack is not None
        assert restored.pack.storyboard_bw_asset_id == "bw_001"
        assert len(restored.pack.refs) >= 2


class TestDerivePanelsFromBeats:
    def test_eight_beats_one_panel(self):
        beats = _sample_beats(8)
        panels = derive_panels_from_beats(beats, 15_000)
        assert len(panels) == 1
        assert panels[0].beat_range == (1, 8)
        assert panels[0].desired_duration_ms == 15_000
        assert len(panels[0].beat_ids) == 8

    def test_fifteen_beats_two_panels(self):
        beats = _sample_beats(15)
        panels = derive_panels_from_beats(beats, 30_000)
        assert len(panels) == 2
        assert panels[0].beat_range == (1, 8)
        assert panels[1].beat_range == (8, 15)
        assert panels[0].desired_duration_ms == 15_000
        assert panels[1].desired_duration_ms == 15_000

    def test_empty_beats(self):
        assert derive_panels_from_beats([], 30_000) == []


class TestStoryboardBeatsPanelsRoundTrip:
    def test_full_round_trip(self):
        beats = _sample_beats(8)
        panels = derive_panels_from_beats(beats, 15_000)
        sb = Storyboard(
            project=ProjectInfo(project_id="proj_panel_test", title="Panel Test"),
            beats=beats,
            panels=panels,
        )
        restored = Storyboard.from_dict(sb.to_dict())
        assert len(restored.beats) == 8
        assert len(restored.panels) == 1
        assert restored.beats[0].beat_id == "beat_001"
        assert restored.panels[0].beat_range == (1, 8)
        assert restored.total_duration_ms() == 15_000

    def test_panel_by_id(self):
        beats = _sample_beats(3)
        panels = derive_panels_from_beats(beats, 9_000)
        sb = Storyboard(beats=beats, panels=panels)
        found = sb.panel_by_id(panels[0].panel_id)
        assert found is not None
        assert found.sequence == 1

    def test_beat_by_id(self):
        beats = _sample_beats(3)
        sb = Storyboard(beats=beats, panels=derive_panels_from_beats(beats, 9_000))
        assert sb.beat_by_id("beat_002") is not None
        assert sb.beat_by_id("missing") is None
