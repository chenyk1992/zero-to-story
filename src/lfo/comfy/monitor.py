"""WebSocket listener + polling monitor for ComfyUI prompt execution."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from .client import ComfyApiClient


class ComfyMonitor:
    """Monitor a prompt's lifecycle via WebSocket events and HTTP polling."""

    def __init__(self, client: ComfyApiClient):
        self.client = client

    # -- WebSocket events -------------------------------------------------- #

    def listen_events(
        self,
        prompt_id: str,
        callback: Callable[[str, dict], None],
        client_id: str | None = None,
    ) -> None:
        """Open a WebSocket connection and relay events for *prompt_id*.

        ``callback(event_type, data)`` is invoked for every matching event.
        The connection closes automatically on ``executed`` or ``execution_error``.
        """
        import websocket  # type: ignore

        ws_url = self.client.base_url.replace("http://", "ws://") + "/ws"
        if client_id:
            ws_url = f"{ws_url}?clientId={client_id}"

        ws = websocket.create_connection(ws_url)
        try:
            while True:
                raw = ws.recv()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_type = msg.get("type", "")
                data = msg.get("data", {})

                # Only dispatch events belonging to our prompt
                if data.get("prompt_id") and data["prompt_id"] != prompt_id:
                    continue

                callback(event_type, data)

                if event_type in ("executed", "execution_error"):
                    break
        finally:
            ws.close()

    # -- HTTP polling ------------------------------------------------------ #

    def poll_status(self, prompt_id: str) -> dict:
        """Query ``/history/{prompt_id}`` and return a status summary."""
        history = self.client.get_history(prompt_id)

        if prompt_id not in history:
            return {"prompt_id": prompt_id, "found": False, "status": "not_found"}

        entry = history[prompt_id]
        status_info = entry.get("status", {})
        outputs = entry.get("outputs", {})

        return {
            "prompt_id": prompt_id,
            "found": True,
            "status": status_info.get("status_str", "unknown"),
            "completed": status_info.get("completed", False),
            "executing": status_info.get("executing", False),
            "error": status_info.get("error"),
            "outputs": outputs,
        }

    def poll_until_done(
        self,
        prompt_id: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
        on_tick: Callable[[dict], None] | None = None,
    ) -> dict:
        """Block until the prompt completes or *timeout* seconds elapse.

        ``on_tick(status)`` is called after each poll.
        Returns the final status dict.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.poll_status(prompt_id)
            if on_tick:
                on_tick(status)
            if status.get("completed") or status.get("error"):
                return status
            time.sleep(interval)

        return {"prompt_id": prompt_id, "found": True, "status": "timeout"}

    # -- combined wait ----------------------------------------------------- #

    def wait_for_output(
        self,
        prompt_id: str,
        *,
        client_id: str | None = None,
        on_event: Callable[[str, dict], None] | None = None,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
    ) -> dict:
        """Wait for completion using WebSocket (primary) + polling (fallback).

        Returns the final status dict from :meth:`poll_status`.
        """
        ws_completed = False

        def _on_ws_event(event_type: str, data: dict) -> None:
            nonlocal ws_completed
            if on_event:
                on_event(event_type, data)
            if event_type in ("executed", "execution_error"):
                ws_completed = True

        try:
            # WebSocket may not always fire for completed prompts; use short timeout
            self.listen_events(prompt_id, _on_ws_event, client_id=client_id)
        except Exception:
            pass

        if ws_completed:
            return self.poll_status(prompt_id)

        # Fallback to polling
        return self.poll_until_done(
            prompt_id, interval=poll_interval, timeout=timeout
        )
