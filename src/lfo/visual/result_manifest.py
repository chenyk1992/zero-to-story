"""Visual Result Manifest — imported result metadata with hash verification.

A VisualResultManifest captures the outcome of a visual task execution,
including the content metadata, semantic content_hash (LFO-CJ1), and the
file_hash (SHA-256 of actual file bytes). Mismatch between content_hash
and recomputed hash signals data corruption (RESULT_HASH_MISMATCH).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lfo.visual.errors import VisualResultError
from lfo.visual.hashing import hash_visual_object

# Valid status values for result manifests
_STATUSES = ("pending", "imported", "qc_passed", "qc_failed", "approved")

# SHA-256 hex pattern
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


@dataclass(frozen=True)
class VisualResultManifest:
    """Immutable visual result manifest.

    content: arbitrary JSON-serializable metadata (no floats).
    content_hash: LFO-CJ1 semantic hash of content.
    file_hash: SHA-256 hex digest of the actual file bytes.
    status: current lifecycle state.
    """
    task_id: str
    content: dict[str, Any]
    content_hash: str
    file_hash: str | None = None
    status: str = "pending"

    def compute_content_hash(self) -> str:
        """Recompute LFO-CJ1 hash from current content."""
        return hash_visual_object(self.content)

    def content_hash_matches(self) -> bool:
        """Check if stored content_hash matches recomputed hash."""
        return self.content_hash == self.compute_content_hash()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "status": self.status,
        }
        if self.file_hash is not None:
            d["file_hash"] = self.file_hash
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> VisualResultManifest:
        """Deserialize from dict."""
        return VisualResultManifest(
            task_id=d["task_id"],
            content=d["content"],
            content_hash=d["content_hash"],
            file_hash=d.get("file_hash"),
            status=d.get("status", "pending"),
        )


def _validate_sha256(value: str, field: str) -> None:
    """Validate a SHA-256 hex string."""
    if not _SHA256_RE.match(value):
        raise VisualResultError(
            f"{field} must be a 64-char lowercase hex SHA-256 string, got: {value!r}"
        )


def validate_result_manifest(data: dict[str, Any]) -> VisualResultManifest:
    """Validate raw dict and construct a VisualResultManifest.

    Args:
        data: Raw dict with manifest fields.

    Returns:
        Validated VisualResultManifest.

    Raises:
        VisualResultError: On missing fields or invalid formats.
    """
    if "task_id" not in data:
        raise VisualResultError("Missing required field: 'task_id'")
    if "content" not in data:
        raise VisualResultError("Missing required field: 'content'")

    task_id = data["task_id"]
    content = data["content"]
    file_hash = data.get("file_hash")
    status = data.get("status", "pending")

    if file_hash is not None:
        _validate_sha256(file_hash, "file_hash")

    if status not in _STATUSES:
        raise VisualResultError(
            f"Invalid status '{status}'. Must be one of {_STATUSES}"
        )

    # Compute content_hash if not provided; validate if provided
    if "content_hash" in data:
        content_hash = data["content_hash"]
        _validate_sha256(content_hash, "content_hash")
    else:
        content_hash = hash_visual_object(content)

    return VisualResultManifest(
        task_id=task_id,
        content=content,
        content_hash=content_hash,
        file_hash=file_hash,
        status=status,
    )
