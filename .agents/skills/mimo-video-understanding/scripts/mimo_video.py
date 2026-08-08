#!/usr/bin/env python3
"""MiMo V2.5 video understanding helper.

Uses the current public MiMo API endpoint by default:
https://api.xiaomimimo.com/v1/chat/completions

Credentials are read from MIMO_API_KEY. Do not hard-code API keys in this file.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5"
BASE64_LIMIT_CHARS = 50 * 1024 * 1024


def is_url(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def get_mime_type(file_path: str) -> str:
    mime, _ = mimetypes.guess_type(file_path)
    if mime and mime.startswith("video/"):
        return mime
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".wmv": "video/x-ms-wmv",
    }
    return mime_map.get(ext, "video/mp4")


def encode_video_base64(file_path: str) -> tuple[str, str, int]:
    mime_type = get_mime_type(file_path)
    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    if len(b64_data) > BASE64_LIMIT_CHARS:
        raise ValueError(
            "Local video exceeds MiMo Base64 limit: "
            f"{len(b64_data)} chars > {BASE64_LIMIT_CHARS}. "
            "Use a public URL, compress the video, speed up/cut a review clip, or lower resolution first."
        )
    return f"data:{mime_type};base64,{b64_data}", mime_type, len(b64_data)


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
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str):
        return reasoning
    return ""


def analyze_video(
    video: str,
    prompt: str,
    fps: float = 2.0,
    media_resolution: str = "default",
    max_tokens: int = 1024,
    output: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
) -> str:
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise RuntimeError("MIMO_API_KEY is not set")

    if is_url(video):
        video_url = video
        encoded_chars = None
    else:
        if not os.path.exists(video):
            raise FileNotFoundError(f"视频文件不存在: {video}")
        video_url, _, encoded_chars = encode_video_base64(video)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": video_url},
                        "fps": fps,
                        "media_resolution": media_resolution,
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_completion_tokens": max_tokens,
    }

    endpoint = chat_completions_url(base_url or os.environ.get("MIMO_VIDEO_BASE_URL", DEFAULT_BASE_URL))
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
        raise RuntimeError(f"MiMo video API HTTP {exc.code}: {error_body}") from exc

    parsed = json.loads(body)
    result = extract_message_text(parsed)
    if not result:
        finish_reason = (parsed.get("choices") or [{}])[0].get("finish_reason")
        print(
            "Warning: MiMo video API returned empty message content"
            + (f"; finish_reason={finish_reason}" if finish_reason else ""),
            file=sys.stderr,
        )
    if encoded_chars is not None:
        print(f"Encoded local video as Base64 chars: {encoded_chars}", file=sys.stderr)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(result)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MiMo V2.5 视频理解")
    parser.add_argument("--video", required=True, help="视频文件路径或 URL")
    parser.add_argument("--prompt", required=True, help="分析提示词")
    parser.add_argument("--fps", type=float, default=2.0, help="每秒抽帧数 [0.1, 10]")
    parser.add_argument("--media-resolution", default="default", choices=["default", "max"], help="分辨率档次")
    parser.add_argument("--max-tokens", type=int, default=1024, help="最大输出 token 数")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=["mimo-v2.5", "mimo-v2-omni"], help="模型名称")
    parser.add_argument("--base-url", default=None, help="API base URL 或完整 /chat/completions URL")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    result = analyze_video(
        video=args.video,
        prompt=args.prompt,
        fps=args.fps,
        media_resolution=args.media_resolution,
        max_tokens=args.max_tokens,
        output=args.output,
        model=args.model,
        base_url=args.base_url,
    )

    print(result)


if __name__ == "__main__":
    main()
