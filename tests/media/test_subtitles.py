"""Tests for subtitle renderer."""

from __future__ import annotations

from lfo.media.subtitles import (
    SubtitleCue,
    clip_local_to_global_cues,
    cues_to_srt,
    cues_to_vtt,
    parse_srt,
    parse_vtt,
    trim_cues,
    validate_srt,
)


class TestCuesToSrt:
    def test_single_cue(self) -> None:
        cues = [SubtitleCue(start_ms=0, end_ms=3000, text="Hello world")]
        srt = cues_to_srt(cues)
        assert "1" in srt
        assert "00:00:00,000 --> 00:00:03,000" in srt
        assert "Hello world" in srt

    def test_multiple_cues(self) -> None:
        cues = [
            SubtitleCue(start_ms=0, end_ms=2000, text="First"),
            SubtitleCue(start_ms=2500, end_ms=5000, text="Second"),
        ]
        srt = cues_to_srt(cues)
        assert "1\n" in srt
        assert "2\n" in srt
        assert "First" in srt
        assert "Second" in srt

    def test_time_formatting(self) -> None:
        cues = [SubtitleCue(start_ms=3_661_001, end_ms=3_662_000, text="Test")]
        srt = cues_to_srt(cues)
        assert "01:01:01,001 --> 01:01:02,000" in srt

    def test_empty_cues(self) -> None:
        assert cues_to_srt([]).strip() == ""


class TestCuesToVtt:
    def test_header(self) -> None:
        cues = [SubtitleCue(start_ms=0, end_ms=1000, text="Hi")]
        vtt = cues_to_vtt(cues)
        assert vtt.startswith("WEBVTT")

    def test_time_format(self) -> None:
        cues = [SubtitleCue(start_ms=1500, end_ms=3000, text="Hello")]
        vtt = cues_to_vtt(cues)
        assert "00:00:01.500 --> 00:00:03.000" in vtt


class TestValidateSrt:
    def test_valid_srt(self) -> None:
        srt = "1\n00:00:00,000 --> 00:00:03,000\nHello\n\n2\n00:00:03,000 --> 00:00:05,000\nWorld"
        errors = validate_srt(srt)
        assert errors == []

    def test_missing_arrow(self) -> None:
        srt = "1\n00:00:00,000 -- 00:00:03,000\nHello"
        errors = validate_srt(srt)
        assert len(errors) == 1

    def test_parse_external_subtitles(self) -> None:
        assert parse_srt("1\n00:00:01,000 --> 00:00:02,000\nHi") == [SubtitleCue(1000, 2000, "Hi")]
        assert parse_vtt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi") == [SubtitleCue(1000, 2000, "Hi")]


class TestClipLocalToGlobal:
    def test_offset_applied(self) -> None:
        cues = [SubtitleCue(start_ms=1000, end_ms=2000, text="Hi")]
        global_cues = clip_local_to_global_cues(cues, 5000)
        assert global_cues[0].start_ms == 6000
        assert global_cues[0].end_ms == 7000

    def test_trim_cues_intersects_and_rebases_to_edit_time(self) -> None:
        cues = [
            SubtitleCue(0, 1100, "before"),
            SubtitleCue(1200, 3200, "crosses head"),
            SubtitleCue(4000, 5000, "outside"),
        ]
        assert trim_cues(cues, 1000, 3500) == [
            SubtitleCue(0, 100, "before"),
            SubtitleCue(200, 2200, "crosses head"),
        ]

    def test_clip_local_to_global_supports_source_trim(self) -> None:
        cues = clip_local_to_global_cues(
            [SubtitleCue(1000, 3000, "line")],
            5000,
            source_in_ms=1500,
        )
        assert cues == [SubtitleCue(5000, 6500, "line")]
