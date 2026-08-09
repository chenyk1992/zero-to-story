"""Tests for review service."""
from __future__ import annotations

import pytest

from lfo.assets.review import ReviewService, ReviewStatus


class TestReviewService:
    def test_create_review(self) -> None:
        svc = ReviewService()
        r = svc.create_review(
            target_type="asset",
            target_id="hero.img",
            file_hash="abc123",
        )
        assert r.status == ReviewStatus.PENDING
        assert r.target_id == "hero.img"
        assert r.file_hash == "abc123"
        assert r.review_id

    def test_approve(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        approved = svc.approve(r.review_id, decided_by="user", notes="Looks good")
        assert approved.status == ReviewStatus.APPROVED
        assert approved.decided_by == "user"
        assert approved.notes == "Looks good"
        assert approved.decided_at is not None

    def test_reject(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        rejected = svc.reject(r.review_id, decided_by="user", notes="Fix lighting")
        assert rejected.status == ReviewStatus.REJECTED

    def test_invalidate(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        svc.approve(r.review_id)
        invalidated = svc.invalidate(r.review_id)
        assert invalidated.status == ReviewStatus.INVALIDATED

    def test_cannot_approve_non_pending(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        svc.approve(r.review_id)
        with pytest.raises(ValueError, match="Cannot approve"):
            svc.approve(r.review_id)

    def test_cannot_reject_non_pending(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        svc.reject(r.review_id)
        with pytest.raises(ValueError, match="Cannot reject"):
            svc.reject(r.review_id)

    def test_check_validity(self) -> None:
        svc = ReviewService()
        r = svc.create_review(target_type="asset", target_id="x")
        assert svc.check_validity(r) is True
        svc.approve(r.review_id)
        assert svc.check_validity(r) is True
        svc.invalidate(r.review_id)
        assert svc.check_validity(r) is False

    def test_invalidate_for_asset(self) -> None:
        svc = ReviewService()
        r1 = svc.create_review(target_type="asset", target_id="hero.img")
        r2 = svc.create_review(target_type="asset", target_id="hero.img")
        r3 = svc.create_review(target_type="asset", target_id="bg.img")
        svc.approve(r1.review_id)
        invalidated = svc.invalidate_for_asset("hero.img")
        assert len(invalidated) == 2
        assert r1.status == ReviewStatus.INVALIDATED
        assert r2.status == ReviewStatus.INVALIDATED
        assert r3.status == ReviewStatus.PENDING

    def test_list_reviews(self) -> None:
        svc = ReviewService()
        svc.create_review(target_type="asset", target_id="a")
        svc.create_review(target_type="package", target_id="p1")
        svc.create_review(target_type="asset", target_id="b")
        assets = svc.list_reviews(target_type="asset")
        assert len(assets) == 2
        all_reviews = svc.list_reviews()
        assert len(all_reviews) == 3

    def test_get_missing(self) -> None:
        svc = ReviewService()
        assert svc.get("nonexistent") is None

    def test_get_or_raise(self) -> None:
        svc = ReviewService()
        with pytest.raises(KeyError):
            svc.approve("nonexistent")
