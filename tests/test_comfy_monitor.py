from __future__ import annotations

from lfo.comfy.exceptions import ComfyUnreachableError
from lfo.comfy.monitor import ComfyMonitor


class _FlakyHistoryClient:
    base_url = "http://127.0.0.1:8188"

    def __init__(self) -> None:
        self.calls = 0

    def get_history(self, prompt_id: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise ComfyUnreachableError("history endpoint is busy")
        return {prompt_id: {"status": {"status_str": "success", "completed": True}, "outputs": {}}}


def test_poll_until_done_retries_temporary_history_timeout() -> None:
    client = _FlakyHistoryClient()
    status = ComfyMonitor(client).poll_until_done("prompt-1", interval=0, timeout=1)

    assert status["completed"] is True
    assert client.calls == 2
