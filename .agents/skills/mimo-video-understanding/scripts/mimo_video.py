#!/usr/bin/env python3
"""MiMo audio/video understanding helper (legacy video entrypoint retained).

Uses the current public MiMo API endpoint by default:
https://api.xiaomimimo.com/v1/chat/completions

Credentials are read from MIMO_API_KEY. Do not hard-code API keys in this file.
"""

# Chinese CLI help uses natural punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.6-pro"
CURRENT_MODELS = ("mimo-v2.6-pro", "mimo-v2.6-flash")
VIDEO_MODELS = (*CURRENT_MODELS, "mimo-v2-omni")
BASE64_LIMIT_CHARS = 50 * 1024 * 1024
MEDIA_MIME_TYPES = {
    "video": {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".wmv": "video/x-ms-wmv",
    },
    "audio": {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    },
}


def is_url(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def get_mime_type(file_path: str, media_type: str = "video") -> str:
    ext = Path(file_path).suffix.lower()
    mime_map = MEDIA_MIME_TYPES[media_type]
    if ext not in mime_map:
        raise ValueError(f"Unsupported local {media_type} format: {ext or '(no extension)'}")
    return mime_map[ext]


def encode_media_base64(file_path: str, media_type: str) -> tuple[str, str, int]:
    mime_type = get_mime_type(file_path, media_type)
    path = Path(file_path)
    encoded_size = 4 * ((path.stat().st_size + 2) // 3)
    if encoded_size > BASE64_LIMIT_CHARS:
        raise ValueError(
            f"Local {media_type} exceeds MiMo Base64 limit: "
            f"{encoded_size} chars > {BASE64_LIMIT_CHARS}. "
            "Use an existing accessible URL or an authorized smaller review copy."
        )
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"Local {media_type} is empty")
    b64_data = base64.b64encode(raw).decode("ascii")
    if len(b64_data) > BASE64_LIMIT_CHARS:
        raise ValueError(f"Local {media_type} exceeds MiMo Base64 limit after reading")
    return f"data:{mime_type};base64,{b64_data}", mime_type, len(b64_data)


def encode_video_base64(file_path: str) -> tuple[str, str, int]:
    return encode_media_base64(file_path, "video")


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return normalized + "/chat/completions"


def extract_message_text(response: dict) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") not in {None, "text", "output_text"}:
                    continue
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        text = "\n".join(parts)
    else:
        return ""
    # Some responses include tagged reasoning in content despite thinking=disabled.
    # Never use that prefix (or an unfinished reasoning block) as the final answer.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text.strip()


def analyze_video(
    video: str,
    prompt: str,
    fps: float = 2.0,
    media_resolution: str = "default",
    max_tokens: int = 1024,
    output: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
    thinking: str = "disabled",
) -> str:
    return _analyze_media(
        video,
        "video",
        prompt,
        max_tokens,
        output,
        model,
        base_url,
        thinking,
        fps=fps,
        media_resolution=media_resolution,
    )


def analyze_audio(
    audio: str,
    prompt: str,
    max_tokens: int = 1024,
    output: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
    thinking: str = "disabled",
) -> str:
    return _analyze_media(audio, "audio", prompt, max_tokens, output, model, base_url, thinking)


def _analyze_media(
    media: str,
    media_type: str,
    prompt: str,
    max_tokens: int,
    output: str | None,
    model: str,
    base_url: str | None,
    thinking: str,
    *,
    fps: float = 2.0,
    media_resolution: str = "default",
) -> str:
    allowed_models = VIDEO_MODELS if media_type == "video" else CURRENT_MODELS
    if model not in allowed_models:
        raise ValueError(f"Unsupported {media_type} model: {model}")
    if thinking not in {"enabled", "disabled"}:
        raise ValueError("thinking must be 'enabled' or 'disabled'")
    if model not in CURRENT_MODELS and thinking == "enabled":
        raise ValueError("Explicit thinking control is supported only for mimo-v2.6-pro/flash")
    if not prompt.strip() or max_tokens <= 0:
        raise ValueError("A nonempty prompt and positive max_tokens are required")
    if media_type == "video" and (
        not 0.1 <= fps <= 10 or media_resolution not in {"default", "max"}
    ):
        raise ValueError("Video requires fps in [0.1, 10] and media_resolution default/max")
    if output and not is_url(media) and Path(output).resolve() == Path(media).resolve():
        raise ValueError("Output must not overwrite the source media")
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise RuntimeError("MIMO_API_KEY is not set")

    if is_url(media):
        media_url = media
        encoded_chars = None
    else:
        media_url, _, encoded_chars = encode_media_base64(media, media_type)

    media_part = (
        {
            "type": "video_url",
            "video_url": {"url": media_url},
            "fps": fps,
            "media_resolution": media_resolution,
        }
        if media_type == "video"
        else {"type": "input_audio", "input_audio": {"data": media_url}}
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    media_part,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_completion_tokens": max_tokens,
    }
    if model in CURRENT_MODELS:
        payload["thinking"] = {"type": thinking}

    endpoint = chat_completions_url(
        base_url or os.environ.get(f"MIMO_{media_type.upper()}_BASE_URL", DEFAULT_BASE_URL)
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiMo {media_type} API HTTP {exc.code}: {error_body}") from exc

    parsed = json.loads(body)
    result = extract_message_text(parsed)
    finish_reason = (parsed.get("choices") or [{}])[0].get("finish_reason")
    if finish_reason == "length":
        raise RuntimeError(
            f"MiMo {media_type} API response was truncated; finish_reason=length. "
            "Disable thinking, shorten the prompt/media, or increase --max-tokens "
            "before explicitly running again. No output file was written."
        )
    if finish_reason != "stop":
        raise RuntimeError(
            f"MiMo {media_type} API response did not finish normally; "
            f"finish_reason={finish_reason}. No output file was written."
        )
    if not result.strip():
        raise RuntimeError(
            f"MiMo {media_type} API returned no final answer"
            + (f"; finish_reason={finish_reason}" if finish_reason else "")
            + ". No output file was written."
        )
    if encoded_chars is not None:
        print(f"Encoded local {media_type} as Base64 chars: {encoded_chars}", file=sys.stderr)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(result)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MiMo 音频/视频理解")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", help="视频文件路径或 URL")
    source.add_argument("--audio", help="音频文件路径或 URL")
    parser.add_argument("--prompt", required=True, help="分析提示词")
    parser.add_argument(
        "--fps", type=float, default=None, help="仅视频：每秒抽帧数 [0.1, 10]，默认 2"
    )
    parser.add_argument(
        "--media-resolution",
        default=None,
        choices=["default", "max"],
        help="仅视频：分辨率档次，默认 default",
    )
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大输出 token 数")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=VIDEO_MODELS,
        help="模型名称；旧 Omni 仅保留视频入口",
    )
    parser.add_argument(
        "--base-url", default=None, help="API base URL 或完整 /chat/completions URL"
    )
    parser.add_argument(
        "--thinking",
        default="disabled",
        choices=["enabled", "disabled"],
        help="深度思考开关；描述任务默认关闭，避免思考耗尽正文输出额度",
    )
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    if args.audio and (args.fps is not None or args.media_resolution is not None):
        parser.error("--fps and --media-resolution are video-only options")
    if args.audio and args.model not in CURRENT_MODELS:
        parser.error(f"--audio requires one of: {', '.join(CURRENT_MODELS)}")
    options = dict(
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        output=args.output,
        model=args.model,
        base_url=args.base_url,
        thinking=args.thinking,
    )
    result = (
        analyze_audio(args.audio, **options)
        if args.audio
        else analyze_video(
            args.video,
            fps=args.fps if args.fps is not None else 2.0,
            media_resolution=args.media_resolution or "default",
            **options,
        )
    )

    print(result)


if __name__ == "__main__":
    main()
