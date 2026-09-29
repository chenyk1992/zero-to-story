from __future__ import annotations

import hashlib
import json
import math
import os
import wave
from array import array
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe, run_command
from lfo.media.music_timeline import inspect_music


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixtures(tmp_path: Path):
    song = tmp_path / "song.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=330:duration=3", "-c:a", "flac", str(song)])
    timeline = inspect_music(song, start_ms=500, end_ms=2500)
    timeline_path = tmp_path / "music_timeline.json"
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    clips = []
    for index, color in enumerate(("red", "blue"), start=1):
        clip = tmp_path / f"clip{index}.mp4"
        run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                     "-i", f"color=c={color}:s=320x240:r=25:d=1.6", "-c:v", "libx264",
                     "-pix_fmt", "yuv420p", str(clip)])
        clips.append(clip)
    edit = {
        "schema": "lfo.mv.edit.v1", "music_timeline": str(timeline_path),
        "width": 320, "height": 240, "fps": 25,
        "native_audio_strategy": "replace", "sound_effects": [], "text_events": [],
        "segments": [
            {"run_id": f"run-{index}", "path": str(clip), "sha256": digest(clip),
             "source_in_ms": 0, "source_out_ms": 1000, "timeline_start_ms": (index - 1) * 1000,
             "transition": "cut"}
            for index, clip in enumerate(clips, start=1)
        ],
    }
    return edit, clips, song


def test_edit_rejects_gaps_overlaps_hash_changes_and_source_overruns(tmp_path):
    from lfo.media.mv_edit import validate_edit

    edit, clips, _ = fixtures(tmp_path)
    validate_edit(edit)
    edit["segments"][1]["timeline_start_ms"] = 1100
    with pytest.raises(ValueError, match="空洞|重叠|连续"):
        validate_edit(edit)
    edit["segments"][1]["timeline_start_ms"] = 1000
    edit["segments"][0]["source_out_ms"] = 2000
    with pytest.raises(ValueError, match="源片"):
        validate_edit(edit)
    edit["segments"][0]["source_out_ms"] = 1000
    edit["segments"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        validate_edit(edit)
    edit["segments"][0]["sha256"] = digest(clips[0])
    edit["segments"][0]["transition"] = "dissolve"
    with pytest.raises(ValueError, match="转场"):
        validate_edit(edit)


def test_render_cut_edit_with_middle_song_window_and_verified_lyrics(tmp_path):
    from lfo.media.mv_edit import render_edit

    edit, clips, song = fixtures(tmp_path)
    effect = tmp_path / "effect.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=990:duration=0.3", "-c:a", "flac", str(effect)])
    edit["sound_effects"] = [{"path": str(effect), "sha256": digest(effect), "source_in_ms": 0,
                              "source_out_ms": 300, "timeline_start_ms": 1300, "gain_db": -12}]
    edit["text_events"] = [{"start_ms": 800, "end_ms": 1400, "text": "天亮了！", "kind": "lyric", "status": "verified"}]
    output = tmp_path / "mv.mp4"
    result = render_edit(edit, output)
    assert output.is_file() and result["sha256"] == digest(output)
    assert result["listening_status"] == "INCONCLUSIVE"
    assert 1900 <= probe(output)["duration_ms"] <= 2100
    assert probe(output)["has_audio"] is True
    assert result["lyric_count"] == 1
    sampled = []
    for index, second in enumerate((0.2, 1.2)):
        pixel = tmp_path / f"pixel-{index}.rgb"
        run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-ss", str(second),
                     "-i", str(output), "-frames:v", "1", "-vf", "crop=2:2:0:0",
                     "-pix_fmt", "rgb24", "-f", "rawvideo", str(pixel)])
        sampled.append(pixel.read_bytes()[:3])
    assert sampled[0][0] > sampled[0][2] and sampled[1][2] > sampled[1][0]
    with pytest.raises(ValueError, match="覆盖"):
        render_edit(edit, clips[0])


def test_unverified_lyric_cannot_be_rendered(tmp_path):
    from lfo.media.mv_edit import validate_edit

    edit, _, _ = fixtures(tmp_path)
    edit["text_events"] = [{"start_ms": 800, "end_ms": 1400, "text": "也许", "kind": "lyric", "status": "candidate"}]
    with pytest.raises(ValueError, match="核对"):
        validate_edit(edit)


def test_many_short_cuts_follow_cumulative_frame_boundaries(tmp_path):
    from lfo.media.mv_edit import render_edit

    edit, clips, song = fixtures(tmp_path)
    timeline = inspect_music(song, start_ms=500, end_ms=1600)
    Path(edit["music_timeline"]).write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    edit["segments"] = [
        {"run_id": f"run-{index}", "path": str(clips[0]), "sha256": digest(clips[0]),
         "source_in_ms": 0, "source_out_ms": 110, "timeline_start_ms": index * 110,
         "transition": "cut"}
        for index in range(10)
    ]
    result = render_edit(edit, tmp_path / "short-cuts.mp4")
    assert result["video_frame_count"] == 28
    assert [part["output_frame_count"] for part in result["segments"]] == [3, 3, 2, 3, 3, 2, 3, 3, 3, 3]


def test_non_frame_aligned_source_in_is_snapped_and_reported(tmp_path):
    from lfo.media.mv_edit import render_edit

    edit, clips, song = fixtures(tmp_path)
    timeline = inspect_music(song, start_ms=500, end_ms=700)
    Path(edit["music_timeline"]).write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    edit["segments"] = [
        {"run_id": f"run-{index}", "path": str(clips[0]), "sha256": digest(clips[0]),
         "source_in_ms": 20, "source_out_ms": 120, "timeline_start_ms": index * 100,
         "transition": "cut"}
        for index in range(2)
    ]
    result = render_edit(edit, tmp_path / "unaligned.mp4")
    assert result["video_frame_count"] == 5
    assert [part["output_frame_count"] for part in result["segments"]] == [2, 3]
    assert [part["source_trim_in_ms"] for part in result["segments"]] == [0, 0]


def test_rejects_source_range_longer_than_video_stream(tmp_path):
    from lfo.media.mv_edit import validate_edit

    edit, clips, _ = fixtures(tmp_path)
    long_audio = tmp_path / "long-audio.mp4"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "color=c=red:s=320x240:r=25:d=1", "-f", "lavfi",
                 "-i", "sine=frequency=330:duration=3", "-c:v", "libx264",
                 "-c:a", "aac", str(long_audio)])
    edit["segments"] = [{"run_id": "long-audio", "path": str(long_audio), "sha256": digest(long_audio),
                         "source_in_ms": 0, "source_out_ms": 2000, "timeline_start_ms": 0,
                         "transition": "cut"}]
    with pytest.raises(ValueError, match="视频流|源片"):
        validate_edit(edit)


def test_subtitle_renders_beneath_apostrophe_parent(tmp_path):
    from lfo.media.mv_edit import render_edit

    edit, _, _ = fixtures(tmp_path)
    edit["text_events"] = [{"start_ms": 800, "end_ms": 1400, "text": "灯亮了", "kind": "lyric", "status": "verified"}]
    folder = tmp_path / "O'Brien"
    folder.mkdir()
    result = render_edit(edit, folder / "mv.mp4")
    assert Path(result["path"]).is_file()
    assert result["lyric_count"] == 1


def test_sound_effect_does_not_lower_the_whole_master_song(tmp_path):
    from lfo.media.mv_edit import render_edit

    edit, _, _ = fixtures(tmp_path)
    plain = tmp_path / "plain.mp4"
    with_effect = tmp_path / "with-effect.mp4"
    render_edit(edit, plain)
    effect = tmp_path / "effect.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=990:duration=0.3", "-c:a", "flac", str(effect)])
    edit["sound_effects"] = [{"path": str(effect), "sha256": digest(effect), "source_in_ms": 0,
                              "source_out_ms": 300, "timeline_start_ms": 1300, "gain_db": -6}]
    render_edit(edit, with_effect)

    def rms(path: Path) -> float:
        pcm = tmp_path / f"{path.stem}.wav"
        run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-ss", "0.2",
                     "-t", "0.6", "-i", str(path), "-vn", "-ar", "16000", "-ac", "1",
                     "-c:a", "pcm_s16le", str(pcm)])
        with wave.open(str(pcm), "rb") as stream:
            samples = array("h")
            samples.frombytes(stream.readframes(stream.getnframes()))
        return math.sqrt(sum(sample * sample for sample in samples) / len(samples))

    assert abs(20 * math.log10(rms(with_effect) / rms(plain))) < 0.75
