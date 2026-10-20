"""Verify new finishing features against decoded pixels and audio, in temp files."""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import zlib
from array import array
from pathlib import Path

import pytest

from lfo.media._ffmpeg import run_command
from lfo.media.audio import (
    AudioMixer,
    AudioMixRequest,
    AudioTrack,
    DuckingWindow,
    parse_ducking_windows,
)
from lfo.media.music_timeline import inspect_music
from lfo.media.mv_edit import render_edit, validate_edit


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png(path: Path, width: int, height: int, *, logo: bool = False) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    rows = b"".join(
        b"\0" + b"".join(
            bytes((255, 0, 0, 255 if x < width // 2 else 0)) if logo
            else bytes((0, 255, 0, 255)) for x in range(width)
        ) for _ in range(height)
    )
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


@pytest.fixture
def project(tmp_path: Path):
    folder = tmp_path / "媒体 O'Brien"
    folder.mkdir()
    song, video, voice = folder / "song.flac", folder / "source.mp4", folder / "voice.flac"
    ffmpeg = os.environ.get("LFO_FFMPEG") or "ffmpeg"
    for output, tone, duration in ((song, 330, 4), (voice, 990, 0.5)):
        run_command([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                     f"sine=frequency={tone}:duration={duration}", "-c:a", "flac", str(output)])
    run_command([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                 "color=c=blue:s=96x64:r=20:d=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)])
    timeline = folder / "timeline.json"
    timeline.write_text(json.dumps(inspect_music(song, start_ms=500, end_ms=3500)), encoding="utf-8")
    card, logo = folder / "片尾.png", folder / "透明 Logo.png"
    png(card, 96, 64)
    png(logo, 40, 20, logo=True)
    edit = {"schema": "lfo.mv.edit.v1", "music_timeline": str(timeline),
            "width": 96, "height": 64, "fps": 20, "native_audio_strategy": "replace",
            "segments": [{"run_id": "accepted-video", "path": str(video), "sha256": sha(video),
                          "source_in_ms": 0, "source_out_ms": 3000, "timeline_start_ms": 0}],
            "sound_effects": [{"path": str(voice), "sha256": sha(voice), "source_in_ms": 0,
                               "source_out_ms": 500, "timeline_start_ms": 1200, "gain_db": 0}]}
    return edit, card, logo, folder


def rms(path: Path, start: float, duration: float, frequency: int = 330) -> float:
    result = subprocess.run(
        [os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-i", str(path), "-ss", str(start),
         "-t", str(duration), "-vn", "-af", f"bandpass=f={frequency}:width_type=h:w=40",
         "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1"],
        capture_output=True, check=True,
    )
    samples = array("h")
    samples.frombytes(result.stdout)
    assert len(samples) > 0
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def pixel(path: Path, second: float, x: int, y: int) -> bytes:
    result = subprocess.run(
        [os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-ss", str(second), "-i", str(path),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y}", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
        capture_output=True, check=True,
    )
    assert len(result.stdout) == 12
    return result.stdout[:3]


def overlay(logo: Path) -> dict:
    return {"path": str(logo), "sha256": sha(logo), "source_note": "user supplied logo; visually selected",
            "start_ms": 500, "end_ms": 1500, "x": 10, "y": 10, "width": 40, "height": 20}


def test_ducking_changes_only_music_windows_and_preserves_dialogue(project):
    edit, _, _, folder = project
    plain = folder / "plain.mp4"
    ducked = folder / "ducked.mp4"
    render_edit(edit, plain)
    edit["music_ducking"] = [
        {"start_ms": 1000, "end_ms": 1600, "gain_db": -6, "attack_ms": 200, "release_ms": 200},
        {"start_ms": 1400, "end_ms": 2000, "gain_db": -12, "attack_ms": 200, "release_ms": 200},
    ]
    receipt = render_edit(edit, ducked)
    def difference(start, length, frequency=330):
        return 20 * math.log10(
            rms(ducked, start, length, frequency) / rms(plain, start, length, frequency)
        )
    assert abs(difference(0.3, 0.2)) < 0.5
    assert difference(1.02, 0.12) == pytest.approx(-6, abs=0.8)
    assert difference(1.45, 0.1) == pytest.approx(-12, abs=1.0)  # not -18 on overlap
    assert -6 < difference(0.88, 0.05) < -1  # attack
    assert -11 < difference(2.08, 0.05) < -2  # release
    assert abs(difference(2.5, 0.2)) < 0.5
    assert abs(difference(1.45, 0.1, 990)) < 0.8  # foreground remains intact
    assert receipt["music_ducking"] == edit["music_ducking"]
    assert receipt["video_frame_count"] == 60


@pytest.mark.parametrize("count", [100, 240])
def test_many_dialogue_windows_render_and_preserve_envelope(project, count):
    edit, _, _, folder = project
    plain = folder / "plain.mp4"
    render_edit(edit, plain)
    edit["music_ducking"] = [
        {"start_ms": 800 + index, "end_ms": 1800 + index, "gain_db": -6}
        for index in range(count)
    ]
    rendered = folder / "many-windows.mp4"
    result = render_edit(edit, rendered)
    assert len(result["music_ducking"]) == count
    assert 20 * math.log10(rms(rendered, 1.4, 0.15) / rms(plain, 1.4, 0.15)) == pytest.approx(-6, abs=0.8)
    assert 20 * math.log10(rms(rendered, 2.7, 0.15) / rms(plain, 2.7, 0.15)) == pytest.approx(0, abs=0.5)


def test_imported_video_can_reach_formal_render_with_real_provenance(project):
    edit, _, _, folder = project
    segment = edit["segments"][0]
    segment.pop("run_id")
    segment["source_note"] = "user supplied screen recording, selected version and scope checked"
    source = Path(segment["path"])
    before = sha(source)
    receipt = render_edit(edit, folder / "imported-final.mp4")
    assert receipt["video_frame_count"] == 60
    assert receipt["segments"][0]["run_id"] is None
    assert receipt["segments"][0]["source_note"] == segment["source_note"]
    assert sha(source) == before
    segment["source_note"] = " "
    with pytest.raises(ValueError, match="source_note"):
        validate_edit(edit)
    segment["source_note"] = "selected import"
    segment["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        validate_edit(edit)


@pytest.mark.parametrize("protected", ["timeline", "song", "video", "logo", "output"])
def test_cache_tree_cannot_contain_input_or_output_files(project, protected):
    edit, _, logo, folder = project
    cache = folder / "cache"
    cache.mkdir()
    output = folder / "new.mp4"
    if protected == "output":
        output = cache / "new.mp4"
    elif protected == "logo":
        moved = cache / logo.name
        logo.rename(moved)
        edit["image_overlays"] = [overlay(moved)]
    elif protected == "video":
        original = Path(edit["segments"][0]["path"])
        moved = cache / original.name
        original.rename(moved)
        edit["segments"][0]["path"] = str(moved)
    else:
        timeline_path = Path(edit["music_timeline"])
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        if protected == "timeline":
            moved = cache / "manifest.json"
            timeline_path.rename(moved)
            edit["music_timeline"] = str(moved)
        else:
            original = Path(timeline["source"]["path"])
            moved = cache / original.name
            original.rename(moved)
            timeline["source"]["path"] = str(moved)
            timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    before = {path: sha(path) for path in folder.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="缓存目录"):
        render_edit(edit, output, cache_dir=cache)
    assert not output.exists()
    assert {path: sha(path) for path in folder.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("postroll", [0, 500])
def test_old_lyric_window_is_clipped_without_reaching_postroll(project, monkeypatch, postroll):
    import lfo.media.mv_edit as module

    edit, card, _, folder = project
    edit["postroll_duration_ms"] = postroll
    if postroll:
        edit["segments"].append({"kind": "image", "path": str(card), "sha256": sha(card),
                                 "source_note": "imported card", "timeline_start_ms": 3000,
                                 "duration_ms": postroll})
    edit["text_events"] = [{"kind": "lyric", "text": "END", "status": "verified",
                            "start_ms": 3200, "end_ms": 3800}]
    original = module.render_ass
    ends = []

    def capture(events, **kwargs):
        ends.extend(event["end_ms"] for event in events)
        return original(events, **kwargs)

    monkeypatch.setattr(module, "render_ass", capture)
    render_edit(edit, folder / "clipped-lyrics.mp4")
    assert ends and all(end == 3000 for end in ends)
    if postroll:
        edit["text_events"][0]["start_ms"] = 3600
        with pytest.raises(ValueError, match="文字事件"):
            validate_edit(edit)


@pytest.mark.parametrize("entry", ["formal", "preview", "visual"])
def test_cache_rejects_input_symlink_before_replacing_directory_entry(project, entry):
    from lfo.media.mv_preview import render_preview
    from lfo.media.mv_render import render_visual_segments

    edit, _, _, folder = project
    cache = folder / "cache"
    cache.mkdir()
    link = cache / "manifest.json"
    target = Path(edit["segments"][0]["path"] if entry == "visual" else edit["music_timeline"])
    link.symlink_to(target)
    before = sha(target)
    with pytest.raises(ValueError, match="缓存目录"):
        if entry == "formal":
            edit["music_timeline"] = str(link)
            render_edit(edit, folder / "new.mp4", cache_dir=cache)
        elif entry == "preview":
            value = {"schema": "lfo.mv.preview.v1", "music_timeline": str(link),
                     "width": 96, "height": 64, "fps": 20,
                     "segments": [{"timeline_start_ms": 0, "duration_ms": 3000,
                                   "media": {"type": "video", **edit["segments"][0]}}]}
            render_preview(value, folder / "new.mp4", cache_dir=cache)
        else:
            item = {**edit["segments"][0], "kind": "video", "path": str(link),
                    "duration_ms": 3000}
            render_visual_segments([item], width=96, height=64, fps=20, cache_dir=cache)
    assert link.is_symlink() and link.resolve() == target.resolve()
    assert sha(target) == before
    assert sorted(path.name for path in cache.iterdir()) == ["manifest.json"]


def test_timed_transparent_logo_survives_formal_render_with_subtitles(project):
    edit, _, logo, folder = project
    edit["image_overlays"] = [overlay(logo)]
    edit["text_events"] = [{"kind": "visual", "text": "THANK YOU", "start_ms": 2500,
                            "end_ms": 3200}]
    result = render_edit(edit, folder / "logo.mp4")
    output = Path(result["path"])
    assert pixel(output, 0.45, 14, 14)[2] > 180
    assert pixel(output, 0.5, 14, 14)[0] > 180
    assert pixel(output, 1.5, 14, 14)[2] > 180
    assert pixel(output, 0.8, 40, 14)[2] > 180  # alpha area preserves source blue
    assert result["video_frame_count"] == 60
    assert result["audio_duration_ms"] == pytest.approx(3000, abs=50)
    assert result["image_overlays"][0]["sha256"] == sha(logo)


def test_appended_image_endcard_pads_silence_and_reuses_segment_cache(project):
    edit, card, _, folder = project
    original = {path: sha(path) for path in (card, Path(edit["segments"][0]["path"]))}
    edit["postroll_duration_ms"] = 500
    edit["native_audio_strategy"] = "mix"
    edit["segments"].append({"kind": "image", "path": str(card), "sha256": sha(card),
                             "source_note": "imported end card, approved visual", "timeline_start_ms": 3000,
                             "duration_ms": 500})
    result = render_edit(edit, folder / "endcard.mp4", cache_dir=folder / "cache")
    output = Path(result["path"])
    assert pixel(output, 2.95, 2, 2)[2] > 180
    assert pixel(output, 3.0, 2, 2)[1] > 180
    assert rms(output, 3.25, 0.15) < 5  # no looped or stretched song
    assert rms(output, 2.7, 0.15) > 100
    assert result["video_frame_count"] == 70
    assert result["audio_duration_ms"] == pytest.approx(3500, abs=50)
    assert result["segments"][1]["kind"] == "image"
    assert result["segments"][1]["run_id"] is None
    assert result["segments"][1]["output_start_frame"] == 60
    assert result["segments"][1]["source_in_ms"] is None
    again = render_edit(edit, folder / "cached.mp4", cache_dir=folder / "cache")
    assert again["cache_hits"] == 2
    assert all(sha(path) == before for path, before in original.items())


def test_image_can_replace_a_slot_inside_song_without_extending_duration(project):
    edit, card, _, folder = project
    edit["segments"][-1]["source_out_ms"] = 2000
    edit["segments"].append({"kind": "image", "path": str(card), "sha256": sha(card),
                             "source_note": "selected card", "timeline_start_ms": 2000, "duration_ms": 1000})
    result = render_edit(edit, folder / "within-song.mp4")
    assert result["video_frame_count"] == 60
    assert rms(Path(result["path"]), 2.5, 0.2) > 100


@pytest.mark.parametrize("window", [
    {"start_ms": -1, "end_ms": 100}, {"start_ms": 0, "end_ms": 3001},
    {"start_ms": 100, "end_ms": 100}, {"start_ms": True, "end_ms": 100},
    {"start_ms": 0, "end_ms": 100, "gain_db": float("nan")},
    {"start_ms": 0, "end_ms": 100, "gain_db": 1},
    {"start_ms": 0, "end_ms": 100, "release_ms": -1},
    {"start_ms": 0, "end_ms": 100, "unknown": 1},
])
def test_ducking_rejects_invalid_windows(window):
    with pytest.raises(ValueError):
        parse_ducking_windows([window], 3000)


@pytest.mark.parametrize("field,value", [("start_ms", -1), ("end_ms", 3001), ("x", -1),
                                        ("width", 200), ("opacity", float("nan")), ("opacity", 2)])
def test_overlay_validation_rejects_outside_timeline_or_frame(project, field, value):
    edit, _, logo, _ = project
    item = overlay(logo)
    item[field] = value
    edit["image_overlays"] = [item]
    with pytest.raises(ValueError):
        validate_edit(edit)


def test_image_hash_source_note_and_duration_are_required(project):
    edit, card, logo, _ = project
    item = overlay(logo)
    edit["image_overlays"] = [item]
    item["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        validate_edit(edit)
    item["sha256"] = sha(logo)
    item.pop("source_note")
    with pytest.raises(ValueError, match="source_note"):
        validate_edit(edit)
    edit["image_overlays"] = []
    edit["segments"] = [{"kind": "image", "path": str(card), "sha256": sha(card),
                         "source_note": "user card", "timeline_start_ms": 0, "duration_ms": 3500}]
    with pytest.raises(ValueError, match="总时长"):
        validate_edit(edit)  # no implicit picture extension


def test_new_layers_cannot_be_overwritten_by_output(project):
    edit, _, logo, _ = project
    edit["image_overlays"] = [overlay(logo)]
    before = logo.read_bytes()
    with pytest.raises(ValueError, match="覆盖"):
        render_edit(edit, logo)
    assert logo.read_bytes() == before


def test_shared_mixer_window_time_is_after_track_offset_and_replaces_legacy_duck(project):
    edit, _, _, folder = project
    song = json.loads(Path(edit["music_timeline"]).read_text())["source"]["path"]
    source = edit["segments"][0]["path"]
    plain, ducked = folder / "offset-plain.mp4", folder / "offset-ducked.mp4"
    for output, windows in ((plain, []), (ducked, [DuckingWindow(1000, 1500)])):
        result = AudioMixer().mix(AudioMixRequest(
            tracks=[AudioTrack(song, "music", offset_ms=500, duck_group="background", ducking_windows=windows),
                    AudioTrack(edit["sound_effects"][0]["path"], "dialogue", offset_ms=1200)],
            clip_duration_ms=3000, source_video_path=source, output_path=str(output), normalize_inputs=False,
        ))
        assert result.success, result.error
    assert rms(plain, 0.2, 0.15) < 5
    assert 20 * math.log10(rms(ducked, 1.1, 0.1) / rms(plain, 1.1, 0.1)) == pytest.approx(-12, abs=1)
    assert abs(20 * math.log10(rms(ducked, 0.65, 0.1) / rms(plain, 0.65, 0.1))) < 0.5
    assert abs(20 * math.log10(rms(ducked, 2.2, 0.2) / rms(plain, 2.2, 0.2))) < 0.5


def test_overlay_order_and_opacity_are_applied_to_alpha(project):
    edit, card, logo, folder = project
    edit["image_overlays"] = [overlay(logo), {**overlay(card), "opacity": 0.5,
                                             "start_ms": 900, "end_ms": 1300}]
    output = folder / "layers.mp4"
    render_edit(edit, output)
    before = pixel(output, 0.8, 14, 14)
    during = pixel(output, 1.0, 14, 14)
    after = pixel(output, 1.4, 14, 14)
    assert before[0] > 180 and after[0] > 180
    assert 70 < during[0] < 180 and 70 < during[1] < 180 and during[2] < 30


@pytest.mark.parametrize("key,value", [("music_ducking", [{"start_ms": 0, "end_ms": 10}]),
                                     ("image_overlays", [{}]), ("postroll_duration_ms", 100)])
def test_preview_does_not_silently_ignore_formal_effects(key, value):
    from lfo.media.mv_preview import validate_preview

    with pytest.raises(ValueError, match="正式后期"):
        validate_preview({"schema": "lfo.mv.preview.v1", key: value})
