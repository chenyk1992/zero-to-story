"""Technical QC — validate generated media against materialized output contract.

QC rules check decodability, duration tolerance, resolution, fps, codec,
and audio presence against the contract defined at materialization time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QCRuleResult:
    """Result of a single QC rule check."""

    rule: str
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class QCReport:
    """Aggregated QC result for a media asset."""

    passed: bool
    results: list[QCRuleResult] = field(default_factory=list)
    asset_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failures(self) -> list[QCRuleResult]:
        return [r for r in self.results if not r.passed]


@dataclass
class QCContract:
    """The contract that generated output must satisfy."""

    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    tolerance_ms: int = 500  # acceptable duration deviation
    expected_width: int | None = None
    expected_height: int | None = None
    expected_fps: float | None = None
    expected_codec: str | None = None
    requires_audio: bool | None = None  # None = don't care
    min_width: int | None = None
    min_height: int | None = None
    max_width: int | None = None
    max_height: int | None = None


class TechnicalQC:
    """Run QC checks against a contract."""

    def check(self, probe_result: dict[str, Any], contract: QCContract) -> QCReport:
        """Run all QC checks.

        Args:
            probe_result: ffprobe-like metadata dict with keys like
                duration_ms, width, height, fps, codec, has_audio.
            contract: The QC contract to validate against.

        Returns:
            QCReport with per-rule results and overall pass/fail.
        """
        results: list[QCRuleResult] = []

        results.append(self.check_decodable(probe_result))
        results.append(self.check_duration(probe_result, contract))
        results.append(self.check_resolution(probe_result, contract))
        results.append(self.check_fps(probe_result, contract))
        results.append(self.check_codec(probe_result, contract))
        results.append(self.check_audio(probe_result, contract))

        overall_passed = all(r.passed for r in results)
        return QCReport(
            passed=overall_passed,
            results=results,
            asset_metadata=dict(probe_result),
        )

    def check_decodable(self, probe_result: dict[str, Any]) -> QCRuleResult:
        """Check the media is decodable (has basic stream info)."""
        has_video = probe_result.get("width") is not None and probe_result.get("height") is not None
        return QCRuleResult(
            rule="decodable",
            passed=has_video,
            message="" if has_video else "No video stream found",
        )

    def check_duration(
        self, probe_result: dict[str, Any], contract: QCContract,
    ) -> QCRuleResult:
        """Check duration is within tolerance of expected."""
        actual = probe_result.get("duration_ms")
        if actual is None:
            return QCRuleResult(rule="duration", passed=False, message="No duration info")

        # Check min/max constraints
        if contract.min_duration_ms is not None and actual < contract.min_duration_ms:
            return QCRuleResult(
                rule="duration", passed=False,
                message=f"Duration {actual}ms < min {contract.min_duration_ms}ms",
                expected=contract.min_duration_ms, actual=actual,
            )
        if contract.max_duration_ms is not None and actual > contract.max_duration_ms:
            return QCRuleResult(
                rule="duration", passed=False,
                message=f"Duration {actual}ms > max {contract.max_duration_ms}ms",
                expected=contract.max_duration_ms, actual=actual,
            )
        return QCRuleResult(rule="duration", passed=True)

    def check_resolution(
        self, probe_result: dict[str, Any], contract: QCContract,
    ) -> QCRuleResult:
        """Check resolution matches expected or is within bounds."""
        width = probe_result.get("width")
        height = probe_result.get("height")
        if width is None or height is None:
            return QCRuleResult(rule="resolution", passed=False, message="No resolution info")

        # Exact match if expected
        if contract.expected_width is not None and width != contract.expected_width:
            return QCRuleResult(
                rule="resolution", passed=False,
                message=f"Width {width} != expected {contract.expected_width}",
                expected=contract.expected_width, actual=width,
            )
        if contract.expected_height is not None and height != contract.expected_height:
            return QCRuleResult(
                rule="resolution", passed=False,
                message=f"Height {height} != expected {contract.expected_height}",
                expected=contract.expected_height, actual=height,
            )
        # Bounds check
        if contract.min_width is not None and width < contract.min_width:
            return QCRuleResult(rule="resolution", passed=False,
                message=f"Width {width} < min {contract.min_width}")
        if contract.max_width is not None and width > contract.max_width:
            return QCRuleResult(rule="resolution", passed=False,
                message=f"Width {width} > max {contract.max_width}")
        return QCRuleResult(rule="resolution", passed=True)

    def check_fps(
        self, probe_result: dict[str, Any], contract: QCContract,
    ) -> QCRuleResult:
        """Check fps matches expected."""
        if contract.expected_fps is None:
            return QCRuleResult(rule="fps", passed=True)
        actual = probe_result.get("fps")
        if actual is None:
            return QCRuleResult(rule="fps", passed=False, message="No fps info")
        if abs(float(actual) - float(contract.expected_fps)) > 0.01:
            return QCRuleResult(
                rule="fps", passed=False,
                message=f"FPS {actual} != expected {contract.expected_fps}",
                expected=contract.expected_fps, actual=actual,
            )
        return QCRuleResult(rule="fps", passed=True)

    def check_codec(
        self, probe_result: dict[str, Any], contract: QCContract,
    ) -> QCRuleResult:
        """Check codec matches expected."""
        if contract.expected_codec is None:
            return QCRuleResult(rule="codec", passed=True)
        actual = probe_result.get("codec")
        if actual is None:
            return QCRuleResult(rule="codec", passed=False, message="No codec info")
        if actual != contract.expected_codec:
            return QCRuleResult(
                rule="codec", passed=False,
                message=f"Codec {actual} != expected {contract.expected_codec}",
                expected=contract.expected_codec, actual=actual,
            )
        return QCRuleResult(rule="codec", passed=True)

    def check_audio(
        self, probe_result: dict[str, Any], contract: QCContract,
    ) -> QCRuleResult:
        """Check audio presence matches contract."""
        if contract.requires_audio is None:
            return QCRuleResult(rule="audio", passed=True)
        has_audio = probe_result.get("has_audio", False)
        if contract.requires_audio and not has_audio:
            return QCRuleResult(rule="audio", passed=False, message="Audio required but missing")
        if not contract.requires_audio and has_audio:
            return QCRuleResult(rule="audio", passed=False, message="Audio present but not expected")
        return QCRuleResult(rule="audio", passed=True)
