from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe, run_command
from lfo.media.mv_preview import _verify_ass_support
from lfo.media.story_edit import (
    _check_adopted_assets,
    render_story_edit,
    render_story_preview,
    validate_story_edit,
    validate_story_preview,
)
from lfo.media.story_edit import (
    main as story_edit_main,
)
from lfo.media.subtitles import parse_srt


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_ass_support() -> bool:
    try:
        _verify_ass_support()
        return True
    except ValueError:
        return False


def _make_fixtures(tmp_path: Path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("real FFmpeg is required for story_edit integration")
    ffmpeg = os.environ.get("LFO_FFMPEG") or "ffmpeg"
    clips: list[Path] = []
    for index, (color, freq) in enumerate((("red", 330), ("blue", 520)), start=1):
        clip = tmp_path / f"clip{index}.mp4"
        run_command([
            ffmpeg, "-v", "error", "-f", "lavfi",
            "-i", f"color=c={color}:s=320x180:r=24:d=2.0",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration=2.0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip),
        ])
        clips.append(clip)
    bgm = tmp_path / "bgm.flac"
    run_command([
        ffmpeg, "-v", "error", "-f", "lavfi",
        "-i", "sine=frequency=220:sample_rate=48000:duration=3.0",
        "-c:a", "flac", str(bgm),
    ])
    still = tmp_path / "board.png"
    run_command([
        ffmpeg, "-v", "error", "-f", "lavfi",
        "-i", "color=c=green:s=320x180:r=24:d=0.1",
        "-frames:v", "1", str(still),
    ])
    return clips, bgm, still


def test_validate_story_edit_rejects_gaps_jl_overflow_and_missing_provenance(tmp_path: Path) -> None:
    clips, bgm, still = _make_fixtures(tmp_path)
    base = {
        "schema": "lfo.story.edit.v1",
        "width": 320,
        "height": 180,
        "fps": 24,
        "native_audio_strategy": "mix",
        "seam_fade_ms": 40,
        "segments": [
            {
                "kind": "video",
                "run_id": "r1",
                "path": str(clips[0]),
                "sha256": _digest(clips[0]),
                "source_in_ms": 0,
                "source_out_ms": 1000,
                "timeline_start_ms": 0,
                "audio_tail_ms": 200,
            },
            {
                "kind": "video",
                "run_id": "r2",
                "path": str(clips[1]),
                "sha256": _digest(clips[1]),
                "source_in_ms": 500,
                "source_out_ms": 1500,
                "timeline_start_ms": 1000,
                "audio_lead_ms": 200,
            },
        ],
        "audio_tracks": [
            {
                "role": "bgm",
                "source_note": "score",
                "path": str(bgm),
                "sha256": _digest(bgm),
                "source_in_ms": 0,
                "source_out_ms": 2000,
                "timeline_start_ms": 0,
                "gain_db": -12.0,
            }
        ],
    }
    validated = validate_story_edit(base)
    assert validated["duration_ms"] == 2000

    # J-cut pulling before timeline 0 fails.
    bad_j = json.loads(json.dumps(base))
    bad_j["segments"][0]["source_in_ms"] = 500
    bad_j["segments"][0]["source_out_ms"] = 1500
    bad_j["segments"][0]["audio_lead_ms"] = 100
    with pytest.raises(ValueError, match="起点 0"):
        validate_story_edit(bad_j)

    # L-cut past timeline end fails.
    bad_l = json.loads(json.dumps(base))
    bad_l["segments"][1]["audio_tail_ms"] = 100
    with pytest.raises(ValueError, match="总时长"):
        validate_story_edit(bad_l)

    # Missing provenance fails.
    bad_prov = json.loads(json.dumps(base))
    del bad_prov["segments"][0]["run_id"]
    with pytest.raises(ValueError, match="run_id|source_note"):
        validate_story_edit(bad_prov)

    # Image segment cannot carry J/L-cut or video trim.
    bad_img = json.loads(json.dumps(base))
    bad_img["segments"] = [{
        "kind": "image",
        "source_note": "still",
        "path": str(still),
        "sha256": _digest(still),
        "duration_ms": 1000,
        "timeline_start_ms": 0,
        "audio_lead_ms": 100,
    }]
    with pytest.raises(ValueError, match="静态图片"):
        validate_story_edit(bad_img)

    # Replace strategy requires audio_tracks.
    bad_replace = json.loads(json.dumps(base))
    bad_replace["native_audio_strategy"] = "replace"
    bad_replace["audio_tracks"] = []
    with pytest.raises(ValueError, match="audio_tracks"):
        validate_story_edit(bad_replace)


def test_render_story_edit_jl_cut_loudness_clean_srt_and_cache(tmp_path: Path) -> None:
    clips, bgm, _ = _make_fixtures(tmp_path)
    has_ass = _has_ass_support()
    edit = {
        "schema": "lfo.story.edit.v1",
        "width": 320,
        "height": 180,
        "fps": 24,
        "native_audio_strategy": "mix",
        "seam_fade_ms": 50,
        "loudness": {"enabled": True, "target_i": -16.0},
        "music_ducking": [{"start_ms": 200, "end_ms": 1600, "gain_db": -10.0}],
        "segments": [
            {
                "kind": "video",
                "run_id": "r1",
                "path": str(clips[0]),
                "sha256": _digest(clips[0]),
                "source_in_ms": 0,
                "source_out_ms": 1000,
                "timeline_start_ms": 0,
                "audio_tail_ms": 200,
            },
            {
                "kind": "video",
                "run_id": "r2",
                "path": str(clips[1]),
                "sha256": _digest(clips[1]),
                "source_in_ms": 400,
                "source_out_ms": 1400,
                "timeline_start_ms": 1000,
                "audio_lead_ms": 200,
            },
        ],
        "audio_tracks": [
            {
                "role": "bgm",
                "source_note": "score",
                "path": str(bgm),
                "sha256": _digest(bgm),
                "source_in_ms": 0,
                "source_out_ms": 2000,
                "timeline_start_ms": 0,
                "gain_db": -12.0,
            }
        ],
        "subtitles": (
            [{"start_ms": 100, "end_ms": 1800, "text": "测试对白字幕"}] if has_ass else []
        ),
    }
    cache_dir = tmp_path / "cache"
    out1 = tmp_path / "final.mp4"
    clean1 = tmp_path / "clean.mp4"
    srt1 = tmp_path / "final.srt"
    receipt = render_story_edit(
        edit,
        out1,
        clean_output_path=clean1,
        srt_output_path=srt1 if has_ass else None,
        cache_dir=cache_dir,
    )
    assert receipt["schema"] == "lfo.story.render-receipt.v1"
    assert receipt["video_frame_count"] == 48
    assert receipt["cache_hits"] == 0 and receipt["cache_misses"] == 2
    assert out1.is_file() and clean1.is_file()
    assert probe(out1)["has_audio"] is True
    assert probe(clean1)["has_audio"] is True
    if has_ass:
        assert srt1.is_file()
        assert parse_srt(srt1.read_text(encoding="utf-8"))[0].text == "测试对白字幕"
        assert _digest(out1) != _digest(clean1)

    # Second render reuses segment cache.
    out2 = tmp_path / "final-v2.mp4"
    receipt2 = render_story_edit(edit, out2, cache_dir=cache_dir)
    assert receipt2["cache_hits"] == 2 and receipt2["cache_misses"] == 0


def test_render_story_edit_mute_produces_valid_silent_audio(tmp_path: Path) -> None:
    clips, _, still = _make_fixtures(tmp_path)
    edit = {
        "schema": "lfo.story.edit.v1",
        "width": 320,
        "height": 180,
        "fps": 24,
        "native_audio_strategy": "mute",
        "loudness": {"enabled": True, "target_i": -16.0},
        "segments": [
            {
                "kind": "image",
                "source_note": "card",
                "path": str(still),
                "sha256": _digest(still),
                "duration_ms": 1000,
                "timeline_start_ms": 0,
            }
        ],
    }
    out = tmp_path / "muted.mp4"
    receipt = render_story_edit(edit, out)
    assert receipt["video_frame_count"] == 24
    assert probe(out)["has_audio"] is True


def test_story_preview_animatic_validation_and_render(tmp_path: Path) -> None:
    clips, bgm, still = _make_fixtures(tmp_path)
    preview = {
        "schema": "lfo.story.preview.v1",
        "width": 320,
        "height": 180,
        "fps": 24,
        "segments": [
            {
                "shot_id": "S1",
                "timeline_start_ms": 0,
                "duration_ms": 1000,
                "media": {"type": "image", "path": str(still), "sha256": _digest(still)},
            },
            {
                "shot_id": "S2",
                "timeline_start_ms": 1000,
                "duration_ms": 1000,
                "media": {"type": "placeholder", "label": "男主推门入室"},
            },
        ],
        "audio_tracks": [
            {
                "role": "voiceover",
                "path": str(bgm),
                "sha256": _digest(bgm),
                "source_in_ms": 0,
                "source_out_ms": 1500,
                "timeline_start_ms": 200,
            }
        ],
    }
    validated = validate_story_preview(preview)
    assert validated["duration_ms"] == 2000

    bad = {**preview, "loudness": {"enabled": True}}
    with pytest.raises(ValueError, match="lfo.story.edit.v1"):
        validate_story_preview(bad)

    if not _has_ass_support():
        pytest.skip("ASS filter or CJK font unavailable for preview burn-in")
    out = tmp_path / "animatic.mp4"
    receipt = render_story_preview(preview, out)
    assert receipt["schema"] == "lfo.story.preview.v1"
    assert receipt["purpose"] == "story-animatic-preview"
    assert receipt["placeholder_count"] == 1
    assert receipt["content_review"] == "NOT_REVIEWED"
    assert probe(out)["has_audio"] is True


def test_story_edit_cli_and_adoption_check(tmp_path: Path, monkeypatch) -> None:
    clips, _, _ = _make_fixtures(tmp_path)
    clip_sha = _digest(clips[0])
    edit = {
        "schema": "lfo.story.edit.v1",
        "width": 320,
        "height": 180,
        "fps": 24,
        "native_audio_strategy": "keep",
        "segments": [
            {
                "kind": "video",
                "run_id": "run-1",
                "path": str(clips[0]),
                "sha256": clip_sha,
                "source_in_ms": 0,
                "source_out_ms": 1000,
                "timeline_start_ms": 0,
            }
        ],
    }
    run_record = {
        "id": "run-1",
        "status": "succeeded",
        "review": {"decision": "ACCEPT", "output_path": str(clips[0]), "output_sha256": clip_sha},
    }
    monkeypatch.setattr("lfo.media.story_edit._canvas_read", lambda *_args: {"runs": [run_record]})
    _check_adopted_assets(edit, "c1")

    run_record["review"]["decision"] = "REJECT"
    with pytest.raises(ValueError, match="正式采用"):
        _check_adopted_assets(edit, "c1")

    edit_path = tmp_path / "edit.json"
    edit_path.write_text(json.dumps(edit), encoding="utf-8")
    assert story_edit_main(["validate", "--edit", str(edit_path)]) == 0
