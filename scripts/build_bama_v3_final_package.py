"""Build the V3 final assembly package from the accepted dialogue-locked panels."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PANEL_SOURCES = [
    ("P001", "run-c1fb7a00d85b", "mixed.mp4", 101),
    ("P002", "run-d752c9f4cfff", "dialogue-locked.mp4", 102),
    ("P003", "run-3174b0f0c31e", "dialogue-locked.mp4", 110),
    ("P004", "run-442232c9bce8", "dialogue-locked.mp4", 112),
    ("P005", "run-66d69e0f2043", "dialogue-locked.mp4", 113),
    ("P006", "run-5cbdb66944eb", "dialogue-locked.mp4", 114),
    ("P007", "run-480932c8ea41", "dialogue-locked.mp4", 115),
    ("P008", "run-17f7e94fca89", "dialogue-locked.mp4", 116),
    ("P009", "run-814f3267fb8a", "dialogue-locked.mp4", 117),
    ("P010", "run-673de544c716", "dialogue-locked.mp4", 120),
    ("P011", "run-deedf7e2989b", "dialogue-locked.mp4", 121),
    ("P012", "run-a6a9a6c03343", "dialogue-locked.mp4", 123),
    ("P013", "run-0d8dc5b90e34", "dialogue-locked.mp4", 124),
    ("P014", "run-103388e6d32f", "dialogue-locked.mp4", 129),
    ("P015", "run-cc4b901e22e4", "dialogue-locked.mp4", 133),
    ("P016", "run-3616f1270ead", "dialogue-locked.mp4", 138),
    ("P017", "run-7c95935aaf43", "dialogue-locked.mp4", 139),
    ("P018", "run-ee2900b9da2d", "dialogue-locked.mp4", 140),
]
CLIP_DURATION_MS = 10_100


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
            raise ValueError(f"Role-prefixed subtitle is forbidden: {text}")
        cues.append({"start_ms": _timestamp_ms(times.group(1)), "end_ms": _timestamp_ms(times.group(2)), "text": text})
    return cues


def _distribute_cues(cues: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = [[] for _ in PANEL_SOURCES]
    for cue in cues:
        index = int(cue["start_ms"]) // CLIP_DURATION_MS
        if index >= len(result):
            raise ValueError(f"Subtitle cue starts beyond the 18-panel timeline: {cue}")
        offset = index * CLIP_DURATION_MS
        local_end = int(cue["end_ms"]) - offset
        if local_end > CLIP_DURATION_MS:
            raise ValueError(f"Subtitle cue crosses a panel boundary: {cue}")
        result[index].append({"start_ms": int(cue["start_ms"]) - offset, "end_ms": local_end, "text": cue["text"]})
    return result


def build_package(project_root: Path, subtitle_file: Path) -> dict[str, Any]:
    cues_by_panel = _distribute_cues(_parse_srt(subtitle_file))
    assets: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    for sequence, (panel, run_id, filename, revision) in enumerate(PANEL_SOURCES, start=1):
        clip_id = f"panel-{sequence:03d}"
        source_uri = f"outputs/{run_id}/clips/{clip_id}/{filename}"
        source_path = project_root / source_uri
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        asset_key = f"source_video.v3.{panel.lower()}"
        assets.append({
            "asset_key": asset_key,
            "media_type": "video",
            "source": {"uri": source_uri},
            "provenance": {"source_type": "runtime_artifact", "producer": "lfo", "operation": "video.dialogue_locked", "producer_version": "2026-08-25"},
            "review": {"required": True},
            "metadata": {"panel": panel, "source_run": run_id, "package_revision": revision, "approved": True, "version": "V3"},
        })
        clips.append({
            "clip_id": clip_id,
            "sequence": sequence,
            "duration_ms": CLIP_DURATION_MS,
            "generation": {
                "operation": "video.passthrough",
                "prompt": f"Pass through accepted V3 {panel} dialogue-locked clip exactly for final assembly.",
                "requirements": {"aspect_ratio": "16:9", "width": 1920, "height": 1080, "fps": 24, "native_audio": "allowed"},
                "references": [{"reference_id": f"source-video-v3-{panel.lower()}", "asset_key": asset_key, "semantic_usage": "source.accepted_video", "instruction": f"Use accepted V3 {panel} clip exactly; do not regenerate.", "binding": {"required": True, "priority": 100, "placement": "fixed", "slot": "source_video", "on_unsupported": "fail"}}],
            },
            "audio": {"native_audio": "preserve"},
            "subtitles": {"cues": cues_by_panel[sequence - 1]},
            "source_context": {"skill": "zero-to-story", "creative_unit": "episode-assembly", "panel": panel, "source_run": run_id, "approved_clip": True, "prompt_format": "prompt-v3-dialogue-locked", "subtitle_source": subtitle_file.name, "last_frame": f"lastframes/v3-20260825/{panel}.png"},
        })
    return {
        "schema": "lfo.video-execution.v1",
        "package_id": "ba-ma-ting-wo-jie-shi-episode-001-final-v3-r001",
        "revision": 1,
        "project": {"title": "爸妈听我解释｜episode-001｜V3 final assembly", "project_id": "爸妈听我解释-episode-001", "locale": "zh-CN"},
        "assets": assets,
        "clips": clips,
        "output": {"container": "mp4", "video_encoder": "h264", "audio_encoder": "aac", "width": 1920, "height": 1080, "fps": 24, "sample_rate": 48000, "transitions": "cut", "subtitles_mode": "both", "directory": "episode-001-final-v3"},
        "timeline": {"assembly_mode": "accepted_v3_dialogue_locked_passthrough", "duration_note": "18 clips at the reviewed 10.100s panel cadence; subtitle source is subtitle-cues-v2.srt.", "subtitle_source": subtitle_file.name, "prior_package": "ba-ma-ting-wo-jie-shi-episode-001-final-v2-r001"},
        "approval": {"approved_by": "user", "notes": "P001–P018 V3 dialogue-locked execution; failed H3 runs retained; repaired panels are explicitly recorded in V3-execution-log.md."},
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
    print(json.dumps({"output": str(args.output), "revision": package["revision"], "assets": len(package["assets"]), "clips": len(package["clips"]), "subtitle_cues": sum(len(clip["subtitles"]["cues"]) for clip in package["clips"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
