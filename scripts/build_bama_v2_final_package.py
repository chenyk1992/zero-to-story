"""Build the V2 final assembly package from accepted Episode-001 panel runs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CLIP_DURATION_MS = 10_100
ACCEPTED_RUNS = [
    "run-89d4a06c1d69",
    "run-8eca952b8224",
    "run-65814ea448ac",
    "run-7a12fd18f557",
    "run-5ba56dcd327a",
    "run-11b2acfe2937",
    "run-abf15496c04a",
    "run-94cfe2fba2e9",
    "run-11e91bf0187f",
    "run-a400ee242649",
    "run-69a7b3dce131",
    "run-6009ebf25fda",
    "run-95ff3c99d7b5",
    "run-3052017d3230",
    "run-4d8859d4e323",
    "run-a90f90023c7f",
    "run-4c2931ab738b",
    "run-eb608856c1de",
]


def _timestamp_ms(value: str) -> int:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value)
    if match is None:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def _parse_srt(path: Path) -> list[dict[str, Any]]:
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig").strip())
    cues: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        if len(lines) < 3:
            raise ValueError(f"Invalid SRT block: {block!r}")
        times = re.fullmatch(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1],
        )
        if times is None:
            raise ValueError(f"Invalid SRT cue timing: {lines[1]}")
        text = "\n".join(lines[2:]).strip()
        if not text:
            raise ValueError(f"Empty SRT cue: {lines[0]}")
        if re.match(r"^(老爸|老妈|爸爸|妈妈|七大姑|八大姨|九舅|舅舅|小胖|小美|哥|姐)[：:]", text):
            raise ValueError(f"Role-prefixed subtitle is forbidden in V2: {text}")
        cues.append(
            {
                "start_ms": _timestamp_ms(times.group(1)),
                "end_ms": _timestamp_ms(times.group(2)),
                "text": text,
            }
        )
    return cues


def _distribute_cues(cues: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = [[] for _ in ACCEPTED_RUNS]
    for cue in cues:
        clip_index = int(cue["start_ms"]) // CLIP_DURATION_MS
        if clip_index >= len(result):
            raise ValueError(f"Subtitle cue starts beyond the 18-panel timeline: {cue}")
        offset = clip_index * CLIP_DURATION_MS
        local_start = int(cue["start_ms"]) - offset
        local_end = int(cue["end_ms"]) - offset
        if local_end > CLIP_DURATION_MS:
            raise ValueError(f"Subtitle cue crosses a panel boundary: {cue}")
        result[clip_index].append(
            {"start_ms": local_start, "end_ms": local_end, "text": cue["text"]}
        )
    return result


def build_package(project_root: Path, subtitle_file: Path) -> dict[str, Any]:
    cues_by_clip = _distribute_cues(_parse_srt(subtitle_file))
    assets: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    for index, run_id in enumerate(ACCEPTED_RUNS, start=1):
        panel = f"p{index:03d}"
        clip_id = f"panel-{index:03d}"
        source_uri = f"outputs/{run_id}/clips/{clip_id}/mixed.mp4"
        source_path = project_root / source_uri
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing accepted V2 clip: {source_path}")
        asset_key = f"source_video.v2.{panel}"
        assets.append(
            {
                "asset_key": asset_key,
                "media_type": "video",
                "source": {"uri": source_uri},
                "provenance": {
                    "source_type": "runtime_artifact",
                    "producer": "lfo",
                    "operation": "video.mix",
                    "producer_version": "2026-08-25",
                },
                "review": {"required": True},
                "metadata": {
                    "panel": panel,
                    "source_run": run_id,
                    "approved": True,
                    "version": "V2",
                },
            }
        )
        clips.append(
            {
                "clip_id": clip_id,
                "sequence": index,
                "duration_ms": CLIP_DURATION_MS,
                "generation": {
                    "operation": "video.passthrough",
                    "prompt": f"Pass through approved V2 {panel} mixed clip for final episode assembly.",
                    "requirements": {
                        "aspect_ratio": "16:9",
                        "width": 1920,
                        "height": 1080,
                        "fps": 24,
                        "native_audio": "allowed",
                    },
                    "references": [
                        {
                            "reference_id": f"source-video-v2-{panel}",
                            "asset_key": asset_key,
                            "semantic_usage": "source.accepted_video",
                            "instruction": f"Use approved V2 {panel} mixed video exactly.",
                            "binding": {
                                "required": True,
                                "priority": 100,
                                "placement": "fixed",
                                "slot": "source_video",
                                "on_unsupported": "fail",
                            },
                        }
                    ],
                },
                "audio": {"native_audio": "preserve"},
                "subtitles": {"cues": cues_by_clip[index - 1]},
                "source_context": {
                    "skill": "zero-to-story",
                    "creative_unit": "episode-assembly",
                    "panel": panel,
                    "source_run": run_id,
                    "approved_clip": True,
                    "prompt_format": "passthrough-approved-v2-clip",
                    "subtitle_source": subtitle_file.name,
                },
            }
        )
    return {
        "schema": "lfo.video-execution.v1",
        "package_id": "ba-ma-ting-wo-jie-shi-episode-001-final-v2-r001",
        "revision": 1,
        "project": {
            "title": "爸妈听我解释｜episode-001｜V2 final assembly",
            "project_id": "爸妈听我解释-episode-001",
            "locale": "zh-CN",
        },
        "assets": assets,
        "clips": clips,
        "output": {
            "container": "mp4",
            "video_encoder": "h264",
            "audio_encoder": "aac",
            "width": 1920,
            "height": 1080,
            "fps": 24,
            "sample_rate": 48000,
            "transitions": "cut",
            "subtitles_mode": "both",
            "directory": "episode-001-final-v2",
        },
        "timeline": {
            "assembly_mode": "approved_v2_clip_passthrough",
            "duration_note": "18 clips at the reviewed 10.100s panel cadence; V2 SRT ends at 181.500s.",
            "subtitle_source": subtitle_file.name,
            "prior_package": "ba-ma-ting-wo-jie-shi-episode-001-final-r002",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--subtitle-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = build_package(args.project_root.resolve(), args.subtitle_file.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "revision": package["revision"],
                "assets": len(package["assets"]),
                "clips": len(package["clips"]),
                "subtitle_cues": sum(len(clip["subtitles"]["cues"]) for clip in package["clips"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
