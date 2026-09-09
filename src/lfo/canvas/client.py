"""Shared HTTP client for CLI and MCP, never direct database access."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lfo.canvas.settings import CanvasSettings


class CanvasClient:
    def __init__(self, settings: CanvasSettings, url: str | None = None):
        self.settings = settings
        self._url = url

    @property
    def url(self) -> str:
        if self._url:
            return self._url.rstrip("/")
        try:
            record = json.loads(self.settings.discovery.read_text(encoding="utf-8"))
            if record["project_root"] != str(self.settings.project_root):
                raise ValueError("服务所属项目不匹配")
            return record["url"]
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError("画布服务尚未启动，请先运行 canvas serve 或调用 canvas_open") from exc

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/api/") or ".." in path:
            raise ValueError("只允许调用画布 API")
        data = (
            json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if body is not None
            else None
        )
        request = Request(
            self.url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "X-Canvas-Request": "1"},
        )
        try:
            with urlopen(request, timeout=120) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                message = json.load(exc)["error"]["message"]
            except (ValueError, KeyError):
                message = f"画布服务返回 {exc.code}"
            raise ValueError(message) from exc
        except URLError as exc:
            raise ValueError("画布服务未响应，请检查本地服务是否正在运行") from exc

    def ensure_server(self) -> str:
        try:
            health = self.request("GET", "/api/health")
            if health["project_root"] != str(self.settings.project_root):
                raise ValueError("当前端口正在服务其他项目")
            return self.url
        except ValueError:
            pass
        if not (self.settings.frontend / "index.html").is_file():
            raise ValueError("请先在 web/canvas 执行 npm install 和 npm run build")
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "lfo.canvas",
            "--project",
            str(self.settings.project_root),
            "--data-dir",
            str(self.settings.data_dir),
            "--media-root",
            str(self.settings.media_root),
            "--port",
            str(self.settings.port),
            "serve",
        ]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        env["PYTHONPATH"] = str(self.settings.project_root / "src")
        with (self.settings.data_dir / "server.log").open("ab") as log:
            process = subprocess.Popen(
                command,
                cwd=self.settings.project_root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=os.name != "nt",
            )
        for _ in range(50):
            try:
                health = self.request("GET", "/api/health")
                if health["project_root"] != str(self.settings.project_root):
                    raise ValueError("当前端口正在服务其他项目")
                return self.url
            except ValueError:
                if process.poll() is not None:
                    raise ValueError("画布启动失败，请检查应用数据目录中的 server.log") from None
                time.sleep(0.1)
        raise ValueError("画布启动超时，请检查本地端口是否可用")

    def edit(
        self, canvas_id: str, version: int, operations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        canvas = self.request("GET", f"/api/canvases/{canvas_id}")
        if canvas["version"] != version:
            raise ValueError("画布已有新版本，请重新读取后应用修改")
        graph = copy.deepcopy(canvas["graph"])
        name = canvas["name"]
        for operation in operations:
            action = operation["op"]
            if action == "add_node":
                graph["nodes"].append(operation["node"])
            elif action == "update_node":
                node = next(
                    (node for node in graph["nodes"] if node["id"] == operation["node_id"]), None
                )
                if node is None:
                    raise ValueError("没有找到需要修改的组件")
                node["data"].update(operation.get("data", {}))
                if "position" in operation:
                    node["position"] = operation["position"]
            elif action == "remove_node":
                graph["nodes"] = [
                    node for node in graph["nodes"] if node["id"] != operation["node_id"]
                ]
                graph["edges"] = [
                    edge
                    for edge in graph["edges"]
                    if operation["node_id"] not in {edge["source"], edge["target"]}
                ]
                graph["selection"] = [
                    node_id
                    for node_id in graph.get("selection", [])
                    if node_id != operation["node_id"]
                ]
            elif action == "connect":
                graph["edges"].append(operation["edge"])
            elif action == "disconnect":
                graph["edges"] = [
                    edge for edge in graph["edges"] if edge["id"] != operation["edge_id"]
                ]
            elif action == "select":
                graph["selection"] = operation["node_ids"]
            elif action == "rename":
                name = operation["name"]
            elif action in {"workspace", "update_workspace"}:
                patch = operation.get("patch")
                if patch is None:
                    patch = operation.get("metadata")
                if patch is None:
                    patch = operation.get("workspace")
                if not isinstance(patch, dict):
                    raise ValueError("workspace 操作需要 object patch")
                workspace = graph.get("workspace", {})
                if not isinstance(workspace, dict):
                    raise ValueError("当前画布 workspace 不是 object")
                workspace = copy.deepcopy(workspace)
                for key, value in patch.items():
                    if not isinstance(key, str) or not key.strip():
                        raise ValueError("workspace 字段名需要是非空字符串")
                    if value is None:
                        workspace.pop(key, None)
                    else:
                        workspace[key] = value
                if workspace:
                    graph["workspace"] = workspace
                else:
                    graph.pop("workspace", None)
            else:
                raise ValueError(f"不支持的画布操作：{action}")
        return self.request(
            "PUT", f"/api/canvases/{canvas_id}", {"version": version, "graph": graph, "name": name}
        )
