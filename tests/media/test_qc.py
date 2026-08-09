"""Tests for TechnicalQC."""
from __future__ import annotations

from lfo.media.qc import QCContract, TechnicalQC


class TestTechnicalQC:
    def test_passing_media(self) -> None:
        qc = TechnicalQC()
        probe = {
            "width": 1080, "height": 1920, "fps": 24.0,
            "duration_ms": 5000, "codec": "h264", "has_audio": True,
        }
        contract = QCContract(
            expected_width=1080, expected_height=1920,
            expected_fps=24.0, expected_codec="h264", requires_audio=True,
        )
        report = qc.check(probe, contract)
        assert report.passed
        assert len(report.failures) == 0

    def test_fails_resolution_mismatch(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 800, "height": 600, "fps": 24.0, "duration_ms": 5000, "codec": "h264"}
        contract = QCContract(expected_width=1080, expected_height=1920)
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "resolution" for r in report.failures)

    def test_fails_duration_too_short(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 24.0, "duration_ms": 100, "codec": "h264"}
        contract = QCContract(min_duration_ms=500)
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "duration" for r in report.failures)

    def test_fails_fps_mismatch(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 30.0, "duration_ms": 5000, "codec": "h264"}
        contract = QCContract(expected_fps=24.0)
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "fps" for r in report.failures)

    def test_fails_codec_mismatch(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 24.0, "duration_ms": 5000, "codec": "h265"}
        contract = QCContract(expected_codec="h264")
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "codec" for r in report.failures)

    def test_fails_audio_missing(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 24.0, "duration_ms": 5000, "codec": "h264", "has_audio": False}
        contract = QCContract(requires_audio=True)
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "audio" for r in report.failures)

    def test_not_decodable(self) -> None:
        qc = TechnicalQC()
        probe = {"duration_ms": 5000}
        contract = QCContract()
        report = qc.check(probe, contract)
        assert not report.passed
        assert any(r.rule == "decodable" for r in report.failures)

    def test_no_audio_required_passes_without_audio(self) -> None:
        """When audio is not required, absence of audio is OK."""
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 24.0, "duration_ms": 5000, "codec": "h264", "has_audio": False}
        contract = QCContract()
        report = qc.check(probe, contract)
        assert report.passed

    def test_duration_within_bounds(self) -> None:
        qc = TechnicalQC()
        probe = {"width": 1080, "height": 1920, "fps": 24.0, "duration_ms": 5000, "codec": "h264"}
        contract = QCContract(min_duration_ms=1000, max_duration_ms=60000)
        report = qc.check(probe, contract)
        assert report.passed
