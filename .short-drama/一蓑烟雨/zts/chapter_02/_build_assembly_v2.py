from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lfo.contracts.builder import VideoPackageBuilder


PROJECT_ID = "yisuo-ep002-codex-director"
PANEL_ORDER = [f"P{i:03d}" for i in range(1, 13)]

SUBTITLE_CUES: dict[str, list[tuple[int, int, str]]] = {
    "P001": [(0, 3000, "范滂，字孟博。登车揽辔，慨然有澄清天下之志……")],
    "P002": [
        (0, 5000, "党锢祸起，诏书急捕范滂。滂辞别老母——他说："),
        (5000, 9000, "滂归黄泉，存亡各得其所。"),
        (9000, 15000, "惟愿母亲割舍不忍之心，勿增悲戚。"),
    ],
    "P003": [
        (0, 3200, "他的母亲回答：你今日得以与李膺、杜密齐名，死了又有什么遗憾！"),
        (3200, 10000, "既想要美名，又想要长寿，天下哪有两全的事。"),
    ],
    "P004": [
        (0, 5600, "娘。孩儿若长大做了范滂，母亲答应吗？"),
        (5600, 10500, "你能做范滂，我就不能做范滂的母亲吗？"),
        (10500, 14000, "都记住——世上可以没有官。不可以没有人讲真话。"),
    ],
    "P005": [
        (3800, 5600, "哥，《六国论》背到‘较秦之所得’——下一句。"),
        (5600, 8500, "与战胜而得者，其实百倍。"),
    ],
    "P006": [
        (0, 2600, "爹说你文气纵横，就是坐不住。"),
        (2600, 6500, "坐着写出来的文章是死的。我得走着写。"),
        (8000, 11000, "……他永远是最亮的那一个。"),
    ],
    "P007": [(7000, 10000, "别抹。写的什么？")],
    "P008": [
        (0, 4200, "天……地。先生说，饭管一天，字管一辈子。"),
        (4200, 7000, "明天起，活计做完了，搬个小凳坐到堂下去听。"),
        (7000, 9000, "夫人……让我听课？"),
    ],
    "P009": [
        (3000, 6200, "字如其人。"),
        (6200, 10000, "灰会散——你写下来的，不会。"),
    ],
    "P010": [
        (3000, 5000, "行啊。照这个进度，明年你就能给我挑错了。"),
        (5000, 6800, "借我十个胆子也不敢——"),
    ],
    "P011": [
        (0, 7800, "少爷！少爷！青神王方王贡士家遣了媒人，正候在堂上——说是为他家小姐提亲！"),
        (7800, 11300, "王小姐？哪个王小姐？就是听说琴棋书画样样——"),
    ],
    "P012": [(0, 4000, "书还没教完呢，先生这魂儿，先被人勾走了。")],
}


def _duration_ms(path: Path) -> int:
    value = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return max(1, round(float(value) * 1000))


def build(root: Path, revision: int = 1) -> Path:
    project_root = root / "workspace" / "projects" / PROJECT_ID
    state_path = project_root / "chapter2-v2-generation-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    records = {str(item["panel"]): item for item in state.get("panels", [])}
    missing = [panel for panel in PANEL_ORDER if panel not in records]
    if missing:
        raise ValueError(f"Cannot assemble before all panels are accepted: {missing}")

    package = VideoPackageBuilder(
        f"yisuo-ep002-v2-assembly-r{revision:03d}",
        "一蓑烟雨 · 第二章 · 最新创作预检版 · Final Assembly",
        revision=revision,
        locale="zh-CN",
        project_id=PROJECT_ID,
    )
    segments: list[dict[str, int | str]] = []
    for sequence, panel in enumerate(PANEL_ORDER, 1):
        record: dict[str, Any] = records[panel]
        source = Path(str(record["mixed_path"]))
        if not source.exists():
            raise FileNotFoundError(source)
        uri = source.relative_to(project_root).as_posix()
        asset_key = f"source_video.{panel.lower()}"
        duration_ms = _duration_ms(source)
        package.add_asset(
            asset_key=asset_key,
            media_type="video",
            uri=uri,
            producer="lfo",
            operation="video.accepted.mixed",
            source_type="derived_media",
            review_required=True,
            metadata={
                "panel": panel,
                "run_id": record["run_id"],
                "tail_lock": record["tail_path"],
                "qc_basis": "lfo_technical_qc_after_creative_preflight",
            },
        )
        cues = [
            {"start_ms": start, "end_ms": end, "text": text}
            for start, end, text in SUBTITLE_CUES.get(panel, [])
            if start < duration_ms
        ]
        package.add_clip(
            clip_id=f"panel-{sequence:03d}",
            sequence=sequence,
            duration_ms=duration_ms,
            operation="video.passthrough",
            prompt=f"Pass through accepted latest-preflight clip {panel}",
            requirements={
                "aspect_ratio": "9:16",
                "megapixels": 0.4,
                "fps": 24,
                "native_audio": "allowed",
            },
            references=[
                {
                    "reference_id": "source-video",
                    "asset_key": asset_key,
                    "semantic_usage": "source.accepted_video",
                    "binding": {
                        "required": True,
                        "priority": 100,
                        "placement": "fixed",
                        "slot": "source_video",
                        "on_unsupported": "fail",
                    },
                }
            ],
            audio={"native_audio": "preserve"},
            subtitles={"cues": cues},
            source_context={
                "creative_skill": "zero-to-story",
                "prompt_skill": "h3-prompt-writing",
                "creative_unit": "final_assembly",
                "panel": panel,
                "source_run_id": record["run_id"],
                "source_path": uri,
                "creative_blueprint": ".short-drama/一蓑烟雨/zts/chapter_02/creative_blueprint.json",
                "continuity_policy": "real_tail_locked_generation_chain",
            },
        )
        segments.append({"clip_id": f"panel-{sequence:03d}", "source_in_ms": 0})

    package.timeline(segments=segments)
    package.output(
        container="mp4",
        video_encoder="h264",
        audio_encoder="aac",
        width=1080,
        height=1920,
        fps=24,
        sample_rate=48000,
        loudness_db="-16",
        transitions="cut",
        subtitles_mode="both",
        directory="yisuo-ep002-v2-final",
    )
    package.approval(
        approved_by="user",
        approved_at="2026-08-30T00:00:00+08:00",
        notes=(
            "Final assembly follows a creative-blueprint-first Chapter 2 rerun. All 12 panels passed the "
            "LFO per-clip generation/audio/QC chain; same-scene panels were generated from the real accepted "
            "previous tail frame, and hard scene changes were regenerated with approved identity and storyboard "
            "references. Timeline is cut-only, subtitles are deterministic, and audio targets -16 LUFS."
        ),
    )
    destination = project_root / f"assembly-package-v2-r{revision:03d}.json"
    return package.write(destination)


def main() -> int:
    root = Path(__file__).resolve().parents[4]
    destination = build(root)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
