"""Bounded, speech-protected edits for an already existing media file.

The creative caller decides which pauses are safe to remove.  This module
does not run VAD, infer silence from signal energy, transcribe speech, change
playback speed, or decide whether an output is accepted.  It only validates
explicitly confirmed source ranges, protects caller-supplied speech ranges
through a caller-supplied tail margin, maps subtitles, and delegates the
video/audio cut to :class:`~lfo.media.timeline.TimelineAssembler`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import MediaCommandError, probe
from lfo.media.audio_qc import AudioQCReport
from lfo.media.subtitles import SubtitleCue, map_cues_over_kept_intervals
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineResult, TimelineSpec

_CONFIRMED_SILENCE_SOURCES = frozenset({"verified_instruction", "manual_review"})


def _require_ms(value: object, field_name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer number of milliseconds")
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be {qualifier}")
    return value


def _validate_interval(start_ms: int, end_ms: int, field_name: str) -> None:
    _require_ms(start_ms, f"{field_name}.start_ms")
    _require_ms(end_ms, f"{field_name}.end_ms", positive=True)
    if end_ms <= start_ms:
        raise ValueError(f"{field_name} must have end_ms greater than start_ms")


@dataclass(frozen=True, slots=True)
class SourceInterval:
    """A half-open source-media interval in milliseconds."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms, "source interval")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True, slots=True)
class ConfirmedSilentInterval:
    """A pause the caller has explicitly verified as safe to remove.

    ``confirmation`` records how the caller established that the interval is
    removable.  Automatic VAD or signal-threshold output is deliberately not
    an accepted value; an automatic suggestion must be reviewed and passed
    in as ``verified_instruction`` or ``manual_review`` first.
    """

    start_ms: int
    end_ms: int
    confirmation: str = "verified_instruction"

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms, "confirmed silent interval")
        if self.confirmation not in _CONFIRMED_SILENCE_SOURCES:
            allowed = ", ".join(sorted(_CONFIRMED_SILENCE_SOURCES))
            raise ValueError(
                "confirmed silent intervals require explicit verification "
                f"({allowed}); automatic silence detection is not sufficient"
            )

    @property
    def source_interval(self) -> SourceInterval:
        return SourceInterval(self.start_ms, self.end_ms)


@dataclass(frozen=True, slots=True)
class ProtectedSpeechInterval:
    """A speech range that must remain, including its required tail margin."""

    start_ms: int
    end_ms: int
    tail_margin_ms: int = 0
    event_id: str | None = None

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms, "protected speech interval")
        _require_ms(self.tail_margin_ms, "protected speech tail_margin_ms")

    def protected_interval(self, source_duration_ms: int) -> SourceInterval:
        """Return the speech interval expanded by its caller-supplied tail."""
        _require_ms(source_duration_ms, "source_duration_ms", positive=True)
        if self.end_ms + self.tail_margin_ms > source_duration_ms:
            raise ValueError("Source media has insufficient tail margin after protected speech")
        return SourceInterval(
            self.start_ms,
            self.end_ms + self.tail_margin_ms,
        )


@dataclass(frozen=True, slots=True)
class EditSegment:
    """One source range and its position in the edited output timeline."""

    source_in_ms: int
    source_out_ms: int
    output_start_ms: int

    def __post_init__(self) -> None:
        _validate_interval(self.source_in_ms, self.source_out_ms, "edit segment source range")
        _require_ms(self.output_start_ms, "edit segment output_start_ms")

    @property
    def output_end_ms(self) -> int:
        return self.output_start_ms + self.source_out_ms - self.source_in_ms

    @property
    def duration_ms(self) -> int:
        return self.source_out_ms - self.source_in_ms


@dataclass(frozen=True, slots=True)
class SpeechProtectedEditSpec:
    """Inputs for one bounded edit of an actual source media file.

    ``source_duration_ms`` is optional caller-known metadata.  When supplied,
    it must exactly match the duration probed from ``source_path``; the probe
    remains authoritative for the executable edit.  Subtitle cues use source
    media time and are mapped onto the resulting kept timeline.
    """

    source_path: str | Path
    output_path: str | Path | None = None
    confirmed_silent_intervals: Sequence[ConfirmedSilentInterval] = ()
    protected_speech_intervals: Sequence[ProtectedSpeechInterval] = ()
    subtitle_cues: Sequence[SubtitleCue] = ()
    source_duration_ms: int | None = None
    audio_qc_report: AudioQCReport | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confirmed_silent_intervals",
            tuple(self.confirmed_silent_intervals),
        )
        object.__setattr__(
            self,
            "protected_speech_intervals",
            tuple(self.protected_speech_intervals),
        )
        object.__setattr__(self, "subtitle_cues", tuple(self.subtitle_cues))
        if self.source_duration_ms is not None:
            _require_ms(self.source_duration_ms, "source_duration_ms", positive=True)
        if self.audio_qc_report is not None and not isinstance(self.audio_qc_report, AudioQCReport):
            raise TypeError("audio_qc_report must be an AudioQCReport")


@dataclass(frozen=True, slots=True)
class SpeechProtectedEditPlan:
    """Validated mapping produced before any output file is written."""

    source_path: str
    output_path: str | None
    source_duration_ms: int
    output_duration_ms: int
    removed_intervals: tuple[SourceInterval, ...]
    kept_intervals: tuple[SourceInterval, ...]
    segments: tuple[EditSegment, ...]
    mapped_subtitle_cues: tuple[SubtitleCue, ...] = ()
    audio_qc_readiness: str = "not_evaluated"
    audio_review_required: bool = False
    source_metadata: Mapping[str, Any] = field(default_factory=dict)

    def timeline_spec(
        self,
        output_path: str | Path | None = None,
        *,
        output_codec: str = "libx264",
        audio_codec: str = "aac",
    ) -> TimelineSpec:
        """Build the existing synchronous video/audio timeline cut."""
        requested_output = output_path or self.output_path
        if requested_output is None:
            raise ValueError("An output_path is required to apply the edit")
        fps_value = self.source_metadata.get("fps")
        fps = float(fps_value) if isinstance(fps_value, int | float) and fps_value > 0 else 0.0
        has_audio = self.source_metadata.get("has_audio")
        if not isinstance(has_audio, bool):
            has_audio = None
        return TimelineSpec(
            segments=[
                ClipSegment(
                    clip_id=f"speech-edit-{index:04d}",
                    file_path=self.source_path,
                    duration_ms=self.source_duration_ms,
                    source_in_ms=segment.source_in_ms,
                    source_out_ms=segment.source_out_ms,
                    has_audio=has_audio,
                )
                for index, segment in enumerate(self.segments)
            ],
            output_fps=fps,
            output_codec=output_codec,
            audio_codec=audio_codec,
            output_path=str(requested_output),
        )


@dataclass(frozen=True, slots=True)
class SpeechProtectedEditResult:
    """Technical result of applying a plan; acceptance stays with the caller."""

    success: bool
    plan: SpeechProtectedEditPlan | None = None
    output_path: str | None = None
    command: tuple[str, ...] | None = None
    error: str | None = None

    @property
    def audio_qc_readiness(self) -> str | None:
        return self.plan.audio_qc_readiness if self.plan is not None else None

    @property
    def audio_review_required(self) -> bool:
        return bool(self.plan and self.plan.audio_review_required)


class SpeechProtectedEditor:
    """Plan and apply caller-approved, cut-only speech-protected edits."""

    def __init__(self, assembler: TimelineAssembler | None = None) -> None:
        self._assembler = assembler or TimelineAssembler()

    def plan(self, spec: SpeechProtectedEditSpec) -> SpeechProtectedEditPlan:
        """Probe the source and return a validated, deterministic edit map."""
        source = Path(spec.source_path)
        metadata = dict(probe(source))
        source_duration = metadata.get("duration_ms")
        if (
            isinstance(source_duration, bool)
            or not isinstance(source_duration, int)
            or source_duration <= 0
        ):
            raise ValueError("Source media has no positive probed duration")
        if spec.source_duration_ms is not None and spec.source_duration_ms != source_duration:
            raise ValueError(
                "Known source_duration_ms does not match the probed media duration "
                f"({spec.source_duration_ms} != {source_duration})"
            )

        removals = self._normalize_removals(
            spec.confirmed_silent_intervals,
            source_duration,
        )
        protected = self._protected_ranges(spec.protected_speech_intervals, source_duration)
        self._ensure_speech_is_protected(removals, protected)
        kept = self._complement(removals, source_duration)
        if not kept:
            raise ValueError("Confirmed removals would remove the entire source media")

        self._validate_subtitle_cues(spec.subtitle_cues, source_duration)
        mapped_cues = map_cues_over_kept_intervals(
            spec.subtitle_cues,
            [(interval.start_ms, interval.end_ms) for interval in kept],
        )
        segments: list[EditSegment] = []
        output_cursor = 0
        for interval in kept:
            segment = EditSegment(
                interval.start_ms,
                interval.end_ms,
                output_cursor,
            )
            segments.append(segment)
            output_cursor = segment.output_end_ms

        readiness = "not_evaluated"
        review_required = False
        if spec.audio_qc_report is not None:
            report = spec.audio_qc_report
            readiness = report.acceptance_readiness.value
            review_required = not report.passed or report.inconclusive

        return SpeechProtectedEditPlan(
            source_path=str(source.resolve()),
            output_path=(str(Path(spec.output_path).resolve()) if spec.output_path else None),
            source_duration_ms=source_duration,
            output_duration_ms=output_cursor,
            removed_intervals=tuple(removals),
            kept_intervals=tuple(kept),
            segments=tuple(segments),
            mapped_subtitle_cues=tuple(mapped_cues),
            audio_qc_readiness=readiness,
            audio_review_required=review_required,
            source_metadata=metadata,
        )

    def build_command(
        self,
        plan: SpeechProtectedEditPlan,
        output_path: str | Path | None = None,
    ) -> list[str]:
        """Return the FFmpeg argv for a previously validated plan."""
        return self._assembler.build_command(plan.timeline_spec(output_path))

    def apply(
        self,
        spec: SpeechProtectedEditSpec,
        *,
        timeout_s: float = 600.0,
    ) -> SpeechProtectedEditResult:
        """Apply one plan and publish its output atomically.

        ``success`` only means that the technical edit completed and produced
        a file.  The caller remains responsible for listening, visual review,
        continuity, and the final ACCEPT/REJECT decision.
        """
        try:
            plan = self.plan(spec)
            if plan.output_path is None:
                raise ValueError("An output_path is required to apply the edit")
            source = Path(plan.source_path).resolve()
            output = Path(plan.output_path).resolve()
            if source == output:
                raise ValueError("The edit output_path must differ from source_path")
            output.parent.mkdir(parents=True, exist_ok=True)
            result: TimelineResult = self._assembler.assemble(
                plan.timeline_spec(),
                timeout_s=timeout_s,
            )
            if not result.success or not result.output_path:
                return SpeechProtectedEditResult(
                    False,
                    plan=plan,
                    command=tuple(result.command) if result.command else None,
                    error=result.error or "Speech-protected edit failed",
                )
            return SpeechProtectedEditResult(
                True,
                plan=plan,
                output_path=result.output_path,
                command=tuple(result.command) if result.command else None,
            )
        except (MediaCommandError, OSError, TypeError, ValueError, KeyError) as exc:
            return SpeechProtectedEditResult(False, error=str(exc))

    @staticmethod
    def _normalize_removals(
        intervals: Sequence[ConfirmedSilentInterval],
        source_duration_ms: int,
    ) -> list[SourceInterval]:
        candidates: list[SourceInterval] = []
        for index, interval in enumerate(intervals, 1):
            if not isinstance(interval, ConfirmedSilentInterval):
                raise TypeError(
                    f"confirmed_silent_intervals[{index - 1}] must be a ConfirmedSilentInterval"
                )
            candidate = interval.source_interval
            SpeechProtectedEditor._validate_in_source(
                candidate,
                source_duration_ms,
                f"confirmed silent interval {index}",
            )
            candidates.append(candidate)
        candidates.sort(key=lambda item: (item.start_ms, item.end_ms))
        merged: list[SourceInterval] = []
        for candidate in candidates:
            if merged and candidate.start_ms <= merged[-1].end_ms:
                merged[-1] = SourceInterval(
                    merged[-1].start_ms,
                    max(merged[-1].end_ms, candidate.end_ms),
                )
            else:
                merged.append(candidate)
        return merged

    @staticmethod
    def _protected_ranges(
        intervals: Sequence[ProtectedSpeechInterval],
        source_duration_ms: int,
    ) -> list[SourceInterval]:
        protected: list[SourceInterval] = []
        for index, interval in enumerate(intervals, 1):
            if not isinstance(interval, ProtectedSpeechInterval):
                raise TypeError(
                    f"protected_speech_intervals[{index - 1}] must be a ProtectedSpeechInterval"
                )
            base = SourceInterval(interval.start_ms, interval.end_ms)
            SpeechProtectedEditor._validate_in_source(
                base,
                source_duration_ms,
                f"protected speech interval {index}",
            )
            protected.append(interval.protected_interval(source_duration_ms))
        protected.sort(key=lambda item: (item.start_ms, item.end_ms))
        merged: list[SourceInterval] = []
        for candidate in protected:
            if merged and candidate.start_ms <= merged[-1].end_ms:
                merged[-1] = SourceInterval(
                    merged[-1].start_ms,
                    max(merged[-1].end_ms, candidate.end_ms),
                )
            else:
                merged.append(candidate)
        return merged

    @staticmethod
    def _ensure_speech_is_protected(
        removals: Sequence[SourceInterval],
        protected: Sequence[SourceInterval],
    ) -> None:
        for removal in removals:
            for speech in protected:
                if removal.start_ms < speech.end_ms and speech.start_ms < removal.end_ms:
                    raise ValueError(
                        "Confirmed silent interval overlaps protected speech "
                        f"({removal.start_ms}-{removal.end_ms} overlaps "
                        f"{speech.start_ms}-{speech.end_ms})"
                    )

    @staticmethod
    def _complement(
        removals: Sequence[SourceInterval],
        source_duration_ms: int,
    ) -> list[SourceInterval]:
        kept: list[SourceInterval] = []
        cursor = 0
        for removal in removals:
            if cursor < removal.start_ms:
                kept.append(SourceInterval(cursor, removal.start_ms))
            cursor = removal.end_ms
        if cursor < source_duration_ms:
            kept.append(SourceInterval(cursor, source_duration_ms))
        return kept

    @staticmethod
    def _validate_in_source(
        interval: SourceInterval,
        source_duration_ms: int,
        field_name: str,
    ) -> None:
        if interval.end_ms > source_duration_ms:
            raise ValueError(
                f"{field_name} {interval.start_ms}-{interval.end_ms} exceeds "
                f"source duration {source_duration_ms}"
            )

    @staticmethod
    def _validate_subtitle_cues(
        cues: Sequence[SubtitleCue],
        source_duration_ms: int,
    ) -> None:
        for index, cue in enumerate(cues, 1):
            if not isinstance(cue, SubtitleCue):
                raise TypeError(f"subtitle_cues[{index - 1}] must be a SubtitleCue")
            if cue.start_ms < 0 or cue.end_ms <= cue.start_ms:
                raise ValueError(f"Subtitle cue {index}: invalid time range")
            if cue.end_ms > source_duration_ms:
                raise ValueError(f"Subtitle cue {index}: exceeds source media duration")


__all__ = [
    "ConfirmedSilentInterval",
    "EditSegment",
    "ProtectedSpeechInterval",
    "SourceInterval",
    "SpeechProtectedEditPlan",
    "SpeechProtectedEditResult",
    "SpeechProtectedEditSpec",
    "SpeechProtectedEditor",
]
