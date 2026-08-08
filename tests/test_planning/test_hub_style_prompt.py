from lfo.planning.panel_pack import (
    DEFAULT_PURPOSE_CHARACTER,
    DEFAULT_PURPOSE_COMPOSITION,
    PanelPack,
    PanelPackRef,
)
from lfo.planning.hub_style_prompt import compile_hub_style_panel_prompt


def test_hub_style_order_and_picture_bindings():
    pack = PanelPack(
        panel_id="panel_02",
        beat_range=(8, 15),
        storyboard_bw_asset_id="bw2",
        refs=[
            PanelPackRef(1, "character", "a1", "char_linye", DEFAULT_PURPOSE_CHARACTER),
            PanelPackRef(2, "character", "a2", "char_zhao", "仅作为前段人物连续性参考。"),
            PanelPackRef(3, "composition", "bw2", "panel_02", DEFAULT_PURPOSE_COMPOSITION),
        ],
        characters_in_panel=["char_linye", "char_zhao"],
        trim_reason=None,
    )
    text = compile_hub_style_panel_prompt(
        pack=pack,
        opening="林野在画面左侧提着外卖箱、刚刚站稳。",
        action_chain="林野短暂停留在手机上的欠款与订单抽象光块前，随后平稳转入高架桥下旧巷。",
        sound_design="车流和市井声逐渐抽空，只留下脚步、手机震动；不要背景音乐。",
        medium_lock="Medium: 3D rendered suspense, real urban space. NOT 2D anime cel-shading.",
        quality_negatives="避免身份漂移、时间闪烁、错误文字。",
    )
    action = "林野短暂停留在手机上的欠款与订单抽象光块前，随后平稳转入高架桥下旧巷。"
    sound = "车流和市井声逐渐抽空，只留下脚步、手机震动；不要背景音乐。"
    medium = "Medium: 3D rendered suspense, real urban space. NOT 2D anime cel-shading."
    negatives = "避免身份漂移、时间闪烁、错误文字。"

    assert text.index("林野在画面左侧") < text.index("图片1")
    assert "图片1" in text and "图片2" in text and "图片3" in text
    assert DEFAULT_PURPOSE_COMPOSITION in text
    assert "不要背景音乐" in text
    assert medium in text
    assert negatives in text
    assert text.index("图片3") < text.index(action)
    assert text.index(action) < text.index(sound)
    assert text.index(sound) < text.index(medium)
    assert text.index(medium) < text.index(negatives)


def test_hub_style_auto_injects_no_bgm():
    pack = PanelPack(
        panel_id="panel_01",
        beat_range=(0, 7),
        storyboard_bw_asset_id="bw1",
        refs=[
            PanelPackRef(1, "character", "a1", "char_linye", DEFAULT_PURPOSE_CHARACTER),
        ],
        characters_in_panel=["char_linye"],
        trim_reason=None,
    )
    text = compile_hub_style_panel_prompt(
        pack=pack,
        opening="开场。",
        action_chain="动作链。",
        sound_design="只有脚步声和风声",
        medium_lock="Medium: test.",
        quality_negatives="",
    )
    assert "不要背景音乐" in text
    assert text.index("动作链。") < text.index("不要背景音乐")
