from __future__ import annotations

from typing import Any

from lfo.backends.passthrough import PASSTHROUGH_BACKEND_ID
from lfo.backends.video_router import H3_PRESENTER_BACKEND_ID, VideoTaskRouter
from lfo.execution.handlers import HandlerResult, TaskHandler


class RecordingHandler(TaskHandler):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, task_id: str, task_type: str, logical_key: str, metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        self.calls.append((backend_id := str(metadata["backend_id"]), metadata))
        return HandlerResult(success=True, artifact_type=backend_id)


def test_router_maps_h3_aliases_to_one_handler_and_preserves_metadata() -> None:
    h3 = RecordingHandler()
    passthrough = RecordingHandler()
    router = VideoTaskRouter(h3, passthrough)
    presenter_metadata = {"backend_id": H3_PRESENTER_BACKEND_ID, "operation": "video.virtual_presenter"}
    h3_metadata = {"backend_id": "comfyui.h3", "operation": "video.reference_to_video"}

    assert router.execute("t1", "video.generate", "k1", h3_metadata, "a1").success
    assert router.execute("t2", "video.generate", "k2", presenter_metadata, "a2").success
    assert router.handlers["comfyui.h3"] is router.handlers[H3_PRESENTER_BACKEND_ID]
    assert h3.calls == [("comfyui.h3", h3_metadata), (H3_PRESENTER_BACKEND_ID, presenter_metadata)]
    assert passthrough.calls == []


def test_router_dispatches_passthrough_and_rejects_unknown_backend() -> None:
    h3 = RecordingHandler()
    passthrough = RecordingHandler()
    router = VideoTaskRouter(h3, passthrough)
    metadata = {"backend_id": PASSTHROUGH_BACKEND_ID}
    assert router.execute("t", "video.generate", "k", metadata, "a").success
    result = router.execute("t", "video.generate", "k", {"backend_id": "missing"}, "a")
    assert not result.success
    assert result.retryable is False


def test_mapping_constructor_keeps_h3_alias() -> None:
    h3 = RecordingHandler()
    router = VideoTaskRouter({"comfyui.h3": h3})
    assert router.handlers[H3_PRESENTER_BACKEND_ID] is h3
