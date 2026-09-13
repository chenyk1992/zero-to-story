"""Small, evidence-based audio checks.

The caller owns creative decisions and the final listening review.  This
module only checks hard audio requirements and treats speech analysis as
review evidence; it never judges visual content.
"""

from __future__ import annotations

import difflib
import itertools
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from lfo.media._ffmpeg import MediaCommandError, probe


class AudioAcceptanceReadiness(StrEnum):
    """Whether the report permits adoption without another audio review."""

    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SpeechEventExpectation:
    event_id: str
    speaker_id: str
    text: str
    start_ms: int
    end_ms: int
    allow_overlap: bool = False


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_speech_events(value: object) -> tuple[SpeechEventExpectation, ...]:
    """Read only complete, typed event declarations from an untrusted value."""
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    events: list[SpeechEventExpectation] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        event_id, speaker_id, text = (item.get(key) for key in ("event_id", "speaker_id", "text"))
        start_ms, end_ms = item.get("start_ms"), item.get("end_ms")
        if not all(
            isinstance(item_value, str) and item_value.strip()
            for item_value in (event_id, speaker_id, text)
        ):
            continue
        if not all(
            isinstance(item_value, int) and not isinstance(item_value, bool)
            for item_value in (start_ms, end_ms)
        ):
            continue
        events.append(
            SpeechEventExpectation(
                cast(str, event_id),
                cast(str, speaker_id),
                cast(str, text),
                cast(int, start_ms),
                cast(int, end_ms),
                item.get("allow_overlap") is True,
            )
        )
    return tuple(events)


@dataclass(frozen=True, slots=True)
class AudioAcceptanceContract:
    """The small portion of an audio contract this module can evaluate."""

    require_audio: bool | None = None
    max_peak_db: float | None = -0.1
    min_mean_db: float | None = -60.0
    timing_tolerance_ms: int = 300
    transcript_similarity: float = 0.90
    speech_events: tuple[SpeechEventExpectation, ...] = ()

    @classmethod
    def from_dict(cls, value: object) -> AudioAcceptanceContract | None:
        if not isinstance(value, Mapping):
            return None
        events = _parse_speech_events(value.get("speech_events", []))

        def _float(key: str, default: float | None) -> float | None:
            candidate = value.get(key, default)
            if candidate is None:
                return None
            number = _number(candidate)
            return default if number is None else number

        tolerance = value.get("timing_tolerance_ms", 300)
        if not isinstance(tolerance, int) or isinstance(tolerance, bool) or tolerance < 0:
            tolerance = 300
        similarity = _float("transcript_similarity", 0.90)
        if similarity is None or not 0 <= similarity <= 1:
            similarity = 0.90
        require_audio = value.get("require_audio")
        if not isinstance(require_audio, bool):
            require_audio = None
        return cls(
            require_audio=require_audio,
            max_peak_db=_float("max_peak_db", -0.1),
            min_mean_db=_float("min_mean_db", -60.0),
            timing_tolerance_ms=tolerance,
            transcript_similarity=similarity,
            speech_events=events,
        )


@dataclass(frozen=True, slots=True)
class AudioQCRuleResult:
    rule: str
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class AudioQCReport:
    passed: bool
    inconclusive: bool = False
    results: list[AudioQCRuleResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failures(self) -> list[AudioQCRuleResult]:
        return [result for result in self.results if not result.passed]

    @property
    def acceptance_readiness(self) -> AudioAcceptanceReadiness:
        """Return adoption state while keeping uncertain speech evidence reviewable."""
        if not self.passed:
            if self.failures and all(rule.rule.startswith("speech_") for rule in self.failures):
                return AudioAcceptanceReadiness.REVIEW_REQUIRED
            return AudioAcceptanceReadiness.REJECTED
        if self.inconclusive:
            return AudioAcceptanceReadiness.REVIEW_REQUIRED
        return AudioAcceptanceReadiness.READY

    @property
    def ready_for_acceptance(self) -> bool:
        """Whether no additional audio review is indicated by this report."""
        return self.acceptance_readiness is AudioAcceptanceReadiness.READY

    @property
    def requires_review(self) -> bool:
        """Whether the report passed but still needs an audio review."""
        return self.acceptance_readiness is AudioAcceptanceReadiness.REVIEW_REQUIRED


class AudioQualityQC:
    """Evaluate the declared audio stream and optional speech evidence."""

    def check(
        self,
        artifact_path: str | Path,
        contract: AudioAcceptanceContract | None = None,
        *,
        analysis: Mapping[str, Any] | None = None,
        probe_result: Mapping[str, Any] | None = None,
    ) -> AudioQCReport:
        path = Path(artifact_path)
        try:
            metadata = dict(probe_result) if probe_result is not None else dict(probe(path))
        except (MediaCommandError, OSError, ValueError, KeyError, TypeError) as exc:
            return AudioQCReport(
                passed=False,
                results=[
                    AudioQCRuleResult(
                        "audio_artifact",
                        False,
                        f"Audio artifact cannot be inspected: {exc}",
                        "probe-readable media",
                        str(path),
                    )
                ],
                metadata={"file_path": str(path)},
            )
        policy = contract or AudioAcceptanceContract()
        results: list[AudioQCRuleResult] = []
        inconclusive = False
        audio_value = metadata.get("has_audio")
        has_audio = audio_value if isinstance(audio_value, bool) else None
        if has_audio is None:
            return AudioQCReport(
                passed=True,
                inconclusive=True,
                results=[
                    AudioQCRuleResult(
                        "audio_stream",
                        True,
                        "audio presence is not a boolean; manual listening is required",
                        "boolean",
                        audio_value,
                    )
                ],
                metadata=metadata,
            )
        if policy.require_audio is not None:
            passed = has_audio == policy.require_audio
            results.append(
                AudioQCRuleResult(
                    "audio_stream",
                    passed,
                    "" if passed else "audio stream does not match the locked audio contract",
                    policy.require_audio,
                    has_audio,
                )
            )

        if not has_audio:
            # No signal checks can be meaningful without an audio stream.  The
            # stream rule above is the only hard result when audio is optional.
            return AudioQCReport(
                passed=all(result.passed for result in results),
                inconclusive=False,
                results=results,
                metadata=metadata,
            )

        analysis_map = analysis if isinstance(analysis, Mapping) else None
        status = str(analysis_map.get("status", "")).upper() if analysis_map else ""
        review_message: str | None = None
        review_expected: Any = None
        review_actual: Any = None
        if status == "INCONCLUSIVE":
            inconclusive = True
            review_message = "speech analyzer returned INCONCLUSIVE; manual listening is required"
            review_expected, review_actual = "PASS or a reviewed INCONCLUSIVE", status
        elif policy.speech_events and analysis_map is None:
            inconclusive = True
            review_message = "no speech-analysis evidence supplied; manual listening is required"
            review_expected = "analysis evidence"
        elif (
            policy.speech_events
            and analysis_map is not None
            and not isinstance(analysis_map.get("speech_events"), list)
        ):
            inconclusive = True
            review_message = "speech event evidence is unavailable; manual listening is required"
            review_expected = "speech_events array"

        if review_message is not None:
            results.append(
                AudioQCRuleResult(
                    "speech_analysis",
                    True,
                    review_message,
                    review_expected,
                    review_actual,
                )
            )

        if analysis_map is not None and status != "INCONCLUSIVE":
            inconclusive = self._check_signal_metrics(policy, analysis_map, results) or inconclusive
            if policy.speech_events:
                if isinstance(analysis_map.get("speech_events"), list):
                    self._check_speech_events(policy, analysis_map, results)

        passed = all(result.passed for result in results)
        return AudioQCReport(
            passed=passed,
            inconclusive=inconclusive,
            results=results,
            metadata=metadata,
        )

    @staticmethod
    def _check_signal_metrics(
        policy: AudioAcceptanceContract,
        analysis: Mapping[str, Any],
        results: list[AudioQCRuleResult],
    ) -> bool:
        inconclusive = False
        peak = _number(analysis.get("peak_db"))
        if policy.max_peak_db is not None and "peak_db" in analysis and peak is None:
            inconclusive = True
            results.append(
                AudioQCRuleResult(
                    "peak_headroom",
                    True,
                    "peak metric is unavailable; manual listening is required",
                    f"< {policy.max_peak_db} dB",
                    analysis.get("peak_db"),
                )
            )
        elif policy.max_peak_db is not None and peak is not None:
            passed = peak < policy.max_peak_db
            results.append(
                AudioQCRuleResult(
                    "peak_headroom",
                    passed,
                    "audio peak is at/over the clipping threshold" if not passed else "",
                    f"< {policy.max_peak_db} dB",
                    peak,
                )
            )
        mean = _number(analysis.get("mean_db"))
        if policy.speech_events and policy.min_mean_db is not None and "mean_db" in analysis and mean is None:
            inconclusive = True
            results.append(
                AudioQCRuleResult(
                    "speech_energy",
                    True,
                    "mean metric is unavailable; manual listening is required",
                    f"> {policy.min_mean_db} dB",
                    analysis.get("mean_db"),
                )
            )
        elif policy.speech_events and policy.min_mean_db is not None and mean is not None:
            passed = mean > policy.min_mean_db
            results.append(
                AudioQCRuleResult(
                    "speech_energy",
                    passed,
                    "audio energy is too low for the declared speech events" if not passed else "",
                    f"> {policy.min_mean_db} dB",
                    mean,
                )
            )
        return inconclusive

    @staticmethod
    def _check_speech_events(
        policy: AudioAcceptanceContract,
        analysis: Mapping[str, Any],
        results: list[AudioQCRuleResult],
    ) -> None:
        actual_value = analysis.get("speech_events", [])
        actual = (
            [item for item in actual_value if isinstance(item, Mapping)]
            if isinstance(actual_value, list)
            else []
        )
        actual_by_id = {
            str(item.get("event_id")): item
            for item in actual
            if isinstance(item.get("event_id"), str)
        }
        for expected in policy.speech_events:
            observed = actual_by_id.get(expected.event_id)
            if observed is None:
                results.append(
                    AudioQCRuleResult(
                        f"speech_event:{expected.event_id}",
                        False,
                        "declared speech event is missing from analyzer evidence",
                        expected.text,
                        None,
                    )
                )
                continue
            actual_text = str(observed.get("text", ""))
            similarity = _text_similarity(expected.text, actual_text)
            speaker_ok = observed.get("speaker_id") in (None, expected.speaker_id)
            start_ok = _within_tolerance(
                observed.get("start_ms"), expected.start_ms, policy.timing_tolerance_ms
            )
            end_ok = _within_tolerance(
                observed.get("end_ms"), expected.end_ms, policy.timing_tolerance_ms
            )
            passed = (
                similarity >= policy.transcript_similarity and speaker_ok and start_ok and end_ok
            )
            results.append(
                AudioQCRuleResult(
                    f"speech_event:{expected.event_id}",
                    passed,
                    "speech text, speaker or timing differs from the locked contract"
                    if not passed
                    else "",
                    {
                        "speaker_id": expected.speaker_id,
                        "text": expected.text,
                        "start_ms": expected.start_ms,
                        "end_ms": expected.end_ms,
                    },
                    {
                        "speaker_id": observed.get("speaker_id"),
                        "text": actual_text,
                        "start_ms": observed.get("start_ms"),
                        "end_ms": observed.get("end_ms"),
                        "similarity": similarity,
                    },
                )
            )

        ordered = sorted(
            (
                item
                for item in actual
                if isinstance(item.get("start_ms"), int) and isinstance(item.get("end_ms"), int)
            ),
            key=lambda item: int(item["start_ms"]),
        )
        for previous, current in itertools.pairwise(ordered):
            if int(current["start_ms"]) < int(previous["end_ms"]):
                previous_id = str(previous.get("event_id", "unknown"))
                current_id = str(current.get("event_id", "unknown"))
                allowed = any(
                    event.event_id in {previous_id, current_id} and event.allow_overlap
                    for event in policy.speech_events
                )
                if not allowed:
                    results.append(
                        AudioQCRuleResult(
                            "speech_overlap",
                            False,
                            f"speech events {previous_id} and {current_id} overlap",
                            "no overlap",
                            {"previous": previous_id, "current": current_id},
                        )
                    )


def _within_tolerance(value: object, expected: int, tolerance: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value - expected) <= tolerance
    )


def _text_similarity(expected: str, actual: str) -> float:
    return difflib.SequenceMatcher(None, _normalize_text(expected), _normalize_text(actual)).ratio()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(
        r"[\s\u3000\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a\u2018\u2019\u201c\u201d'\"\u2026\u2014\uff08\uff09()《》<>「」【】\[\],.!?;:]+",
        "",
        normalized,
    ).lower()


__all__ = [
    "AudioAcceptanceContract",
    "AudioAcceptanceReadiness",
    "AudioQCReport",
    "AudioQCRuleResult",
    "AudioQualityQC",
    "SpeechEventExpectation",
]
