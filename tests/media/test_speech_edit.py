"""Tests for bounded, speech-protected media edits."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe
from lfo.media.audio_qc import AudioQCReport
from lfo.media.speech_edit import (
    ConfirmedSilentInterval,
    ProtectedSpeechInterval,
    SpeechProtectedEditor,
    SpeechProtectedEditSpec,
)
from lfo.media.subtitles import SubtitleCue


def _fake_source(tmp_path: Path) -> Path:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source fixture")
    return source


def _patch_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lfo.media.speech_edit.probe",
        lambda _path: {"duration_ms": 1_000, "has_audio": True, "fps": 24.0},
    )


def test_plan_uses_actual_duration_and_maps_cues_over_removed_pause(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _fake_source(tmp_path)
    _patch_probe(monkeypatch)
    plan = SpeechProtectedEditor().plan(
        SpeechProtectedEditSpec(
            source_path=source,
            source_duration_ms=1_000,
            confirmed_silent_intervals=[ConfirmedSilentInterval(300, 500)],
            protected_speech_intervals=[
                ProtectedSpeechInterval(100, 200, tail_margin_ms=50, event_id="D001")
            ],
            subtitle_cues=[
                # This cue crosses the removed pause and should be split.
                SubtitleCue(0, 600, "line"),
                SubtitleCue(600, 900, "after"),
            ],
            audio_qc_report=AudioQCReport(passed=True, inconclusive=True),
        )
    )

    assert plan.source_duration_ms == 1_000
    assert plan.output_duration_ms == 800
    assert [(item.start_ms, item.end_ms) for item in plan.kept_intervals] == [
        (0, 300),
        (500, 1_000),
    ]
    assert [(cue.start_ms, cue.end_ms, cue.text) for cue in plan.mapped_subtitle_cues] == [
        (0, 300, "line"),
        (300, 400, "line"),
        (400, 700, "after"),
    ]
    assert plan.audio_qc_readiness == "review_required"
    assert plan.audio_review_required


def test_automatic_silence_detection_is_not_a_removal_authority() -> None:
    with pytest.raises(ValueError, match="automatic silence detection"):
        ConfirmedSilentInterval(100, 200, confirmation="vad")


def test_pause_overlapping_protected_speech_tail_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _fake_source(tmp_path)
    _patch_probe(monkeypatch)
    with pytest.raises(ValueError, match="overlaps protected speech"):
        SpeechProtectedEditor().plan(
            SpeechProtectedEditSpec(
                source_path=source,
                confirmed_silent_intervals=[ConfirmedSilentInterval(300, 400)],
                protected_speech_intervals=[ProtectedSpeechInterval(100, 320, tail_margin_ms=100)],
            )
        )


def test_failed_audio_report_allows_repair_planning_but_requires_new_review(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _fake_source(tmp_path)
    _patch_probe(monkeypatch)
    plan = SpeechProtectedEditor().plan(
        SpeechProtectedEditSpec(
            source_path=source,
            output_path=tmp_path / "output.mp4",
            audio_qc_report=AudioQCReport(passed=False),
        )
    )

    assert plan.audio_review_required
    assert plan.audio_qc_readiness == "rejected"


def test_required_tail_margin_cannot_be_silently_shortened(monkeypatch, tmp_path):
    _patch_probe(monkeypatch)
    with pytest.raises(ValueError, match="insufficient tail margin"):
        SpeechProtectedEditor().plan(
            SpeechProtectedEditSpec(
                source_path=_fake_source(tmp_path),
                protected_speech_intervals=[ProtectedSpeechInterval(100, 900, tail_margin_ms=200)],
            )
        )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_real_edit_keeps_video_audio_in_sync(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "edited.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=96x64:r=12:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
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

    result = SpeechProtectedEditor().apply(
        SpeechProtectedEditSpec(
            source_path=source,
            output_path=output,
            confirmed_silent_intervals=[ConfirmedSilentInterval(350, 550)],
            protected_speech_intervals=[ProtectedSpeechInterval(100, 250, tail_margin_ms=50)],
            subtitle_cues=[],
        )
    )

    assert result.success, result.error
    assert output.is_file()
    metadata = probe(output)
    assert metadata["has_audio"]
    assert 700 <= metadata["duration_ms"] <= 900
