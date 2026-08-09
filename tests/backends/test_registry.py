"""Tests for BackendRegistry."""
from __future__ import annotations

import pytest

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry


def _make_manifest(
    backend_id: str = "comfyui.h3",
    revision: str = "1.0.0",
    operations: list[str] | None = None,
    workflow_hash: str = "hash123",
) -> CapabilityManifest:
    return CapabilityManifest(
        backend_id=backend_id,
        revision=revision,
        workflow_hash=workflow_hash,
        operations=operations or ["video.text_to_video"],
    )


class TestBackendRegistry:
    def test_register_and_get(self) -> None:
        reg = BackendRegistry()
        m = _make_manifest()
        reg.register(m)
        result = reg.get("comfyui.h3", "1.0.0")
        assert result is m

    def test_get_missing_returns_none(self) -> None:
        reg = BackendRegistry()
        assert reg.get("nonexistent", "1") is None

    def test_query_by_operation(self) -> None:
        reg = BackendRegistry()
        reg.register(_make_manifest(operations=["video.text_to_video"]))
        reg.register(_make_manifest(
            backend_id="other", revision="1",
            operations=["video.image_to_video"],
        ))
        results = reg.query_by_operation("video.text_to_video")
        assert len(results) == 1
        assert results[0].backend_id == "comfyui.h3"

    def test_query_no_match(self) -> None:
        reg = BackendRegistry()
        reg.register(_make_manifest())
        results = reg.query_by_operation("video.nonexistent")
        assert results == []

    def test_duplicate_registration_same_hash(self) -> None:
        """Registering same backend+revision+hash twice is idempotent."""
        reg = BackendRegistry()
        m1 = _make_manifest()
        m2 = _make_manifest()
        reg.register(m1)
        reg.register(m2)
        assert reg.count == 1

    def test_duplicate_registration_different_hash_raises(self) -> None:
        """Registering same backend+revision with different hash raises."""
        reg = BackendRegistry()
        reg.register(_make_manifest(workflow_hash="hash_a"))
        with pytest.raises(ValueError, match="different workflow_hash"):
            reg.register(_make_manifest(workflow_hash="hash_b"))

    def test_all_manifests(self) -> None:
        reg = BackendRegistry()
        reg.register(_make_manifest())
        reg.register(_make_manifest(backend_id="other", revision="2"))
        assert len(reg.all_manifests()) == 2

    def test_operation_index_updated(self) -> None:
        reg = BackendRegistry()
        reg.register(_make_manifest(operations=["op1", "op2"]))
        assert len(reg.query_by_operation("op1")) == 1
        assert len(reg.query_by_operation("op2")) == 1
