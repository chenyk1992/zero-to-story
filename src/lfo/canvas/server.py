"""Loopback-only HTTP bridge and static media delivery for the local canvas."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlsplit

from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


class RuntimeLock:
    """Prevent two services from owning the same project queue."""

    def __init__(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.file = (folder / "server.lock").open("a+b")

    def __enter__(self):
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError("当前项目画布服务已经运行，请使用已有页面") from exc
        return self

    def __exit__(self, *_args):
        self.file.close()


class CanvasHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: CanvasService):
        self.service = service
        super().__init__(address, CanvasHandler)


class CanvasHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def canvas_server(self) -> CanvasHTTPServer:
        return cast(CanvasHTTPServer, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        # Prompts, local paths and provider credentials never enter HTTP logs.
        pass

    def _json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _origin_allowed(self) -> bool:
        port = self.canvas_server.server_address[1]
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in allowed_hosts}:
            return False
        return self.headers.get("Sec-Fetch-Site") not in {"cross-site"}

    def _body(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("请求需要 JSON 内容")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 4 * 1024 * 1024:
            raise ValueError("配置内容为空或过大")
        data = json.loads(
            self.rfile.read(size),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid {value}")),
        )
        if not isinstance(data, dict):
            raise ValueError("请求内容需要是对象")
        return data

    def _handle(self) -> None:
        if not self._origin_allowed():
            self.close_connection = True
            self._json(
                {"error": {"code": "origin_rejected", "message": "只允许当前本地画布访问"}}, 403
            )
            return
        if self.command in {"POST", "PUT"} and not (
            self.headers.get("Origin") or self.headers.get("X-Canvas-Request") == "1"
        ):
            self.close_connection = True
            self._json({"error": {"code": "request_rejected", "message": "缺少画布请求标识"}}, 403)
            return
        try:
            self._dispatch()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            status = getattr(
                exc, "status", 400 if isinstance(exc, (ValueError, KeyError, TypeError)) else 500
            )
            code = getattr(exc, "code", "invalid_request" if status == 400 else "service_error")
            self.close_connection = True
            self._json({"error": {"code": code, "message": str(exc)}}, status)

    def _dispatch(self) -> None:
        service = self.canvas_server.service
        url = urlsplit(self.path)
        path = unquote(url.path)
        query = parse_qs(url.query)
        segments = path.strip("/").split("/")
        method = self.command
        if method == "GET" and path == "/api/health":
            self._json({"status": "ok", "project_root": str(service.settings.project_root)})
        elif path == "/api/capabilities" and method in {"GET", "POST"}:
            tools = self._body().get("host_tools") if method == "POST" else None
            self._json({"capabilities": service.catalog.public(tools)})
        elif method == "GET" and path == "/api/events":
            self._json(
                service.events(
                    after=int(query.get("after", ["0"])[0]),
                    canvas_id=query.get("canvas_id", [None])[0],
                    wait_seconds=float(query.get("wait_seconds", ["0"])[0]),
                )
            )
        elif method == "POST" and path == "/api/events/ack":
            body = self._body()
            self._json(service.store.acknowledge_event(body["consumer_id"], body["event_id"]))
        elif method == "GET" and path == "/api/events/cursor":
            self._json({"cursor": service.store.get_event_cursor(query["consumer_id"][0])})
        elif method == "GET" and path == "/api/readiness":
            self._json(service.readiness(query["canvas_id"][0], query["node_id"][0]))
        elif method == "GET" and path == "/api/continuations":
            self._json(
                service.read_continuations(
                    session_id=query.get("session_id", [None])[0],
                    canvas_id=query.get("canvas_id", [None])[0],
                )
            )
        elif method == "POST" and path == "/api/continuations":
            body = self._body()
            payload = service.configure_continuation(
                body["canvas_id"],
                body["session_id"],
                body["node_ids"],
                body["authorization"],
                body["canvas_version"],
                body.get("revision"),
            )
            self._json(payload, 201 if payload.get("created") else 200)
        elif method == "POST" and path == "/api/continuations/hook":
            body = self._body()
            self._json(
                service.continuation_hook(
                    body["session_id"],
                    body["event"],
                    body.get("agent_id"),
                    body.get("turn_id"),
                )
            )
        elif (
            method == "POST"
            and len(segments) == 4
            and segments[:2] == ["api", "continuations"]
            and segments[3] in {"state", "units"}
        ):
            body = self._body()
            continuation_id = segments[2]
            if segments[3] == "state":
                self._json(
                    service.update_continuation_state(
                        continuation_id,
                        body["revision"],
                        body["state"],
                        body.get("reason"),
                    )
                )
            else:
                self._json(
                    service.update_continuation_unit(
                        continuation_id,
                        body["revision"],
                        body["unit_id"],
                        body["state"],
                        agent_id=body.get("agent_id"),
                        node_id=body.get("node_id"),
                        run_id=body.get("run_id"),
                        turn_id=body.get("turn_id"),
                        reason=body.get("reason"),
                    )
                )
        elif path == "/api/canvases":
            if method == "GET":
                self._json({"canvases": service.store.list_canvases()})
            elif method == "POST":
                body = self._body()
                self._json(
                    service.store.create_canvas(body.get("name", "未命名画布"), body.get("graph")),
                    201,
                )
            else:
                self._not_found()
        elif len(segments) == 3 and segments[:2] == ["api", "canvases"]:
            if method == "GET":
                canvas = service.store.get_canvas(segments[2])
                if query.get("node_id"):
                    node_id = query["node_id"][0]
                    edges = [edge for edge in canvas["graph"]["edges"] if edge["target"] == node_id]
                    ids = {node_id, *(edge["source"] for edge in edges)}
                    nodes = [node for node in canvas["graph"]["nodes"] if node["id"] in ids]
                    if not any(node["id"] == node_id for node in nodes):
                        raise ValueError("没有找到该组件")
                    self._json(
                        {
                            "id": canvas["id"],
                            "version": canvas["version"],
                            "nodes": nodes,
                            "edges": edges,
                        }
                    )
                else:
                    self._json(canvas)
            elif method == "PUT":
                body = self._body()
                self._json(
                    service.store.save_canvas(
                        segments[2], body["version"], body["graph"], name=body.get("name")
                    )
                )
            else:
                self._not_found()
        elif len(segments) == 4 and segments[:2] == ["api", "canvases"] and segments[3] == "runs":
            if method == "GET":
                runs = (
                    service.store.list_runs(segments[2])
                    if query.get("summary") == ["1"]
                    else service.runs(segments[2])
                )
                self._json(
                    {
                        "runs": [service.run_summary(run["id"]) for run in runs]
                        if query.get("summary") == ["1"]
                        else runs
                    }
                )
            elif method == "POST":
                body = self._body()
                self._json(
                    service.confirm(
                        segments[2], body["node_id"], body["version"], body["request_id"]
                    ),
                    201,
                )
            else:
                self._not_found()
        elif method == "GET" and path == "/api/runs":
            runs = service.store.list_runs() if query.get("summary") == ["1"] else service.runs()
            if query.get("status"):
                runs = [run for run in runs if run["status"] == query["status"][0]]
            self._json(
                {
                    "runs": [service.run_summary(run["id"]) for run in runs]
                    if query.get("summary") == ["1"]
                    else runs
                }
            )
        elif method == "GET" and len(segments) == 3 and segments[:2] == ["api", "runs"]:
            self._json(
                service.run_summary(segments[2])
                if query.get("summary") == ["1"]
                else service._public_run(service.store.get_run(segments[2]))
            )
        elif method == "POST" and len(segments) == 4 and segments[:2] == ["api", "runs"]:
            body = self._body()
            if segments[3] == "claim":
                self._json(service.claim_agent(segments[2], body.get("host_tools")))
            elif segments[3] == "complete":
                self._json(service.complete_agent(segments[2], **body))
            elif segments[3] == "reconcile":
                self._json(service.reconcile_run(segments[2], **body))
            elif segments[3] == "claim-recovery":
                token = service.store.claim_recovery(segments[2], **body)
                service._notify()
                self._json(
                    {
                        "run_id": segments[2],
                        "owner_token": token,
                    }
                )
            elif segments[3] == "progress":
                self._json(service.progress_agent(segments[2], **body))
            elif segments[3] == "attention":
                self._json(service.set_attention(segments[2], **body))
            elif segments[3] == "claim-review":
                token = service.store.claim_review(segments[2], body.get("owner_token"))
                service._notify()
                self._json({"run_id": segments[2], "owner_token": token})
            elif segments[3] == "review":
                self._json(service.review_output(segments[2], **body))
            elif segments[3] == "cancel":
                self._json(service.cancel_pending(segments[2]))
            else:
                self._not_found()
        elif method == "POST" and path == "/api/assets/import":
            self._json(service.media.import_file(self._body()["path"]), 201)
        elif method == "POST" and path == "/api/assets":
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512 * 1024 * 1024:
                raise ValueError("请选择非空且不超过 512 MB 的素材")
            target = service.media.upload_path(query.get("name", [""])[0])
            try:
                with target.open("wb") as stream:
                    remaining = size
                    while remaining:
                        block = self.rfile.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError("素材上传中断")
                        stream.write(block)
                        remaining -= len(block)
            except Exception:
                target.unlink(missing_ok=True)
                raise
            self._json(service.media.asset(target, query["name"][0]), 201)
        elif method == "GET" and path == "/api/media":
            self._file(service.media.resolve(query.get("path", [""])[0]), media=True)
        elif method == "GET" and not path.startswith("/api/"):
            root = service.settings.frontend.resolve()
            target = (root / path.lstrip("/")).resolve()
            if not target.is_relative_to(root):
                raise ValueError("页面路径无效")
            if not target.is_file():
                target = root / "index.html"
            if not target.is_file():
                self._json(
                    {
                        "error": {
                            "code": "frontend_missing",
                            "message": "请先构建画布页面：在 web/canvas 中运行 npm run build",
                        }
                    },
                    503,
                )
            else:
                self._file(target)
        else:
            self._not_found()

    def _not_found(self) -> None:
        self._json({"error": {"code": "not_found", "message": "没有找到这个画布操作"}}, 404)

    def _file(self, path: Path, *, media: bool = False) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        partial = False
        if media and self.headers.get("Range"):
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers["Range"])
            if not match or not any(match.groups()):
                self._range_error(size)
                return
            first, last = match.groups()
            start = int(first) if first else max(0, size - int(last))
            end = min(size - 1, int(last)) if last and first else size - 1
            if start > end or start >= size:
                self._range_error(size)
                return
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header(
            "Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        if media:
            self.send_header("Accept-Ranges", "bytes")
        else:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
            )
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                block = stream.read(min(256 * 1024, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def _range_error(self, size: int) -> None:
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle


def serve(settings: CanvasSettings) -> None:
    with RuntimeLock(settings.data_dir):
        service = CanvasService(settings, start_worker=False)
        try:
            server = CanvasHTTPServer(("127.0.0.1", settings.port), service)
        except OSError:
            service.close()
            raise
        # A stopped process cannot prove whether a submitted provider job ended.
        # Never resubmit such work or replay a queue on startup.
        for run in service.store.list_runs():
            if run["status"] == "running":
                service.store.update_run(
                    run["id"],
                    status="unknown",
                    error="服务已重启；需确认原任务的远端状态，不会自动重新提交",
                )
            elif run["status"] == "queued":
                service.store.update_run(
                    run["id"], status="failed", error="服务停止前尚未开始，请重新确认执行"
                )
        port = server.server_address[1]
        address = f"http://127.0.0.1:{port}"
        settings.discovery.write_text(
            json.dumps(
                {"url": address, "pid": os.getpid(), "project_root": str(settings.project_root)}
            ),
            encoding="utf-8",
        )
        service.start_worker()
        print(address, flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            service.close()
            server.server_close()
            settings.discovery.unlink(missing_ok=True)
