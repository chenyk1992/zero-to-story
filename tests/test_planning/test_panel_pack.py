from lfo.planning.panel_pack import (
    DEFAULT_PURPOSE_COMPOSITION,
    PanelPackRef,
    build_panel_pack,
    panel_pack_from_dict,
    panel_pack_to_dict,
    trim_panel_pack,
    validate_panel_pack,
)


def test_build_min_two_refs():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="asset_bw_01",
        character_assets=[("char_a", "asset_char_a")],
        max_ref_images=3,
    )
    assert len(pack.refs) == 2
    assert pack.refs[-1].role == "composition"
    assert (
        DEFAULT_PURPOSE_COMPOSITION in pack.refs[-1].purpose
        or pack.refs[-1].purpose == DEFAULT_PURPOSE_COMPOSITION
    )
    assert validate_panel_pack(pack, max_ref_images=3) == []


def test_trim_to_three_keeps_composition_and_main_chars():
    composition = PanelPackRef(0, "composition", "bw", "panel_01", DEFAULT_PURPOSE_COMPOSITION)
    candidates = [
        PanelPackRef(0, "character", "c1", "char_1", "main"),
        PanelPackRef(0, "character", "c2", "char_2", "main"),
        PanelPackRef(0, "scene", "s1", "scene_1", "env"),
        PanelPackRef(0, "prop", "p1", "prop_1", "prop"),
    ]
    refs, reason = trim_panel_pack(candidates, composition=composition, max_ref_images=3)
    assert len(refs) == 3
    assert any(r.role == "composition" for r in refs)
    assert reason  # non-empty trim reason
    # slots renumbered 1..3
    assert [r.slot for r in refs] == [1, 2, 3]


def test_validate_rejects_missing_identity():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="asset_bw_01",
        character_assets=[],
        max_ref_images=3,
    )
    # builder may still create invalid pack if no chars — validate must catch
    errs = validate_panel_pack(pack, max_ref_images=3)
    assert any("identity" in e.lower() or "character" in e.lower() for e in errs)


def test_panel_pack_dict_roundtrip():
    pack = build_panel_pack(
        panel_id="panel_02",
        beat_range=(8, 15),
        bw_asset_id="asset_bw_02",
        character_assets=[("char_b", "asset_char_b")],
        max_ref_images=3,
    )
    restored = panel_pack_from_dict(panel_pack_to_dict(pack))
    assert restored.panel_id == pack.panel_id
    assert restored.beat_range == pack.beat_range
    assert restored.storyboard_bw_asset_id == pack.storyboard_bw_asset_id
    assert len(restored.refs) == len(pack.refs)
    assert validate_panel_pack(restored, max_ref_images=3) == []
