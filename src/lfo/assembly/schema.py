"""Assembly schema — data structures for the assembly pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AssemblyClip:
    """A resolved clip ready for assembly."""
    shot_id: str
    selected_clip_id: str
    output_asset_id: str
    file_path: str
    duration_sec: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False


@dataclass
class AssemblyInputSnapshot:
    """Concrete input snapshot for an assembly build.

    All clip selectors are resolved to specific selected_clip_ids.
    """
    edl_id: str
    project_id: str
    clips: list[AssemblyClip] = field(default_factory=list)
    export_profile_id: str = "vertical_h264_v1"

    @property
    def total_duration_sec(self) -> float:
        return sum(c.duration_sec for c in self.clips)


@dataclass
class AssemblyResult:
    """Result of an assembly build."""
    success: bool = False
    output_asset_id: str = ""
    output_file_path: str = ""
    duration_sec: float = 0.0
    error: str = ""
