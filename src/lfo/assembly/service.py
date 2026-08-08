"""Assembly Service — orchestrate clip resolution → compilation → asset registration."""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime

from lfo.assembly.compiler import AssemblyCompiler
from lfo.assembly.schema import AssemblyClip, AssemblyInputSnapshot, AssemblyResult
from lfo.core.database import Database
from lfo.services.edl_service import EDLService


class AssemblyService:
    """Orchestrate assembly: resolve EDL → build snapshot → compile → register."""

    def __init__(
        self,
        db: Database,
        compiler: AssemblyCompiler | None = None,
        edl_service: EDLService | None = None,
    ) -> None:
        self.db = db
        self.compiler = compiler or AssemblyCompiler(db)
        self.edl_service = edl_service or EDLService(db)

    def build_from_edl(
        self,
        edl_id: str,
        output_filename: str = "",
    ) -> AssemblyResult:
        """Build the full assembly for an EDL.

        Steps:
        1. Resolve all clip selectors to concrete selected_clip_ids
        2. Build AssemblyInputSnapshot with file paths
        3. Compile via FFmpeg
        4. Register output as asset
        5. Create asset_relations for lineage
        """
        edl = self.edl_service._load_edl(edl_id)
        if edl is None:
            return AssemblyResult(error=f"EDL {edl_id} not found")
        if edl.status != "approved":
            return AssemblyResult(error=f"EDL status is '{edl.status}', must be 'approved'")

        resolved = self.edl_service.resolve_clips(edl_id)
        snapshot = self._build_snapshot(edl_id, edl.project_id, resolved)

        if not snapshot.clips:
            return AssemblyResult(error="No clips resolved for assembly")

        result = self.compiler.assemble(snapshot, output_filename)
        if not result.success:
            return result

        # Register output asset
        output_asset_id = uuid.uuid4().hex
        now = _utc_now()
        task_id = self._resolve_task_id(snapshot.clips[0].output_asset_id)

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, asset_type, file_path, file_hash, file_size,
                duration, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                output_asset_id,
                task_id,
                "video",
                result.output_file_path,
                "",
                os.path.getsize(result.output_file_path),
                result.duration_sec,
                json.dumps({
                    "source": "assembly",
                    "edl_id": edl_id,
                    "clip_count": len(snapshot.clips),
                }),
                now,
                now,
            ),
        )

        # Register asset relations: each clip's output → final assembly
        for clip in snapshot.clips:
            self.db.execute(
                """INSERT INTO asset_relations
                   (source_asset_id, target_asset_id, relation_type, metadata)
                   VALUES (?, ?, ?, ?)""",
                (
                    clip.output_asset_id,
                    output_asset_id,
                    "assembled_into",
                    json.dumps({"edl_id": edl_id, "shot_id": clip.shot_id}),
                ),
            )

        result.output_asset_id = output_asset_id
        return result

    # -- internal helpers -------------------------------------------------

    def _build_snapshot(
        self,
        edl_id: str,
        project_id: str,
        resolved_clips: list,
    ) -> AssemblyInputSnapshot:
        """Build snapshot from resolved clip selectors."""
        clips = []
        for rc in resolved_clips:
            row = self.db.fetchone(
                """SELECT a.file_path, a.duration, a.width, a.height, a.metadata
                   FROM selected_clips sc
                   JOIN assets a ON sc.output_asset_id = a.asset_id
                   WHERE sc.selected_clip_id = ?""",
                (rc.selected_clip_id,),
            )
            if row is None:
                continue
            meta = json.loads(row[4]) if row[4] else {}
            clips.append(AssemblyClip(
                shot_id=rc.shot_id,
                selected_clip_id=rc.selected_clip_id,
                output_asset_id=rc.selected_clip_id,  # will be updated below
                file_path=row[0],
                duration_sec=row[1] or 0.0,
                width=row[2] or 0,
                height=row[3] or 0,
                fps=meta.get("fps", 0.0),
                has_audio=meta.get("has_audio", False),
            ))

        # Update output_asset_id to the actual output asset (not selected_clip_id)
        for clip in clips:
            row = self.db.fetchone(
                "SELECT output_asset_id FROM selected_clips WHERE selected_clip_id = ?",
                (clip.selected_clip_id,),
            )
            if row and row[0]:
                clip.output_asset_id = row[0]

        return AssemblyInputSnapshot(
            edl_id=edl_id,
            project_id=project_id,
            clips=clips,
        )

    def _resolve_task_id(self, asset_id: str) -> str:
        row = self.db.fetchone(
            "SELECT task_id FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        return row[0] if row else ""


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
