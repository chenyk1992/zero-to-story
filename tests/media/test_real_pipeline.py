"""Small end-to-end media pipeline test using actual FFmpeg files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.subtitles import SubtitleCue, SubtitleRenderer
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_timeline_preserves_source_resolution_with_unicode_space_paths(tmp_path: Path) -> None:
    media_dir = tmp_path / "媒体 文件"
    media_dir.mkdir()
    source = media_dir / "原始 片段.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=96x64:rate=12:duration=0.4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.4",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    timeline_path = media_dir / "时间线.mp4"
    timeline = TimelineAssembler().assemble(
        TimelineSpec(
            segments=[ClipSegment("clip", str(source), 400)], output_path=str(timeline_path)
        )
    )
    assert timeline.success, timeline.error
    assert not list(media_dir.glob(".*.concat.txt"))
    timeline_metadata = probe(timeline_path)
    assert timeline_metadata["duration_ms"] > 0
    assert timeline_metadata["width"] == 96
    assert timeline_metadata["height"] == 64


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_timeline_applies_exact_source_trim(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=96x64:rate=12:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "trimmed.mp4"
    result = TimelineAssembler().assemble(
        TimelineSpec(
            segments=[
                ClipSegment(
                    "clip",
                    str(source),
                    1_000,
                    source_in_ms=200,
                    source_out_ms=700,
                )
            ],
            output_path=str(output),
        )
    )
    assert result.success, result.error
    assert 450 <= probe(output)["duration_ms"] <= 600


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_audio_mix_and_subtitle_burnin(tmp_path: Path) -> None:
    source = tmp_path / "input.mp4"
    audio = tmp_path / "music.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:d=0.3",
            "-an",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", str(audio)],
        check=True,
        capture_output=True,
    )
    mixed = tmp_path / "mixed.mp4"
    mix = AudioMixer().mix(
        AudioMixRequest(
            source_video_path=str(source),
            output_path=str(mixed),
            native_audio_strategy="replace",
            tracks=[AudioTrack(str(audio), "music", gain_db=-3)],
        )
    )
    assert mix.success, mix.error
    assert probe(mixed)["has_audio"]
    srt = tmp_path / "caption.srt"
    SubtitleRenderer().render_srt([SubtitleCue(0, 200, "Hello")], srt, duration_ms=300)
    burnin = tmp_path / "captioned.mp4"
    try:
        SubtitleRenderer().burn_in(mixed, srt, burnin)
    except Exception as exc:  # Some FFmpeg builds omit libass.
        pytest.skip(f"FFmpeg subtitle filter unavailable: {exc}")
    assert probe(burnin)["width"] == 64


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_audio_mix_pads_short_track_to_declared_clip_duration(tmp_path: Path) -> None:
    source = tmp_path / "silent-source.mp4"
    short_audio = tmp_path / "short.wav"
    mixed = tmp_path / "mixed.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:r=12:d=0.6",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.1",
            str(short_audio),
        ],
        check=True,
        capture_output=True,
    )
    result = AudioMixer().mix(
        AudioMixRequest(
            source_video_path=str(source),
            output_path=str(mixed),
            native_audio_strategy="replace",
            tracks=[AudioTrack(str(short_audio), "music")],
            clip_duration_ms=600,
        )
    )
    assert result.success, result.error
    metadata = probe(mixed)
    assert metadata["has_audio"]
    assert 550 <= metadata["duration_ms"] <= 700


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_timeline_normalizes_heterogeneous_segments_and_mixes_silence(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    output = tmp_path / "timeline.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=96x64:r=12:d=0.4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.4",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(first),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x96:r=15:d=0.4",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(second),
        ],
        check=True,
        capture_output=True,
    )
    result = TimelineAssembler().assemble(
        TimelineSpec(
            segments=[
                ClipSegment("first", str(first), 400),
                ClipSegment("second", str(second), 400),
            ],
            output_width=80,
            output_height=100,
            output_fps=24.0,
            output_path=str(output),
        )
    )
    assert result.success, result.error
    metadata = probe(output)
    assert metadata["width"] == 80
    assert metadata["height"] == 100
    assert metadata["has_audio"]
    assert metadata["fps"] == pytest.approx(24.0, abs=0.1)
    assert 650 <= metadata["duration_ms"] <= 900


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_timeline_keeps_all_silent_segments_without_an_audio_stream(tmp_path: Path) -> None:
    first = tmp_path / "silent-first.mp4"
    second = tmp_path / "silent-second.mp4"
    output = tmp_path / "silent-timeline.mp4"
    for path, size in ((first, "96x64"), (second, "64x96")):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={size}:r=12:d=0.25",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    result = TimelineAssembler().assemble(
        TimelineSpec(
            segments=[
                ClipSegment("first", str(first), 250),
                ClipSegment("second", str(second), 250),
            ],
            output_width=80,
            output_height=100,
            output_fps=24.0,
            output_path=str(output),
        )
    )
    assert result.success, result.error
    metadata = probe(output)
    assert not metadata["has_audio"]
    assert metadata["width"] == 80
    assert metadata["height"] == 100
