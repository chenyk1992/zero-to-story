"""Backend routing for clip-level video generation tasks."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lfo.backends.comfy_h3 import ComfyH3VideoHandler, build_h3_backend_registry
from lfo.backends.passthrough import (
    PASSTHROUGH_BACKEND_ID,
    VideoPassthroughHandler,
    build_passthrough_capability,
)
from lfo.backends.registry import BackendRegistry
from lfo.execution.handlers import HandlerResult, TaskHandler

H3_BACKEND_ID = "comfyui.h3"
H3_PRESENTER_BACKEND_ID = "comfyui.h3-presenter"
H3_PRESENTER_OPERATION = "video.virtual_presenter"


def build_video_backend_registry(
    h3_registry: BackendRegistry | None = None,
) -> BackendRegistry:
    """Build the production video registry.

    The bundled H3 capabilities and the built-in passthrough capability live
    in one registry.  H3-presenter capabilities are owned by the H3 registry
    builder so the router does not duplicate provider workflow declarations.
    """

    registry = h3_registry or build_h3_backend_registry()
    registry.register(build_passthrough_capability())
    return registry


class VideoTaskRouter(TaskHandler):
    """Dispatch ``video.generate`` to a handler selected by backend_id."""

    def __init__(
        self,
        comfy_h3_handler: TaskHandler | Mapping[str, TaskHandler] | None = None,
        passthrough_handler: TaskHandler | None = None,
        *,
        backend_handlers: Mapping[str, TaskHandler] | None = None,
    ) -> None:
        # Accept a mapping as the first positional argument as a convenience
        # for tests and integrations that already own their handlers.
        if isinstance(comfy_h3_handler, Mapping):
            initial_handlers = dict(comfy_h3_handler)
            h3_handler: TaskHandler | None = None
        else:
            initial_handlers = {}
            h3_handler = comfy_h3_handler

        if h3_handler is None and not initial_handlers:
            h3_handler = ComfyH3VideoHandler()
        if passthrough_handler is None and not initial_handlers:
            passthrough_handler = VideoPassthroughHandler()

        handlers: dict[str, TaskHandler] = {
            H3_BACKEND_ID: h3_handler,  # type: ignore[dict-item]
            H3_PRESENTER_BACKEND_ID: h3_handler,  # type: ignore[dict-item]
            PASSTHROUGH_BACKEND_ID: passthrough_handler,  # type: ignore[dict-item]
        }
        handlers.update(initial_handlers)
        if backend_handlers:
            handlers.update(backend_handlers)
        h3 = handlers.get(H3_BACKEND_ID) or handlers.get(H3_PRESENTER_BACKEND_ID)
        if h3 is not None:
            # Keep the two public H3 backend IDs on one handler even when a
            # caller supplies an existing mapping instead of positional
            # handler arguments.
            handlers[H3_BACKEND_ID] = h3
            handlers[H3_PRESENTER_BACKEND_ID] = h3
        self.handlers = {key: value for key, value in handlers.items() if value is not None}

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
        backend_id = metadata.get("backend_id")
        if not isinstance(backend_id, str) or not backend_id:
            return HandlerResult(
                success=False,
                error="video.generate metadata.backend_id is required",
                retryable=False,
            )
        handler = self.handlers.get(backend_id)
        if handler is None:
            return HandlerResult(
                success=False,
                error=f"Unknown video backend: {backend_id}",
                retryable=False,
            )

        return handler.execute(
            task_id,
            task_type,
            logical_key,
            metadata,
            attempt_id,
        )


# The descriptive aliases keep imports stable for callers that use a
# ``default`` naming convention.
build_default_video_backend_registry = build_video_backend_registry
build_video_router_registry = build_video_backend_registry


__all__ = [
    "H3_PRESENTER_BACKEND_ID",
    "H3_PRESENTER_OPERATION",
    "VideoTaskRouter",
    "build_default_video_backend_registry",
    "build_video_backend_registry",
    "build_video_router_registry",
]
