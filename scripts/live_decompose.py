"""Live decompose: feed a Chinese story synopsis into the real LLM via mmx
and print the resulting storyboard.

Usage:
    python scripts/live_decompose.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src/ is on path (src layout)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lfo.storyboard import (
    AudioPolicy,
    Character,
    DecomposeError,
    Intake,
    IntakeConstraints,
    InputSourceType,
    MmxLLMClient,
    ProjectInfo,
    Scene,
    Story,
    StoryboardDecomposer,
    StyleGuide,
)
from lfo.storyboard.decompose import _render_prompt as _render_decompose_prompt
from lfo.storyboard.style_brief import build_medium_lock, build_style_keywords


NOVEL_ID = "我今天不上班"
CHAPTER_ID = "chapter_01"
WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"
NOVEL_DIR = WORKSPACE / NOVEL_ID / CHAPTER_ID

# Logline + synopsis for the model
LOGLINE = "特价鸡蛋引发的血案——超市小哥陈默在僵尸末日里靠三年摸鱼经验化险为夷"
SYNOPSIS = (
    "早上八点超市刚开门，纠缠生产日期的花衬衫大爷突然发狂咬人，僵尸末日爆发。"
    "陈默凭摸鱼经验一脚踹翻洗发水货架让新员工丧尸表演平地摔，转身钻进仓库。"
    "他靠在冰柜上抽烟，听到广播宣布病毒爆发。"
    "他精准地把烟头弹进工业酒精桶纵火阻挡丧尸，踢开天窗爬上超市屋顶。"
    "远处高级公寓顶楼，穿制服的雷子正用望远镜看他。"
    "陈默骂了句脏话，跳进隔壁写字楼，末日逃生正式开始。"
)


def build_intake() -> Intake:
    intake = Intake(
        project_id=f"{NOVEL_ID}-{CHAPTER_ID}",
        constraints=IntakeConstraints(
            target_duration_ms=30000,  # 30s total
            aspect_ratio="9:16",
            delivery_width=1080,
            delivery_height=1920,
            language="zh-CN",
            visual_style="cinematic dark comedy",
            max_characters=1,  # 聚焦陈默
            max_scenes=3,  # 超市/仓库/屋顶
            pacing="fast",
            mood="satirical horror comedy",
            audio_policy="effects_only",
        ),
    )
    intake.add_source(
        source_type=InputSourceType.STORY_SYNOPSIS,
        content=SYNOPSIS,
    )
    return intake


def build_decomposer(llm: MmxLLMClient) -> StoryboardDecomposer:
    visual_style = "anime style, cinematic dark comedy, clean line art, high contrast"
    medium_lock = build_medium_lock(visual_style)
    style_keywords = build_style_keywords(visual_style)

    project = ProjectInfo(
        project_id=f"{NOVEL_ID}-{CHAPTER_ID}",
        title="特价鸡蛋引发的血案",
        novel_id=NOVEL_ID,
        chapter_id=CHAPTER_ID,
    )
    story = Story(
        logline=LOGLINE,
        synopsis=SYNOPSIS,
        theme="末日生存 × 摸鱼哲学",
        emotional_arc="漠然 → 机警 → 黑色幽默",
    )
    style = StyleGuide(
        visual_style=visual_style,
        color_palette="冷白荧光 + 暖橙火焰",
        lighting="超市内冷光荧光 → 黄昏屋顶暖光",
        mood="satirical horror comedy",
        reference_films=["僵尸世界大战", "死侍"],
        medium_lock=medium_lock,
        style_keywords=style_keywords,
    )
    characters = [
        Character(
            character_id="char_chenmo",
            name="陈默",
            description="25 岁中国男性超市员工，蓝色制服，短发凌乱，眼神带着摸鱼者的从容，腰间绑着钢管的扫码枪",
            role="protagonist",
            age="25",
            gender="male",
            distinguishing_features="扫码枪钢管、漫不经心的吐槽、冷笑",
            signature_action="靠货架抽烟，嘴角挂冷笑",
            key_prop="绑钢管的扫码枪",
        ),
    ]
    scenes = [
        Scene(
            scene_id="scene_supermarket",
            name="超市",
            description="货架密集、灯光惨白的连锁超市内部，地上有滑腻的洗发水障碍",
            time_of_day="day",
            lighting="fluorescent, cold",
            mood="panic with dark humor",
            environment="interior",
        ),
        Scene(
            scene_id="scene_warehouse",
            name="仓库",
            description="超市后仓，堆满工业酒精桶和备用货架",
            time_of_day="day",
            lighting="dim fluorescent with cigarette glow",
            mood="tense calm",
            environment="interior",
        ),
        Scene(
            scene_id="scene_rooftop",
            name="屋顶",
            description="超市屋顶平台，远处是燃烧中的城市天际线",
            time_of_day="dusk",
            lighting="warm golden hour against orange flames",
            mood="apocalyptic",
            environment="exterior",
        ),
    ]
    audio_policy = AudioPolicy(
        mode="effects_only",
        music="none",
        sound_effects="auto",
        dialogue="none",
        ambient="auto",
    )
    return StoryboardDecomposer(
        llm=llm,
        project=project,
        story=story,
        style=style,
        characters=characters,
        scenes=scenes,
        audio_policy=audio_policy,
    )


def main() -> int:
    print("=" * 60)
    print("Live StoryboardDecomposer test")
    print("=" * 60)
    print(f"Novel: {NOVEL_ID}")
    print(f"Chapter: {CHAPTER_ID}")
    print(f"Synopsis length: {len(SYNOPSIS)} chars")
    print()
    print("Calling mmx → LLM...")
    print("This will take 30-90 seconds depending on model size.")
    print()

    llm = MmxLLMClient(
        model="MiniMax-M3",
        max_tokens=16384,
        temperature=0.4,
        timeout_sec=300,
    )
    decomposer = build_decomposer(llm)
    intake = build_intake()

    try:
        sb = decomposer.decompose(intake, logline=LOGLINE)
    except DecomposeError as exc:
        # Save raw LLM output for debugging — re-run the LLM call manually
        sys_prompt, user_prompt = _render_decompose_prompt(
            intake=intake,
            project=decomposer.project,
            story=decomposer.story,
            style=decomposer.style,
            characters=decomposer.characters,
            scenes=decomposer.scenes,
            logline=LOGLINE,
        )
        raw_path = NOVEL_DIR / "decompose.raw.txt"
        try:
            raw = llm.complete(sys_prompt, user_prompt)
            raw_path.write_text(
                f"[FAILED on first call] {exc}\n\n--- RAW LLM OUTPUT ---\n{raw}\n--- (len={len(raw)}) ---",
                encoding="utf-8",
            )
            print(f"\nFAILURE: DecomposeError: {exc}")
            print(f"  Raw LLM output saved to: {raw_path} (len={len(raw)})")
        except Exception as exc2:
            raw_path.write_text(
                f"[FAILED on first call] {exc}\n[Re-call failed: {exc2}]",
                encoding="utf-8",
            )
            print(f"\nFAILURE: DecomposeError: {exc}")
            print(f"  (Re-call also failed: {exc2})")
            print(f"  See: {raw_path}")
        return 1
    except Exception as exc:
        print(f"\nUNEXPECTED ERROR: {type(exc).__name__}: {exc}")
        raise

    # Summary
    print()
    print("=" * 60)
    print(f"DECOMPOSE RESULT: {len(sb.shots)} shots, {len(sb.scenes)} scenes, {len(sb.props)} props")
    print(f"Medium Lock: {sb.style.medium_lock[:60]}...")
    print(f"Style Keywords: {sb.style.style_keywords}")
    print("=" * 60)

    for i, shot in enumerate(sb.shots, 1):
        cont = shot.continuity
        hint = shot.generation_hint
        prev = cont.previous_shot_id or "(none)"
        sfn = "I2V" if cont.start_frame_needed else "T2V"
        print(f"\n  Shot {i}: {shot.shot_id} [{sfn}]")
        print(f"    Scene:      {shot.scene_id}")
        print(f"    Camera:     {shot.camera.shot_size} / {shot.camera.angle} / {shot.camera.movement}")
        print(f"    Duration:   {shot.desired_duration_ms} ms")
        print(f"    Prev → Nxt: {prev} → {cont.next_shot_id or '(none)'}")
        print(f"    Mode:       {hint.preferred_mode} ({hint.notes})")
        if shot.characters:
            for c in shot.characters:
                print(f"    Character:  {c.character_id} ({c.screen_position}, {c.action})")
        print(f"    Description: {shot.description[:80]}...")
        if shot.action_beats:
            for beat in shot.action_beats:
                print(f"      Beat {beat.sequence} ({beat.duration_ms}ms): {beat.description}")

    total_ms = sb.total_duration_ms()
    target_ms = intake.constraints.target_duration_ms
    print(f"\nTotal duration: {total_ms} ms (target: {target_ms} ms)")

    # Persist
    out_path = NOVEL_DIR / "storyboard.decomposed.json"
    out_path.write_text(
        json.dumps(sb.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
