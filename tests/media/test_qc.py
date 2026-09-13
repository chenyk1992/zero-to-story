"""Tests for the intentionally narrow generation-quality gate."""

from __future__ import annotations

import pytest

import lfo.media.qc as qc_module
from lfo.media.qc import GenerationQualityContract, GenerationQualityQC


class TestGenerationQualityQC:
    def test_valid_video_passes_minimal_technical_gate(self, tmp_path, monkeypatch) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"provider output")
        monkeypatch.setattr(qc_module, "probe", lambda path: {
            "duration_ms": 5000,
            "width": 720,
            "height": 1280,
            "codec": "h264",
        })

        report = GenerationQualityQC().check(artifact)

        assert report.passed
        assert report.failures == []
        assert [result.rule for result in report.results] == [
            "decodable", "video_stream", "duration", "resolution",
        ]
        assert report.asset_metadata["file_size"] == len(b"provider output")

    def test_unreadable_video_fails_decode_check(self, tmp_path, monkeypatch) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"not a video")
        monkeypatch.setattr(qc_module, "probe", lambda path: (_ for _ in ()).throw(ValueError("bad media")))

        report = GenerationQualityQC().check(artifact)

        assert not report.passed
        assert report.failures[0].rule == "decodable"

    def test_invalid_technical_metadata_fails_without_semantic_checks(
        self, tmp_path, monkeypatch
    ) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"provider output")
        monkeypatch.setattr(qc_module, "probe", lambda path: {
            "duration_ms": 0,
            "width": 0,
            "height": 1280,
            "codec": "h264",
        })

        report = GenerationQualityQC().check(artifact)

        assert not report.passed
        assert {item.rule for item in report.failures} == {"duration", "video_stream", "resolution"}

    def test_missing_artifact_fails(self, tmp_path) -> None:
        report = GenerationQualityQC().check(tmp_path / "missing.mp4")

        assert not report.passed
        assert report.failures[0].rule == "generation_artifact"

    def test_empty_artifact_fails(self, tmp_path) -> None:
        artifact = tmp_path / "empty.mp4"
        artifact.touch()

        report = GenerationQualityQC().check(artifact)

        assert not report.passed
        assert "missing or empty" in report.failures[0].message

    def test_optional_artifact_policy_is_supported(self, tmp_path) -> None:
        report = GenerationQualityQC().check(
            tmp_path / "not-created.mp4",
            GenerationQualityContract(require_artifact=False),
        )

        assert report.passed

    @pytest.mark.parametrize("duration", [float("nan"), float("inf"), float("-inf")])
    def test_nonfinite_duration_fails(self, tmp_path, monkeypatch, duration) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"provider output")
        monkeypatch.setattr(qc_module, "probe", lambda path: {
            "duration_ms": duration,
            "width": 720,
            "height": 1280,
            "codec": "h264",
        })

        report = GenerationQualityQC().check(artifact)

        assert not report.passed
        assert any(result.rule == "duration" for result in report.failures)

    @pytest.mark.parametrize("width,height", [(True, 720), (720, False)])
    def test_boolean_resolution_value_fails(self, tmp_path, monkeypatch, width, height) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"provider output")
        monkeypatch.setattr(qc_module, "probe", lambda path: {
            "duration_ms": 5000,
            "width": width,
            "height": height,
            "codec": "h264",
        })

        report = GenerationQualityQC().check(artifact)

        assert not report.passed
        assert {result.rule for result in report.failures} >= {"video_stream", "resolution"}

    def test_technical_and_semantic_rules_are_not_exposed(self) -> None:
        assert not hasattr(qc_module, "TechnicalQC")
        assert not hasattr(qc_module, "QCContract")
