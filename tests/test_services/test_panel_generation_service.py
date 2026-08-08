"""Tests for PanelGenerationService."""
from __future__ import annotations

from lfo.services.panel_generation_service import PanelGenerationService
from lfo.storyboard.storyboard import (
    Beat,
    CharacterAppearance,
    Panel,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)


def _make_storyboard_with_panel() -> Storyboard:
    beats = [
        Beat(
            beat_id="beat_001",
            sequence=1,
            scene_id="scene_001",
            description="林野提着外卖箱站在巷口。",
            sound="脚步声和车流",
            characters=[CharacterAppearance(character_id="char_linye")],
        ),
        Beat(
            beat_id="beat_002",
            sequence=2,
            scene_id="scene_001",
            description="他低头看手机上的欠款提示。",
            sound="手机震动",
            characters=[CharacterAppearance(character_id="char_linye")],
        ),
    ]
    panel = Panel(
        panel_id="panel_001",
        sequence=1,
        beat_range=(1, 2),
        beat_ids=["beat_001", "beat_002"],
        desired_duration_ms=15_000,
        bw_asset_id="asset_bw_001",
    )
    return Storyboard(
        project=ProjectInfo(project_id="proj-test", title="Test"),
        style=StyleGuide(medium_lock="Medium: 3D rendered suspense. NOT 2D anime."),
        beats=beats,
        panels=[panel],
    )


class TestPanelGenerationService:
    def test_one_panel_char_and_bw_produces_r2v_hub_prompt(self):
        storyboard = _make_storyboard_with_panel()
        available_assets = {
            "char_linye": {
                "character_ref": {
                    "status": "approved",
                    "asset_id": "asset_char_linye",
                },
            },
        }

        service = PanelGenerationService()
        plan = service.generate_plan(
            storyboard,
            "proj-test",
            available_assets=available_assets,
        )

        assert len(plan.panel_plans) == 1
        panel_plan = plan.panel_plans[0]
        assert panel_plan.panel_id == "panel_001"
        assert panel_plan.workflow_mode == "r2v"
        assert panel_plan.workflow_id == "h3_standard_r2v"
        assert panel_plan.selection_status == "confirmed"
        assert panel_plan.task_type == "video.h3"
        assert "图片1" in panel_plan.prompt_text
        assert panel_plan.pack.storyboard_bw_asset_id == "asset_bw_001"
        assert any(ref.role == "character" for ref in panel_plan.pack.refs)

    def test_uses_existing_panel_pack_when_set(self):
        from lfo.planning.panel_pack import build_panel_pack

        storyboard = _make_storyboard_with_panel()
        existing_pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 2),
            bw_asset_id="asset_bw_001",
            character_assets=[("char_linye", "asset_char_linye")],
        )
        storyboard.panels[0].pack = existing_pack

        service = PanelGenerationService()
        plan = service.generate_plan(storyboard, "proj-test")

        assert plan.panel_plans[0].pack is existing_pack
        assert plan.panel_plans[0].workflow_mode == "r2v"

    def test_empty_panels_returns_empty_plan(self):
        storyboard = Storyboard(
            project=ProjectInfo(project_id="proj-empty"),
            panels=[],
        )
        service = PanelGenerationService()
        plan = service.generate_plan(storyboard, "proj-empty")
        assert plan.panel_plans == []
