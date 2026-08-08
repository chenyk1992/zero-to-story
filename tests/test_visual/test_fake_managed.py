"""Tests for FakeManagedProvider."""
from __future__ import annotations

import pytest

from lfo.visual.providers.fake_managed import FakeManagedProvider


def _make_fake(**kwargs) -> FakeManagedProvider:
    return FakeManagedProvider(
        provider_revision_id="rev-1",
        config={"endpoint": "http://fake"},
        capabilities={"text_to_image": True, "reference_to_image": True},
    )


def test_submit_returns_execution_id():
    p = _make_fake()
    eid = p.submit({"task_id": "t1", "purpose": "character_reference"})
    assert eid is not None


def test_collect_returns_manifest():
    p = _make_fake()
    eid = p.submit({"task_id": "t1"})
    manifest = p.collect(eid)
    assert "content" in manifest
    assert "file_hash" in manifest
    assert len(manifest["file_hash"]) == 64


def test_probe_available_by_default():
    p = _make_fake()
    result = p.probe()
    assert result.available is True
    assert result.capabilities.text_to_image is True


def test_probe_unavailable_when_set():
    p = _make_fake()
    p.set_next_response(unavailable=True)
    result = p.probe()
    assert result.available is False


def test_submit_raises_when_unavailable():
    p = _make_fake()
    p.set_next_response(unavailable=True)
    with pytest.raises(RuntimeError, match="unavailable"):
        p.submit({"task_id": "t1"})


def test_collect_hash_mismatch():
    p = _make_fake()
    p.set_next_response(hash_mismatch=True)
    eid = p.submit({"task_id": "t1"})
    manifest = p.collect(eid)
    assert manifest["file_hash"] == "f" * 64


def test_collect_wrong_size():
    p = _make_fake()
    p.set_next_response(wrong_size=True)
    eid = p.submit({"task_id": "t1"})
    manifest = p.collect(eid)
    assert manifest["content"]["width"] == 640


def test_collect_corrupt():
    p = _make_fake()
    p.set_next_response(corrupt=True)
    eid = p.submit({"task_id": "t1"})
    manifest = p.collect(eid)
    assert manifest["file_hash"] == "not-a-valid-hash"


def test_fault_consumed_once():
    """One-shot faults only affect the first collect."""
    p = _make_fake()
    p.set_next_response(wrong_size=True)
    eid = p.submit({"task_id": "t1"})
    m1 = p.collect(eid)
    assert m1["content"]["width"] == 640
    # Second collect: fault is consumed, normal size
    m2 = p.collect(eid)
    assert m2["content"]["width"] == 1024


def test_cancel_removes_execution():
    p = _make_fake()
    eid = p.submit({"task_id": "t1"})
    p.cancel(eid)
    with pytest.raises(ValueError, match="Unknown"):
        p.collect(eid)


def test_declared_capabilities():
    p = _make_fake()
    caps = p.declared_capabilities()
    assert caps.text_to_image is True
    assert caps.reference_to_image is True
    assert caps.image_edit is False
