from __future__ import annotations

import pytest


def test_ass_preserves_chinese_multiline_and_escapes_control_syntax():
    from lfo.media.mv_subtitles import render_ass

    ass = render_ass([{"start_ms": 100, "end_ms": 1500, "text": "雨{停}\\了\n好！", "kind": "lyric", "status": "verified"}], width=1080, height=1920)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "雨\\{停\\}\\了\\N好！" in ass
    assert "Style: Lyric" in ass


def test_ass_rejects_unverified_lyrics_and_supports_explicit_fade():
    from lfo.media.mv_subtitles import render_ass

    with pytest.raises(ValueError, match="核对"):
        render_ass([{"start_ms": 0, "end_ms": 900, "text": "待校对", "kind": "lyric", "status": "candidate"}], width=1920, height=1080)
    ass = render_ass([{"start_ms": 0, "end_ms": 900, "text": "归来", "kind": "visual", "effect": "fade"}], width=1920, height=1080)
    assert "{\\fad(" in ass
    assert "PlayResX: 1920" in ass and "MarginV" in ass


def test_short_scale_event_keeps_effect_inside_its_duration():
    from lfo.media.mv_subtitles import render_ass

    ass = render_ass([{"start_ms": 0, "end_ms": 120, "text": "啊", "kind": "visual", "effect": "scale"}], width=1080, height=1080)
    assert "\\t(0,120," in ass
