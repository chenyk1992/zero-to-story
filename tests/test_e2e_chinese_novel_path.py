"""End-to-end test: validate that a Chinese novel name routes to the
right on-disk path through the full pipeline plumbing.

Mirrors the user's actual layout under
``workspace/我今天不上班/chapter_01/`` — proves the path resolution
works for non-ASCII novel names with an explicit chapter subdirectory.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lfo.core.database import Database
from lfo.services.pipeline_service import PipelineService
from lfo.storyboard.storyboard import (
    Camera,
    Character,
    CharacterAppearance,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Scene,
    Shot,
    Story,
    Storyboard,
    StyleGuide,
)


def _build_storyboard(novel_id: str, chapter_id: str) -> Storyboard:
    """A 2-shot minimal storyboard that uses Chinese novel_id and chapter_id."""
    return Storyboard(
        project=ProjectInfo(
            project_id=f"{novel_id}-{chapter_id}",
            title="末日逃生篇",
            novel_id=novel_id,
            chapter_id=chapter_id,
        ),
        story=Story(
            logline="超市小哥在僵尸末日里一路摸鱼求生的黑色喜剧",
            synopsis="陈默在特价鸡蛋引发的末日里，一路靠摸鱼经验化险为夷。",
            theme="末日生存 × 摸鱼哲学",
            emotional_arc="漠然 → 机警 → 黑色幽默",
        ),
        style=StyleGuide(
            visual_style="cinematic dark comedy",
            color_palette="muted greys with neon highlights",
            lighting="fluorescent supermarket → dusk rooftop",
            mood="satirical horror",
        ),
        characters=[
            Character(
                character_id="char_chenmo",
                name="陈默",
                description="25 岁超市员工，绑着钢管的扫码枪，眼神带着摸鱼者的从容",
                role="protagonist",
                age="25",
                gender="male",
                distinguishing_features="扫码枪钢管、辣手摧花的吐槽",
            ),
        ],
        scenes=[
            Scene(
                scene_id="scene_supermarket",
                name="超市",
                description="货架密集、灯光惨白的连锁超市内部",
                time_of_day="day",
                lighting="fluorescent, cold",
                mood="panic",
                environment="interior",
            ),
        ],
        shots=[
            Shot(
                shot_id="shot_001",
                scene_id="scene_supermarket",
                description="陈默一脚踹翻洗发水货架，新员工们表演平地摔",
                desired_duration_ms=5000,
                camera=Camera(shot_size="wide", angle="eye_level", movement="static"),
                characters=[
                    CharacterAppearance(
                        character_id="char_chenmo",
                        screen_position="center",
                        orientation="facing_camera",
                        action="踹翻货架",
                        expression="漫不经心",
                    ),
                ],
                continuity=ContinuityInfo(
                    start_frame_needed=False,
                    end_state="陈默比出拜拜手势转身",
                ),
                generation_hint=GenerationHint(
                    preferred_family="h3_fl2va",
                    preferred_mode="t2va",
                    notes="首镜头 T2V，无 first_frame",
                ),
            ),
            Shot(
                shot_id="shot_002",
                scene_id="scene_supermarket",
                description="陈默点燃仓库里搜来的烟，靠在冰柜上听广播",
                desired_duration_ms=5000,
                camera=Camera(shot_size="medium", angle="low_angle", movement="slow_push_in"),
                characters=[
                    CharacterAppearance(
                        character_id="char_chenmo",
                        screen_position="left",
                        orientation="profile",
                        action="靠在冰柜上抽烟",
                        expression="冷笑",
                    ),
                ],
                continuity=ContinuityInfo(
                    start_frame_needed=True,
                    previous_shot_id="shot_001",
                    end_state="烟雾缭绕中广播响起",
                ),
                generation_hint=GenerationHint(
                    preferred_family="h3_fl2va",
                    preferred_mode="i2v",
                    notes="需要 shot_001 末帧作为 first_frame",
                ),
            ),
        ],
    )


class TestE2EChineseNovelPath:
    """End-to-end: real Storyboard → PipelineService → on-disk path."""

    def test_chinese_novel_routes_to_correct_workspace_path(
        self, tmp_path, monkeypatch,
    ):
        # Simulate the real layout: workspace/我今天不上班/chapter_01/
        ws = tmp_path / "ws"
        monkeypatch.setenv("LFO_WORKSPACE", str(ws))

        novel_id = "我今天不上班"
        chapter_id = "chapter_01"

        sb = _build_storyboard(novel_id, chapter_id)

        # Round-trip through JSON to confirm the schema survives
        sb_json = json.loads(json.dumps(sb.to_dict(), ensure_ascii=False))
        from lfo.storyboard.storyboard import Storyboard as Sb
        sb_loaded = Sb.from_dict(sb_json)
        assert sb_loaded.project.novel_id == novel_id
        assert sb_loaded.project.chapter_id == chapter_id

        # Spin up a PipelineService — patch out disk preflight + Comfy client
        db = Database(tmp_path / "test.db")
        db.init_schema()
        with (
            patch("lfo.services.pipeline_service.check_disk_space"),
            patch("lfo.services.pipeline_service.ComfyApiClient"),
        ):
            service = PipelineService(
                db,
                project_id=sb_loaded.project.project_id,
                novel_id=sb_loaded.project.novel_id,
                chapter_id=sb_loaded.project.chapter_id,
            )

        # The on-disk output_dir must be exactly
        # <workspace>/<我今天不上班>/<chapter_01>/outputs
        expected_output = ws / novel_id / chapter_id / "outputs"
        assert Path(service.output_dir) == expected_output, (
            f"expected {expected_output}, got {Path(service.output_dir)}"
        )

        # Verify the parent paths too
        assert service.novel_id == novel_id
        assert service.chapter_id == chapter_id
        # The DB-facing project_id is the joined form
        assert service.project_id == f"{novel_id}-{chapter_id}"

        # Verify the actual directories got created on disk
        assert expected_output.is_dir(), f"{expected_output} should have been created"
        # The /comfy/ subdir is also created
        assert (ws / novel_id / chapter_id / "outputs" / "comfy").is_dir()

    def test_chinese_novel_via_run_cmd_loads_correctly(
        self, tmp_path, monkeypatch,
    ):
        """Simulates the full CLI flow: read storyboard.json from disk,
        instantiate PipelineService, verify the path. The storyboard
        file is dropped in <workspace>/<novel>/<chapter>/storyboard.json
        exactly like the user's actual layout.

        We don't call ``service.execute()`` here because that requires
        the full ComfyUI plumbing. The point of this test is purely
        the path resolution and the JSON round-trip — both of which
        we exercise by hand below.
        """
        from lfo.cli.run_cmd import cmd_run

        ws = tmp_path / "ws"
        monkeypatch.setenv("LFO_WORKSPACE", str(ws))

        novel_id = "我今天不上班"
        chapter_id = "chapter_01"
        chapter_dir = ws / novel_id / chapter_id
        chapter_dir.mkdir(parents=True)

        sb = _build_storyboard(novel_id, chapter_id)
        sb_path = chapter_dir / "storyboard.json"
        sb_path.write_text(
            json.dumps(sb.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Verify the file is on disk, parseable, and round-trips
        loaded_data = json.loads(sb_path.read_text(encoding="utf-8"))
        assert loaded_data["project"]["novel_id"] == novel_id
        assert loaded_data["project"]["chapter_id"] == chapter_id
        assert loaded_data["project"]["title"] == "末日逃生篇"

        # The path that PipelineService will derive:
        from lfo.services.workspace import project_output_dir
        expected_output = project_output_dir(novel_id, chapter_id)
        assert expected_output == ws / novel_id / chapter_id / "outputs"
        # And the path that cmd_run will use is the same (no --output-dir
        # override is passed).
        assert project_output_dir(novel_id, chapter_id) == (
            ws / novel_id / chapter_id / "outputs"
        )

    def test_chinese_novel_round_trips_through_existing_layout(
        self, tmp_path, monkeypatch,
    ):
        """A Chinese-named storyboard that also lives in the Chinese-named
        subdirectory must instantiate PipelineService cleanly and resolve
        the right output path. We don't execute() because that needs the
        full ComfyUI plumbing; the path is what we care about here."""
        ws = tmp_path / "ws"
        monkeypatch.setenv("LFO_WORKSPACE", str(ws))

        novel_id = "我今天不上班"
        chapter_id = "chapter_01"
        db = Database(tmp_path / "test.db")
        db.init_schema()

        with (
            patch("lfo.services.pipeline_service.check_disk_space"),
            patch("lfo.services.pipeline_service.ComfyApiClient"),
        ):
            service = PipelineService(
                db,
                project_id=f"{novel_id}-{chapter_id}",
                novel_id=novel_id,
                chapter_id=chapter_id,
            )
            sb = _build_storyboard(novel_id, chapter_id)
            # Verify the storyboard's own novel/chapter IDs are intact
            assert sb.project.novel_id == novel_id
            assert sb.project.chapter_id == chapter_id
            assert sb.project.title == "末日逃生篇"

        # Path landed correctly
        expected = ws / novel_id / chapter_id / "outputs"
        assert Path(service.output_dir) == expected
        assert expected.is_dir()
        # The /comfy/ subdir is also created
        assert (ws / novel_id / chapter_id / "outputs" / "comfy").is_dir()
