# ruff: noqa: RUF001
"""Canvas production transport through the official local Comfy MCP server."""

from __future__ import annotations

import json
import math
import os
import pathlib
import shlex
import shutil
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .mcp_client import ComfyMcpSession, McpCallError

DYNAMIC_MEDIA_INPUTS = {
    "LoadImage": frozenset({"image"}),
    "LoadVideo": frozenset({"file"}),
    "LoadAudio": frozenset({"audio"}),
}
Uploader = Callable[[pathlib.Path], str]


class ExecutorError(RuntimeError):
    """A production error with an explicit remote-state verdict."""

    stage: str

    def __init__(
        self, message: str, *, provider_task_id: str | None = None, status: str = "failed"
    ) -> None:
        super().__init__(message)
        self.provider_task_id = provider_task_id
        if status not in {"failed", "unknown"}:
            raise ValueError(f"unsupported executor error status: {status}")
        self.status = status


@dataclass(frozen=True)
class RuntimeConfig:
    base_url: str = "http://127.0.0.1:8188"
    mcp_command: str = ""
    comfy_bin: str = ""
    timeout_seconds: float = 7_200.0
    project_root: pathlib.Path | None = None
    model_venv: pathlib.Path | None = None


@dataclass(frozen=True)
class OutputRef:
    filename: str
    file_type: str = "absolute"
    node_id: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ComfyResult:
    provider_task_id: str
    outputs: tuple[OutputRef, ...]


def _read_config(path: pathlib.Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutorError(f"无法读取 Comfy MCP 配置 {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("comfy_mcp", {}), dict):
        raise ExecutorError("Comfy MCP 配置必须包含 comfy_mcp 对象")
    return value.get("comfy_mcp", {})


def _endpoint(url: str) -> tuple[str, int]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username or parsed.password or parsed.path not in {"", "/"}
        or parsed.query or parsed.fragment
    ):
        raise ExecutorError("Comfy MCP 目标必须是无路径和凭据的本机 HTTP 回环地址")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ExecutorError("Comfy MCP 端口无效") from exc
    if port == 0:
        raise ExecutorError("Comfy MCP 端口无效")
    port = port or 8188
    return ("127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname), port


def load_runtime_config(
    *, config_path: pathlib.Path | None = None, base_url: str | None = None,
    timeout_seconds: float | None = None,
) -> RuntimeConfig:
    root = pathlib.Path(__file__).resolve().parents[3]
    local_config = root / ".lfo" / "comfy-mcp.json"
    values = _read_config(config_path if config_path is not None else (
        local_config if local_config.is_file() else None
    ))
    targets = [value for value in (base_url, os.environ.get("LFO_COMFY_MCP_URL"), values.get("url")) if value]
    endpoints = {_endpoint(str(value)) for value in targets}
    if len(endpoints) > 1:
        raise ExecutorError("Comfy MCP 目标配置相互冲突")
    endpoint = str(targets[0]) if targets else "http://127.0.0.1:8188"
    inherited = [key for key in ("COMFYUI_URL", "COMFYUI_HOST") if os.environ.get(key)]
    if inherited:
        raise ExecutorError("Comfy MCP 检测到冲突的目标环境变量：" + ", ".join(inherited))
    command = os.environ.get("LFO_COMFY_MCP_COMMAND") or values.get("command")
    if not command:
        local = root / ".venv" / "comfy-mcp" / "Scripts" / "comfy-mcp.exe"
        command = str(local) if local.is_file() else "comfy-mcp"
    comfy_bin = os.environ.get("LFO_COMFY_MCP_COMFY_BIN") or values.get("comfy_bin") or "comfy"
    resolved_command = shutil.which(str(command))
    resolved_bin = shutil.which(str(comfy_bin))
    if not resolved_command:
        raise ExecutorError(f"找不到 Comfy MCP 服务：{command}")
    if not resolved_bin:
        raise ExecutorError(f"找不到 Comfy MCP 所需的官方 CLI：{comfy_bin}")
    raw_timeout = timeout_seconds if timeout_seconds is not None else (
        os.environ.get("LFO_COMFY_MCP_TIMEOUT") or values.get("timeout_seconds", 7_200)
    )
    try:
        timeout = float(raw_timeout)
    except (ValueError, TypeError) as exc:
        raise ExecutorError("Comfy MCP 运行超时无效") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ExecutorError("Comfy MCP 运行超时必须是正数")
    venv = os.environ.get("LFO_COMFY_MCP_MODEL_VENV") or values.get("model_venv")
    return RuntimeConfig(
        base_url=str(endpoint), mcp_command=resolved_command, comfy_bin=resolved_bin,
        timeout_seconds=timeout, project_root=root,
        model_venv=pathlib.Path(venv).resolve() if venv else None,
    )


def _session(config: RuntimeConfig, *, model_venv: pathlib.Path | None = None) -> ComfyMcpSession:
    return ComfyMcpSession(
        config.mcp_command or "comfy-mcp", config.comfy_bin or "comfy", config.base_url,
        cwd=config.project_root or pathlib.Path(__file__).resolve().parents[3],
        model_venv=model_venv or config.model_venv,
    )


@contextmanager
def _connected(config: RuntimeConfig, *, model_venv: pathlib.Path | None = None) -> Iterator[ComfyMcpSession]:
    try:
        with _session(config, model_venv=model_venv) as session:
            yield session
    except McpCallError as exc:
        raise ExecutorError(f"Comfy MCP 会话不可用: {exc}") from exc


def _running(info: object, config: RuntimeConfig) -> bool:
    if not isinstance(info, dict):
        raise ExecutorError("Comfy MCP server_info 返回值无效")
    server = info.get("server")
    if not isinstance(server, dict) or not isinstance(server.get("running"), bool):
        raise ExecutorError("Comfy MCP server_info 缺少服务状态")
    if server["running"]:
        reported = server.get("url")
        if not isinstance(reported, str) or _endpoint(reported) != _endpoint(config.base_url):
            raise ExecutorError("Comfy MCP 服务地址与画布配置不一致")
    return server["running"]


def _model_environment(info: dict[str, Any], config: RuntimeConfig) -> pathlib.Path | None:
    if config.model_venv is not None:
        candidates = [config.model_venv]
    else:
        workspace = info.get("workspace", {})
        value = workspace.get("path") if isinstance(workspace, dict) else None
        if not isinstance(value, str) or not value:
            raise ExecutorError("Comfy MCP 未报告既有工作区")
        root = pathlib.Path(value)
        candidates = [root / ".venv", root / "venv", root.parent / "standalone-env"]
    for candidate in candidates:
        executable = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if executable.is_file():
            return candidate
    raise ExecutorError("找不到既有 ComfyUI 模型 Python 环境；不会安装或改用画布环境")


@contextmanager
def ready_session(config: RuntimeConfig) -> Iterator[ComfyMcpSession]:
    """Reuse an online instance or start the configured local workspace once."""
    from .admission import state_directory

    with _connected(config) as first:
        try:
            info = first.call("server_info")
        except McpCallError as exc:
            raise ExecutorError(str(exc)) from exc
        if _running(info, config):
            yield first
            return
    # The first MCP process had no model venv. Start a new one with the
    # install's own venv so official launch never borrows Canvas's Python.
    assert isinstance(info, dict)
    model_venv = _model_environment(info, config)
    folder = state_directory()
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / "startup.json"
    if marker.exists():
        raise ExecutorError("上次 ComfyUI 启动尚未核实；停止重复启动")
    host, port = _endpoint(config.base_url)
    settings = info.get("config", {})
    extras = shlex.split(str(settings.get("default_launch_extras") or ""), posix=False)
    if any(
        arg == flag or arg.startswith(flag + "=")
        for arg in extras for flag in ("--listen", "--port", "--enable-cors-header")
    ):
        raise ExecutorError("既有 ComfyUI 启动选项含目标或网络暴露设置，需先核实配置")
    extras += ["--listen", host, "--port", str(port), "--disable-auto-launch"]
    with _connected(config, model_venv=model_venv) as launched:
        try:
            if not _running(launched.call("server_info"), config):
                marker.write_text(json.dumps({"base_url": config.base_url, "workspace": info["workspace"]["path"]}), encoding="utf-8")
                launched.call("launch_comfyui", {"extra_args": extras}, timeout=210)
            if not _running(launched.call("server_info"), config):
                raise ExecutorError("Comfy MCP 启动后服务未就绪")
            marker.unlink(missing_ok=True)
            yield launched
        except McpCallError as exc:
            raise ExecutorError(str(exc), status="unknown") from exc


def upload_input(path: pathlib.Path, session: ComfyMcpSession) -> str:
    if not path.is_file():
        raise ExecutorError(f"上传源文件不存在：{path}")
    # A unique local basename prevents a previous run's input from being reused.
    try:
        with tempfile.TemporaryDirectory(prefix="canvas-comfy-upload-") as folder:
            unique = pathlib.Path(folder) / f"canvas-{uuid.uuid4().hex}-{path.name}"
            shutil.copyfile(path, unique)
            payload = session.call(
                "upload_file", {"paths": [str(unique.resolve())], "overwrite": False}, timeout=330
            )
    except McpCallError as exc:
        raise ExecutorError(f"Comfy MCP 上传失败：{exc}") from exc
    uploads = payload.get("uploads") if isinstance(payload, dict) else None
    if not isinstance(uploads, list) or len(uploads) != 1 or not isinstance(uploads[0], dict):
        raise ExecutorError("Comfy MCP 上传回执无效")
    item = uploads[0]
    name, subfolder = item.get("cloud_name"), item.get("subfolder", "")
    if (
        not isinstance(name, str) or not name or pathlib.PurePath(name).name != name
        or not isinstance(subfolder, str)
        or pathlib.PurePath(subfolder).is_absolute()
        or pathlib.PurePath(subfolder).drive
        or ".." in pathlib.PurePath(subfolder).parts
        or item.get("type") != "input"
    ):
        raise ExecutorError("Comfy MCP 上传回执包含无效文件位置")
    return f"{subfolder}/{name}" if subfolder else name


def _node_inputs(node_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = node_info.get("inputs")
    if not isinstance(items, list):
        raise ExecutorError("Comfy MCP 节点 schema 无效")
    return {item["name"]: item for item in items if isinstance(item, dict) and isinstance(item.get("name"), str)}


def preflight_workflow(
    workflow: dict[str, Any], workflow_path: pathlib.Path, session: ComfyMcpSession,
) -> None:
    """Check live node choices and the official workflow verdict."""
    schemas: dict[str, dict[str, Any]] = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
            raise ExecutorError(f"工作流节点 {node_id} 无效")
        name = node["class_type"]
        if name not in schemas:
            try:
                info = session.call("nodes", {"action": "get", "name": name})
            except McpCallError as exc:
                raise ExecutorError(f"缺少 Comfy 节点 {name}: {exc}") from exc
            if not isinstance(info, dict) or info.get("name") != name:
                raise ExecutorError(f"Comfy MCP 节点 {name} schema 无效")
            schemas[name] = _node_inputs(info)
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise ExecutorError(f"工作流节点 {node_id} 输入无效")
        for key, value in inputs.items():
            if isinstance(value, list) or key in DYNAMIC_MEDIA_INPUTS.get(name, ()):
                continue
            schema = schemas[name].get(key)
            choices = schema.get("choices") if schema else None
            if isinstance(choices, list) and choices and value not in choices:
                raise ExecutorError(f"Comfy 节点 {name}.{key} 的选项不受支持：{value!r}")
    try:
        verdict = session.call("validate_workflow", {"workflow_path": str(workflow_path.resolve())})
    except McpCallError as exc:
        raise ExecutorError(f"Comfy MCP 工作流预检失败：{exc}") from exc
    if not isinstance(verdict, dict) or verdict.get("valid") is not True:
        raise ExecutorError(f"Comfy MCP 工作流预检未通过：{verdict}")


def model_files(session: ComfyMcpSession, folder: str) -> list[str]:
    try:
        value = session.call("search_models", {"folder": folder})
    except McpCallError as exc:
        raise ExecutorError(f"无法核实本机模型目录 {folder}: {exc}") from exc
    files = value.get("files") if isinstance(value, dict) else None
    if not isinstance(files, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in files):
        raise ExecutorError(f"Comfy MCP 模型目录 {folder} 返回值无效")
    return [item["name"].replace("\\", "/") for item in files]


def _status(value: Any, prompt_id: str) -> str:
    if not isinstance(value, dict) or value.get("prompt_id") != prompt_id:
        raise ExecutorError("Comfy MCP 原任务状态返回值无效", provider_task_id=prompt_id, status="unknown")
    raw_status = value.get("status")
    status = raw_status.strip().lower() if isinstance(raw_status, str) else None
    if status not in {"pending", "queued", "running", "allocated", "executing", "completed", "complete", "success", "succeeded", "done", "error", "failed", "cancelled", "canceled"}:
        raise ExecutorError(f"Comfy MCP 原任务状态未知：{status!r}", provider_task_id=prompt_id, status="unknown")
    return status


def run_workflow(
    workflow_path: pathlib.Path, output_dir: pathlib.Path, config: RuntimeConfig,
    session: ComfyMcpSession, *, guard: Any, emit: Callable[[dict[str, Any]], None] | None = None,
) -> ComfyResult:
    """Submit once, persist the ID, prove terminal state, then fetch outputs."""
    guard.submitted()
    try:
        submitted = session.call(
            "run_workflow", {"workflow_path": str(workflow_path.resolve()), "wait": False}, timeout=90
        )
    except McpCallError as exc:
        raise ExecutorError(f"Comfy MCP 提交结果未知：{exc}", status="unknown") from exc
    prompt_id = submitted.get("prompt_id") if isinstance(submitted, dict) else None
    if not isinstance(prompt_id, str) or not prompt_id:
        raise ExecutorError("Comfy MCP 提交未返回 prompt_id；原任务状态未知", status="unknown")
    guard.submitted(prompt_id)
    if emit:
        emit({"stage": "generation", "provider_task_id": prompt_id})
    deadline = time.monotonic() + config.timeout_seconds
    while time.monotonic() < deadline:
        try:
            state = session.call("job", {"action": "status", "prompt_id": prompt_id}, timeout=90)
        except McpCallError as exc:
            raise ExecutorError(f"无法核实原 Comfy 任务：{exc}", provider_task_id=prompt_id, status="unknown") from exc
        status = _status(state, prompt_id)
        if status in {"completed", "complete", "success", "succeeded", "done"}:
            guard.finished()
            if emit:
                # The caller still holds VideoSubmissionGuard while fetching
                # outputs and closing MCP. Only the adapter may announce
                # collection after leaving that context and releasing the lock.
                emit({"stage": "generation", "provider_task_id": prompt_id, "remote_finished": True})
            break
        if status in {"error", "failed", "cancelled", "canceled"}:
            guard.finished()
            raise ExecutorError(f"Comfy 原任务结束：{status}; {state.get('error')}", provider_task_id=prompt_id)
        time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
    else:
        raise ExecutorError("Comfy 原任务等待超时；未重复提交", provider_task_id=prompt_id, status="unknown")
    fetched_dir = output_dir / "mcp-outputs"
    fetched_dir.mkdir(parents=True, exist_ok=True)
    try:
        value = session.call(
            "fetch_outputs", {"prompt_id": prompt_id, "out_dir": str(fetched_dir.resolve())}, timeout=330
        )
    except McpCallError as exc:
        raise ExecutorError(f"Comfy 生成完成但产物取回失败：{exc}", provider_task_id=prompt_id) from exc
    files = value.get("files") if isinstance(value, dict) else None
    if not isinstance(files, list) or not files:
        raise ExecutorError("Comfy 生成完成但未返回文件", provider_task_id=prompt_id)
    refs: list[OutputRef] = []
    seen: set[pathlib.Path] = set()
    for item in files:
        raw = item.get("path") if isinstance(item, dict) else None
        if not isinstance(raw, str):
            raise ExecutorError("Comfy 返回无效产物路径", provider_task_id=prompt_id)
        path = pathlib.Path(raw).resolve()
        if not path.is_relative_to(fetched_dir.resolve()) or not path.is_file() or path in seen:
            raise ExecutorError("Comfy 产物位置越界、重复或不存在", provider_task_id=prompt_id)
        seen.add(path)
        node_id = item.get("node_id")
        source_url = item.get("url")
        refs.append(OutputRef(str(path), node_id=str(node_id) if node_id is not None else None,
                              source_url=source_url if isinstance(source_url, str) else None))
    return ComfyResult(prompt_id, tuple(refs))
