"""Tests for the H3 prompt-manifest preflight contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_PATH = (
    Path(__file__).parents[2]
    / ".agents"
    / "skills"
    / "h3-prompt-writing"
    / "scripts"
    / "validate_prompt_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("prompt_manifest_validator", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _valid_manifest() -> dict[str, Any]:
    prompt = (
        "For the target video, at 0.00 seconds into the target video, "
        "<Picture 1> (from [Shot 1]) is fully referenced.\n\n"
        "integrated_multimodal_description: [Shot 1] A woman (S1) says: "
        "<d>[Chinese] 你好。</d>\n\n"
        "overall_soundscape: Quiet room tone.\n\n"
        "non_diegetic_music: N/A"
    )
    return {
        "schema": MODULE.SCHEMA,
        "clip_id": "P001",
        "plan_hash": "a" * 64,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "operation": "video.image_to_video",
        "duration_ms": 8000,
        "prompt": prompt,
        "setup_windows": [{"id": "C001", "start_ms": 0, "end_ms": 8000}],
        "dialogue_events": [
            {
                "event_id": "D001",
                "speaker_id": "S1",
                "text": "你好。",
                "start_ms": 1200,
                "end_ms": 1800,
                "allow_overlap": False,
            }
        ],
        "references": [
            {"label": "Picture 1", "slot": "first_frame", "media_type": "image"}
        ],
    }


def test_valid_manifest_passes() -> None:
    assert MODULE.validate_prompt_manifest(_valid_manifest()) == []


def test_prompt_hash_and_exact_dialogue_are_checked() -> None:
    manifest = _valid_manifest()
    manifest["prompt_hash"] = "b" * 64
    manifest["dialogue_events"][0]["text"] = "再见。"
    issues = MODULE.validate_prompt_manifest(manifest)
    messages = "\n".join(issue.format() for issue in issues)
    assert "prompt_hash" in messages
    assert "exact dialogue text" in messages


def test_setup_and_dialogue_overlaps_are_rejected() -> None:
    manifest = _valid_manifest()
    manifest["setup_windows"] = [
        {"id": "C001", "start_ms": 0, "end_ms": 5000},
        {"id": "C002", "start_ms": 4500, "end_ms": 8000},
    ]
    manifest["dialogue_events"].append(
        {
            "event_id": "D002",
            "speaker_id": "S2",
            "text": "你好。",
            "start_ms": 1500,
            "end_ms": 2200,
        }
    )
    issues = MODULE.validate_prompt_manifest(manifest)
    messages = "\n".join(issue.format() for issue in issues)
    assert "windows must not overlap" in messages
    assert "speech events overlap" in messages


def test_prompt_path_is_resolved_inside_manifest_directory(tmp_path: Path) -> None:
    manifest = _valid_manifest()
    prompt = manifest.pop("prompt")
    manifest_path = tmp_path / "manifest.json"
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    manifest["prompt_path"] = prompt_path.name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    assert MODULE.validate_prompt_manifest(manifest, base_dir=tmp_path) == []

    manifest["prompt_path"] = "../prompt.txt"
    issues = MODULE.validate_prompt_manifest(manifest, base_dir=tmp_path)
    assert any("inside the manifest directory" in issue.message for issue in issues)
