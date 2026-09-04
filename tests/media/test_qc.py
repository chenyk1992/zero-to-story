"""Tests for the intentionally narrow generation-quality gate."""

from __future__ import annotations

import lfo.media.qc as qc_module
from lfo.media.qc import GenerationQualityContract, GenerationQualityQC


class TestGenerationQualityQC:
    def test_non_empty_generation_artifact_passes(self, tmp_path) -> None:
        artifact = tmp_path / "generated.mp4"
        artifact.write_bytes(b"provider output")

        report = GenerationQualityQC().check(artifact)

        assert report.passed
        assert report.failures == []
        assert [result.rule for result in report.results] == ["generation_artifact"]
        assert report.asset_metadata["file_size"] == len(b"provider output")

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

    def test_technical_and_semantic_rules_are_not_exposed(self) -> None:
        assert not hasattr(qc_module, "TechnicalQC")
        assert not hasattr(qc_module, "QCContract")
        assert not hasattr(GenerationQualityContract, "expected_width")
        assert not hasattr(GenerationQualityContract, "expected_fps")
        assert not hasattr(GenerationQualityContract, "expected_codec")
