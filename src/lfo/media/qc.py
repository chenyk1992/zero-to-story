"""Generation-output review for media tasks.

The runtime deliberately keeps this stage small.  H3 is responsible for the
visual interpretation of the approved prompt, while audio mixing and boundary
evidence have their own operational checks.  This module therefore only asks
whether the generation handler produced a non-empty artifact.  It does not
probe or judge duration, resolution, frame rate, codecs, audio streams, black
frames, freeze frames, mid-shot actions, identity/space continuity, props, or
on-screen text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QCRuleResult:
    """Result of a single generation-quality rule."""

    rule: str
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class QCReport:
    """Aggregated generation-quality result for a media artifact."""

    passed: bool
    results: list[QCRuleResult] = field(default_factory=list)
    asset_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failures(self) -> list[QCRuleResult]:
        return [result for result in self.results if not result.passed]


@dataclass(frozen=True)
class GenerationQualityContract:
    """Minimal contract for the generation-output gate.

    ``require_artifact`` is intentionally the only policy here.  Output
    encoding and audio policy are handled by their respective pipeline stages;
    semantic review is an operator decision outside the LFO runtime gate.
    """

    require_artifact: bool = True


class GenerationQualityQC:
    """Check only that generation returned a usable file artifact."""

    def check(
        self,
        artifact_path: str | Path | None,
        contract: GenerationQualityContract | None = None,
    ) -> QCReport:
        policy = contract or GenerationQualityContract()
        path = Path(artifact_path) if artifact_path is not None else None
        try:
            exists = path is not None and path.is_file()
            size = path.stat().st_size if exists and path is not None else 0
        except OSError:
            # A provider may finish while its managed copy is still being
            # released or become unreadable.  Treat that as a retryable empty
            # artifact rather than allowing the QC handler to crash the run.
            exists = False
            size = 0
        non_empty = exists and size > 0
        passed = non_empty if policy.require_artifact else True
        result = QCRuleResult(
            rule="generation_artifact",
            passed=passed,
            message="" if passed else "Generated artifact is missing or empty",
            expected="non-empty file" if policy.require_artifact else "optional",
            actual=(str(path), size) if path is not None else None,
        )
        return QCReport(
            passed=passed,
            results=[result],
            asset_metadata={
                "file_path": str(path) if path is not None else None,
                "file_size": size,
            },
        )


__all__ = [
    "GenerationQualityContract",
    "GenerationQualityQC",
    "QCReport",
    "QCRuleResult",
]
