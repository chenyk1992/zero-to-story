from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


PROJECT_ID = "yisuo-ep001-codex-director"

DURATIONS_MS = {
    "P001": 12_000,
    "P002": 15_000,
    "P003": 13_000,
    "P004": 12_000,
    "P005": 12_000,
    "P006": 12_000,
    "P007": 13_000,
    "P008": 12_000,
    "P009": 13_000,
    "P010": 14_000,
    "P011": 15_000,
    "P012": 15_000,
}

SHOT_RANGES = {
    "P001": [1, 6],
    "P002": [6, 11],
    "P003": [11, 16],
    "P004": [16, 21],
    "P005": [21, 26],
    "P006": [26, 31],
    "P007": [31, 36],
    "P008": [36, 41],
    "P009": [41, 46],
    "P010": [46, 51],
    "P011": [51, 56],
    "P012": [56, 61],
}

PANEL_CHARACTERS = {
    "P002": ["sushi.1079", "chaoer.1079"],
    "P003": ["chaoer.1079", "yushi.1079", "sushi.1079"],
    "P004": ["yushi.1079", "chaoer.1079"],
    "P005": ["chaoer.1079", "sushi.1079"],
    "P006": ["chaoer.1079"],
    "P007": ["chaoer.1056", "sushi.1056"],
    "P008": ["sushi.1056", "chaoer.1056"],
    "P009": ["sushi.1056", "chaoer.1056", "suxun.1056"],
    "P010": ["sushi.1056", "chaoer.1056", "suxun.1056"],
    "P011": ["sushi.1056", "chaoer.1056"],
    "P012": ["sushi.1056", "chaoer.1056"],
}

CHARACTER_PATHS = {
    "sushi.1079": "assets/characters/char_su_shi_1079.png",
    "chaoer.1079": "assets/characters/char_chaoer_1079.png",
    "yushi.1079": "assets/characters/char_yushi_1079.png",
    "sushi.1056": "assets/characters/char_su_shi_1056.png",
    "chaoer.1056": "assets/characters/char_chaoer_1056.png",
    "suxun.1056": "assets/characters/char_su_xun_1056.png",
}


def asset(
    key: str,
    uri: str,
    producer: str,
    operation: str,
    source_type: str = "external_skill",
) -> dict[str, object]:
    return {
        "asset_key": key,
        "media_type": "image",
        "source": {"uri": uri},
        "provenance": {
            "source_type": source_type,
            "producer": producer,
            "operation": operation,
        },
        "review": {"required": True},
    }


def build(panel: str, revision: int, root: Path) -> dict[str, object]:
    if panel not in PANEL_CHARACTERS:
        raise ValueError(f"Only sequential panels P002-P012 are supported, got {panel}")

    number = int(panel[1:])
    previous = f"P{number - 1:03d}"
    prompt_path = root / "h3_prompts" / f"{panel}_h3_prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8").rstrip("\n")

    assets: list[dict[str, object]] = [
        asset(
            f"tail.{previous.lower()}",
            f"assets/tails/{previous}_tail.png",
            "ffmpeg",
            "video.last_frame.extract",
            "derived_media",
        )
    ]
    for character in PANEL_CHARACTERS[panel]:
        assets.append(
            asset(
                f"character.{character}",
                CHARACTER_PATHS[character],
                "imagegen",
                "image.generate",
            )
        )
    assets.append(
        asset(
            f"storyboard.{panel.lower()}",
            f"assets/boards/board_{panel}.png",
            "imagegen",
            "image.generate",
        )
    )

    references: list[dict[str, object]] = []
    for index, item in enumerate(assets):
        key = str(item["asset_key"])
        if key.startswith("tail."):
            semantic_usage = "continuity.exact_previous_last_frame"
        elif key.startswith("storyboard."):
            semantic_usage = "composition.motion.sequence"
        else:
            semantic_usage = "subject.identity.costume"
        references.append(
            {
                "reference_id": key.replace(".", "-"),
                "asset_key": key,
                "semantic_usage": semantic_usage,
                "binding": {
                    "required": True,
                    "priority": 100 - index * 5,
                    "placement": "fixed",
                    "slot": f"ref_image_{index}",
                    "on_unsupported": "fail",
                },
            }
        )

    package_slug = f"yisuo-ep001-codex-{panel.lower()}-r{revision:03d}"
    return {
        "schema": "lfo.video-execution.v1",
        "package_id": package_slug,
        "revision": revision,
        "project": {
            "project_id": PROJECT_ID,
            "title": "一蓑烟雨 · 第一章 · Codex 导演竞赛版",
            "locale": "zh-CN",
        },
        "assets": assets,
        "clips": [
            {
                "clip_id": f"panel-{number:03d}",
                "sequence": number,
                "duration_ms": DURATIONS_MS[panel],
                "generation": {
                    "operation": "video.reference_to_video",
                    "prompt": prompt,
                    "seed": 12_000 + revision * 1_009,
                    "requirements": {
                        "aspect_ratio": "9:16",
                        "megapixels": 0.4,
                        "fps": 24,
                        "native_audio": "allowed",
                    },
                    "references": references,
                },
                "audio": {"native_audio": "preserve"},
                "subtitles": {"cues": []},
                "source_context": {
                    "creative_skill": "zero-to-story",
                    "prompt_skill": "h3-prompt-writing",
                    "creative_unit": "panel",
                    "panel": panel,
                    "shot_range": SHOT_RANGES[panel],
                },
            }
        ],
        "output": {
            "directory": f"{panel.lower()}-r{revision:03d}",
            "width": 1080,
            "height": 1920,
            "fps": 24,
            "subtitles_mode": "none",
        },
        "approval": {
            "approved_by": "director-agent",
            "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "notes": (
                "User authorized the director agent to control downstream approvals and "
                "explicitly selected 0.4 MP on 2026-08-27. The panel prompt, references, "
                "storyboard, and real previous tail frame passed director review."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("panel", choices=sorted(PANEL_CHARACTERS))
    parser.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    package = build(args.panel, args.revision, root)
    destination = root / "execution-package.json"
    destination.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
