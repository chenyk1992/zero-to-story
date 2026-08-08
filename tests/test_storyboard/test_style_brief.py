"""Tests for style_brief — Medium Lock generation."""
from __future__ import annotations

import pytest

from lfo.storyboard.style_brief import (
    DEFAULT_MEDIUM_LOCK,
    MEDIUM_LOCK_TEMPLATES,
    build_medium_lock,
    build_style_keywords,
)


class TestBuildMediumLock:
    """build_medium_lock() returns appropriate Medium Lock statements."""

    def test_user_override_wins(self):
        """Explicit user override always wins."""
        result = build_medium_lock("anime", user_override="Medium: custom lock.")
        assert result == "Medium: custom lock."

    def test_user_override_wins_even_with_empty_style(self):
        result = build_medium_lock("", user_override="Medium: custom.")
        assert result == "Medium: custom."

    def test_empty_style_returns_empty(self):
        """No style info → no lock."""
        assert build_medium_lock("") == ""

    def test_anime_match(self):
        result = build_medium_lock("2d_anime")
        assert "2D hand-drawn animation" in result
        assert "NOT 3D render" in result

    def test_3d_match(self):
        result = build_medium_lock("3d_render")
        assert "3D rendered scene" in result
        assert "NOT 2D anime" in result

    def test_cyberpunk_match(self):
        result = build_medium_lock("cyberpunk realistic")
        assert "cyberpunk" in result.lower()
        assert "NOT anime" in result

    def test_ghibli_match(self):
        result = build_medium_lock("ghibli style")
        assert "Ghibli" in result

    def test_realistic_match(self):
        result = build_medium_lock("photorealistic")
        assert "Photorealistic" in result

    def test_watercolor_match(self):
        result = build_medium_lock("watercolor painting")
        assert "Watercolor" in result

    def test_no_match_fallback(self):
        """Unknown style → default fallback lock."""
        result = build_medium_lock("xyz_unknown_style")
        assert result == DEFAULT_MEDIUM_LOCK

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        result = build_medium_lock("ANIME")
        assert "2D hand-drawn animation" in result

    def test_all_templates_start_with_medium(self):
        """Every template must start with 'Medium:' for consistency."""
        for _keyword, lock in MEDIUM_LOCK_TEMPLATES:
            assert lock.startswith("Medium:"), f"Template doesn't start with 'Medium:': {lock}"

    def test_all_templates_contain_not(self):
        """Every template must contain at least one NOT exclusion."""
        for _keyword, lock in MEDIUM_LOCK_TEMPLATES:
            assert "NOT" in lock, f"Template missing NOT exclusion: {lock}"


class TestBuildStyleKeywords:
    """build_style_keywords() extracts keywords from visual_style strings."""

    def test_empty(self):
        assert build_style_keywords("") == []

    def test_simple_comma(self):
        result = build_style_keywords("cinematic, neon-lit, rain-soaked")
        assert result == ["cinematic", "neon-lit", "rain-soaked"]

    def test_chinese_comma(self):
        result = build_style_keywords("电影感，霓虹灯，雨夜")
        assert result == ["电影感", "霓虹灯", "雨夜"]

    def test_spaces(self):
        result = build_style_keywords("cinematic neon-lit rain-soaked")
        assert result == ["cinematic", "neon-lit", "rain-soaked"]

    def test_mixed_separators(self):
        result = build_style_keywords("cinematic, neon-lit、rain-soaked")
        assert "cinematic" in result
        assert "neon-lit" in result

    def test_filters_english_stopwords(self):
        """Common English stopwords should be filtered out."""
        result = build_style_keywords("anime style, cinematic, clean line art, high contrast")
        # "style" and "high" are stopwords; meaningful keywords remain
        assert "style" not in result
        assert "high" not in result
        assert "anime" in result
        assert "cinematic" in result
        assert "clean" in result
        assert "line" in result
        assert "art" in result
        assert "contrast" in result

    def test_filters_chinese_stopwords(self):
        """Common Chinese stopwords (了 的 是) should be filtered out."""
        # Chinese commas split — "的" should still be filtered as a standalone
        result = build_style_keywords("电影感，的，霓虹灯，是，光")
        assert "的" not in result
        assert "是" not in result
        assert "电影感" in result
        assert "霓虹灯" in result
        assert "光" in result

    def test_dedupes_preserving_order(self):
        """Duplicate keywords should be removed, first occurrence kept."""
        result = build_style_keywords("anime, anime, cinematic, anime")
        assert result.count("anime") == 1
        assert result[0] == "anime"
        assert result[1] == "cinematic"
