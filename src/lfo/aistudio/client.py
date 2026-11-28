"""Loopback HTTP client and local runtime config discovery for AIStudio2API."""

# ruff: noqa: RUF001 -- User-facing diagnostics follow repository Chinese conventions.

from __future__ import annotations

import base64
import http.client
import json
import math
import os
import shutil
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFINITIVE_HTTP_FAILURE_CODES = frozenset({400, 401, 403, 404, 405, 409, 413, 415, 422, 429})


class ExecutorError(RuntimeError):
    """A production error carrying explicit Canvas run terminal semantics."""

    stage: str = "input_validation"

    def __init__(
        self,
        message: str,
        *,
        provider_task_id: str | None = None,
        status: str = "failed",
        stage: str | None = None,
    ) -> None:
        super().__init__(message)
        if status not in {"failed", "unknown"}:
            raise ValueError(f"unsupported executor error status: {status}")
        self.provider_task_id = provider_task_id
        self.status = status
        if stage is not None:
            self.stage = stage


@dataclass(frozen=True)
class AIStudioConfig:
    base_url: str = "http://127.0.0.1:2048"
    api_key: str = ""
    request_timeout_seconds: float = 300.0
    video_timeout_seconds: float = 1800.0
    poll_interval_seconds: float = 3.0


@dataclass(frozen=True)
class GeneratedImage:
    mime_type: str
    data: bytes
    provider_task_id: str | None = None


@dataclass(frozen=True)
class VideoOperationState:
    operation_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    model: str | None = None
    size: str | None = None
    seconds: str | None = None


def redact_secret(text: str, secret: str = "") -> str:
    """Ensure local API keys never leak into logs, exceptions or run records."""
    if not text:
        return text
    cleaned = text
    if secret and len(secret) >= 4:
        cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def normalize_loopback_base_url(raw: str) -> str:
    """Accept only plain HTTP loopback endpoints without credentials or query strings."""
    if not isinstance(raw, str) or not raw.strip():
        raise ExecutorError("AIStudio2API 地址不能为空")
    parsed = urlsplit(raw.strip())
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or path not in {"", "/v1", "/v1beta"}
    ):
        raise ExecutorError("AIStudio2API 仅允许本机回环 HTTP 地址（如 http://127.0.0.1:2048）")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ExecutorError("AIStudio2API 端口无效") from exc
    if port is not None and not (1 <= port <= 65535):
        raise ExecutorError("AIStudio2API 端口必须在 1–65535 之间")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"http://{host}:{port}" if port else f"http://{host}"


def _positive_float(raw: str | None, default: float, label: str) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ExecutorError(f"{label} 需要正数") from exc
    if not math.isfinite(value) or value <= 0:
        raise ExecutorError(f"{label} 需要有限正数")
    return value


def _discover_magpie_studio_config(home: Path) -> tuple[str | None, str]:
    studio_cfg = home / ".local" / "share" / "magpie-ai-studio" / "config.json"
    if studio_cfg.is_file():
        try:
            payload = json.loads(studio_cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ExecutorError(f"无法读取本机 AIStudio2API 配置 {studio_cfg.name}: {exc}") from exc
        if isinstance(payload, dict):
            port = payload.get("port", 2048)
            if isinstance(port, bool) or not isinstance(port, int) or not (1 <= port <= 65535):
                raise ExecutorError("magpie-ai-studio 配置中的端口无效")
            key = ""
            for field in ("apiKey", "proxyApiKey", "api_key", "proxy_api_key"):
                candidate = payload.get(field)
                if isinstance(candidate, str) and candidate.strip():
                    key = candidate.strip()
                    break
            return f"http://127.0.0.1:{port}", key

    plugin_auth = home / ".config" / "magpie" / "plugin-auth.json"
    if plugin_auth.is_file():
        try:
            payload = json.loads(plugin_auth.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ExecutorError(f"无法读取 Magpie 插件认证配置 {plugin_auth.name}: {exc}") from exc
        if isinstance(payload, dict):
            for name, entry in payload.items():
                if not str(name).startswith("ai-studio") or not isinstance(entry, dict):
                    continue
                meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
                raw_url = (
                    entry.get("baseURL")
                    or entry.get("baseUrl")
                    or meta.get("baseURL")
                    or meta.get("baseUrl")
                    or "http://127.0.0.1:2048"
                )
                key = ""
                for source in (entry, meta):
                    for field in ("key", "apiKey", "api_key"):
                        candidate = source.get(field)
                        if isinstance(candidate, str) and candidate.strip():
                            key = candidate.strip()
                            break
                    if key:
                        break
                return normalize_loopback_base_url(str(raw_url)), key
    return None, ""


def load_runtime_config(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> AIStudioConfig:
    """Resolve loopback endpoint and optional API key from env or local Magpie config."""
    environment = env if env is not None else os.environ

    env_url = environment.get("LFO_AISTUDIO_BASE_URL", "").strip()
    env_key = environment.get("LFO_AISTUDIO_API_KEY", "").strip()

    if env_url:
        base_url = normalize_loopback_base_url(env_url)
        api_key = env_key
    else:
        resolved_home = (home or Path.home()).expanduser()
        discovered_url, discovered_key = _discover_magpie_studio_config(resolved_home)
        if not discovered_url:
            raise ExecutorError(
                "未找到本机 AIStudio2API 配置；请先启用 Magpie ai-studio 或设置 LFO_AISTUDIO_BASE_URL"
            )
        base_url = normalize_loopback_base_url(discovered_url)
        api_key = env_key or discovered_key

    return AIStudioConfig(
        base_url=base_url,
        api_key=api_key,
        request_timeout_seconds=_positive_float(
            environment.get("LFO_AISTUDIO_REQUEST_TIMEOUT"), 300.0, "LFO_AISTUDIO_REQUEST_TIMEOUT"
        ),
        video_timeout_seconds=_positive_float(
            environment.get("LFO_AISTUDIO_VIDEO_TIMEOUT"), 1800.0, "LFO_AISTUDIO_VIDEO_TIMEOUT"
        ),
        poll_interval_seconds=_positive_float(
            environment.get("LFO_AISTUDIO_POLL_INTERVAL"), 3.0, "LFO_AISTUDIO_POLL_INTERVAL"
        ),
    )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse HTTP redirects so loopback auth headers never cross origins."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise urllib.error.HTTPError(
            req.full_url,
            code,
            "AIStudio2API 回环接口不允许 HTTP 重定向",
            headers,
            fp,
        )


def _extract_error_message(raw_body: bytes, secret: str) -> str:
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except ValueError:
        return redact_secret(text[:400], secret)
    if isinstance(parsed, dict):
        err = parsed.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return redact_secret(err["message"].strip(), secret)
        if isinstance(err, str):
            return redact_secret(err.strip(), secret)
        if isinstance(parsed.get("message"), str):
            return redact_secret(parsed["message"].strip(), secret)
    return redact_secret(text[:400], secret)


def _is_pre_send_connection_error(exc: BaseException) -> bool:
    if isinstance(exc, ConnectionRefusedError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            return True
        if isinstance(reason, socket.gaierror):
            return True
    return False


class AIStudioClient:
    """Minimal, dependency-free loopback client for AIStudio2API."""

    def __init__(self, config: AIStudioConfig) -> None:
        self.config = AIStudioConfig(
            base_url=normalize_loopback_base_url(config.base_url),
            api_key=config.api_key,
            request_timeout_seconds=config.request_timeout_seconds,
            video_timeout_seconds=config.video_timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )

    def _headers(self, *, accept: str = "application/json", json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": accept}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            headers["x-goog-api-key"] = self.config.api_key
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        mutating: bool = False,
        timeout: float | None = None,
        provider_task_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=body,
            headers=self._headers(json_body=body is not None),
            method=method,
        )
        effective_timeout = timeout or self.config.request_timeout_seconds
        try:
            with self._opener.open(req, timeout=effective_timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            err_body = exc.read() if exc.fp is not None else b""
            detail = _extract_error_message(err_body, self.config.api_key) or redact_secret(
                str(exc.reason), self.config.api_key
            )
            definitive = exc.code in DEFINITIVE_HTTP_FAILURE_CODES or not mutating
            raise ExecutorError(
                f"AIStudio2API 请求失败（HTTP {exc.code}）：{detail}",
                provider_task_id=provider_task_id,
                status="failed" if definitive else "unknown",
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
            pre_send = _is_pre_send_connection_error(exc)
            detail = redact_secret(str(exc), self.config.api_key)
            if pre_send:
                raise ExecutorError(
                    f"无法连接本机 AIStudio2API（{self.config.base_url}），请确认服务已启动：{detail}",
                    provider_task_id=provider_task_id,
                    status="failed",
                ) from exc
            raise ExecutorError(
                f"AIStudio2API 通信中断：{detail}",
                provider_task_id=provider_task_id,
                status="unknown" if mutating or provider_task_id else "failed",
            ) from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise ExecutorError(
                "AIStudio2API 返回了非 JSON 响应",
                provider_task_id=provider_task_id,
                status="unknown" if mutating or provider_task_id else "failed",
            ) from exc
        if not isinstance(decoded, dict):
            raise ExecutorError(
                "AIStudio2API 响应结构无效",
                provider_task_id=provider_task_id,
                status="unknown" if mutating or provider_task_id else "failed",
            )
        return decoded

    def check_health(self) -> None:
        payload = self._request_json("GET", "/health", mutating=False, timeout=10.0)
        if payload.get("status") != "ok":
            raise ExecutorError("本机 AIStudio2API 健康检查未通过", status="failed")

    def list_models(self) -> dict[str, dict[str, Any]]:
        payload = self._request_json("GET", "/v1/models", mutating=False, timeout=15.0)
        items = payload.get("data")
        if not isinstance(items, list):
            raise ExecutorError("AIStudio2API 模型目录响应无效", status="failed")
        catalog: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"].strip()
            if not model_id:
                continue
            catalog[model_id] = item
            options = item.get("capability_options")
            if isinstance(options, dict) and isinstance(options.get("aliases"), list):
                for alias in options["aliases"]:
                    if isinstance(alias, str) and alias.strip() and alias.strip() not in catalog:
                        catalog[alias.strip()] = item
        return catalog

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        reference_images: list[tuple[str, bytes]],
        aspect_ratio: str | None,
        resolution: str,
    ) -> GeneratedImage:
        parts: list[dict[str, Any]] = [
            {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(raw).decode("ascii"),
                }
            }
            for mime_type, raw in reference_images
        ]
        parts.append({"text": prompt})
        image_config: dict[str, Any] = {"imageSize": resolution}
        if aspect_ratio:
            image_config["aspectRatio"] = aspect_ratio
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": image_config,
            },
        }
        encoded_model = quote(model.strip(), safe="-_.")
        response = self._request_json(
            "POST",
            f"/v1beta/models/{encoded_model}:generateContent",
            payload,
            mutating=True,
        )
        response_id = response.get("responseId")
        task_id = str(response_id).strip() if isinstance(response_id, str) and response_id.strip() else None

        prompt_feedback = response.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            reason = redact_secret(
                str(prompt_feedback.get("blockReasonMessage") or prompt_feedback["blockReason"]),
                self.config.api_key,
            )
            raise ExecutorError(f"AI Studio 拦截了图片请求：{reason}", provider_task_id=task_id, status="failed")

        candidates = response.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ExecutorError("AI Studio 未返回候选图片结果", provider_task_id=task_id, status="failed")

        finish_reasons: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            cand_parts = content.get("parts") if isinstance(content, dict) else None
            if isinstance(cand_parts, list):
                for part in cand_parts:
                    if not isinstance(part, dict):
                        continue
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not isinstance(inline, dict):
                        continue
                    mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "").strip()
                    b64_data = inline.get("data")
                    if mime_type.startswith("image/") and isinstance(b64_data, str) and b64_data.strip():
                        raw_b64 = b64_data.strip()
                        if "," in raw_b64 and raw_b64.startswith("data:"):
                            raw_b64 = raw_b64.split(",", 1)[1]
                        padded = raw_b64 + "=" * (-len(raw_b64) % 4)
                        try:
                            image_bytes = base64.urlsafe_b64decode(padded) if ("-" in raw_b64 or "_" in raw_b64) else base64.b64decode(padded)
                        except ValueError as exc:
                            raise ExecutorError("AI Studio 返回的图片 Base64 无法解码", provider_task_id=task_id, status="failed") from exc
                        if image_bytes:
                            return GeneratedImage(mime_type=mime_type, data=image_bytes, provider_task_id=task_id)
            finish = redact_secret(str(candidate.get("finishReason") or "").strip(), self.config.api_key)
            finish_msg = redact_secret(str(candidate.get("finishMessage") or "").strip(), self.config.api_key)
            if finish or finish_msg:
                finish_reasons.append(f"{finish} {finish_msg}".strip())

        detail = "；".join(finish_reasons) if finish_reasons else "响应不含图像数据"
        raise ExecutorError(f"AI Studio 未生成可用图片：{detail}", provider_task_id=task_id, status="failed")

    def submit_video(
        self,
        *,
        model: str,
        prompt: str,
        first_frame: tuple[str, bytes] | None,
        reference_images: list[tuple[str, bytes]],
        aspect_ratio: str,
        duration_seconds: int,
        resolution: str,
        negative_prompt: str | None = None,
    ) -> str:
        instance: dict[str, Any] = {"prompt": prompt}
        if first_frame is not None:
            mime_type, raw = first_frame
            instance["image"] = {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(raw).decode("ascii"),
                }
            }
        if reference_images:
            instance["referenceImages"] = [
                {
                    "image": {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    }
                }
                for mime_type, raw in reference_images
            ]
        parameters: dict[str, Any] = {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration_seconds,
            "resolution": resolution,
            "numberOfVideos": 1,
        }
        if negative_prompt and negative_prompt.strip():
            parameters["negativePrompt"] = negative_prompt.strip()

        encoded_model = quote(model.strip(), safe="-_.")
        response = self._request_json(
            "POST",
            f"/v1beta/models/{encoded_model}:predictLongRunning",
            {"instances": [instance], "parameters": parameters},
            mutating=True,
        )
        raw_name = response.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ExecutorError("AIStudio2API 未返回有效视频任务编号", status="unknown")
        operation_id = raw_name.strip().removeprefix("operations/").strip()
        if not operation_id:
            raise ExecutorError("AIStudio2API 返回的视频任务编号为空", status="unknown")
        return operation_id

    def get_video_operation(self, operation_id: str) -> VideoOperationState:
        clean_id = operation_id.strip().removeprefix("operations/").strip()
        if not clean_id:
            raise ExecutorError("视频任务编号为空", status="failed")
        encoded_id = quote(clean_id, safe="-_.~")
        response = self._request_json(
            "GET",
            f"/v1/videos/{encoded_id}",
            mutating=False,
            timeout=30.0,
            provider_task_id=clean_id,
        )
        status = str(response.get("status") or "").strip().lower()
        if status not in {"queued", "in_progress", "processing", "completed", "failed"}:
            raise ExecutorError(
                f"AIStudio2API 返回了未知视频状态：{status or '<empty>'}",
                provider_task_id=clean_id,
                status="unknown",
            )
        error_code = None
        error_message = None
        err = response.get("error")
        if isinstance(err, dict):
            if isinstance(err.get("code"), str):
                error_code = err["code"].strip()
            if isinstance(err.get("message"), str):
                error_message = redact_secret(err["message"].strip(), self.config.api_key)
        return VideoOperationState(
            operation_id=clean_id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            model=response.get("model") if isinstance(response.get("model"), str) else None,
            size=response.get("size") if isinstance(response.get("size"), str) else None,
            seconds=str(response["seconds"]) if response.get("seconds") is not None else None,
        )

    def wait_for_video(
        self,
        operation_id: str,
        *,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
    ) -> VideoOperationState:
        clean_id = operation_id.strip().removeprefix("operations/").strip()
        deadline = monotonic_fn() + self.config.video_timeout_seconds
        transient_failures = 0
        max_transient_failures = 5

        while True:
            try:
                state = self.get_video_operation(clean_id)
                transient_failures = 0
            except ExecutorError as exc:
                # Missing task history cannot prove upstream failure; preserve unknown for operator reconciliation.
                if "HTTP 404" in str(exc):
                    raise ExecutorError(
                        f"AIStudio2API 未找到已提交的视频任务 {clean_id}，远端终态未知，请先核实后再处理",
                        provider_task_id=clean_id,
                        status="unknown",
                    ) from exc
                transient_failures += 1
                if transient_failures >= max_transient_failures or monotonic_fn() >= deadline:
                    raise ExecutorError(
                        f"轮询视频任务 {clean_id} 时连接中断，未确认远端终态：{exc}",
                        provider_task_id=clean_id,
                        status="unknown",
                    ) from exc
                sleep_fn(min(self.config.poll_interval_seconds * transient_failures, 10.0))
                continue

            if state.status == "completed":
                return state
            if state.status == "failed":
                if state.error_code == "video_not_found":
                    detail = state.error_message or "服务重启前任务没有生成完成"
                    raise ExecutorError(
                        f"AIStudio2API 丢失了视频任务 {clean_id} 的完成记录（{detail}），远端终态未知",
                        provider_task_id=clean_id,
                        status="unknown",
                    )
                detail = state.error_message or state.error_code or "上游未返回具体原因"
                raise ExecutorError(
                    f"AI Studio 视频生成失败：{detail}",
                    provider_task_id=clean_id,
                    status="failed",
                )

            remaining = deadline - monotonic_fn()
            if remaining <= 0:
                raise ExecutorError(
                    f"等待 AI Studio 视频任务 {clean_id} 超时，远端仍在处理中，请稍后核实原任务结果",
                    provider_task_id=clean_id,
                    status="unknown",
                )
            sleep_fn(min(self.config.poll_interval_seconds, remaining))

    def download_video(
        self,
        operation_id: str,
        destination: Path,
        *,
        sleep_fn=time.sleep,
    ) -> None:
        clean_id = operation_id.strip().removeprefix("operations/").strip()
        encoded_id = quote(clean_id, safe="-_.~")
        url = f"{self.config.base_url}/v1/videos/{encoded_id}/content"
        last_error: Exception | None = None

        for attempt in range(1, 4):
            req = urllib.request.Request(
                url,
                headers=self._headers(accept="video/mp4,application/octet-stream,*/*"),
                method="GET",
            )
            try:
                with self._opener.open(req, timeout=self.config.request_timeout_seconds) as resp, destination.open("wb") as out:
                    shutil.copyfileobj(resp, out)
                if destination.is_file() and destination.stat().st_size > 0:
                    return
                last_error = ExecutorError("下载的视频文件为空", provider_task_id=clean_id, status="unknown")
            except urllib.error.HTTPError as exc:
                err_body = exc.read() if exc.fp is not None else b""
                detail = _extract_error_message(err_body, self.config.api_key) or redact_secret(
                    str(exc.reason), self.config.api_key
                )
                if exc.code == 404:
                    raise ExecutorError(
                        f"AIStudio2API 视频结果记录缺失（{clean_id}）：{detail}",
                        provider_task_id=clean_id,
                        status="unknown",
                    ) from exc
                last_error = ExecutorError(
                    f"下载视频结果失败（HTTP {exc.code}）：{detail}",
                    provider_task_id=clean_id,
                    status="unknown",
                )
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
                last_error = ExecutorError(
                    f"下载视频结果时连接中断（{clean_id}）：{redact_secret(str(exc), self.config.api_key)}",
                    provider_task_id=clean_id,
                    status="unknown",
                )
            if attempt < 3:
                sleep_fn(min(self.config.poll_interval_seconds * attempt, 6.0))

        assert last_error is not None
        if isinstance(last_error, ExecutorError):
            raise last_error
        raise ExecutorError(str(last_error), provider_task_id=clean_id, status="unknown")
