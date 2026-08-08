"""Tests for LFO Draft approval lifecycle."""
from lfo.storyboard.draft import (
    DRAFT_APPROVED,
    DRAFT_PENDING,
    DRAFT_REJECTED,
    DRAFT_SUPERSEDED,
    Draft,
    approve_draft,
    check_approval_valid,
    create_draft,
    invalidate_approval,
    reject_draft,
    supersede_draft,
)


class TestCreateDraft:
    def test_create_pending(self):
        d = create_draft("proj_001")
        assert d.status == DRAFT_PENDING
        assert d.project_id == "proj_001"
        assert d.revision == 1

    def test_create_with_revision(self):
        d = create_draft("proj_001", revision=3, content_hash="abc123")
        assert d.revision == 3
        assert d.content_hash == "abc123"

    def test_draft_id_auto(self):
        d = create_draft("proj_001")
        assert d.draft_id.startswith("draft_")


class TestApproveDraft:
    def test_approve(self):
        d = create_draft("proj_001", revision=2)
        approval = approve_draft(d, content_hash="hash_v2", reviewer="user")

        assert d.status == DRAFT_APPROVED
        assert len(d.approvals) == 1
        assert approval.approved_hash == "hash_v2"
        assert approval.approved_revision == 2
        assert approval.reviewer == "user"

    def test_approve_with_notes(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="h1", notes="Looks good!")
        assert d.approvals[0].notes == "Looks good!"

    def test_multiple_approvals(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="h1")
        approve_draft(d, content_hash="h2")
        assert len(d.approvals) == 2
        assert d.content_hash == "h2"


class TestRejectDraft:
    def test_reject(self):
        d = create_draft("proj_001")
        reject_draft(d, notes="Change the ending")

        assert d.status == DRAFT_REJECTED
        assert d.pending_notes == "Change the ending"

    def test_reject_then_approve(self):
        d = create_draft("proj_001")
        reject_draft(d, notes="Fix it")
        approve_draft(d, content_hash="fixed_hash")

        assert d.status == DRAFT_APPROVED
        assert d.content_hash == "fixed_hash"


class TestInvalidateApproval:
    def test_invalidate_on_change(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="hash_v1")

        invalidated = invalidate_approval(d, new_content_hash="hash_v2")
        assert invalidated is True
        assert d.status == DRAFT_PENDING

    def test_no_invalidate_when_unchanged(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="hash_v1")

        invalidated = invalidate_approval(d, new_content_hash="hash_v1")
        assert invalidated is False
        assert d.status == DRAFT_APPROVED

    def test_invalidate_when_not_approved(self):
        d = create_draft("proj_001")
        invalidated = invalidate_approval(d, new_content_hash="anything")
        assert invalidated is False


class TestSupersede:
    def test_supersede(self):
        d = create_draft("proj_001")
        supersede_draft(d)
        assert d.status == DRAFT_SUPERSEDED


class TestCheckApprovalValid:
    def test_valid(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="h1")
        assert check_approval_valid(d, "h1") is True

    def test_invalid_when_changed(self):
        d = create_draft("proj_001")
        approve_draft(d, content_hash="h1")
        assert check_approval_valid(d, "h2") is False

    def test_invalid_when_pending(self):
        d = create_draft("proj_001")
        assert check_approval_valid(d, "h1") is False


class TestDraftRoundTrip:
    def test_to_dict(self):
        d = create_draft("proj_001", revision=2)
        approve_draft(d, content_hash="h1")
        data = d.to_dict()
        restored = Draft.from_dict(data)
        assert restored.project_id == "proj_001"
        assert restored.status == DRAFT_APPROVED
        assert len(restored.approvals) == 1
