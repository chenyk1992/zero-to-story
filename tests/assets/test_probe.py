"""Tests for media probing."""
from __future__ import annotations

import json
import pathlib
from unittest import mock

import pytest

from lfo.assets.probe import MediaProbe, ProbeResult


class TestHeaderSniffing:
    """Test magic-byte header detection without ffprobe."""

    def test_png_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "image"

    def test_jpeg_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "image.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 28)
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "image"

    def test_gif_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "anim.gif"
        f.write_bytes(b"GIF89a" + b"\x00" * 26)
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "image"

    def test_webvtt_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "sub.vtt"
        f.write_bytes(b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello")
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "subtitle"

    def test_pdf_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4" + b"\x00" * 24)
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "document"

    def test_mp4_detected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "vid.mp4"
        f.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 20)
        probe = MediaProbe(ffprobe_path=None)
        result = probe.probe(f)
        assert result.media_type == "video"

    def test_empty_file_rejected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "empty.png"
        f.write_bytes(b"")
        probe = MediaProbe(ffprobe_path=None)
        with pytest.raises(ValueError, match="empty"):
            probe.probe(f)

    def test_missing_file_rejected(self, tmp_path: pathlib.Path) -> None:
        probe = MediaProbe(ffprobe_path=None)
        with pytest.raises(FileNotFoundError):
            probe.probe(tmp_path / "ghost.png")

    def test_oversized_rejected(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "big.bin"
        f.write_bytes(b"\x00" * 100)
        probe = MediaProbe(ffprobe_path=None, max_file_size=10)
        with pytest.raises(ValueError, match="max size"):
            probe.probe(f)


class TestFfprobeParsing:
    """Test ffprobe JSON parsing (mocked subprocess)."""

    def test_parse_video(self) -> None:
        probe = MediaProbe(ffprobe_path="/fake/ffprobe")
        data = {
            "format": {"duration": "10.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }
        result = probe._parse_ffprobe(data, None)
        assert result.media_type == "video"
        assert result.width == 1920
        assert result.height == 1080
        assert result.duration_ms == 10500.0
        assert result.fps == 30.0
        assert result.codec == "h264"
        assert result.has_audio is True
        assert result.audio_codec == "aac"
        assert result.sample_rate == 48000
        assert result.channels == 2

    def test_parse_audio_only(self) -> None:
        probe = MediaProbe(ffprobe_path="/fake/ffprobe")
        data = {
            "format": {"duration": "60.0"},
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 2,
                }
            ],
        }
        result = probe._parse_ffprobe(data, None)
        assert result.media_type == "audio"
        assert result.has_audio is True
        assert result.width is None
        assert result.height is None

    def test_parse_fps_decimal(self) -> None:
        probe = MediaProbe(ffprobe_path="/fake/ffprobe")
        assert probe._parse_fps("29.970000") == pytest.approx(29.97)
        assert probe._parse_fps("24/1") == 24.0
        assert probe._parse_fps("30000/1001") == pytest.approx(29.97, abs=0.01)
        assert probe._parse_fps(None) is None
        assert probe._parse_fps("0/0") is None

    def test_probe_calls_ffprobe(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "vid.mp4"
        f.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 20)
        probe = MediaProbe(ffprobe_path="/fake/ffprobe")
        ffprobe_output = json.dumps({
            "format": {"duration": "5.0", "format_name": "mov,mp4"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1280,
                    "height": 720,
                    "r_frame_rate": "24/1",
                }
            ],
        })
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0,
                stdout=ffprobe_output,
                stderr="",
            )
            result = probe.probe(f)
            assert result.media_type == "video"
            assert result.width == 1280
            assert result.height == 720
            mock_run.assert_called_once()
            # Verify ffprobe was called with the file path.
            cmd = mock_run.call_args[0][0]
            assert str(f) in cmd

    def test_ffprobe_failure_falls_back(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "vid.mp4"
        f.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 20)
        probe = MediaProbe(ffprobe_path="/fake/ffprobe")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1,
                stdout="",
                stderr="Invalid data",
            )
            result = probe.probe(f)
            # Falls back to header sniffing.
            assert result.media_type == "video"


class TestProbeResult:
    def test_to_dict(self) -> None:
        pr = ProbeResult(
            media_type="video",
            width=1920,
            height=1080,
            duration_ms=5000.0,
            fps=24.0,
            codec="h264",
            has_audio=True,
            audio_codec="aac",
        )
        d = pr.to_dict()
        assert d == {
            "media_type": "video",
            "width": 1920,
            "height": 1080,
            "duration_ms": 5000.0,
            "fps": 24.0,
            "codec": "h264",
            "has_audio": True,
            "audio_codec": "aac",
        }

    def test_to_dict_minimal(self) -> None:
        pr = ProbeResult(media_type="document")
        assert pr.to_dict() == {"media_type": "document"}
