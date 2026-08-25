"""Small end-to-end media pipeline test using actual FFmpeg files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.export import Exporter, ExportSpec
from lfo.media.subtitles import SubtitleCue, SubtitleRenderer
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_timeline_export_preserves_source_resolution_with_unicode_space_paths(tmp_path: Path) -> None:
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
    final_path = media_dir / "最终 成片.mp4"
    exported = Exporter().export(
        ExportSpec("run", "package", "ph", "mh", str(final_path)), str(timeline_path)
    )
    assert exported.success, exported.error
    final_metadata = probe(final_path)
    assert final_metadata["duration_ms"] > 0
    assert final_metadata["width"] == 96
    assert final_metadata["height"] == 64


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
