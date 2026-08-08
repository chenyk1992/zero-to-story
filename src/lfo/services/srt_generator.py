"""SRT Generator — produce subtitle sidecar from EDL timeline.

Reads shot narration text from the storyboard and computes time ranges
from the assembly clip durations.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.assembly.schema import AssemblyInputSnapshot
from lfo.core.database import Database
from lfo.storyboard.storyboard import Storyboard


@dataclass
class SRTCue:
    """A single subtitle cue."""
    index: int
    start_sec: float
    end_sec: float
    text: str

    def to_srt_time(self, sec: float) -> str:
        """Convert seconds to SRT time format: HH:MM:SS,mmm."""
        if sec < 0:
            sec = 0
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        seconds = int(sec % 60)
        millis = int((sec % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def to_srt(self) -> str:
        """Format this cue as SRT block."""
        return (
            f"{self.index}\n"
            f"{self.to_srt_time(self.start_sec)} --> {self.to_srt_time(self.end_sec)}\n"
            f"{self.text}\n"
        )


@dataclass
class SRTResult:
    """Result of SRT generation."""
    success: bool = False
    file_path: str = ""
    cue_count: int = 0
    asset_id: str = ""
    error: str = ""


class SRTGenerator:
    """Generate SRT subtitle files from EDL + storyboard narration."""

    def __init__(
        self,
        db: Database,
        output_dir: str = "",
    ) -> None:
        self.db = db
        self.output_dir = output_dir or os.path.join(os.getcwd(), "srt_output")

    def generate(
        self,
        edl_id: str,
        storyboard: Storyboard,
        snapshot: AssemblyInputSnapshot,
        language: str = "zh-CN",
        output_filename: str = "",
    ) -> SRTResult:
        """Generate SRT subtitle file.

        Args:
            edl_id: The EDL being assembled.
            storyboard: Storyboard containing shot narration.
            snapshot: Resolved assembly snapshot with clip durations.
            language: Language code for filename.
            output_filename: Optional output filename (without extension).

        Returns:
            SRTResult with file path and cue count.
        """
        result = SRTResult()

        if not snapshot.clips:
            result.error = "No clips in snapshot"
            return result

        # Build shot_id → narration lookup from storyboard
        narration_map: dict[str, str] = {}
        for shot in storyboard.shots:
            if shot.narration:
                narration_map[shot.shot_id] = shot.narration

        # Build cues from clips in order
        cues: list[SRTCue] = []
        current_time = 0.0
        for _i, clip in enumerate(snapshot.clips):
            text = narration_map.get(clip.shot_id, "")
            if text:
                duration = clip.duration_sec if clip.duration_sec > 0 else 5.0
                cues.append(SRTCue(
                    index=len(cues) + 1,
                    start_sec=current_time,
                    end_sec=current_time + duration,
                    text=text,
                ))
            current_time += clip.duration_sec if clip.duration_sec > 0 else 5.0

        if not cues:
            result.error = "No subtitle text found for any shot"
            return result

        # Write SRT file
        os.makedirs(self.output_dir, exist_ok=True)
        filename = output_filename or f"final_{edl_id}_{language}"
        if not filename.endswith(".srt"):
            filename = f"{filename}.srt"
        file_path = os.path.join(self.output_dir, filename)

        srt_content = self._format_srt(cues)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        result.success = True
        result.file_path = file_path
        result.cue_count = len(cues)
        return result

    def register_srt_asset(
        self,
        edl_id: str,
        project_id: str,
        file_path: str,
        cue_count: int,
    ) -> str:
        """Register the SRT file as an asset in the database.

        Returns the asset_id.
        """
        asset_id = uuid.uuid4().hex
        now = _utc_now()
        task_id = self._resolve_task_id(edl_id)

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, file_size,
                metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                task_id,
                "subtitle",
                file_path,
                "",
                os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                json.dumps({
                    "source": "srt_generator",
                    "edl_id": edl_id,
                    "cue_count": cue_count,
                }),
                now,
                now,
            ),
        )

        return asset_id

    # -- internal helpers -------------------------------------------------

    def _format_srt(self, cues: list[SRTCue]) -> str:
        """Format cues as complete SRT file content."""
        blocks = [cue.to_srt() for cue in cues]
        return "\n".join(blocks) + "\n"

    def _resolve_task_id(self, edl_id: str) -> str:
        row = self.db.fetchone(
            "SELECT project_id FROM edit_decision_lists WHERE edl_id = ?",
            (edl_id,),
        )
        if row is None:
            return ""
        # Find any task for this project
        task_row = self.db.fetchone(
            "SELECT task_id FROM tasks WHERE project_id = ? LIMIT 1",
            (row[0],),
        )
        return task_row[0] if task_row else ""


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
