"""Local MiniMax voice-cloning adapter.

The adapter follows MiniMax's two-request flow:
1. multipart upload to /v1/files/upload;
2. JSON request to /v1/voice_clone using the returned file_id.

It intentionally uses only Python's standard library so the skill can run in
the local Windows workspace without installing another SDK.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request


MAX_AUDIO_BYTES = 20 * 1024 * 1024
MIN_CLONE_SECONDS = 10.0
MAX_CLONE_SECONDS = 5 * 60.0
MAX_PROMPT_SECONDS = 8.0
SUPPORTED_SUFFIXES = {".mp3", ".m4a", ".wav"}
VOICE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]$")


class VoiceCloneError(RuntimeError):
    """A user-actionable local or MiniMax API error."""


@dataclass(frozen=True)
class AudioInfo:
    path: Path
    size_bytes: int
    duration_seconds: float
    format_name: str


def _json_or_text(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text[:2000]


def _error_detail(payload: Any) -> str:
    if isinstance(payload, dict):
        base_resp = payload.get("base_resp")
        if isinstance(base_resp, dict):
            status_msg = base_resp.get("status_msg")
            status_code = base_resp.get("status_code")
            if status_msg or status_code is not None:
                return f"status_code={status_code}, status_msg={status_msg}"
        for key in ("message", "error", "detail"):
            value = payload.get(key)
            if value:
                return str(value)[:1000]
    return str(payload)[:1000]


def _post(url: str, *, headers: dict[str, str], body: bytes, timeout: float) -> Any:
    http_request = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            payload = _json_or_text(response.read())
    except error.HTTPError as exc:
        payload = _json_or_text(exc.read())
        raise VoiceCloneError(
            f"MiniMax HTTP {exc.code} at {url}: {_error_detail(payload)}"
        ) from exc
    except error.URLError as exc:
        raise VoiceCloneError(f"无法连接 MiniMax ({url}): {exc.reason}") from exc
    except TimeoutError as exc:
        raise VoiceCloneError(f"MiniMax 请求超时 ({url})") from exc

    if not isinstance(payload, dict):
        raise VoiceCloneError(f"MiniMax 返回了非 JSON 对象: {_error_detail(payload)}")
    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict) and base_resp.get("status_code") not in (None, 0, "0"):
        raise VoiceCloneError(f"MiniMax API 失败: {_error_detail(payload)}")
    return payload


def _probe_audio(path: Path) -> tuple[float, str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise VoiceCloneError(
            "找不到 ffprobe，无法验证音频时长；请先安装 FFmpeg 并确保 ffprobe 在 PATH 中。"
        )

    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[:1000]
        raise VoiceCloneError(f"ffprobe 无法读取音频: {detail}")

    try:
        data = json.loads(completed.stdout)
        format_data = data["format"]
        duration = float(format_data["duration"])
        format_name = str(format_data.get("format_name") or "unknown")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VoiceCloneError("ffprobe 返回的音频元数据不完整。") from exc
    return duration, format_name


def inspect_audio(
    raw_path: str | os.PathLike[str],
    *,
    minimum_seconds: float = MIN_CLONE_SECONDS,
    maximum_seconds: float = MAX_CLONE_SECONDS,
) -> AudioInfo:
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise VoiceCloneError(f"音频文件不存在: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        allowed = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise VoiceCloneError(f"不支持的音频格式 {path.suffix!r}；仅支持 {allowed}。")

    size_bytes = path.stat().st_size
    if size_bytes > MAX_AUDIO_BYTES:
        raise VoiceCloneError(
            f"音频大小为 {size_bytes / 1024 / 1024:.2f} MB，超过 20 MB 限制；请先压缩。"
        )

    duration_seconds, format_name = _probe_audio(path)
    if duration_seconds < minimum_seconds:
        raise VoiceCloneError(
            f"音频时长为 {duration_seconds:.2f} 秒，少于 {minimum_seconds:g} 秒；"
            "请先用 ffmpeg 循环补足后再上传。"
        )
    if duration_seconds > maximum_seconds:
        raise VoiceCloneError(
            f"音频时长为 {duration_seconds:.2f} 秒，超过 {maximum_seconds:g} 秒；"
            "请先在静音处裁切或压缩到限制内。"
        )
    return AudioInfo(path, size_bytes, duration_seconds, format_name)


def _multipart_body(path: Path, *, purpose: str) -> tuple[bytes, str]:
    boundary = f"----lfo-voice-clone-{secrets.token_hex(16)}"
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded_name = parse.quote(path.name, safe="")
    safe_name = path.name.replace('"', "_")

    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="purpose"\r\n\r\n'
            f"{purpose}\r\n"
        ).encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{safe_name}"; '
            f"filename*=UTF-8''{encoded_name}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8"),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("ascii"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _upload_file(
    path: Path,
    *,
    purpose: str,
    api_key: str,
    base_url: str,
    timeout: float,
) -> Any:
    body, content_type = _multipart_body(path, purpose=purpose)
    response = _post(
        f"{base_url.rstrip('/')}/v1/files/upload",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        body=body,
        timeout=timeout,
    )
    file_data = response.get("file")
    if not isinstance(file_data, dict) or file_data.get("file_id") in (None, ""):
        raise VoiceCloneError(f"上传成功但响应中没有 file_id: {_error_detail(response)}")
    return file_data["file_id"]


def _validate_voice_id(voice_id: str) -> str:
    if not VOICE_ID_PATTERN.fullmatch(voice_id):
        raise VoiceCloneError(
            "voice_id 必须为 8-256 个字符，以英文字母开头和结尾，"
            "且只能包含字母、数字、-、_。"
        )
    return voice_id


def _generated_voice_id(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"lfo_{timestamp}_{digest}"


def _build_clone_payload(args: argparse.Namespace, *, file_id: Any, voice_id: str, prompt_file_id: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "file_id": file_id,
        "voice_id": voice_id,
        "need_noise_reduction": args.need_noise_reduction,
        "need_volume_normalization": args.need_volume_normalization,
        "aigc_watermark": args.aigc_watermark,
    }
    if args.text is not None:
        payload["text"] = args.text
        payload["model"] = args.model
    if args.language_boost:
        payload["language_boost"] = args.language_boost
    if args.text_validation is not None:
        payload["text_validation"] = args.text_validation
        payload["accuracy"] = args.accuracy
    if prompt_file_id is not None:
        payload["clone_prompt"] = {
            "prompt_audio": prompt_file_id,
            "prompt_text": args.prompt_text,
        }
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload an audio sample and call MiniMax /v1/voice_clone locally."
    )
    parser.add_argument("--audio", required=True, help="Primary clone audio path")
    parser.add_argument("--voice-id", help="Optional custom MiniMax voice_id")
    parser.add_argument("--text", help="Optional demo text; incurs TTS preview usage")
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="Skip demo synthesis; omit text and model from the clone request",
    )
    parser.add_argument("--model", default="speech-2.8-hd")
    parser.add_argument("--language-boost", help="MiniMax language_boost value, e.g. Chinese or auto")
    parser.add_argument("--text-validation", help="Expected transcript for ASR similarity validation")
    parser.add_argument("--accuracy", type=float, default=0.7)
    parser.add_argument("--prompt-audio", help="Optional <8 second prompt audio path")
    parser.add_argument("--prompt-text", help="Transcript for --prompt-audio")
    parser.add_argument("--need-noise-reduction", action="store_true")
    parser.add_argument("--need-volume-normalization", action="store_true")
    parser.add_argument("--aigc-watermark", action="store_true")
    parser.add_argument(
        "--base-url",
        default=os.getenv("MINIMAX_API_BASE_URL", "https://api.minimaxi.com"),
        help="MiniMax API base URL (or MINIMAX_API_BASE_URL)",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the audio and print the request plan without network calls",
    )
    parser.add_argument(
        "--legal-confirmed",
        action="store_true",
        help="Required after the user confirms lawful use and speaker authorization",
    )
    args = parser.parse_args()
    if not args.legal_confirmed:
        parser.error("请先取得用户的法律合规确认，再传入 --legal-confirmed。")
    if args.text and args.no_demo:
        parser.error("--text 与 --no-demo 不能同时使用。")
    if not args.text and not args.no_demo:
        parser.error("请提供已确认的 --text，或明确使用 --no-demo。")
    if len(args.text or "") > 1000:
        parser.error("--text 最多 1000 个字符。")
    if len(args.text_validation or "") > 200:
        parser.error("--text-validation 最多 200 个字符。")
    if not 0 <= args.accuracy <= 1:
        parser.error("--accuracy 必须在 0 到 1 之间。")
    if args.prompt_audio and not args.prompt_text:
        parser.error("使用 --prompt-audio 时必须同时提供 --prompt-text。")
    if args.prompt_text and not args.prompt_audio:
        parser.error("使用 --prompt-text 时必须同时提供 --prompt-audio。")
    return args


def main() -> int:
    args = _parse_args()
    try:
        audio = inspect_audio(args.audio)
        prompt_audio = None
        if args.prompt_audio:
            prompt_audio = inspect_audio(
                args.prompt_audio,
                minimum_seconds=0.01,
                maximum_seconds=MAX_PROMPT_SECONDS,
            )

        voice_id = _validate_voice_id(args.voice_id) if args.voice_id else _generated_voice_id(audio.path)
        plan = {
            "audio": {
                "path": str(audio.path),
                "size_bytes": audio.size_bytes,
                "duration_seconds": round(audio.duration_seconds, 3),
                "format": audio.format_name,
            },
            "voice_id": voice_id,
            "upload_purpose": "voice_clone",
            "clone_endpoint": f"{args.base_url.rstrip('/')}/v1/voice_clone",
            "model": None if args.no_demo else args.model,
            "has_demo_text": args.text is not None,
            "has_prompt_audio": prompt_audio is not None,
            "need_noise_reduction": args.need_noise_reduction,
            "need_volume_normalization": args.need_volume_normalization,
        }
        if args.dry_run:
            print(json.dumps({"dry_run": True, "plan": plan}, ensure_ascii=False, indent=2))
            return 0

        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            raise VoiceCloneError("未找到 MINIMAX_API_KEY；请通过环境变量提供，不要写入 skill 文件。")

        file_id = _upload_file(
            audio.path,
            purpose="voice_clone",
            api_key=api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        prompt_file_id = None
        if prompt_audio:
            prompt_file_id = _upload_file(
                prompt_audio.path,
                purpose="prompt_audio",
                api_key=api_key,
                base_url=args.base_url,
                timeout=args.timeout,
            )

        payload = _build_clone_payload(
            args,
            file_id=file_id,
            voice_id=voice_id,
            prompt_file_id=prompt_file_id,
        )
        response = _post(
            f"{args.base_url.rstrip('/')}/v1/voice_clone",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=args.timeout,
        )
        result = {
            "audio": plan["audio"],
            "file_id": file_id,
            "prompt_file_id": prompt_file_id,
            "voice_id": voice_id,
            "request": {
                "endpoint": plan["clone_endpoint"],
                "model": plan["model"],
                "has_demo_text": plan["has_demo_text"],
            },
            "response": response,
        }
        if response.get("input_sensitive_type") not in (None, 0, "0"):
            result["warning"] = "MiniMax 标记了输入音频风险；请在使用该音色前向用户展示并确认。"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except VoiceCloneError as exc:
        print(f"voice-clone error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
