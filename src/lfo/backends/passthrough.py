"""Built-in video passthrough backend.

The passthrough backend is intentionally small: it accepts one already
resolved video reference and copies it into the run's managed artifact path.
It does not import assets, update the CAS, or write runtime state.  Those
responsibilities stay with the application and execution layers.
"""
from __future__ import annotations

import pathlib
from typing import Any

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.services.artifact_layout import ArtifactLayoutError, atomic_copy_verified, managed_path

PASSTHROUGH_BACKEND_ID = "builtin.video-passthrough"
PASSTHROUGH_BACKEND_REVISION = "1.0.0"
PASSTHROUGH_OPERATION = "video.passthrough"


class VideoPassthroughHandler(TaskHandler):
    """Copy one resolved video reference to the managed output path."""

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        if task_type != "video.generate":
            return HandlerResult(
                success=False,
                error=f"Unsupported task type: {task_type}",
                retryable=False,
            )

        try:
            references = metadata.get("resolved_references")
            if not isinstance(references, list) or len(references) != 1:
                raise ValueError("video.passthrough requires exactly one resolved video reference")
            reference = references[0]
            if not isinstance(reference, dict):
                raise TypeError("resolved_references[0] must be an object")
            if reference.get("media_type") != "video":
                raise ValueError("video.passthrough requires a video reference")
            source_raw = reference.get("file_path")
            if not isinstance(source_raw, str) or not source_raw:
                raise ValueError("video.passthrough reference is missing file_path")

            destination = managed_path(
                metadata.get("output_path"),
                metadata.get("artifact_layout"),
            )
            file_hash, size = atomic_copy_verified(pathlib.Path(source_raw), destination)
            return HandlerResult(
                success=True,
                artifact_type="video",
                artifact_metadata={
                    "file_path": str(destination.resolve()),
                    "file_hash": file_hash,
                    # Keep the short hash key for callers that consume the
                    # durable artifact signature directly.
                    "hash": file_hash,
                    "size": size,
                    "media_type": "video",
                },
            )
        except (ArtifactLayoutError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            return HandlerResult(success=False, error=str(exc), retryable=False)


# Concise aliases make the backend discoverable without coupling callers to
# one historical class spelling.
PassthroughVideoHandler = VideoPassthroughHandler
PassthroughHandler = VideoPassthroughHandler


def build_passthrough_capability() -> CapabilityManifest:
    """Return the immutable capability declaration for passthrough."""

    return CapabilityManifest(
        backend_id=PASSTHROUGH_BACKEND_ID,
        revision=PASSTHROUGH_BACKEND_REVISION,
        # This is a built-in operation rather than a provider workflow.  The
        # non-empty stable marker satisfies the shared manifest contract.
        workflow_hash="builtin-video-passthrough-v1",
        operations=[PASSTHROUGH_OPERATION],
        accepted_media_types=["video"],
        max_references=1,
        output_signature={"media_type": "video"},
        reproducibility_claim="exact",
    )


def build_passthrough_backend_registry() -> BackendRegistry:
    """Build a registry containing the built-in passthrough capability."""

    registry = BackendRegistry()
    registry.register(build_passthrough_capability())
    return registry


# Compatibility names for integrations that refer to the capability as a
# manifest or the backend as a generic video handler.
build_video_passthrough_capability = build_passthrough_capability
build_video_passthrough_registry = build_passthrough_backend_registry
build_passthrough_registry = build_passthrough_backend_registry


__all__ = [
    "PASSTHROUGH_BACKEND_ID",
    "PASSTHROUGH_BACKEND_REVISION",
    "PASSTHROUGH_OPERATION",
    "PassthroughHandler",
    "PassthroughVideoHandler",
    "VideoPassthroughHandler",
    "build_passthrough_backend_registry",
    "build_passthrough_capability",
    "build_passthrough_registry",
    "build_video_passthrough_capability",
    "build_video_passthrough_registry",
]
