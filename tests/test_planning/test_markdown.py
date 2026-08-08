"""Tests for rendering.markdown shared utilities."""
from lfo.rendering.markdown import (
    md_blockquote,
    md_code_block,
    md_error,
    md_heading,
    md_json_pointer,
    md_success,
    md_table,
    md_task_id,
    md_warning,
)


class TestMdHeading:
    def test_level_1(self):
        assert md_heading("Title") == "# Title"

    def test_level_2(self):
        assert md_heading("Section", level=2) == "## Section"

    def test_level_6_clamped(self):
        assert md_heading("Deep", level=6) == "###### Deep"

    def test_clamp_below_1(self):
        assert md_heading("Shallow", level=0) == "# Shallow"

    def test_clamp_above_6(self):
        assert md_heading("Too deep", level=10) == "###### Too deep"


class TestMdTable:
    def test_basic(self):
        result = md_table(["Name", "Age"], [["Alice", "30"], ["Bob", "25"]])
        lines = result.split("\n")
        assert lines[0] == "| Name | Age |"
        assert lines[1] == "| --- | --- |"
        assert lines[2] == "| Alice | 30 |"
        assert lines[3] == "| Bob | 25 |"

    def test_empty_headers(self):
        assert md_table([], []) == "*(no columns)*"

    def test_row_padding(self):
        result = md_table(["A", "B", "C"], [["only_one"]])
        assert "| only_one |  |  |" in result

    def test_row_truncation(self):
        result = md_table(["A", "B"], [["1", "2", "3"]])
        assert "| 1 | 2 |" in result

    def test_empty_rows(self):
        result = md_table(["X"], [])
        assert "| X |" in result
        assert "| --- |" in result


class TestMdCodeBlock:
    def test_with_language(self):
        result = md_code_block("print('hi')", language="python")
        assert result == "```python\nprint('hi')\n```"

    def test_without_language(self):
        result = md_code_block("raw text")
        assert result == "```\nraw text\n```"

    def test_empty_content(self):
        result = md_code_block("")
        assert result == "```\n\n```"


class TestMdBlockquote:
    def test_single_line(self):
        assert md_blockquote("Hello") == "> Hello"

    def test_multi_line(self):
        result = md_blockquote("Line 1\nLine 2")
        assert result == "> Line 1\n> Line 2"

    def test_empty_lines(self):
        result = md_blockquote("Before\n\nAfter")
        assert "> Before" in result
        assert ">" in result.split("\n")[1]


class TestMdSemantic:
    def test_warning(self):
        assert md_warning("be careful") == "> ⚠️ **Warning:** be careful"

    def test_success(self):
        assert md_success("done") == "> ✅ done"

    def test_error(self):
        assert md_error("failed") == "> ❌ failed"


class TestMdJsonPointer:
    def test_with_slash(self):
        assert md_json_pointer("/shots/0") == "`/shots/0`"

    def test_without_slash(self):
        assert md_json_pointer("shots/0") == "`/shots/0`"

    def test_empty(self):
        assert md_json_pointer("") == "`/`"


class TestMdTaskId:
    def test_format(self):
        assert md_task_id("task_video_shot_003") == "`task_video_shot_003`"
