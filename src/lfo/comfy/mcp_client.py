"""Project-owned stdio client for the official local Comfy MCP server."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from concurrent.futures import Future
from datetime import timedelta
from pathlib import Path
from typing import Any

from anyio.from_thread import start_blocking_portal
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REQUIRED_TOOLS = frozenset(
    {
        "server_info", "launch_comfyui", "nodes", "search_models", "upload_file",
        "validate_workflow", "run_workflow", "job", "fetch_outputs",
    }
)


class McpCallError(RuntimeError):
    """An MCP transport, tool, or response-contract failure."""


class ComfyMcpSession:
    """Keep the MCP context in one task while synchronous adapters call it."""

    def __init__(
        self, command: str, comfy_bin: str, base_url: str, *, cwd: Path,
        model_venv: Path | None = None,
    ) -> None:
        self.command = command
        self.comfy_bin = comfy_bin
        self.base_url = base_url
        self.cwd = cwd
        self.model_venv = model_venv
        self._portal_context: Any = None
        self._portal: Any = None
        self._task: Future[Any] | None = None
        self._queue: asyncio.Queue[tuple[str | None, dict[str, Any], float, Future[Any]]] | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        for key in (
            "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "COMFYUI_URL", "COMFYUI_HOST",
            "COMFY_LOCAL_URL", "COMFY_WHERE", "COMFY_BIN",
        ):
            env.pop(key, None)
        env["COMFY_BIN"] = self.comfy_bin
        env["COMFY_LOCAL_URL"] = self.base_url
        env["COMFY_WHERE"] = "local"
        if self.model_venv is not None:
            env["VIRTUAL_ENV"] = str(self.model_venv)
        return env

    async def _serve(self) -> None:
        try:
            async with stdio_client(
                StdioServerParameters(
                    command=self.command, cwd=self.cwd, env=self._environment()
                )
            ) as (read_stream, write_stream), ClientSession(
                read_stream, write_stream,
                read_timeout_seconds=timedelta(seconds=90),
            ) as client:
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                missing = REQUIRED_TOOLS - names
                if missing:
                    raise McpCallError("Comfy MCP 缺少必要工具: " + ", ".join(sorted(missing)))
                self._queue = asyncio.Queue()
                self._ready.set()
                while True:
                    name, args, timeout, reply = await self._queue.get()
                    if name is None:
                        reply.set_result(None)
                        return
                    try:
                        result = await client.call_tool(
                            name, args,
                            read_timeout_seconds=timedelta(seconds=timeout),
                        )
                        if result.isError:
                            detail = "; ".join(
                                block.text for block in result.content
                                if getattr(block, "type", None) == "text"
                            )
                            raise McpCallError(
                                f"Comfy MCP {name} 失败: {detail or '未知错误'}"
                            )
                        value = result.structuredContent
                        if value is None:
                            blocks = [
                                block for block in result.content
                                if getattr(block, "type", None) == "text"
                            ]
                            if len(blocks) != 1:
                                raise McpCallError(f"Comfy MCP {name} 返回无法解析的内容")
                            try:
                                value = json.loads(blocks[0].text)
                            except (ValueError, TypeError) as exc:
                                raise McpCallError(f"Comfy MCP {name} 未返回 JSON") from exc
                        reply.set_result(value)
                    except BaseException as exc:
                        reply.set_exception(exc)
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            raise

    def __enter__(self) -> ComfyMcpSession:
        self._portal_context = start_blocking_portal()
        self._portal = self._portal_context.__enter__()
        self._task = self._portal.start_task_soon(self._serve)
        if not self._ready.wait(30) or self._startup_error is not None:
            startup_error = self._startup_error or "连接超时"
            try:
                self.__exit__(None, None, None)
            finally:
                raise McpCallError(f"Comfy MCP 启动失败: {startup_error}")
        return self

    def __exit__(self, *_args: object) -> None:
        try:
            if self._portal is not None and self._queue is not None and self._task is not None and not self._task.done():
                reply: Future[Any] = Future()
                self._portal.call(self._queue.put, (None, {}, 0, reply))
                reply.result(timeout=30)
                self._task.result(timeout=30)
        finally:
            # A handshake timeout has no queue to receive the shutdown sentinel.
            # Cancel its task before closing the portal, which otherwise waits
            # indefinitely for that task to finish.
            if self._task is not None and not self._task.done():
                self._task.cancel()
            if self._portal_context is not None:
                self._portal_context.__exit__(None, None, None)
            self._portal_context = None
            self._portal = None

    def call(self, name: str, args: dict[str, Any] | None = None, *, timeout: float = 90) -> Any:
        if self._portal is None or self._queue is None or self._task is None or self._task.done():
            raise McpCallError("Comfy MCP 会话未运行")
        reply: Future[Any] = Future()
        try:
            self._portal.call(self._queue.put, (name, args or {}, timeout, reply))
            return reply.result(timeout=timeout + 10)
        except McpCallError:
            raise
        except Exception as exc:
            raise McpCallError(f"Comfy MCP {name} 通信中断: {exc}") from exc
