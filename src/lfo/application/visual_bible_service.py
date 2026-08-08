"""Visual Bible lifecycle — creation, approval, supersession."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from lfo.visual_bible.hashing import compute_visual_bible_hash
from lfo.visual_bible.schema import VisualBible


@dataclass
class RevisionInfo:
    revision_id: str
    project_id: str
    content_hash: str
    status: str
    parent_revision_id: str | None
    created_by: str
    created_at: str


class VisualBibleService:
    """Manage Visual Bible revisions and approvals."""

    def __init__(self, db):
        self.db = db

    def create_revision(
        self, vb: VisualBible, created_by: str = "user"
    ) -> RevisionInfo:
        """Create a new revision with computed hash.

        - Computes LFO-CJ1 hash from content
        - Sets parent_revision_id to current approved revision
        - Sets status to 'draft'
        """
        content_hash = compute_visual_bible_hash(vb)

        # Find current approved revision to set as parent
        parent = self.db.fetchone(
            "SELECT revision_id FROM visual_bible_revisions "
            "WHERE project_id = ? AND status = 'approved' "
            "ORDER BY created_at DESC LIMIT 1",
            (vb.project_id,),
        )
        parent_revision_id = parent[0] if parent else None

        revision_id = str(uuid.uuid4())

        self.db.execute(
            "INSERT INTO visual_bible_revisions "
            "(revision_id, project_id, content, content_hash, parent_revision_id, "
            "status, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                vb.project_id,
                json.dumps(vb.to_dict()),
                content_hash,
                parent_revision_id,
                "draft",
                created_by,
            ),
        )

        row = self.db.fetchone(
            "SELECT created_at FROM visual_bible_revisions WHERE revision_id = ?",
            (revision_id,),
        )

        return RevisionInfo(
            revision_id=revision_id,
            project_id=vb.project_id,
            content_hash=content_hash,
            status="draft",
            parent_revision_id=parent_revision_id,
            created_by=created_by,
            created_at=row[0],
        )

    def submit_for_review(self, revision_id: str) -> None:
        """Change status from 'draft' to 'pending_review'."""
        self.db.execute(
            "UPDATE visual_bible_revisions "
            "SET status = 'pending_review', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE revision_id = ? AND status = 'draft'",
            (revision_id,),
        )

    def approve_revision(
        self, revision_id: str, approved_by: str
    ) -> None:
        """Approve a revision.

        - Sets status to 'approved'
        - Any previously approved revision becomes 'superseded'
        - Must be transactional
        """
        with self.db.transaction() as conn:
            # Get the project_id for this revision
            row = conn.execute(
                "SELECT project_id FROM visual_bible_revisions "
                "WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Revision not found: {revision_id}")
            project_id = row[0]

            # Supersede any previously approved revision
            conn.execute(
                "UPDATE visual_bible_revisions "
                "SET status = 'superseded', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE project_id = ? AND status = 'approved'",
                (project_id,),
            )

            # Approve the target revision
            conn.execute(
                "UPDATE visual_bible_revisions "
                "SET status = 'approved', approved_by = ?, "
                "approved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE revision_id = ?",
                (approved_by, revision_id),
            )

    def reject_revision(
        self, revision_id: str, reason: str
    ) -> None:
        """Reject a revision. Sets status to 'rejected'."""
        self.db.execute(
            "UPDATE visual_bible_revisions "
            "SET status = 'rejected', rejection_reason = ?, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE revision_id = ? AND status = 'pending_review'",
            (reason, revision_id),
        )

    def get_current_approved(
        self, project_id: str
    ) -> VisualBible | None:
        """Get the currently approved Visual Bible for a project."""
        row = self.db.fetchone(
            "SELECT content FROM visual_bible_revisions "
            "WHERE project_id = ? AND status = 'approved' "
            "ORDER BY approved_at DESC LIMIT 1",
            (project_id,),
        )
        if row is None:
            return None
        data = json.loads(row[0])
        return VisualBible.from_dict(data)

    def get_revision_history(
        self, project_id: str
    ) -> list[RevisionInfo]:
        """Get all revisions for a project, newest first."""
        rows = self.db.fetchall(
            "SELECT revision_id, project_id, content_hash, status, "
            "parent_revision_id, created_by, created_at "
            "FROM visual_bible_revisions "
            "WHERE project_id = ? "
            "ORDER BY created_at DESC",
            (project_id,),
        )
        return [
            RevisionInfo(
                revision_id=r[0],
                project_id=r[1],
                content_hash=r[2],
                status=r[3],
                parent_revision_id=r[4],
                created_by=r[5],
                created_at=r[6],
            )
            for r in rows
        ]

    def export_json(self, project_id: str) -> str | None:
        """Export the approved Visual Bible as JSON string."""
        vb = self.get_current_approved(project_id)
        if vb is None:
            return None
        return json.dumps(vb.to_dict(), indent=2)

    def is_content_approved(
        self, project_id: str, content_hash: str
    ) -> bool:
        """Check if a specific content_hash is the currently approved version."""
        row = self.db.fetchone(
            "SELECT 1 FROM visual_bible_revisions "
            "WHERE project_id = ? AND content_hash = ? AND status = 'approved'",
            (project_id, content_hash),
        )
        return row is not None
