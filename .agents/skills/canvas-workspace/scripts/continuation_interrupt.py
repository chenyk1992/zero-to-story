"""Pause only this host session's opted-in plans when the user interrupts.

This implements the documented Interrupt command contract through the same
local HTTP endpoint. Host event loading still needs verification; a direct
adapter test does not prove a user interrupt invokes it. The adapter never
starts services, reads transcripts, or generates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))


def handle(event: dict) -> dict:
    if event.get("hook_event_name") != "Interrupt":
        return {}
    session_id = event.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return {}
    from lfo.canvas.client import CanvasClient
    from lfo.canvas.settings import CanvasSettings

    url = CanvasClient(CanvasSettings.resolve(ROOT)).url
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("接续服务必须是本机画布")
    body = {"session_id": session_id, "event": "Interrupt"}
    if isinstance(event.get("turn_id"), str):
        body["turn_id"] = event["turn_id"]
    request = Request(
        url.rstrip("/") + "/api/continuations/hook",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Canvas-Request": "1"},
        method="POST",
    )
    with urlopen(request, timeout=1.5) as response:
        result = json.load(response)
    return result if isinstance(result, dict) else {}


def main() -> int:
    try:
        event = json.loads(sys.stdin.read(16385))
        if not isinstance(event, dict):
            raise ValueError("hook input must be an object")
        result = handle(event)
    except (ValueError, OSError, KeyError):
        result = {
            "systemMessage": "生产接续暂停记录未送达；用户中断仍然有效，下次接手先核实暂停状态。"  # noqa: RUF001
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
