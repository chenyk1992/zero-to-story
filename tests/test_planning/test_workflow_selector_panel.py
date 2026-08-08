from lfo.planning.panel_pack import build_panel_pack
from lfo.planning.workflow_selector import select_workflow_for_panel


def test_valid_pack_selects_r2v():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="bw",
        character_assets=[("char_a", "asset_a")],
        max_ref_images=3,
    )
    result = select_workflow_for_panel(pack)
    assert result.workflow_mode == "r2v"
    assert result.workflow_id == "h3_standard_r2v"
    assert result.selection_status == "confirmed"


def test_unapproved_composition_blocked():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="bw",
        character_assets=[("char_a", "asset_a")],
        max_ref_images=3,
    )
    available_assets = {
        "char_a": {
            "character_ref": {"status": "approved", "asset_id": "asset_a"},
        },
        "panel_01": {
            "composition_ref": {"status": "approved", "asset_id": "bw_other"},
        },
    }
    result = select_workflow_for_panel(pack, available_assets=available_assets)
    assert result.selection_status == "blocked"
    assert result.workflow_mode == "r2v"


def test_incomplete_pack_blocked_not_t2va():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="bw",
        character_assets=[],
        max_ref_images=3,
    )
    result = select_workflow_for_panel(pack)
    assert result.selection_status == "blocked"
    assert result.workflow_mode == "r2v"
