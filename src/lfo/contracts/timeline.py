"""Timeline, OutputPolicy and ApprovalDeclaration for VideoExecutionPackage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .strict import ensure_allowed_fields

SUBTITLE_MODES = frozenset({"none", "sidecar", "burnin", "both"})
CONTAINER_FORMATS = frozenset({"mp4", "mov", "mkv", "webm"})
VIDEO_ENCODERS = frozenset({"h264", "h265", "av1", "vp9"})
AUDIO_ENCODERS = frozenset({"aac", "mp3", "opus", "flac", "pcm"})
TRANSITIONS = frozenset({"cut"})


@dataclass
class TimelineSegment:
    """One source clip occurrence on the assembled edit timeline.

    ``source_in_ms`` and ``source_out_ms`` are expressed in the source clip's
    local time.  ``source_out_ms`` is exclusive and may be omitted to use the
    clip's declared duration.
    """

    clip_id: str
    source_in_ms: int = 0
    source_out_ms: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> TimelineSegment:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"clip_id", "source_in_ms", "source_out_ms"})
        clip_id = data.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id:
            raise ValueError(f"{path}.clip_id: required string")
        from lfo.services.artifact_layout import ArtifactLayoutError, safe_component

        try:
            safe_component(clip_id, field="clip_id")
        except ArtifactLayoutError as exc:
            raise ValueError(f"{path}.clip_id: {exc}") from exc
        source_in_ms = data.get("source_in_ms", 0)
        if not isinstance(source_in_ms, int) or isinstance(source_in_ms, bool):
            raise TypeError(f"{path}.source_in_ms: expected integer")
        if source_in_ms < 0:
            raise ValueError(f"{path}.source_in_ms: must be >= 0")
        source_out_ms = data.get("source_out_ms")
        if source_out_ms is not None:
            if not isinstance(source_out_ms, int) or isinstance(source_out_ms, bool):
                raise TypeError(f"{path}.source_out_ms: expected integer or null")
            if source_out_ms <= source_in_ms:
                raise ValueError(f"{path}.source_out_ms: must be greater than source_in_ms")
        return cls(clip_id, source_in_ms, source_out_ms)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"clip_id": self.clip_id}
        if self.source_in_ms:
            result["source_in_ms"] = self.source_in_ms
        if self.source_out_ms is not None:
            result["source_out_ms"] = self.source_out_ms
        return result

    def duration_ms(self, clip_duration_ms: int) -> int:
        """Return this segment's edited duration against a source duration."""
        if not isinstance(clip_duration_ms, int) or clip_duration_ms <= 0:
            raise ValueError(f"{self.clip_id}: source clip duration must be positive")
        if self.source_in_ms >= clip_duration_ms:
            raise ValueError(f"{self.clip_id}: source_in_ms exceeds clip duration")
        source_out_ms = (
            self.source_out_ms
            if self.source_out_ms is not None
            else clip_duration_ms
        )
        if source_out_ms > clip_duration_ms:
            raise ValueError(f"{self.clip_id}: source_out_ms exceeds clip duration")
        if source_out_ms <= self.source_in_ms:
            raise ValueError(f"{self.clip_id}: source_out_ms must be greater than source_in_ms")
        return source_out_ms - self.source_in_ms


@dataclass
class TimelineSpec:
    """Explicit ordered edit list for a VideoExecutionPackage."""

    segments: list[TimelineSegment] = field(default_factory=list)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        path: str = "$.timeline",
        *,
        clip_durations: dict[str, int] | None = None,
    ) -> TimelineSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"segments"})
        segments_data = data.get("segments")
        if not isinstance(segments_data, list):
            raise TypeError(f"{path}.segments: required array")
        segments = [
            TimelineSegment.from_dict(item, f"{path}.segments[{index}]")
            for index, item in enumerate(segments_data)
        ]
        if clip_durations is not None and not segments:
            raise ValueError(f"{path}.segments: must not be empty when clips exist")
        cls._validate_segments(segments, path, clip_durations)
        return cls(segments)

    @classmethod
    def for_clips(cls, clips: list[Any]) -> TimelineSpec:
        """Create the default sequence-ordered edit list for clip objects."""
        ordered = sorted(clips, key=lambda clip: clip.sequence)
        return cls([TimelineSegment(clip.clip_id) for clip in ordered])

    def validate(self, clip_durations: dict[str, int], path: str = "$.timeline") -> None:
        self._validate_segments(self.segments, path, clip_durations)

    @staticmethod
    def _validate_segments(
        segments: list[TimelineSegment],
        path: str,
        clip_durations: dict[str, int] | None,
    ) -> None:
        seen: set[str] = set()
        for index, segment in enumerate(segments):
            segment_path = f"{path}.segments[{index}]"
            if segment.clip_id in seen:
                raise ValueError(f"{segment_path}.clip_id: duplicate clip_id {segment.clip_id!r}")
            seen.add(segment.clip_id)
            if clip_durations is None:
                continue
            if segment.clip_id not in clip_durations:
                raise ValueError(f"{segment_path}.clip_id: unknown clip {segment.clip_id!r}")
            segment.duration_ms(clip_durations[segment.clip_id])
        if clip_durations is not None:
            missing = set(clip_durations) - seen
            if missing:
                raise ValueError(
                    f"{path}.segments: missing clips {sorted(missing)!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {"segments": [segment.to_dict() for segment in self.segments]}


@dataclass
class OutputPolicy:
    """Output encoding and assembly policy.

    Path generation is always done by LFO; the Package may only hint at
    a logical directory name, never an absolute path.
    """

    container: str = "mp4"
    video_encoder: str = "h264"
    audio_encoder: str = "aac"
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    sample_rate: int | None = None
    loudness_db: str | None = None
    transitions: str = "cut"
    subtitles_mode: str = "sidecar"
    directory: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> OutputPolicy:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {
                "container",
                "video_encoder",
                "audio_encoder",
                "width",
                "height",
                "fps",
                "sample_rate",
                "loudness_db",
                "transitions",
                "subtitles_mode",
                "directory",
            },
        )
        container = data.get("container", "mp4")
        if container not in CONTAINER_FORMATS:
            raise ValueError(
                f"{path}.container: must be one of {sorted(CONTAINER_FORMATS)}"
            )
        video_encoder = data.get("video_encoder", "h264")
        if video_encoder not in VIDEO_ENCODERS:
            raise ValueError(
                f"{path}.video_encoder: must be one of {sorted(VIDEO_ENCODERS)}"
            )
        audio_encoder = data.get("audio_encoder", "aac")
        if audio_encoder not in AUDIO_ENCODERS:
            raise ValueError(
                f"{path}.audio_encoder: must be one of {sorted(AUDIO_ENCODERS)}"
            )
        width = data.get("width")
        if width is not None:
            if not isinstance(width, int) or isinstance(width, bool):
                raise TypeError(f"{path}.width: expected integer")
            if width <= 0:
                raise ValueError(f"{path}.width: must be positive")
        height = data.get("height")
        if height is not None:
            if not isinstance(height, int) or isinstance(height, bool):
                raise TypeError(f"{path}.height: expected integer")
            if height <= 0:
                raise ValueError(f"{path}.height: must be positive")
        fps = data.get("fps")
        if fps is not None:
            if not isinstance(fps, int) or isinstance(fps, bool):
                raise TypeError(f"{path}.fps: expected integer")
            if fps <= 0:
                raise ValueError(f"{path}.fps: must be positive")
        sample_rate = data.get("sample_rate")
        if sample_rate is not None:
            if not isinstance(sample_rate, int) or isinstance(sample_rate, bool):
                raise TypeError(f"{path}.sample_rate: expected integer")
            if sample_rate <= 0:
                raise ValueError(f"{path}.sample_rate: must be positive")
        loudness_db = data.get("loudness_db")
        if loudness_db is not None and not isinstance(loudness_db, str):
            raise TypeError(f"{path}.loudness_db: expected string or null")
        transitions = data.get("transitions", "cut")
        if not isinstance(transitions, str):
            raise TypeError(f"{path}.transitions: expected string")
        if transitions not in TRANSITIONS:
            raise ValueError(f"{path}.transitions: only 'cut' is supported")
        subtitles_mode = data.get("subtitles_mode", "sidecar")
        if subtitles_mode not in SUBTITLE_MODES:
            raise ValueError(
                f"{path}.subtitles_mode: must be one of {sorted(SUBTITLE_MODES)}"
            )
        directory = data.get("directory")
        if directory is not None:
            if not isinstance(directory, str):
                raise TypeError(f"{path}.directory: expected string or null")
            from lfo.services.artifact_layout import ArtifactLayoutError, safe_component

            try:
                safe_component(directory, field="directory")
            except ArtifactLayoutError as exc:
                raise ValueError(f"{path}.directory: {exc}") from exc
        return cls(
            container=container,
            video_encoder=video_encoder,
            audio_encoder=audio_encoder,
            width=width,
            height=height,
            fps=fps,
            sample_rate=sample_rate,
            loudness_db=loudness_db,
            transitions=transitions,
            subtitles_mode=subtitles_mode,
            directory=directory,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.container != "mp4":
            d["container"] = self.container
        if self.video_encoder != "h264":
            d["video_encoder"] = self.video_encoder
        if self.audio_encoder != "aac":
            d["audio_encoder"] = self.audio_encoder
        if self.transitions != "cut":
            d["transitions"] = self.transitions
        if self.subtitles_mode != "sidecar":
            d["subtitles_mode"] = self.subtitles_mode
        if self.width is not None:
            d["width"] = self.width
        if self.height is not None:
            d["height"] = self.height
        if self.fps is not None:
            d["fps"] = self.fps
        if self.sample_rate is not None:
            d["sample_rate"] = self.sample_rate
        if self.loudness_db is not None:
            d["loudness_db"] = self.loudness_db
        if self.directory is not None:
            d["directory"] = self.directory
        return d


@dataclass
class ApprovalDeclaration:
    """Skill-side declaration that creative content was approved.

    This is *not* an LFO execution approval. The execution gate is supplied
    by the caller and binds the approved package's exact file SHA-256.
    """

    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ApprovalDeclaration:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"approved_by", "approved_at", "notes"})
        approved_by = data.get("approved_by")
        if approved_by is not None and not isinstance(approved_by, str):
            raise TypeError(f"{path}.approved_by: expected string or null")
        approved_at = data.get("approved_at")
        if approved_at is not None and not isinstance(approved_at, str):
            raise TypeError(f"{path}.approved_at: expected string or null")
        notes = data.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise TypeError(f"{path}.notes: expected string or null")
        return cls(approved_by=approved_by, approved_at=approved_at, notes=notes)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.approved_by is not None:
            d["approved_by"] = self.approved_by
        if self.approved_at is not None:
            d["approved_at"] = self.approved_at
        if self.notes is not None:
            d["notes"] = self.notes
        return d
