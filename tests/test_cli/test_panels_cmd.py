"""Tests for lfo panels plan/pack/prompt CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.cli.panels_cmd import cmd_panels_pack, cmd_panels_plan, cmd_panels_prompt
from lfo.planning.panel_pack import panel_pack_from_dict
from lfo.services.workspace import project_panels_dir


def make_panel_storyboard(tmp_path: Path) -> Path:
    """Minimal storyboard with beats, panels, and fake asset ids."""
    data = {
        "project": {
            "project_id": "test-novel-chapter_01",
            "title": "Panels CLI Test",
            "novel_id": "test-novel",
            "chapter_id": "chapter_01",
        },
        "style": {"medium_lock": "Medium: 3D test. NOT 2D anime."},
        "characters": [
            {
                "character_id": "char_hero",
                "name": "林野",
                "ref_asset_id": "asset_char_hero",
            },
        ],
        "beats": [
            {
                "beat_id": "beat_001",
                "sequence": 1,
                "scene_id": "scene_001",
                "description": "林野站在巷口。",
                "sound": "脚步声和车流",
                "characters": [{"character_id": "char_hero"}],
            },
            {
                "beat_id": "beat_002",
                "sequence": 2,
                "scene_id": "scene_001",
                "description": "他低头看手机。",
                "sound": "手机震动",
                "characters": [{"character_id": "char_hero"}],
            },
        ],
        "panels": [
            {
                "panel_id": "panel_001",
                "sequence": 1,
                "beat_range": [1, 2],
                "beat_ids": ["beat_001", "beat_002"],
                "desired_duration_ms": 15_000,
                "bw_asset_id": "asset_bw_001",
            },
        ],
    }
    sb_path = tmp_path / "storyboard.json"
    sb_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return sb_path


class TestCmdPanelsPlan:
    def test_empty_storyboard_path(self):
        result = cmd_panels_plan(storyboard_path="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_file_not_found(self, tmp_path):
        result = cmd_panels_plan(storyboard_path=str(tmp_path / "missing.json"))
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_plan_counts_and_ranges(self, tmp_path):
        sb_path = make_panel_storyboard(tmp_path)
        result = cmd_panels_plan(storyboard_path=str(sb_path))
        assert result["success"] is True
        assert result["beat_count"] == 2
        assert result["panel_count"] == 1
        assert result["panels"][0]["panel_id"] == "panel_001"
        assert result["panels"][0]["beat_range"] == [1, 2]


class TestCmdPanelsPack:
    def test_writes_panel_pack_json(self, tmp_path, monkeypatch):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("LFO_WORKSPACE", str(workspace))

        sb_path = make_panel_storyboard(tmp_path)
        result = cmd_panels_pack(storyboard_path=str(sb_path), max_ref_images=3)
        assert result["success"] is True
        assert result["written_count"] == 1

        panels_dir = project_panels_dir("test-novel", "chapter_01")
        pack_path = panels_dir / "panel_01_pack.json"
        assert pack_path.exists()

        pack = panel_pack_from_dict(json.loads(pack_path.read_text(encoding="utf-8")))
        assert pack.panel_id == "panel_001"
        assert pack.storyboard_bw_asset_id == "asset_bw_001"
        assert any(ref.role == "character" for ref in pack.refs)
        assert any(ref.role == "composition" for ref in pack.refs)

    def test_max_ref_images_option(self, tmp_path, monkeypatch):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("LFO_WORKSPACE", str(workspace))

        sb_path = make_panel_storyboard(tmp_path)
        result = cmd_panels_pack(
            storyboard_path=str(sb_path),
            max_ref_images=3,
        )
        assert result["success"] is True
        assert result["max_ref_images"] == 3


class TestCmdPanelsPrompt:
    def test_writes_video_prompt_list(self, tmp_path, monkeypatch):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("LFO_WORKSPACE", str(workspace))

        sb_path = make_panel_storyboard(tmp_path)
        pack_result = cmd_panels_pack(storyboard_path=str(sb_path))
        assert pack_result["success"] is True

        prompt_result = cmd_panels_prompt(storyboard_path=str(sb_path))
        assert prompt_result["success"] is True
        assert prompt_result["panel_count"] == 1

        prompt_path = Path(prompt_result["prompt_path"])
        assert prompt_path.name == "video_prompt_list.md"
        assert prompt_path.exists()

        content = prompt_path.read_text(encoding="utf-8")
        assert "## Panel 1" in content
        assert "图片1" in content
        assert "不要背景音乐" in content
        assert "Medium: 3D test" in content

    def test_prompt_reads_edited_pack_from_disk(self, tmp_path, monkeypatch):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("LFO_WORKSPACE", str(workspace))

        sb_path = make_panel_storyboard(tmp_path)
        cmd_panels_pack(storyboard_path=str(sb_path))

        panels_dir = project_panels_dir("test-novel", "chapter_01")
        pack_path = panels_dir / "panel_01_pack.json"
        pack_data = json.loads(pack_path.read_text(encoding="utf-8"))
        pack_data["refs"][0]["purpose"] = "自定义角色用途标记"
        pack_path.write_text(json.dumps(pack_data, ensure_ascii=False), encoding="utf-8")

        prompt_result = cmd_panels_prompt(storyboard_path=str(sb_path))
        assert prompt_result["success"] is True
        content = Path(prompt_result["prompt_path"]).read_text(encoding="utf-8")
        assert "自定义角色用途标记" in content
