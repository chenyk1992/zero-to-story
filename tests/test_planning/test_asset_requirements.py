"""Tests for planning.asset_requirements."""
from lfo.planning.asset_requirements import plan_panel_asset_requirements
from lfo.planning.panel_pack import build_panel_pack
from lfo.planning.workflow_selector import WorkflowSelection
from lfo.storyboard.storyboard import Panel


class TestPlanPanelAssetRequirements:
    def _make_selection(self, mode, *, status: str = "provisional"):
        return WorkflowSelection(
            workflow_id="h3_standard_t2v",
            workflow_family="h3_fl2va",
            workflow_mode=mode,
            reason="test",
            selection_status=status,
        )

    def test_t2va_no_requirements(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[("char_001", "asset_char")],
            max_ref_images=3,
        )
        sel = self._make_selection("t2va")
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        assert reqs == []

    def test_i2v_requires_start_frame(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[],
            max_ref_images=3,
        )
        sel = self._make_selection("i2v")
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        assert len(reqs) == 1
        assert reqs[0].asset_role == "start_frame"
        assert reqs[0].target_id == "panel_001"

    def test_first_last_requires_start_and_end(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[],
            max_ref_images=3,
        )
        sel = self._make_selection("first_last")
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        roles = [r.asset_role for r in reqs]
        assert "start_frame" in roles
        assert "end_frame" in roles
        assert len(reqs) == 2

    def test_confirmed_r2v_returns_no_requirements(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw_asset",
            character_assets=[("char_001", "asset_char")],
            max_ref_images=3,
        )
        sel = self._make_selection("r2v", status="confirmed")
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        assert reqs == []

    def test_blocked_r2v_lists_missing_refs(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="",
            character_assets=[("char_001", "asset_char_001"), ("char_002", "asset_char_002")],
            max_ref_images=3,
        )
        sel = WorkflowSelection(
            workflow_id="h3_standard_r2v",
            workflow_family="h3_ref2va",
            workflow_mode="r2v",
            reason="blocked",
            selection_status="blocked",
            missing_requirements=["composition_ref missing"],
        )
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        roles = [r.asset_role for r in reqs]
        assert roles.count("character_ref") == 2
        assert "composition_ref" in roles

    def test_requirement_ids_unique(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="",
            character_assets=[("char_001", "asset_char")],
            max_ref_images=3,
        )
        sel = WorkflowSelection(
            workflow_id="h3_standard_r2v",
            workflow_family="h3_ref2va",
            workflow_mode="r2v",
            reason="blocked",
            selection_status="blocked",
            missing_requirements=["character_ref missing"],
        )
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        ids = [r.requirement_id for r in reqs]
        assert len(ids) == len(set(ids))

    def test_all_missing_by_default(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[],
            max_ref_images=3,
        )
        sel = self._make_selection("i2v")
        reqs = plan_panel_asset_requirements(panel, pack, sel)
        assert all(r.status == "missing" for r in reqs)

    def test_determinism(self):
        panel = Panel(panel_id="panel_001")
        pack = build_panel_pack(
            panel_id="panel_001",
            beat_range=(1, 8),
            bw_asset_id="bw",
            character_assets=[],
            max_ref_images=3,
        )
        sel = self._make_selection("first_last")
        r1 = plan_panel_asset_requirements(panel, pack, sel)
        r2 = plan_panel_asset_requirements(panel, pack, sel)
        assert [r.requirement_id for r in r1] == [r.requirement_id for r in r2]
