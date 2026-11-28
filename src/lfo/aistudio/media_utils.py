"""Decoded media inspection and atomic materialization for AIStudio2API outputs."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe as probe_video

CODEC_TO_MIME = {
    "png": "image/png",
    "mjpeg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
}
MIME_TO_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


def inspect_static_image(path: Path) -> tuple[dict[str, Any], str]:
    """Decode image metadata with ffprobe; reject non-static or corrupt files."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"图片素材不存在或为空：{path.name}")
    ffprobe_bin = os.environ.get("LFO_FFPROBE") or "ffprobe"
    completed = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"图片无法读取：{path.name}")
    try:
        streams = json.loads(completed.stdout).get("streams", [])
    except ValueError as exc:
        raise ValueError(f"图片探测输出无效：{path.name}") from exc
    if len(streams) != 1 or streams[0].get("codec_name") not in CODEC_TO_MIME:
        raise ValueError("参考素材须为静态 PNG、JPEG、WebP 或 BMP 图片")
    stream = streams[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError(f"图片尺寸无效：{path.name}")
    codec = str(stream["codec_name"])
    return (
        {
            "codec": codec,
            "width": width,
            "height": height,
            "pix_fmt": stream.get("pix_fmt"),
        },
        CODEC_TO_MIME[codec],
    )


def materialize_png(
    image_bytes: bytes,
    mime_type: str,
    output_dir: Path,
    *,
    extra_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify generated image bytes and write a canonical lossless PNG output."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "image.png"
    suffix = MIME_TO_SUFFIX.get(mime_type.lower().strip(), ".img")

    with tempfile.TemporaryDirectory(prefix=".aistudio-img-", dir=output_dir) as tmp:
        tmp_dir = Path(tmp)
        raw_path = tmp_dir / f"raw{suffix}"
        raw_path.write_bytes(image_bytes)
        metadata, _ = inspect_static_image(raw_path)

        candidate = tmp_dir / "candidate.png"
        if metadata["codec"] == "png":
            shutil.copyfile(raw_path, candidate)
        else:
            ffmpeg_bin = os.environ.get("LFO_FFMPEG") or "ffmpeg"
            converted = subprocess.run(
                [
                    ffmpeg_bin,
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(raw_path),
                    "-frames:v",
                    "1",
                    str(candidate),
                ],
                capture_output=True,
                timeout=60,
                check=False,
            )
            if converted.returncode != 0 or not candidate.is_file():
                raise ValueError("无法将生成的图片转换为标准 PNG 格式")
            metadata, _ = inspect_static_image(candidate)
            if metadata["codec"] != "png":
                raise ValueError("转换后的图片不是有效的 PNG 格式")

        candidate.replace(target)

    merged_meta = dict(metadata)
    if extra_metadata:
        merged_meta.update(extra_metadata)
    return {
        "path": str(target.resolve()),
        "kind": "image",
        "name": target.name,
        "metadata": merged_meta,
    }


def materialize_mp4(
    source_video: Path,
    output_dir: Path,
    *,
    extra_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe a downloaded video clip and atomically move it into output_dir."""
    if not source_video.is_file() or source_video.stat().st_size == 0:
        raise ValueError("下载的视频文件不存在或内容为空")
    try:
        metadata = probe_video(source_video.resolve())
    except Exception as exc:
        raise ValueError(f"视频输出无法读取：{exc}") from exc
    if not isinstance(metadata, Mapping):
        raise ValueError("视频探测结果无效")
    duration = metadata.get("duration_ms")
    width = metadata.get("width")
    height = metadata.get("height")
    codec = metadata.get("codec")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
        or isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or not isinstance(codec, str)
        or not codec.strip()
    ):
        raise ValueError("视频输出缺少有效的时长、尺寸或编码信息")

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "video.mp4"
    source_video.replace(target)
    merged_meta = dict(metadata)
    if extra_metadata:
        merged_meta.update(extra_metadata)
    return {
        "path": str(target.resolve()),
        "kind": "video",
        "name": target.name,
        "metadata": merged_meta,
    }
