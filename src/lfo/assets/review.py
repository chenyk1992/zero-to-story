"""Review service — approval records bound to content hashes.

A Review is independent of tasks. It binds to:
- asset_revision_id + file_hash + metadata_hash (for asset review)
- package hash + required assets + output policy hash (for package review)

When any bound content changes, the review is INVALIDATED automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ReviewStatus(str, Enum):
    """Review lifecycle states."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Review:
    """An approval or rejection of a specific content hash."""
    review_id: str
    target_type: str  # "asset" | "package" | "clip"
    target_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    content_hash: str | None = None
    file_hash: str | None = None
    metadata_hash: str | None = None
    bindings: dict[str, Any] = field(default_factory=dict)
    decided_at: str | None = None
    decided_by: str | None = None
    notes: str | None = None
    created_at: str = field(default_factory=_now)


class ReviewService:
    """Manage review lifecycle with automatic invalidation."""

    def __init__(self) -> None:
        # In-memory store for now; will be backed by DB in execution store.
        self._reviews: dict[str, Review] = {}

    def create_review(
        self,
        target_type: str,
        target_id: str,
        content_hash: str | None = None,
        file_hash: str | None = None,
        metadata_hash: str | None = None,
        bindings: dict[str, Any] | None = None,
    ) -> Review:
        """Create a new pending review."""
        review = Review(
            review_id=str(uuid4()),
            target_type=target_type,
            target_id=target_id,
            content_hash=content_hash,
            file_hash=file_hash,
            metadata_hash=metadata_hash,
            bindings=dict(bindings or {}),
        )
        self._reviews[review.review_id] = review
        return review

    def approve(
        self,
        review_id: str,
        decided_by: str | None = None,
        notes: str | None = None,
    ) -> Review:
        """Approve a pending review."""
        review = self._get_or_raise(review_id)
        if review.status != ReviewStatus.PENDING:
            raise ValueError(
                f"Cannot approve review in state {review.status.value}"
            )
        review.status = ReviewStatus.APPROVED
        review.decided_at = _now()
        review.decided_by = decided_by
        review.notes = notes
        return review

    def reject(
        self,
        review_id: str,
        decided_by: str | None = None,
        notes: str | None = None,
    ) -> Review:
        """Reject a pending review."""
        review = self._get_or_raise(review_id)
        if review.status != ReviewStatus.PENDING:
            raise ValueError(
                f"Cannot reject review in state {review.status.value}"
            )
        review.status = ReviewStatus.REJECTED
        review.decided_at = _now()
        review.decided_by = decided_by
        review.notes = notes
        return review

    def invalidate(self, review_id: str) -> Review:
        """Invalidate a review (e.g. when bound content changes)."""
        review = self._get_or_raise(review_id)
        review.status = ReviewStatus.INVALIDATED
        return review

    def check_validity(self, review: Review) -> bool:
        """Check if a review is still valid (PENDING or APPROVED, not INVALIDATED)."""
        return review.status in (ReviewStatus.PENDING, ReviewStatus.APPROVED)

    def get(self, review_id: str) -> Review | None:
        return self._reviews.get(review_id)

    def list_reviews(
        self, target_type: str | None = None, status: ReviewStatus | None = None
    ) -> list[Review]:
        """List reviews, optionally filtered."""
        results = list(self._reviews.values())
        if target_type:
            results = [r for r in results if r.target_type == target_type]
        if status:
            results = [r for r in results if r.status == status]
        return results

    def invalidate_for_asset(self, asset_key: str) -> list[Review]:
        """Invalidate all reviews bound to a given asset key."""
        invalidated = []
        for review in self._reviews.values():
            if review.target_id == asset_key and review.status in (
                ReviewStatus.PENDING,
                ReviewStatus.APPROVED,
            ):
                review.status = ReviewStatus.INVALIDATED
                invalidated.append(review)
        return invalidated

    def _get_or_raise(self, review_id: str) -> Review:
        if review_id not in self._reviews:
            raise KeyError(f"Review not found: {review_id}")
        return self._reviews[review_id]
