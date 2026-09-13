"""The small technical gate used after a video-producing task.

This gate does not attempt to judge the creative result. It only verifies that the
provider returned a real, readable video with a positive duration and usable
dimensions.  There is no semantic scoring or repair route here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe


@dataclass
class QCRuleResult:
    """Result of one small technical check."""

    rule: str
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class QCReport:
    """Aggregated result for one generated video."""

    passed: bool
    results: list[QCRuleResult] = field(default_factory=list)
    asset_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failures(self) -> list[QCRuleResult]:
        return [result for result in self.results if not result.passed]


@dataclass(frozen=True)
class GenerationQualityContract:
    """Minimal technical expectations for a generated video.

    The execution gate deliberately checks only objective technical usability;
    semantic quality and continuity remain outside the runtime.
    """

    require_artifact: bool = True


class GenerationQualityQC:
    """Check that a provider artifact is a usable video file."""

    def check(
        self,
        artifact_path: str | Path | None,
        contract: GenerationQualityContract | None = None,
    ) -> QCReport:
        policy = contract or GenerationQualityContract()
        path = Path(artifact_path) if artifact_path is not None else None
        try:
            file_size = path.stat().st_size if path is not None and path.is_file() else 0
        except OSError:
            file_size = 0
        if file_size <= 0:
            passed = not policy.require_artifact
            result = QCRuleResult(
                rule="generation_artifact",
                passed=passed,
                message="Generated artifact is missing or empty" if not passed else "",
                expected="non-empty file" if policy.require_artifact else "optional",
                actual=(str(path), 0) if path is not None else None,
            )
            return QCReport(
                passed=passed,
                results=[result],
                asset_metadata={
                    "file_path": str(path) if path is not None else None,
                    "file_size": 0,
                },
            )

        assert path is not None
        try:
            metadata = probe(path)
        except Exception as exc:
            result = QCRuleResult(
                rule="decodable",
                passed=False,
                message=f"Generated artifact cannot be decoded: {exc}",
                expected="ffprobe-readable video",
                actual=str(path),
            )
            return QCReport(
                passed=False,
                results=[result],
                asset_metadata={"file_path": str(path), "file_size": file_size},
            )

        metadata = dict(metadata)
        results = [
            QCRuleResult(
                rule="decodable",
                passed=True,
                expected="ffprobe-readable media",
                actual="readable",
            ),
            self._video_stream(metadata),
            self._duration(metadata),
            self._resolution(metadata),
        ]
        return QCReport(
            passed=all(result.passed for result in results),
            results=results,
            asset_metadata={"file_path": str(path), "file_size": file_size, **metadata},
        )

    @staticmethod
    def _video_stream(metadata: dict[str, Any]) -> QCRuleResult:
        width = metadata.get("width")
        height = metadata.get("height")
        codec = metadata.get("codec")
        passed = (
            _positive_dimension(width)
            and _positive_dimension(height)
            and isinstance(codec, str)
            and bool(codec)
        )
        return QCRuleResult(
            rule="video_stream",
            passed=passed,
            message="No usable video stream found" if not passed else "",
            expected="video stream with dimensions and codec",
            actual={"width": width, "height": height, "codec": codec},
        )

    @staticmethod
    def _duration(metadata: dict[str, Any]) -> QCRuleResult:
        actual = metadata.get("duration_ms")
        passed = _positive_finite_number(actual)
        return QCRuleResult(
            rule="duration",
            passed=passed,
            message="Video duration is missing or not positive" if not passed else "",
            expected="> 0 ms",
            actual=actual,
        )

    @staticmethod
    def _resolution(metadata: dict[str, Any]) -> QCRuleResult:
        width = metadata.get("width")
        height = metadata.get("height")
        passed = _positive_dimension(width) and _positive_dimension(height)
        return QCRuleResult(
            rule="resolution",
            passed=passed,
            message="Video resolution is missing or not positive" if not passed else "",
            expected="positive width and height",
            actual={"width": width, "height": height},
        )


def _positive_dimension(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


__all__ = [
    "GenerationQualityContract",
    "GenerationQualityQC",
    "QCReport",
    "QCRuleResult",
]
