"""Tests for immutable production locks and audio acceptance declarations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfo.contracts import (
    AUDIO_ACCEPTANCE_EXTENSION,
    PRODUCTION_LOCK_EXTENSION,
    clip_plan_hash,
    validate_audio_acceptance,
    validate_package,
    validate_production_lock,
    with_production_lock,
)


def _package() -> dict[str, Any]:
    return {
        "schema": "lfo.video-execution.v1",
        "package_id": "pkg-001",
        "revision": 1,
        "project": {"project_id": "lock-test", "title": "Lock test"},
        "assets": [],
        "clips": [
            {
                "clip_id": "P001",
                "sequence": 1,
                "duration_ms": 8000,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "approved prompt",
                    "requirements": {"aspect_ratio": "9:16", "megapixels": 0.4},
                },
                "audio": {"native_audio": "preserve"},
                "subtitles": {"cues": []},
                "source_context": {"panel": "P001"},
            }
        ],
        "output": {"width": 1080, "height": 1920, "fps": 24},
    }


def test_build_lock_round_trips_float_plan_values() -> None:
    package = _package()
    locked = with_production_lock(package)
    assert PRODUCTION_LOCK_EXTENSION in locked["extensions"]
    lock = locked["extensions"][PRODUCTION_LOCK_EXTENSION]
    assert lock["status"] == "LOCKED"
    assert validate_production_lock(locked, require=True).ok
    assert validate_package(locked, require_production_lock=True).ok
    assert lock["clips"]["P001"]["plan_hash"] == clip_plan_hash(package["clips"][0])


def test_omitted_timeline_hashes_the_effective_sequence() -> None:
    concise = _package()
    explicit = deepcopy(concise)
    explicit["timeline"] = {"segments": [{"clip_id": "P001"}]}
    assert validate_production_lock(
        with_production_lock(concise), require=True
    ).ok
    assert validate_production_lock(
        with_production_lock(explicit), require=True
    ).ok
    assert (
        with_production_lock(concise)["extensions"][PRODUCTION_LOCK_EXTENSION]["package_plan_hash"]
        == with_production_lock(explicit)["extensions"][PRODUCTION_LOCK_EXTENSION]["package_plan_hash"]
    )


def test_immutable_plan_changes_fail_but_prompt_revision_does_not() -> None:
    locked = with_production_lock(_package())
    revised_prompt = deepcopy(locked)
    revised_prompt["clips"][0]["generation"]["prompt"] = "reworded prompt"
    assert validate_production_lock(revised_prompt, require=True).ok

    changed_duration = deepcopy(locked)
    changed_duration["clips"][0]["duration_ms"] = 9000
    errors = validate_production_lock(changed_duration, require=True).errors()
    assert any(error.code == "plan_hash_mismatch" for error in errors)


def test_prompt_manifest_evidence_can_follow_a_prompt_only_revision() -> None:
    package = _package()
    manifest = {
        "schema": "h3.prompt-manifest.v1",
        "clip_id": "P001",
        # The manifest binds to the immutable Clip hash.  Its own prompt
        # bytes/hashes are mutable evidence and are excluded from that hash.
        "plan_hash": clip_plan_hash(package["clips"][0]),
        "prompt_hash": "b" * 64,
        "prompt": "original prompt",
        "setup_windows": [{"id": "C001", "start_ms": 0, "end_ms": 8000}],
    }
    package["clips"][0]["extensions"] = {
        "lfo.prompt_manifest.v1": manifest,
    }
    locked = with_production_lock(package)
    revised = deepcopy(locked)
    revised_manifest = revised["clips"][0]["extensions"]["lfo.prompt_manifest.v1"]
    revised_manifest["prompt"] = "rewritten prompt"
    revised_manifest["prompt_hash"] = "c" * 64
    revised_manifest["plan_hash"] = clip_plan_hash(revised["clips"][0])
    assert validate_production_lock(revised, require=True).ok

    changed_output = deepcopy(locked)
    changed_output["output"]["fps"] = 30
    errors = validate_production_lock(changed_output, require=True).errors()
    assert any(error.code == "plan_hash_mismatch" for error in errors)


def test_prompt_manifest_cannot_bind_to_a_different_clip_plan() -> None:
    package = _package()
    package["clips"][0]["extensions"] = {
        "lfo.prompt_manifest.v1": {
            "clip_id": "P001",
            "plan_hash": "f" * 64,
        }
    }
    locked = with_production_lock(package)
    errors = validate_production_lock(locked, require=True).errors()
    assert any(error.code == "manifest_binding" for error in errors)


def test_missing_lock_is_rejected_only_in_strict_mode() -> None:
    package = _package()
    assert validate_package(package).ok
    errors = validate_package(package, require_production_lock=True).errors()
    assert any(error.code == "production_lock_required" for error in errors)


def test_audio_acceptance_contract_is_small_and_strict() -> None:
    valid = {
        "schema": AUDIO_ACCEPTANCE_EXTENSION,
        "require_audio": True,
        "timing_tolerance_ms": 250,
        "transcript_similarity": 0.9,
        "speech_events": [
            {
                "event_id": "D001",
                "speaker_id": "S1",
                "text": "你好。",
                "start_ms": 1000,
                "end_ms": 1800,
                "allow_overlap": False,
            }
        ],
    }
    assert validate_audio_acceptance(valid).ok
    invalid = deepcopy(valid)
    invalid["require_audio"] = False
    assert not validate_audio_acceptance(invalid).ok
