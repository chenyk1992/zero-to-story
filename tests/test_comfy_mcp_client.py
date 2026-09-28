from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from lfo.comfy import mcp_client


@asynccontextmanager
async def fake_stdio(_parameters):
    yield object(), object()


class FakeClient:
    def __init__(self, *_args, missing=None, **_kwargs):
        self.missing = missing

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def initialize(self):
        return None

    async def list_tools(self):
        names = mcp_client.REQUIRED_TOOLS - ({self.missing} if self.missing else set())
        return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in names])

    async def call_tool(self, name, _args, **_kwargs):
        if name == "server_info":
            return SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(type="text", text='{"server":{"running":true}}')])
        return SimpleNamespace(isError=True, structuredContent=None, content=[SimpleNamespace(type="text", text="rejected")])


def test_stdio_handshake_and_text_response(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_client, "stdio_client", fake_stdio)
    monkeypatch.setattr(mcp_client, "ClientSession", FakeClient)
    with mcp_client.ComfyMcpSession("unused", "comfy", "http://127.0.0.1:8188", cwd=tmp_path) as session:
        assert session.call("server_info") == {"server": {"running": True}}
        with pytest.raises(mcp_client.McpCallError, match="rejected"):
            session.call("nodes")


def test_missing_required_tool_refuses_session(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_client, "stdio_client", fake_stdio)
    monkeypatch.setattr(mcp_client, "ClientSession", lambda *a, **k: FakeClient(*a, missing="job", **k))
    with pytest.raises(mcp_client.McpCallError, match="缺少必要工具.*job"):
        with mcp_client.ComfyMcpSession("unused", "comfy", "http://127.0.0.1:8188", cwd=tmp_path):
            pass


def test_handshake_timeout_cancels_session_before_closing_portal(monkeypatch, tmp_path):
    stopped = threading.Event()

    class SlowClient(FakeClient):
        async def initialize(self):
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    monkeypatch.setattr(mcp_client, "stdio_client", fake_stdio)
    monkeypatch.setattr(mcp_client, "ClientSession", SlowClient)
    session = mcp_client.ComfyMcpSession("unused", "comfy", "http://127.0.0.1:8188", cwd=tmp_path)
    wait = session._ready.wait
    monkeypatch.setattr(session._ready, "wait", lambda _timeout: wait(0.05))
    with pytest.raises(mcp_client.McpCallError, match="连接超时"):
        session.__enter__()
    assert stopped.is_set()
    assert session._portal is None
