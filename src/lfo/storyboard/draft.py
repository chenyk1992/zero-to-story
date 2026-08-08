"""LFO Draft — storyboard draft lifecycle and approval.

A Draft tracks the approval state of a storyboard:
- DRAFT_PENDING: awaiting user review
- DRAFT_APPROVED: user approved (bound to content_hash + revision)
- DRAFT_REJECTED: user rejected with notes
- DRAFT_SUPERSEDED: replaced by a newer revision

Approval is bound to a specific content_hash. If the storyboard changes
after approval, the approval is invalidated and the status reverts to
DRAFT_PENDING.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC

DRAFT_PENDING = "pending"
DRAFT_APPROVED = "approved"
DRAFT_REJECTED = "rejected"
DRAFT_SUPERSEDED = "superseded"


@dataclass
class Approval:
    """A single approval record."""
    approval_id: str = field(default_factory=lambda: f"approval_{uuid.uuid4().hex[:8]}")
    approved_hash: str = ""        # content_hash at approval time
    approved_revision: int = 0     # revision at approval time
    approved_at: str = ""          # ISO 8601
    reviewer: str = ""             # who approved
    notes: str = ""                # reviewer notes

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "approved_hash": self.approved_hash,
            "approved_revision": self.approved_revision,
            "approved_at": self.approved_at,
            "reviewer": self.reviewer,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Approval:
        return cls(**data)


@dataclass
class Draft:
    """Draft state for a storyboard."""
    draft_id: str = field(default_factory=lambda: f"draft_{uuid.uuid4().hex[:8]}")
    project_id: str = ""
    status: str = DRAFT_PENDING
    revision: int = 1
    content_hash: str = ""         # current content hash
    created_at: str = ""           # ISO 8601
    updated_at: str = ""           # ISO 8601
    approvals: list[Approval] = field(default_factory=list)
    pending_notes: str = ""        # notes from latest review action

    @property
    def is_approved(self) -> bool:
        return self.status == DRAFT_APPROVED

    @property
    def is_pending(self) -> bool:
        return self.status == DRAFT_PENDING

    @property
    def latest_approval(self) -> Approval | None:
        return self.approvals[-1] if self.approvals else None

    def to_dict(self) -> dict:
        return {
            "draft_id": self.draft_id,
            "project_id": self.project_id,
            "status": self.status,
            "revision": self.revision,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approvals": [a.to_dict() for a in self.approvals],
            "pending_notes": self.pending_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Draft:
        approvals = [Approval.from_dict(a) for a in data.pop("approvals", [])]
        return cls(approvals=approvals, **data)


# ---------------------------------------------------------------------------
# Draft lifecycle functions
# ---------------------------------------------------------------------------

def create_draft(project_id: str, revision: int = 1, content_hash: str = "",
                 draft_id: str = "") -> Draft:
    """Create a new pending draft."""
    from datetime import datetime
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    kwargs = dict(
        project_id=project_id,
        status=DRAFT_PENDING,
        revision=revision,
        content_hash=content_hash,
        created_at=now,
        updated_at=now,
    )
    if draft_id:
        kwargs["draft_id"] = draft_id
    return Draft(**kwargs)


def approve_draft(
    draft: Draft,
    content_hash: str,
    reviewer: str = "user",
    notes: str = "",
) -> Approval:
    """Approve the current draft.

    The approval is bound to the content_hash at the time of approval.
    If the content changes later, invalidate_approval() should be called.
    """
    from datetime import datetime
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    approval = Approval(
        approved_hash=content_hash,
        approved_revision=draft.revision,
        approved_at=now,
        reviewer=reviewer,
        notes=notes,
    )
    draft.approvals.append(approval)
    draft.status = DRAFT_APPROVED
    draft.content_hash = content_hash
    draft.updated_at = now
    draft.pending_notes = ""
    return approval


def reject_draft(draft: Draft, notes: str = "", reviewer: str = "user") -> None:
    """Reject the current draft with notes for revision."""
    from datetime import datetime
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    draft.status = DRAFT_REJECTED
    draft.updated_at = now
    draft.pending_notes = notes


def invalidate_approval(draft: Draft, new_content_hash: str) -> bool:
    """Invalidate approval if content has changed since approval.

    Returns True if the approval was valid but is now invalidated.
    Returns False if content hasn't changed or wasn't approved.
    """
    if draft.status != DRAFT_APPROVED:
        return False
    if draft.content_hash == new_content_hash:
        return False  # content unchanged

    # Content changed — approval is invalidated
    draft.status = DRAFT_PENDING
    draft.pending_notes = (
        f"Content changed (hash mismatch). "
        f"Previous approval was for hash {draft.content_hash[:16]}..."
    )
    return True


def supersede_draft(draft: Draft) -> None:
    """Mark this draft as superseded by a newer revision."""
    draft.status = DRAFT_SUPERSEDED


def check_approval_valid(draft: Draft, current_content_hash: str) -> bool:
    """Check if the current approval is still valid for the given content hash."""
    if draft.status != DRAFT_APPROVED:
        return False
    return draft.content_hash == current_content_hash
