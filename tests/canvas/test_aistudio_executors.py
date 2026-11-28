"""Tests for local AIStudio2API image and video Canvas executors."""

from __future__ import annotations

import base64
import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from lfo.aistudio.client import (
    AIStudioClient,
    AIStudioConfig,
    ExecutorError,
    load_runtime_config,
    normalize_loopback_base_url,
)
from lfo.aistudio.image import normalize_snapshot as normalize_image_snapshot
from lfo.aistudio.video import (
    normalize_snapshot as normalize_video_snapshot,
)
from lfo.aistudio.video import (
    reconcile_operation,
)
from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.graph import CanvasError
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

PROJECT = Path(__file__).resolve().parents[2]


def _make_image(path: Path, *, fmt: str = "png", color: str = "steelblue", size: str = "64x64") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}",
            "-frames:v",
            "1",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return path


def _make_mp4(path: Path, *, duration: float = 1.0, size: str = "320x180") -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={size}:rate=24",
            "-t",
            str(duration),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return path.read_bytes()


class MockAIStudioServer:
    """Thread-safe loopback HTTP fixture emulating AIStudio2API."""

    def __init__(self, *, api_key: str = "super-secret-test-key", jpeg_bytes: bytes = b"", mp4_bytes: bytes = b"") -> None:
        self.api_key = api_key
        self.jpeg_bytes = jpeg_bytes
        self.mp4_bytes = mp4_bytes
        self.lock = threading.Lock()
        self.image_submits: list[dict[str, Any]] = []
        self.video_submits: list[dict[str, Any]] = []
        self.poll_counts: dict[str, int] = {}
        self.download_counts: dict[str, int] = {}
        self.mode: str = "normal"
        self.redirect_target: str | None = None

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _check_auth(self) -> bool:
                if outer.redirect_target:
                    self.send_response(302)
                    self.send_header("Location", outer.redirect_target)
                    self.end_headers()
                    return False
                auth = self.headers.get("Authorization", "")
                goog = self.headers.get("x-goog-api-key", "")
                if outer.api_key and auth != f"Bearer {outer.api_key}" and goog != outer.api_key:
                    self._send_json(401, {"error": {"message": f"invalid key near {outer.api_key}"}})
                    return False
                return True

            def _send_json(self, status: int, body: dict[str, Any]) -> None:
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._send_json(200, {"status": "ok"})
                    return
                if not self._check_auth():
                    return
                if self.path == "/v1/models":
                    self._send_json(
                        200,
                        {
                            "object": "list",
                            "data": [
                                {
                                    "id": "gemini-nano-banana-2.1",
                                    "capability_options": {
                                        "image_aspect_ratios": ["1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "4:5", "5:4", "21:9"],
                                        "image_output_resolutions": ["1K", "2K", "4K"],
                                    },
                                },
                                {
                                    "id": "gemini-3-pro-image",
                                    "capability_options": {
                                        "image_aspect_ratios": ["1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "4:5", "5:4", "21:9"],
                                        "image_output_resolutions": ["1K", "2K", "4K"],
                                    },
                                },
                                {
                                    "id": "gemini-omni-1.2-flash",
                                    "capability_options": {
                                        "video_aspect_ratios": ["16:9", "9:16"],
                                        "video_output_resolutions": ["360p", "720p", "1080p", "4k"],
                                        "video_tasks": ["text_to_video", "image_to_video", "reference_to_video", "edit", "extend"],
                                    },
                                },
                            ],
                        },
                    )
                    return
                if self.path.startswith("/v1/videos/") and self.path.endswith("/content"):
                    op_id = self.path[len("/v1/videos/") : -len("/content")]
                    with outer.lock:
                        outer.download_counts[op_id] = outer.download_counts.get(op_id, 0) + 1
                        mode = outer.mode
                    if mode == "download_fail":
                        self._send_json(502, {"error": {"message": f"upstream storage error ({outer.api_key})"}})
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(outer.mp4_bytes)))
                    self.end_headers()
                    self.wfile.write(outer.mp4_bytes)
                    return
                if self.path.startswith("/v1/videos/"):
                    op_id = self.path[len("/v1/videos/") :]
                    with outer.lock:
                        count = outer.poll_counts.get(op_id, 0) + 1
                        outer.poll_counts[op_id] = count
                        mode = outer.mode
                    if mode == "poll_404":
                        self._send_json(404, {"error": {"code": "video_not_found", "message": "video not found"}})
                        return
                    if mode == "poll_timeout":
                        self._send_json(200, {"id": op_id, "object": "video", "status": "queued", "progress": 0})
                        return
                    if mode == "restart_missing":
                        self._send_json(
                            200,
                            {
                                "id": op_id,
                                "object": "video",
                                "status": "failed",
                                "error": {"code": "video_not_found", "message": "服务重启前任务没有生成完成"},
                            },
                        )
                        return
                    if mode == "terminal_failed":
                        self._send_json(
                            200,
                            {
                                "id": op_id,
                                "object": "video",
                                "status": "failed",
                                "error": {"code": "video_generation_failed", "message": "SAFETY: content filtered"},
                            },
                        )
                        return
                    if mode == "transient_poll_once" and count == 1:
                        self._send_json(503, {"error": {"message": "temporary poll glitch"}})
                        return
                    if count < 2:
                        self._send_json(200, {"id": op_id, "object": "video", "status": "queued", "progress": 0})
                    else:
                        self._send_json(
                            200,
                            {
                                "id": op_id,
                                "object": "video",
                                "model": "gemini-omni-1.2-flash",
                                "status": "completed",
                                "progress": 100,
                            },
                        )
                    return
                self._send_json(404, {"error": {"message": "not found"}})

            def do_POST(self) -> None:
                if not self._check_auth():
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if self.path.endswith(":generateContent"):
                    with outer.lock:
                        outer.image_submits.append({"path": self.path, "payload": payload})
                        mode = outer.mode
                    if mode == "image_bad_request":
                        self._send_json(400, {"error": {"message": f"invalid prompt ({outer.api_key})"}})
                        return
                    if mode == "image_prompt_blocked":
                        self._send_json(
                            200,
                            {
                                "responseId": "img-blocked",
                                "promptFeedback": {
                                    "blockReason": "SAFETY",
                                    "blockReasonMessage": f"blocked with {outer.api_key}",
                                },
                            },
                        )
                        return
                    if mode == "image_finish_blocked":
                        self._send_json(
                            200,
                            {
                                "responseId": "img-finish-blocked",
                                "candidates": [
                                    {
                                        "content": {"parts": []},
                                        "finishReason": "IMAGE_SAFETY",
                                        "finishMessage": f"filtered near {outer.api_key}",
                                    }
                                ],
                            },
                        )
                        return
                    self._send_json(
                        200,
                        {
                            "responseId": f"img-resp-{len(outer.image_submits)}",
                            "candidates": [
                                {
                                    "content": {
                                        "parts": [
                                            {
                                                "inlineData": {
                                                    "mimeType": "image/jpeg",
                                                    "data": base64.b64encode(outer.jpeg_bytes).decode("ascii"),
                                                }
                                            }
                                        ]
                                    },
                                    "finishReason": "STOP",
                                }
                            ],
                        },
                    )
                    return
                if self.path.endswith(":predictLongRunning"):
                    with outer.lock:
                        outer.video_submits.append({"path": self.path, "payload": payload})
                        op_id = f"omni-task-{len(outer.video_submits)}"
                    self._send_json(200, {"name": f"operations/{op_id}"})
                    return
                self._send_json(404, {"error": {"message": "not found"}})

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def mock_aistudio(tmp_path: Path):
    jpg = _make_image(tmp_path / "fixture_out.jpg", fmt="jpg", color="coral", size="96x64")
    mp4_bytes = _make_mp4(tmp_path / "fixture_out.mp4", duration=1.0, size="320x180")
    server = MockAIStudioServer(jpeg_bytes=jpg.read_bytes(), mp4_bytes=mp4_bytes)
    try:
        yield server
    finally:
        server.close()


def _wait_terminal(service: CanvasService, run_id: str, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = service.store.get_run(run_id)
        if run["status"] in {"succeeded", "failed", "unknown", "cancelled"}:
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not settle within {timeout}s")


def test_config_discovery_and_loopback_guard(tmp_path: Path) -> None:
    with pytest.raises(ExecutorError, match="未找到本机 AIStudio2API 配置"):
        load_runtime_config(env={}, home=tmp_path)

    plugin_dir = tmp_path / ".config" / "magpie"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin-auth.json").write_text(
        json.dumps(
            {
                "ai-studio#abc": {
                    "type": "oauth",
                    "key": "plug-secret",
                    "metadata": {"mode": "managed", "baseURL": "http://127.0.0.1:2055/v1"},
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = load_runtime_config(env={}, home=tmp_path)
    assert cfg.base_url == "http://127.0.0.1:2055"
    assert cfg.api_key == "plug-secret"

    studio_dir = tmp_path / ".local" / "share" / "magpie-ai-studio"
    studio_dir.mkdir(parents=True)
    (studio_dir / "config.json").write_text(
        json.dumps({"port": 2099, "apiKey": "studio-secret"}),
        encoding="utf-8",
    )
    cfg2 = load_runtime_config(env={}, home=tmp_path)
    assert cfg2.base_url == "http://127.0.0.1:2099"
    assert cfg2.api_key == "studio-secret"

    # Key-only env overrides credential on discovered Magpie endpoint
    cfg_key_override = load_runtime_config(
        env={"LFO_AISTUDIO_API_KEY": "override-secret"},
        home=tmp_path,
    )
    assert cfg_key_override.base_url == "http://127.0.0.1:2099"
    assert cfg_key_override.api_key == "override-secret"

    # Explicit LFO_AISTUDIO_BASE_URL skips Magpie config completely (does not inherit Magpie key)
    cfg_explicit_no_key = load_runtime_config(
        env={"LFO_AISTUDIO_BASE_URL": "http://127.0.0.1:2099"},
        home=tmp_path,
    )
    assert cfg_explicit_no_key.base_url == "http://127.0.0.1:2099"
    assert cfg_explicit_no_key.api_key == ""

    # Explicit LFO_AISTUDIO_BASE_URL succeeds even when Magpie config files contain malformed JSON
    (studio_dir / "config.json").write_text("{corrupted-json", encoding="utf-8")
    (plugin_dir / "plugin-auth.json").write_text("{corrupted-auth", encoding="utf-8")
    cfg_explicit_with_broken_magpie = load_runtime_config(
        env={
            "LFO_AISTUDIO_BASE_URL": "http://127.0.0.1:2048/v1",
            "LFO_AISTUDIO_API_KEY": "standalone-key",
        },
        home=tmp_path,
    )
    assert cfg_explicit_with_broken_magpie.base_url == "http://127.0.0.1:2048"
    assert cfg_explicit_with_broken_magpie.api_key == "standalone-key"
    with pytest.raises(ExecutorError, match="无法读取本机 AIStudio2API 配置"):
        load_runtime_config(env={}, home=tmp_path)

    for invalid in (
        "https://127.0.0.1:2048",
        "http://192.168.1.10:2048",
        "http://example.com:2048",
        "http://admin:secret@127.0.0.1:2048",
        "http://127.0.0.1:2048?key=secret",
        "http://127.0.0.1:2048/other/path",
    ):
        with pytest.raises(ExecutorError):
            normalize_loopback_base_url(invalid)


def test_redirect_blocked_and_secret_redacted_across_all_image_error_paths(
    mock_aistudio: MockAIStudioServer,
) -> None:
    client = AIStudioClient(
        AIStudioConfig(base_url=mock_aistudio.base_url, api_key=mock_aistudio.api_key)
    )
    for error_mode in ("image_bad_request", "image_prompt_blocked", "image_finish_blocked"):
        mock_aistudio.mode = error_mode
        with pytest.raises(ExecutorError) as exc_info:
            client.generate_image(
                model="gemini-nano-banana-2.1",
                prompt="test",
                reference_images=[],
                aspect_ratio="1:1",
                resolution="1K",
            )
        assert mock_aistudio.api_key not in str(exc_info.value)
        assert "[REDACTED]" in str(exc_info.value)
        assert exc_info.value.status == "failed"

    mock_aistudio.mode = "normal"
    mock_aistudio.redirect_target = "http://evil.example.com/steal"
    with pytest.raises(ExecutorError, match="重定向") as exc_info2:
        client.list_models()
    assert exc_info2.value.status == "failed"


def test_catalog_and_input_contract_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", "http://127.0.0.1:2048")
    catalog = CapabilityCatalog(PROJECT)
    assert catalog.get("aistudio-image")["available"] is True
    assert catalog.get("aistudio-video")["available"] is True

    monkeypatch.delenv("LFO_AISTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LFO_AISTUDIO_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    unavailable_vid = CapabilityCatalog(PROJECT).get("aistudio-video")
    assert unavailable_vid["available"] is False
    assert "AIStudio2API" in unavailable_vid["reason"]

    frame = _make_image(tmp_path / "f.png")
    with pytest.raises(ValueError, match="不支持模式 fl2v"):
        normalize_video_snapshot(
            {
                "node_type": "video",
                "provider": "aistudio-video",
                "model": "gemini-omni-1.2-flash",
                "mode": "fl2v",
                "request_id": "req-1",
                "prompt": "camera pan",
                "parameters": {"duration": 5, "aspect_ratio": "16:9"},
                "inputs": {"first_frame": {"path": str(frame), "kind": "image"}},
            }
        )

    with pytest.raises(ValueError, match="最多支持 6"):
        normalize_video_snapshot(
            {
                "node_type": "video",
                "provider": "aistudio-video",
                "model": "gemini-omni-1.2-flash",
                "mode": "r2v",
                "request_id": "req-r2v-7",
                "prompt": "combine references",
                "parameters": {"duration": 6, "aspect_ratio": "16:9"},
                "inputs": {"reference_images": [{"path": str(frame), "kind": "image"} for _ in range(7)]},
            }
        )

    with pytest.raises(ValueError, match="10 秒"):
        normalize_video_snapshot(
            {
                "node_type": "video",
                "provider": "aistudio-video",
                "model": "gemini-omni-1.1-flash",
                "mode": "t2v",
                "request_id": "req-2",
                "prompt": "camera pan",
                "parameters": {"duration": 12, "aspect_ratio": "16:9"},
                "inputs": {},
            }
        )

    refs = [{"path": str(frame), "kind": "image"} for _ in range(15)]
    with pytest.raises(ValueError, match="最多支持 14"):
        normalize_image_snapshot(
            {
                "node_type": "image",
                "provider": "aistudio-image",
                "model": "gemini-nano-banana-2.1",
                "mode": "reference",
                "request_id": "req-3",
                "prompt": "combine references",
                "parameters": {"aspect_ratio": "16:9", "resolution": "2K"},
                "inputs": {"reference_images": refs},
            }
        )


def test_canvas_worker_image_reference_and_jpeg_to_png_conversion(
    tmp_path: Path, mock_aistudio: MockAIStudioServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", mock_aistudio.base_url)
    monkeypatch.setenv("LFO_AISTUDIO_API_KEY", mock_aistudio.api_key)

    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=True)
    try:
        ref1 = _make_image(settings.media_root / "projects" / "demo" / "ref1.png", color="navy")
        ref2 = _make_image(settings.media_root / "projects" / "demo" / "ref2.png", color="gold")
        a1 = service.media.import_file(str(ref1))
        a2 = service.media.import_file(str(ref2))

        graph = {
            "nodes": [
                {"id": "r1", "type": "asset", "position": {"x": 0, "y": 0}, "data": {"asset": a1}},
                {"id": "r2", "type": "asset", "position": {"x": 0, "y": 100}, "data": {"asset": a2}},
                {
                    "id": "img-node",
                    "type": "image",
                    "position": {"x": 200, "y": 50},
                    "data": {
                        "prompt": "保持图1角色服饰，采用图2暖金逆光",
                        "provider": "aistudio-image",
                        "model": "gemini-nano-banana-2.1",
                        "mode": "reference",
                        "aspect_ratio": "16:9",
                        "options": {"aistudio-image": {"resolution": "2K"}},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "r1", "sourceHandle": "output", "target": "img-node", "targetHandle": "reference_image"},
                {"id": "e2", "source": "r2", "sourceHandle": "output", "target": "img-node", "targetHandle": "reference_image"},
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": ["img-node"],
        }
        canvas = service.store.create_canvas("AI Studio 图片测试", graph)
        confirmed = service.confirm(canvas["id"], "img-node", canvas["version"], "img-req-1")
        assert confirmed["status"] == "queued"

        settled = _wait_terminal(service, confirmed["id"])
        assert settled["status"] == "succeeded", settled.get("error")
        assert len(mock_aistudio.image_submits) == 1
        sent_parts = mock_aistudio.image_submits[0]["payload"]["contents"][0]["parts"]
        assert len(sent_parts) == 3
        assert "inlineData" in sent_parts[0] and "inlineData" in sent_parts[1]
        assert sent_parts[2]["text"] == "保持图1角色服饰，采用图2暖金逆光"

        output = settled["outputs"][0]
        assert output["kind"] == "image"
        assert Path(output["path"]).suffix == ".png"
        assert output["metadata"]["codec"] == "png"
        assert output["metadata"]["width"] == 96
        assert output["metadata"]["height"] == 64

        conditions_file = settings.output_dir(canvas["id"], confirmed["id"]) / "conditions.json"
        assert mock_aistudio.api_key not in conditions_file.read_text(encoding="utf-8")
    finally:
        service.close()


@pytest.mark.parametrize("mode,ref_count", [("i2v", 1), ("r2v", 6)])
def test_canvas_worker_video_reference_modes_boundary_and_single_submit(
    mode: str,
    ref_count: int,
    tmp_path: Path,
    mock_aistudio: MockAIStudioServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_aistudio.mode = "transient_poll_once"
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", mock_aistudio.base_url)
    monkeypatch.setenv("LFO_AISTUDIO_API_KEY", mock_aistudio.api_key)
    monkeypatch.setenv("LFO_AISTUDIO_POLL_INTERVAL", "0.05")

    settings = CanvasSettings(PROJECT, tmp_path / f"state-{mode}", tmp_path / f"media-{mode}", 0)
    service = CanvasService(settings, start_worker=True)
    try:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for idx in range(7):
            img_file = _make_image(settings.media_root / "projects" / "demo" / f"f{idx}.png", color="teal")
            asset = service.media.import_file(str(img_file))
            nodes.append({"id": f"a{idx}", "type": "asset", "position": {"x": 0, "y": idx * 50}, "data": {"asset": asset}})

        if mode == "r2v":
            over_edges = [
                {"id": f"eo{idx}", "source": f"a{idx}", "sourceHandle": "output", "target": "vid-node", "targetHandle": "reference_image"}
                for idx in range(7)
            ]
            over_canvas = service.store.create_canvas(
                "超限校验",
                {
                    "nodes": [
                        *nodes,
                        {
                            "id": "vid-node",
                            "type": "video",
                            "position": {"x": 220, "y": 50},
                            "data": {
                                "prompt": "7 图超限应拒绝",
                                "provider": "aistudio-video",
                                "model": "gemini-omni-1.2-flash",
                                "mode": "r2v",
                                "duration": 6,
                                "aspect_ratio": "16:9",
                            },
                        },
                    ],
                    "edges": over_edges,
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                    "selection": ["vid-node"],
                },
            )
            with pytest.raises((ValueError, CanvasError), match="最多支持 6"):
                service.confirm(over_canvas["id"], "vid-node", over_canvas["version"], "vid-over-7")

        for idx in range(ref_count):
            edges.append(
                {
                    "id": f"e{idx}",
                    "source": f"a{idx}",
                    "sourceHandle": "output",
                    "target": "vid-node",
                    "targetHandle": "first_frame" if mode == "i2v" else "reference_image",
                }
            )
        graph = {
            "nodes": [
                *nodes[:ref_count],
                {
                    "id": "vid-node",
                    "type": "video",
                    "position": {"x": 220, "y": 50},
                    "data": {
                        "prompt": "镜头缓慢推进，雨滴落在霓虹路面上",
                        "provider": "aistudio-video",
                        "model": "gemini-omni-1.2-flash",
                        "mode": mode,
                        "duration": 6,
                        "aspect_ratio": "16:9",
                        "options": {"aistudio-video": {"resolution": "1080p"}},
                    },
                },
            ],
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": ["vid-node"],
        }
        canvas = service.store.create_canvas("AI Studio 视频测试", graph)
        confirmed = service.confirm(canvas["id"], "vid-node", canvas["version"], f"vid-req-{mode}")
        settled = _wait_terminal(service, confirmed["id"])

        assert settled["status"] == "succeeded", settled.get("error")
        assert settled["provider_task_id"] == "omni-task-1"
        assert len(mock_aistudio.video_submits) == 1
        instance = mock_aistudio.video_submits[0]["payload"]["instances"][0]
        if mode == "i2v":
            assert "image" in instance and "referenceImages" not in instance
        else:
            assert len(instance["referenceImages"]) == 6 and "image" not in instance
        assert settled["outputs"][0]["kind"] == "video"
        assert settled["outputs"][0]["metadata"]["width"] == 320
    finally:
        service.close()


def test_canvas_worker_video_unknown_vs_terminal_failed_and_recovery(
    tmp_path: Path, mock_aistudio: MockAIStudioServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", mock_aistudio.base_url)
    monkeypatch.setenv("LFO_AISTUDIO_API_KEY", mock_aistudio.api_key)
    monkeypatch.setenv("LFO_AISTUDIO_POLL_INTERVAL", "0.05")
    monkeypatch.setenv("LFO_AISTUDIO_VIDEO_TIMEOUT", "0.25")

    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=True)
    try:
        def make_t2v_canvas(title: str) -> dict[str, Any]:
            return service.store.create_canvas(
                title,
                {
                    "nodes": [
                        {
                            "id": "v1",
                            "type": "video",
                            "position": {"x": 0, "y": 0},
                            "data": {
                                "prompt": "海浪拍打礁石",
                                "provider": "aistudio-video",
                                "model": "gemini-omni-1.2-flash",
                                "mode": "t2v",
                                "duration": 5,
                                "aspect_ratio": "16:9",
                            },
                        }
                    ],
                    "edges": [],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                    "selection": ["v1"],
                },
            )

        def clear_unknown(run_id: str, req_id: str, task_id: str) -> None:
            tok = service.store.claim_recovery(run_id, "test cleanup")
            service.reconcile_run(
                run_id,
                tok,
                "cancelled",
                {
                    "request_id": req_id,
                    "remote_status": "cancelled",
                    "source": "operator_confirmation",
                    "reason": "cleanup unknown fixture",
                },
                provider_task_id=task_id,
            )

        # 1. Polling timeout -> unknown, preserving operation_id
        mock_aistudio.mode = "poll_timeout"
        c1 = make_t2v_canvas("超时测试")
        r1 = service.confirm(c1["id"], "v1", c1["version"], "req-timeout")
        s1 = _wait_terminal(service, r1["id"])
        assert s1["status"] == "unknown"
        assert s1["provider_task_id"] == "omni-task-1"
        clear_unknown(r1["id"], "req-timeout", "omni-task-1")

        # 2. Polling HTTP 404 (missing task history) -> unknown
        monkeypatch.setenv("LFO_AISTUDIO_VIDEO_TIMEOUT", "5.0")
        mock_aistudio.mode = "poll_404"
        c2 = make_t2v_canvas("404缺失历史测试")
        r2 = service.confirm(c2["id"], "v1", c2["version"], "req-404")
        s2 = _wait_terminal(service, r2["id"])
        assert s2["status"] == "unknown"
        assert s2["provider_task_id"] == "omni-task-2"
        clear_unknown(r2["id"], "req-404", "omni-task-2")

        # 3. Restart missing history (video_not_found) -> unknown, reconcile_operation keeps unknown
        mock_aistudio.mode = "restart_missing"
        c3 = make_t2v_canvas("重启丢失历史测试")
        r3 = service.confirm(c3["id"], "v1", c3["version"], "req-restart")
        s3 = _wait_terminal(service, r3["id"])
        assert s3["status"] == "unknown"
        assert s3["provider_task_id"] == "omni-task-3"
        rec_missing = reconcile_operation(
            "omni-task-3", settings.output_dir(c3["id"], r3["id"]), load_runtime_config()
        )
        assert rec_missing["status"] == "unknown"
        clear_unknown(r3["id"], "req-restart", "omni-task-3")

        # 4. Explicit upstream generation failure (video_generation_failed) -> failed
        mock_aistudio.mode = "terminal_failed"
        c4 = make_t2v_canvas("明确失败测试")
        r4 = service.confirm(c4["id"], "v1", c4["version"], "req-term-fail")
        s4 = _wait_terminal(service, r4["id"])
        assert s4["status"] == "failed"
        assert s4["provider_task_id"] == "omni-task-4"
        assert "SAFETY" in (s4.get("error") or "")

        # 5. Download failure after remote completion -> unknown, then reconcile recovers without re-submit
        mock_aistudio.mode = "download_fail"
        c5 = make_t2v_canvas("下载恢复测试")
        r5 = service.confirm(c5["id"], "v1", c5["version"], "req-dl")
        s5 = _wait_terminal(service, r5["id"])
        assert s5["status"] == "unknown"
        assert s5["provider_task_id"] == "omni-task-5"
        assert mock_aistudio.api_key not in (s5.get("error") or "")
        assert len(mock_aistudio.video_submits) == 5

        mock_aistudio.mode = "normal"
        recovered = reconcile_operation(
            "omni-task-5",
            settings.output_dir(c5["id"], r5["id"]),
            load_runtime_config(),
            request_id="req-dl",
        )
        assert recovered["status"] == "succeeded"
        token5 = service.store.claim_recovery(r5["id"], "recover completed video")
        reconciled = service.reconcile_run(
            r5["id"],
            token5,
            "succeeded",
            recovered["evidence"],
            outputs=recovered["outputs"],
            provider_task_id="omni-task-5",
        )
        assert reconciled["status"] == "succeeded"
        assert len(reconciled["outputs"]) == 1
        assert len(mock_aistudio.video_submits) == 5
    finally:
        service.close()
