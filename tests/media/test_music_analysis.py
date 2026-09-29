from __future__ import annotations

import os

import pytest

from lfo.media._ffmpeg import run_command


def test_silence_has_no_reliable_beat_or_bpm(tmp_path):
    from lfo.media.music_analysis import analyze_music

    path = tmp_path / "silence.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "anullsrc=r=22050:cl=mono", "-t", "2", "-c:a", "flac", str(path)])
    try:
        result = analyze_music(path)
    except RuntimeError as exc:
        if "librosa" in str(exc):
            pytest.skip("librosa not installed in project Python; tested separately in configured analysis environment")
        raise
    assert result["analysis"]["bpm_candidates"] == []
    assert result["beats"] == []
    assert result["listening_status"] == "INCONCLUSIVE"


def test_analysis_never_claims_lyric_or_section_verification(tmp_path):
    from lfo.media.music_analysis import analyze_music

    path = tmp_path / "pulse.flac"
    run_command([os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-f", "lavfi",
                 "-i", "sine=frequency=880:duration=3", "-c:a", "flac", str(path)])
    try:
        result = analyze_music(path)
    except RuntimeError as exc:
        if "librosa" in str(exc):
            pytest.skip("librosa not installed in project Python; tested separately in configured analysis environment")
        raise
    assert result["lyrics"] == result["sections"] == []
    assert result["listening_status"] == "INCONCLUSIVE"
    assert all(beat["status"] == "candidate" for beat in result["beats"])
