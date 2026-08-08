"""EndFrameExtractor — extract the last frame from a video asset.

Responsibilities:
- Extract the last frame from a video file via FFmpeg
- Register the frame as a new asset (type=image) in the database
- Link the frame to the source asset via asset_relations

This enables downstream continuity: the last frame of shot N becomes the
first frame (keyframe) of shot N+1 in I2V mode.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lfo.core.database import Database


@dataclass
class EndFrameResult:
    """Result of end frame extraction."""

    source_asset_id: str
    frame_asset_id: str = ""
    file_path: str = ""
    frame_number: int = 0
    success: bool = False
    error: str = ""


class EndFrameExtractor:
    """Extract the last frame from a video asset."""

    def __init__(
        self,
        db: Database,
        ffmpeg_path: str | None = None,
        output_dir: str = "",
    ) -> None:
        self.db = db
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or ""
        self.output_dir = output_dir or os.path.join(os.getcwd(), "end_frames")

    # -- public API ------------------------------------------------------- #

    def extract_from_clip(self, selected_clip_id: str) -> EndFrameResult:
        """Extract the end frame from an approved selected clip.

        Steps:
        1. Load selected_clips row
        2. Verify status = 'approved'
        3. Get output_asset_id
        4. Delegate to extract(output_asset_id)
        5. Augment relation metadata with selected_clip_id

        Args:
            selected_clip_id: The approved selected clip.

        Returns:
            EndFrameResult with frame asset details.

        Raises:
            ValueError: If clip not found, not approved, or has no output.
        """
        clip_row = self.db.fetchone(
            """SELECT project_id, shot_id, output_asset_id, status
               FROM selected_clips WHERE selected_clip_id = ?""",
            (selected_clip_id,),
        )
        if clip_row is None:
            raise ValueError(f"Selected clip {selected_clip_id} not found")

        status = clip_row[3]
        if status != "approved":
            raise ValueError(
                f"Cannot extract end frame: clip status is '{status}', must be 'approved'"
            )

        output_asset_id = clip_row[2]
        if not output_asset_id:
            raise ValueError(
                f"Selected clip {selected_clip_id} has no output_asset_id"
            )

        result = self.extract(output_asset_id)

        if result.success:
            self.db.execute(
                """INSERT INTO asset_relations
                   (source_asset_id, target_asset_id, relation_type, metadata)
                   VALUES (?, ?, ?, ?)""",
                (
                    output_asset_id,
                    result.frame_asset_id,
                    "end_frame_from",
                    json.dumps({
                        "selected_clip_id": selected_clip_id,
                        "shot_id": clip_row[1],
                    }),
                ),
            )

        return result

    def extract(self, asset_id: str) -> EndFrameResult:
        """Extract the last frame from a video asset.

        Steps:
        1. Load asset from DB (file_path, metadata)
        2. Get frame count from metadata
        3. Extract last frame via FFmpeg
        4. Register as new asset (type=image)
        5. Link to source asset via asset_relations

        Args:
            asset_id: The video asset to extract from.

        Returns:
            EndFrameResult with frame asset details.
        """
        result = EndFrameResult(source_asset_id=asset_id)

        # 1. Load asset
        asset_row = self.db.fetchone(
            """SELECT asset_id, task_id, attempt_id, file_path, metadata, frame_count, width, height
               FROM assets WHERE asset_id = ?""",
            (asset_id,),
        )
        if asset_row is None:
            result.error = f"Asset {asset_id} not found"
            return result

        task_id = asset_row[1]
        attempt_id = asset_row[2]
        file_path = asset_row[3]
        metadata = json.loads(asset_row[4]) if asset_row[4] else {}
        frame_count = asset_row[5] or metadata.get("frames", 0)
        width = asset_row[6] or metadata.get("width", 0)
        height = asset_row[7] or metadata.get("height", 0)

        if not os.path.exists(file_path):
            result.error = f"Video file not found: {file_path}"
            return result

        if not self.ffmpeg_path:
            result.error = "ffmpeg not found in PATH"
            return result

        # 2. Extract last frame
        os.makedirs(self.output_dir, exist_ok=True)
        frame_asset_id = uuid.uuid4().hex
        output_path = os.path.join(
            self.output_dir,
            f"{frame_asset_id}_end_frame.png",
        )

        try:
            self._extract_frame(file_path, output_path)
        except Exception as exc:
            result.error = f"FFmpeg extraction failed: {exc}"
            return result

        # 3. Register asset
        now = _utc_now()
        # Compute file_hash and content_hash for the extracted frame so
        # downstream approval checks (dependency_hash == content_hash) pass.
        file_hash = ""
        content_hash = ""
        if os.path.exists(output_path):
            import hashlib
            sha256 = hashlib.sha256()
            with open(output_path, "rb") as _f:
                for _chunk in iter(lambda: _f.read(8192), b""):
                    sha256.update(_chunk)
            file_hash = sha256.hexdigest()
            content_hash = file_hash  # semantic hash == file hash for images

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, attempt_id, asset_type, file_path,
                file_hash, file_size, width, height, content_hash,
                metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                frame_asset_id,
                task_id,
                attempt_id,
                "image",
                output_path,
                file_hash,
                os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                width,
                height,
                content_hash,
                json.dumps({"source": "end_frame_extraction", "frame_number": frame_count}),
                now,
                now,
            ),
        )

        # 4. Create asset relation
        self.db.execute(
            """INSERT INTO asset_relations
               (source_asset_id, target_asset_id, relation_type, metadata)
               VALUES (?, ?, ?, ?)""",
            (
                asset_id,
                frame_asset_id,
                "derived_from",
                json.dumps({"type": "end_frame", "frame_number": frame_count}),
            ),
        )

        result.frame_asset_id = frame_asset_id
        result.file_path = output_path
        result.frame_number = frame_count
        result.success = True
        return result

    # -- FFmpeg extraction ------------------------------------------------ #

    def _extract_frame(self, video_path: str, output_path: str) -> None:
        """Extract the last frame from a video file using FFmpeg.

        Uses -sseof to seek to near the end, then extracts one frame.
        """
        cmd = [
            self.ffmpeg_path, "-y",
            "-sseof", "-1",           # seek to 1 second before end
            "-i", video_path,
            "-frames:v", "1",          # extract 1 frame
            "-q:v", "2",               # high quality
            output_path,
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"FFmpeg execution failed: {exc}") from exc

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {proc.stderr[:500]}")

        if not os.path.exists(output_path):
            raise RuntimeError("FFmpeg completed but output file not created")


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
