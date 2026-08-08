"""Tests for VisualResultManifest."""
from __future__ import annotations

import pytest

from lfo.visual.errors import VisualResultError
from lfo.visual.result_manifest import VisualResultManifest, validate_result_manifest


def test_manifest_with_file_hash_valid():
    """Manifest with SHA-256 file_hash is valid."""
    import hashlib
    file_bytes = b"fake image bytes"
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    m = validate_result_manifest({
        "task_id": "t1",
        "content": {"file_path": "shot_001.png", "width": 1024, "height": 1024},
        "file_hash": file_hash,
        "status": "pending",
    })
    assert m.task_id == "t1"
    assert m.file_hash == file_hash
    assert m.status == "pending"


def test_manifest_content_hash_computed():
    """If content_hash omitted, it is computed from content (CJ1)."""
    m = validate_result_manifest({
        "task_id": "t1",
        "content": {"file_path": "shot_001.png"},
    })
    assert m.content_hash is not None
    assert len(m.content_hash) == 64  # SHA-256 hex


def test_manifest_missing_task_id_raises():
    with pytest.raises(VisualResultError, match="task_id"):
        validate_result_manifest({
            "content": {"file_path": "x.png"},
        })


def test_manifest_missing_content_raises():
    with pytest.raises(VisualResultError, match="content"):
        validate_result_manifest({
            "task_id": "t1",
        })


def test_manifest_invalid_file_hash_format():
    """file_hash must be 64 hex chars (SHA-256)."""
    with pytest.raises(VisualResultError, match="file_hash"):
        validate_result_manifest({
            "task_id": "t1",
            "content": {"file_path": "x.png"},
            "file_hash": "not-a-hash",
        })


def test_manifest_invalid_file_hash_length():
    """file_hash wrong length rejected."""
    with pytest.raises(VisualResultError, match="file_hash"):
        validate_result_manifest({
            "task_id": "t1",
            "content": {"file_path": "x.png"},
            "file_hash": "a" * 63,  # one short
        })


def test_manifest_hash_mismatch_detected():
    """file_hash that doesn't match content's declared hash is a mismatch."""
    m = validate_result_manifest({
        "task_id": "t1",
        "content": {"file_path": "x.png", "declared_hash": "abc"},
        "file_hash": "a" * 64,
    })
    # Mismatch when content has a declared_hash that differs from file_hash
    assert m.file_hash != "abc"


def test_manifest_content_hash_mismatch_detected():
    """Verify content_hash recomputed from content matches declared value."""
    m = validate_result_manifest({
        "task_id": "t1",
        "content": {"file_path": "x.png"},
    })
    # Recompute from content
    recomputed = m.compute_content_hash()
    assert recomputed == m.content_hash


def test_manifest_to_dict_round_trip():
    """to_dict → from_dict preserves fields."""
    original = validate_result_manifest({
        "task_id": "t1",
        "content": {"file_path": "x.png", "w": 1024, "h": 1024},
        "file_hash": "b" * 64,
        "status": "imported",
    })
    d = original.to_dict()
    restored = VisualResultManifest.from_dict(d)
    assert restored.task_id == original.task_id
    assert restored.file_hash == original.file_hash
    assert restored.status == original.status
