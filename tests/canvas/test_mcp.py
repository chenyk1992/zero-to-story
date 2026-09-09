from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

from lfo.canvas.server import CanvasHTTPServer
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


def test_stdio_mcp_reads_and_edits_the_same_http_canvas(tmp_path):
    pytest.importorskip("mcp")
    import json

    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    project = Path(__file__).resolve().parents[2]
    settings = CanvasSettings(project, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.discovery.write_text(
        json.dumps(
            {"url": f"http://127.0.0.1:{server.server_address[1]}", "project_root": str(project)}
        ),
        encoding="utf-8",
    )

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "lfo.canvas",
                "--project",
                str(project),
                "--data-dir",
                str(settings.data_dir),
                "--media-root",
                str(settings.media_root),
                "mcp",
            ],
            env={**os.environ, "PYTHONPATH": str(project / "src")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert {"canvas_read", "canvas_edit", "canvas_claim", "canvas_complete"}.issubset(
                    {tool.name for tool in listing.tools}
                )
                created = await session.call_tool("canvas_create", {"name": "MCP 画布"})
                assert not created.isError
                canvas = created.structuredContent
                assert canvas is not None
                edited = await session.call_tool(
                    "canvas_edit",
                    {
                        "canvas_id": canvas["id"],
                        "version": canvas["version"],
                        "operations": [
                            {
                                "op": "add_node",
                                "node": {
                                    "id": "image-one",
                                    "type": "image",
                                    "position": {"x": 20, "y": 30},
                                    "data": {
                                        "prompt": "对话写入的提示词",
                                        "provider": "codex-imagegen",
                                        "mode": "create",
                                    },
                                },
                            }
                        ],
                    },
                )
                assert not edited.isError
                actual = service.store.get_canvas(canvas["id"])
                assert actual["graph"]["nodes"][0]["data"]["prompt"] == "对话写入的提示词"
                workspace_edit = await session.call_tool(
                    "canvas_edit",
                    {
                        "canvas_id": canvas["id"],
                        "version": actual["version"],
                        "operations": [
                            {
                                "op": "workspace",
                                "patch": {
                                    "story": "夜行者的故事",
                                    "chapter": "第一章",
                                    "summary": "从门口开始",
                                },
                            }
                        ],
                    },
                )
                assert not workspace_edit.isError
                updated = service.store.get_canvas(canvas["id"])
                assert updated["graph"]["workspace"] == {
                    "story": "夜行者的故事",
                    "chapter": "第一章",
                    "summary": "从门口开始",
                }
                assert updated["graph"]["nodes"] == actual["graph"]["nodes"]
                assert updated["graph"]["edges"] == actual["graph"]["edges"]
                assert updated["graph"]["viewport"] == actual["graph"]["viewport"]
                assert service.store.list_runs() == []

    try:
        anyio.run(exercise)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        service.close()
