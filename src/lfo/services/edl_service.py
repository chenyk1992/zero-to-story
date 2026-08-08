"""EDL Service — edit decision list management.

An EDL is a logical document describing the edit:
- Shot order
- Clip selectors (e.g. "current_approved")
- Track definitions
- Transitions
- Subtitle track config
- Export profile

The EDL does NOT hard-code specific clip revisions. Assembly materialization
resolves "current_approved" to a concrete selected_clip_id at build time.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.core.database import Database
from lfo.core.hashing import compute_content_hash, compute_dependency_hash

EDL_STATUSES = frozenset({
    "draft",
    "awaiting_review",
    "approved",
    "rejected",
    "stale",
})

CLIP_SELECTOR_CURRENT_APPROVED = "current_approved"


@dataclass
class ClipSelector:
    """Reference to a clip for a shot."""
    shot_id: str
    clip_selector: str = CLIP_SELECTOR_CURRENT_APPROVED
    selected_clip_id: str = ""  # resolved at assembly time
    selected_clip_revision: int = 0


@dataclass
class EDLVideoTrack:
    """Single video track with clip references."""
    clips: list[ClipSelector] = field(default_factory=list)


@dataclass
class EDLSubtitleTrack:
    """Subtitle track configuration."""
    enabled: bool = True
    language: str = "zh-CN"
    source_field: str = "narration"  # which shot field to use for text


@dataclass
class EDLDocument:
    """Logical EDL content."""
    shots: list[str] = field(default_factory=list)
    video_track: EDLVideoTrack = field(default_factory=EDLVideoTrack)
    subtitle_track: EDLSubtitleTrack = field(default_factory=EDLSubtitleTrack)
    export_profile_id: str = "vertical_h264_v1"
    transition: str = "hard_cut"


@dataclass
class EDLRecord:
    """An EDL row."""

    edl_id: str
    project_id: str
    revision: int
    content_json: str
    content_hash: str
    dependency_hash: str
    status: str
    created_at: str
    approved_at: str


class EDLService:
    """Manage edit decision lists."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- public API -------------------------------------------------------

    def create_edl(
        self,
        project_id: str,
        shot_ids: list[str],
        export_profile_id: str = "vertical_h264_v1",
        subtitle_enabled: bool = True,
        subtitle_language: str = "zh-CN",
        transition: str = "hard_cut",
    ) -> EDLRecord:
        """Create a draft EDL from an ordered list of shot IDs."""
        revision = self._next_revision(project_id)

        clips = [
            ClipSelector(shot_id=sid, clip_selector=CLIP_SELECTOR_CURRENT_APPROVED)
            for sid in shot_ids
        ]
        doc = EDLDocument(
            shots=shot_ids,
            video_track=EDLVideoTrack(clips=clips),
            subtitle_track=EDLSubtitleTrack(
                enabled=subtitle_enabled,
                language=subtitle_language,
            ),
            export_profile_id=export_profile_id,
            transition=transition,
        )
        content_json = json.dumps({
            "shots": doc.shots,
            "video_track": {
                "clips": [
                    {"shot_id": c.shot_id, "clip_selector": c.clip_selector}
                    for c in doc.video_track.clips
                ],
            },
            "subtitle_track": {
                "enabled": doc.subtitle_track.enabled,
                "language": doc.subtitle_track.language,
                "source_field": doc.subtitle_track.source_field,
            },
            "export_profile_id": doc.export_profile_id,
            "transition": doc.transition,
        }, ensure_ascii=False)
        content_hash = self._compute_content_hash(doc)
        dependency_hash = self._compute_dependency_hash(doc)

        edl_id = uuid.uuid4().hex
        now = _utc_now()
        self.db.execute(
            """INSERT INTO edit_decision_lists
               (edl_id, project_id, revision, content_json,
                content_hash, dependency_hash, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edl_id, project_id, revision, content_json,
                content_hash, dependency_hash, "draft", now,
            ),
        )
        return self._load_edl(edl_id)

    def resolve_clips(self, edl_id: str) -> list[ClipSelector]:
        """Resolve all clip selectors to concrete selected_clip IDs.

        For "current_approved", looks up the approved clip for each shot.
        Returns ClipSelector objects with selected_clip_id populated.
        """
        edl = self._load_edl(edl_id)
        if edl is None:
            raise ValueError(f"EDL {edl_id} not found")

        doc = self._parse_doc(edl.content_json)
        resolved = []
        for clip in doc.video_track.clips:
            if clip.clip_selector == CLIP_SELECTOR_CURRENT_APPROVED:
                row = self.db.fetchone(
                    """SELECT selected_clip_id, revision
                       FROM selected_clips
                       WHERE project_id = ? AND shot_id = ? AND status = 'approved'
                       ORDER BY revision DESC LIMIT 1""",
                    (edl.project_id, clip.shot_id),
                )
                if row is None:
                    raise ValueError(
                        f"No approved clip for shot {clip.shot_id}"
                    )
                resolved.append(ClipSelector(
                    shot_id=clip.shot_id,
                    clip_selector=clip.clip_selector,
                    selected_clip_id=row[0],
                    selected_clip_revision=row[1],
                ))
            else:
                resolved.append(clip)
        return resolved

    def approve_edl(self, edl_id: str) -> EDLRecord:
        """Approve an EDL."""
        edl = self._load_edl(edl_id)
        if edl is None:
            raise ValueError(f"EDL {edl_id} not found")
        if edl.status not in ("draft", "awaiting_review"):
            raise ValueError(f"Cannot approve EDL in status '{edl.status}'")

        now = _utc_now()
        self.db.execute(
            "UPDATE edit_decision_lists SET status = 'approved', approved_at = ? WHERE edl_id = ?",
            (now, edl_id),
        )
        return self._load_edl(edl_id)

    # -- internal helpers -------------------------------------------------

    def _load_edl(self, edl_id: str) -> EDLRecord | None:
        row = self.db.fetchone(
            """SELECT edl_id, project_id, revision, content_json,
                      content_hash, dependency_hash, status, created_at, approved_at
               FROM edit_decision_lists WHERE edl_id = ?""",
            (edl_id,),
        )
        if row is None:
            return None
        return EDLRecord(
            edl_id=row[0],
            project_id=row[1],
            revision=row[2],
            content_json=row[3],
            content_hash=row[4],
            dependency_hash=row[5],
            status=row[6],
            created_at=row[7],
            approved_at=row[8] or "",
        )

    def _next_revision(self, project_id: str) -> int:
        row = self.db.fetchone(
            "SELECT MAX(revision) FROM edit_decision_lists WHERE project_id = ?",
            (project_id,),
        )
        return (row[0] or 0) + 1

    def _parse_doc(self, content_json: str) -> EDLDocument:
        raw = json.loads(content_json)
        clips = [ClipSelector(**c) for c in raw.get("video_track", {}).get("clips", [])]
        subtitle = EDLSubtitleTrack(**raw.get("subtitle_track", {}))
        return EDLDocument(
            shots=raw.get("shots", []),
            video_track=EDLVideoTrack(clips=clips),
            subtitle_track=subtitle,
            export_profile_id=raw.get("export_profile_id", "vertical_h264_v1"),
            transition=raw.get("transition", "hard_cut"),
        )

    def _compute_content_hash(self, doc: EDLDocument) -> str:
        entity = {
            "shots": doc.shots,
            "clip_selectors": [c.clip_selector for c in doc.video_track.clips],
            "subtitle_enabled": doc.subtitle_track.enabled,
            "subtitle_language": doc.subtitle_track.language,
            "export_profile_id": doc.export_profile_id,
            "transition": doc.transition,
        }
        return compute_content_hash(entity)

    def _compute_dependency_hash(self, doc: EDLDocument) -> str:
        # Logical layer: dependency is the export profile hash + content hash
        # Resolved layer (at assembly time) includes concrete clip IDs
        return compute_dependency_hash([
            doc.export_profile_id,
            self._compute_content_hash(doc),
        ])


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")
