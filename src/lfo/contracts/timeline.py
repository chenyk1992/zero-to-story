"""Timeline, OutputPolicy and ApprovalDeclaration for VideoExecutionPackage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUBTITLE_MODES = frozenset({"none", "sidecar", "burnin", "both"})
CONTAINER_FORMATS = frozenset({"mp4", "mov", "mkv", "webm"})
VIDEO_ENCODERS = frozenset({"h264", "h265", "av1", "vp9"})
AUDIO_ENCODERS = frozenset({"aac", "mp3", "opus", "flac", "pcm"})


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
        subtitles_mode = data.get("subtitles_mode", "sidecar")
        if subtitles_mode not in SUBTITLE_MODES:
            raise ValueError(
                f"{path}.subtitles_mode: must be one of {sorted(SUBTITLE_MODES)}"
            )
        directory = data.get("directory")
        if directory is not None:
            if not isinstance(directory, str):
                raise TypeError(f"{path}.directory: expected string or null")
            if (
                not directory
                or directory in {".", ".."}
                or "/" in directory
                or "\\" in directory
                or directory.startswith("/")
                or (len(directory) >= 2 and directory[1] == ":")
                or directory.rstrip(" .") != directory
            ):
                raise ValueError(f"{path}.directory: must be one safe logical path component")
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

    This is *not* an LFO execution approval. LFO maintains its own review
    records bound to package hash, required asset hashes, etc.
    """

    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ApprovalDeclaration:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
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
