from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

from lfo.contracts.builder import VideoPackageBuilder

PROJECT_ID = "yisuo-ep001-codex-director"
PANEL_ORDER = [f"P{i:03d}" for i in range(1, 13)]

# Director-approved first usable frames after paired boundary review.  Values
# come from the generated media's actual scene cuts, not planned prompt times.
SOURCE_IN_MS = {
    "P002": 3771,
    "P003": 2771,
    "P005": 2729,
    "P011": 3729,
}

# Cues are intentionally authored in local clip time. LFO retimes them to the
# assembled timeline and emits the same cues in the global SRT sidecar.
SUBTITLE_CUES: dict[str, list[tuple[int, int, str]]] = {
    "P002": [(4500, 9800, "苏学士在任三年，修堤赈粮，他没有罪啊")],
    "P003": [
        (4000, 6500, "他到底犯了什么罪？！"),
        (6600, 9700, "你们说他到底犯了什么罪！"),
        (11400, 13000, "写诗。"),
    ],
    "P005": [(9000, 12000, "先生——！")],
    "P007": [(150, 1800, "二十三年前 · 北宋 · 眉山")],
    "P008": [
        (5000, 7200, "喂，偷听的。方才那句，你再念念？"),
        (7800, 9500, "小人没偷！我就是……路过！"),
        (10600, 12200, "路过还带着嘴？"),
    ],
    "P009": [
        (1400, 2600, "哪家的？"),
        (2800, 6500, "……没有哪家。爹娘走得早，给镇上各家打杂换饭吃。"),
        (8300, 10700, "我考考你。方才那篇，你听了多久？"),
        (10900, 13000, "……先生晌午才开始念。"),
    ],
    "P010": [
        (4900, 8500, "去账房支身工钱。往后院里的水，他挑。"),
        (10100, 14000, "听见没？你以后是我们家的人了。"),
    ],
    "P011": [
        (5300, 7600, "第一课。这两个字，念“天地”。"),
        (7800, 10100, "先生，我是粗使人，认字……有用吗？"),
        (10300, 13000, "饭管你一天。字，管你一辈子。"),
    ],
    "P012": [
        (3500, 5600, "先生叫什么名字？"),
        (8300, 10800, "苏轼，字子瞻。记住这个名字——"),
        (10800, 12400, "将来，它值一千两黄金。"),
        (12400, 15000, "一千两？！那先生岂不就是天下最有钱的人！"),
    ],
}


def _duration_ms(path: Path) -> int:
    raw = subprocess.check_output(
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
    return max(1, round(float(raw) * 1000))


def _latest_panel_file(project_root: Path, panel: str) -> tuple[int, Path]:
    pattern = re.compile(rf"^{panel.lower()}-r(\d+)$")
    candidates: list[tuple[int, Path]] = []
    for directory in (project_root / "final").glob(f"{panel.lower()}-r*"):
        match = pattern.match(directory.name)
        if not match:
            continue
        files = sorted(directory.glob("*.mp4"))
        if files:
            candidates.append((int(match.group(1)), files[0]))
    if not candidates:
        raise FileNotFoundError(f"No accepted final mp4 found for {panel}")
    return max(candidates, key=lambda item: item[0])


def build(root: Path, destination: Path, revision: int) -> Path:
    project_root = root / "workspace" / "projects" / PROJECT_ID
    builder = VideoPackageBuilder(
        f"yisuo-ep001-codex-chapter-01-assembly-r{revision:03d}",
        "一蓑烟雨 · 第一章 · Codex 导演竞赛版 · Final Assembly",
        revision=revision,
        locale="zh-CN",
        project_id=PROJECT_ID,
    )
    timeline_segments: list[dict[str, int | str]] = []
    for sequence, panel in enumerate(PANEL_ORDER, 1):
        accepted_revision, source = _latest_panel_file(project_root, panel)
        uri = source.relative_to(project_root).as_posix()
        asset_key = f"source_video.{panel.lower()}"
        builder.add_asset(
            asset_key=asset_key,
            media_type="video",
            uri=uri,
            producer="lfo",
            operation="video.final.accepted",
            source_type="derived_media",
            review_required=True,
            metadata={
                "panel": panel,
                "accepted_revision": accepted_revision,
                "qc_basis": "director_visual_qc_plus_mimo",
            },
        )
        cues = [
            {"start_ms": start, "end_ms": end, "text": text}
            for start, end, text in SUBTITLE_CUES.get(panel, [])
        ]
        duration = _duration_ms(source)
        builder.add_clip(
            clip_id=f"panel-{sequence:03d}",
            sequence=sequence,
            duration_ms=duration,
            operation="video.passthrough",
            prompt=f"Pass through director-approved {panel} final clip",
            requirements={
                "aspect_ratio": "9:16",
                "megapixels": 0.4,
                "fps": 24,
                "native_audio": "allowed",
            },
            references=[
                {
                    "reference_id": "source_video",
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
                "accepted_revision": accepted_revision,
                "source_path": uri,
            },
        )
        timeline_segments.append(
            {
                "clip_id": f"panel-{sequence:03d}",
                "source_in_ms": SOURCE_IN_MS.get(panel, 0),
            }
        )
    builder.timeline(segments=timeline_segments)
    builder.output(
        container="mp4",
        video_encoder="h264",
        audio_encoder="aac",
        width=480,
        height=864,
        fps=24,
        sample_rate=48000,
        loudness_db="-16",
        transitions="cut",
        subtitles_mode="both",
        directory="chapter-01-final",
    )
    builder.approval(
        approved_by="director-agent",
        approved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        notes=(
            "All eleven adjacent boundaries were reviewed as previous-tail 2s plus next-head "
            "3s. Source-in trims remove confirmed action rewind at P001→P002, P002→P003, "
            "P004→P005, and P010→P011; all other boundaries remain untrimmed. Assembly uses "
            "accepted 9:16 0.4MP sources, cut-only timeline semantics, deterministic subtitles, "
            "and a conservative -16 LUFS audio master target for mobile playback headroom."
        ),
    )
    return builder.write(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", type=int, default=1)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    destination = (
        root
        / "workspace"
        / "projects"
        / PROJECT_ID
        / f"assembly-package-r{args.revision:03d}.json"
    )
    path = build(root, destination, args.revision)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
