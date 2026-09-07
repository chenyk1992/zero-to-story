from __future__ import annotations

import json
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lfo.contracts.builder import VideoPackageBuilder


PROJECT_ID = "yisuo-ep002-codex-director"
PANEL_ORDER = [f"P{i:03d}" for i in range(1, 13)]

DURATIONS_MS = {
    "P001": 10_000,
    "P002": 15_000,
    "P003": 13_000,
    "P004": 14_000,
    "P005": 10_000,
    "P006": 11_000,
    "P007": 10_000,
    "P008": 11_000,
    "P009": 10_000,
    "P010": 8_000,
    "P011": 13_000,
    "P012": 10_000,
}

R2V_PANELS = {"P001", "P005", "P007", "P010"}

CHARACTER_ASSETS = {
    "character.cheng_furen": "assets/characters/char_cheng_furen_1056.png",
    "character.su_shi.young": "assets/characters/char_su_shi_1056.png",
    "character.su_zhe.young": "assets/characters/char_su_zhe_1056.png",
    "character.chaoer.young": "assets/characters/char_chaoer_1056.png",
}

PANEL_REFERENCE_KEYS = {
    "P001": [
        "character.cheng_furen",
        "character.su_shi.young",
        "character.su_zhe.young",
        "character.chaoer.young",
    ],
    "P005": [
        "character.su_zhe.young",
        "character.su_shi.young",
        "storyboard.p005",
    ],
    "P007": [
        "character.chaoer.young",
        "character.cheng_furen",
        "storyboard.p007",
    ],
    "P010": [
        "character.chaoer.young",
        "character.su_shi.young",
        "storyboard.p010",
    ],
}


def _project_root(root: Path) -> Path:
    return root / "workspace" / "projects" / PROJECT_ID


def _asset(
    builder: VideoPackageBuilder,
    *,
    asset_key: str,
    uri: str,
    producer: str,
    operation: str,
    source_type: str,
    panel: str,
) -> None:
    builder.add_asset(
        asset_key=asset_key,
        media_type="image",
        uri=uri,
        producer=producer,
        operation=operation,
        source_type=source_type,
        review_required=True,
        metadata={
            "panel": panel,
            "creative_preflight": "creative_blueprint.v1",
            "review_basis": "director-approved-before-generation",
        },
    )


def _fixed_reference(
    asset_key: str,
    *,
    slot: str,
    priority: int,
    semantic_usage: str,
    instruction: str,
) -> dict[str, Any]:
    return {
        "reference_id": asset_key.replace(".", "-"),
        "asset_key": asset_key,
        "semantic_usage": semantic_usage,
        "binding": {
            "required": True,
            "priority": priority,
            "placement": "fixed",
            "slot": slot,
            "on_unsupported": "fail",
        },
        "instruction": instruction,
    }


def build_panel_package(root: Path, panel: str, previous_tail: Path | None) -> Path:
    project_root = _project_root(root)
    prompt_path = root / ".short-drama" / "一蓑烟雨" / "zts" / "chapter_02" / "h3_prompts" / f"{panel}_h3_prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8").rstrip("\n")
    number = int(panel[1:])
    operation = "video.reference_to_video" if panel in R2V_PANELS else "video.image_to_video"

    package = VideoPackageBuilder(
        f"yisuo-ep002-v2-{panel.lower()}-r001",
        f"一蓑烟雨 · 第二章 · 创作预检版 · {panel}",
        revision=1,
        locale="zh-CN",
        project_id=PROJECT_ID,
    )

    references: list[dict[str, Any]] = []
    if panel in R2V_PANELS:
        for index, asset_key in enumerate(PANEL_REFERENCE_KEYS[panel], 1):
            if asset_key.startswith("character."):
                _asset(
                    package,
                    asset_key=asset_key,
                    uri=CHARACTER_ASSETS[asset_key],
                    producer="imagegen",
                    operation="image.generate",
                    source_type="external_skill",
                    panel=panel,
                )
                semantic_usage = "subject.identity.costume"
                instruction = "Preserve this character's identity, age, gender, face, hair, and costume exactly."
            else:
                _asset(
                    package,
                    asset_key=asset_key,
                    uri=f"assets/boards/board_{panel}.png",
                    producer="imagegen",
                    operation="image.generate",
                    source_type="external_skill",
                    panel=panel,
                )
                semantic_usage = "composition.motion.sequence"
                instruction = "Use this approved storyboard board for composition, shot order, screen direction, and action timing."
            references.append(
                _fixed_reference(
                    asset_key,
                    slot=f"ref_image_{index - 1}",
                    priority=100 - (index - 1) * 5,
                    semantic_usage=semantic_usage,
                    instruction=instruction,
                )
            )
    else:
        if previous_tail is None:
            raise ValueError(f"{panel}: previous accepted tail is required for I2V")
        previous_number = number - 1
        tail_key = f"continuity.tail.p{previous_number:03d}"
        tail_uri = previous_tail.relative_to(project_root).as_posix()
        _asset(
            package,
            asset_key=tail_key,
            uri=tail_uri,
            producer="lfo",
            operation="media.tail_frame",
            source_type="derived_media",
            panel=panel,
        )
        references.append(
            _fixed_reference(
                tail_key,
                slot="first_frame",
                priority=100,
                semantic_usage="continuity.exact_previous_last_frame",
                instruction=(
                    f"Use the real accepted tail frame of {PANEL_ORDER[number - 2]} as the exact first frame; "
                    "do not replay, dissolve, or reinterpret the preceding action."
                ),
            )
        )

    package.add_clip(
        clip_id=f"panel-{number:03d}",
        sequence=number,
        duration_ms=DURATIONS_MS[panel],
        operation=operation,
        prompt=prompt,
        seed=2_026_083_000 + number,
        requirements={
            "aspect_ratio": "9:16",
            "megapixels": 0.4,
            "fps": 24,
            "native_audio": "allowed",
        },
        references=references,
        audio={"native_audio": "preserve"},
        subtitles={"cues": []},
        source_context={
            "creative_skill": "zero-to-story",
            "prompt_skill": "h3-prompt-writing",
            "creative_unit": "panel",
            "panel": panel,
            "story_source": ".short-drama/一蓑烟雨/episodes/ep002.md",
            "creative_blueprint": ".short-drama/一蓑烟雨/zts/chapter_02/creative_blueprint.json",
            "continuity_policy": "exact_real_previous_tail_as_first_frame",
            "previous_tail": None if previous_tail is None else previous_tail.relative_to(project_root).as_posix(),
            "prompt_file": prompt_path.relative_to(root).as_posix(),
        },
    )
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
        subtitles_mode="none",
        directory=f"yisuo-ep002-v2-{panel.lower()}",
    )
    package.approval(
        approved_by="user",
        approved_at="2026-08-30T00:00:00+08:00",
        notes=(
            "User explicitly authorized autonomous rerender of Chapter 2 under the latest story-first rules. "
            "Creative blueprint static preflight passed before generation. Hard scene changes use approved role/board "
            "references; same-scene panels use the real accepted previous tail as an exact first-frame lock."
        ),
    )
    destination = project_root / f"execution-package-v2-{panel.lower()}-r001.json"
    return package.write(destination)


def _run_cli(root: Path, package_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "lfo.cli.main",
        "--json",
        "execute",
        str(package_path),
        "--approve",
    ]
    print(f"EXECUTE {package_path.name}", flush=True)
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"LFO execute failed for {package_path.name} with exit {completed.returncode}: "
            f"{completed.stdout[-2000:]}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LFO returned non-JSON for {package_path.name}: {completed.stdout[-2000:]}"
        ) from exc
    if not result.get("ok"):
        raise RuntimeError(f"LFO execute rejected {package_path.name}: {json.dumps(result, ensure_ascii=False)}")
    data = result.get("data")
    if not isinstance(data, dict) or not data.get("success", True):
        raise RuntimeError(f"LFO execute did not succeed for {package_path.name}: {json.dumps(result, ensure_ascii=False)}")
    return result


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


def _extract_tail(video_path: Path, tail_path: Path) -> None:
    tail_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-sseof",
            "-0.1",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-y",
            str(tail_path),
        ],
        check=True,
    )


def _mixed_path(project_root: Path, run_id: str, number: int) -> Path:
    return project_root / "outputs" / run_id / "clips" / f"panel-{number:03d}" / "mixed.mp4"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from chapter2-v2-generation-state.json without rerunning accepted panels.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    project_root = _project_root(root)
    tails_dir = project_root / "assets" / "tails"
    state_path = project_root / "chapter2-v2-generation-state.json"
    state: dict[str, Any]
    accepted: list[dict[str, Any]]
    completed_panels: set[str]
    previous_tail: Path | None
    if args.resume and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        accepted = list(state.get("panels", []))
        completed_panels = {str(item["panel"]) for item in accepted}
        previous_tail = None
        if accepted:
            tail_value = accepted[-1].get("tail_path")
            if tail_value:
                previous_tail = Path(str(tail_value))
                if not previous_tail.exists():
                    raise FileNotFoundError(f"Cannot resume: missing previous tail {previous_tail}")
        state["resumed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        print(
            f"RESUME accepted={','.join(sorted(completed_panels)) or 'none'} "
            f"next={PANEL_ORDER[len(completed_panels)] if len(completed_panels) < len(PANEL_ORDER) else 'none'}",
            flush=True,
        )
    else:
        state = {
            "version": "chapter2-v2-generation-state.v1",
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "panels": [],
        }
        accepted = []
        completed_panels = set()
        previous_tail = None

    for panel in PANEL_ORDER:
        if panel in completed_panels:
            continue
        package_path = build_panel_package(root, panel, previous_tail)
        result = _run_cli(root, package_path)
        data = result["data"]
        run_id = data["run_id"]
        number = int(panel[1:])
        mixed_path = _mixed_path(project_root, run_id, number)
        if not mixed_path.exists():
            raise FileNotFoundError(f"Accepted LFO clip is missing: {mixed_path}")
        duration_ms = _duration_ms(mixed_path)
        tail_path = tails_dir / f"chapter2-v2-tail_{panel}.png"
        _extract_tail(mixed_path, tail_path)
        record = {
            "panel": panel,
            "run_id": run_id,
            "package_path": str(package_path),
            "mixed_path": str(mixed_path),
            "duration_ms": duration_ms,
            "tail_path": str(tail_path),
            "accepted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        accepted.append(record)
        state["panels"] = accepted
        state["last_completed"] = panel
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        previous_tail = tail_path
        print(f"ACCEPTED {panel} run={run_id} duration_ms={duration_ms} tail={tail_path.name}", flush=True)

    state["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
