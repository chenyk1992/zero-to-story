"""Song-timed rough-cut previews with explicit stills and ungenerated slots."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe, run_command
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.mv_render import render_visual_segments
from lfo.media.mv_subtitles import render_ass

PREVIEW_SCHEMA = "lfo.mv.preview.v1"


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _timeline(value: dict[str, Any]) -> dict[str, Any]:
    from lfo.media.mv_edit import _timeline as read_edit_timeline

    return read_edit_timeline(value)


def _stream_info(path: Path, kind: str) -> dict[str, Any]:
    from lfo.media.mv_edit import _stream_info as read_stream_info

    return read_stream_info(path, kind)


def _trim_audio(source: Path, output: Path, begin_ms: int, end_ms: int) -> None:
    from lfo.media.mv_edit import _trim_audio as trim_audio

    trim_audio(source, output, begin_ms, end_ms)


def _publish_new_file(temp_path: Path, output_path: Path) -> None:
    from lfo.media.mv_edit import _publish_new_file as publish_new_file

    publish_new_file(temp_path, output_path)


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} 必须是整数毫秒")
    return value


def _verify_ass_support() -> None:
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    font_paths = [
        windows_dir / "Fonts" / "msyh.ttc",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ]
    if not any(path.is_file() for path in font_paths):
        raise ValueError("MV 预览占位需要系统中可用的中文字体（微软雅黑或 Noto Sans CJK）")
    result = run_command(
        [os.environ.get("LFO_FFMPEG") or "ffmpeg", "-hide_banner", "-filters"],
        timeout_s=30,
    )
    if not any("ass" in line.split()[:3] for line in result.stdout.splitlines() if line.strip()):
        raise ValueError("当前 FFmpeg 未启用 ASS 字幕滤镜，无法给预览占位烧录提示标签")


def validate_preview(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a preview-only manifest. It is intentionally not an edit.v1."""
    if not isinstance(value, dict) or value.get("schema") != PREVIEW_SCHEMA:
        raise ValueError("不是受支持的 MV 预览清单")
    from lfo.media.mv_edit import _media, _real

    timeline = _timeline(value)
    width = _integer(value.get("width"), "画幅宽度")
    height = _integer(value.get("height"), "画幅高度")
    fps = _real(value.get("fps"), "帧率")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("输出画幅或帧率无效")
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("MV 预览至少需要一个时间段")
    duration = timeline["window"]["end_ms"] - timeline["window"]["start_ms"]
    expected_start = 0
    normalized: list[dict[str, Any]] = []
    checked_media: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    checked_streams: dict[tuple[Path, str], dict[str, Any]] = {}

    def verified_media(media: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        path_value, digest_value = media.get("path"), media.get("sha256")
        if isinstance(path_value, str) and isinstance(digest_value, str):
            key = path_value, digest_value
            if key not in checked_media:
                checked_media[key] = _media(path_value, digest_value, audio=False)
            return checked_media[key]
        return _media(path_value, digest_value, audio=False)

    def video_stream(path: Path) -> dict[str, Any]:
        key = path, "video"
        if key not in checked_streams:
            checked_streams[key] = _stream_info(path, "video")
        return checked_streams[key]

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise ValueError(f"预览镜头 {index} 必须是对象")
        start = _integer(segment.get("timeline_start_ms"), "预览镜头起点")
        clip_duration = _integer(segment.get("duration_ms"), "预览镜头时长")
        if start != expected_start or clip_duration <= 0:
            raise ValueError("预览镜头时间轴有空洞、重叠或无效时长")
        media = segment.get("media")
        if not isinstance(media, dict):
            raise ValueError(f"预览镜头 {index} 缺少 media 描述")
        media_type = media.get("type")
        item: dict[str, Any] = {
            "timeline_start_ms": start,
            "duration_ms": clip_duration,
            "shot_id": segment.get("shot_id"),
        }
        if media_type == "video":
            path, info = verified_media(media)
            if not info.get("width") or not info.get("height") or not info.get("fps"):
                raise ValueError(f"预览镜头 {index} 声明为视频，但源片帧率无效")
            source_in = _integer(media.get("source_in_ms"), "预览视频入点")
            source_out = _integer(media.get("source_out_ms"), "预览视频出点")
            stream_duration = video_stream(path)["duration_ms"]
            if (
                not 0 <= source_in < source_out <= stream_duration
                or source_out - source_in != clip_duration
            ):
                raise ValueError(f"预览镜头 {index} 视频区间须完整对应时间段且不超出源片")
            item.update(
                {
                    "kind": "video",
                    "path": str(path),
                    "sha256": media["sha256"],
                    "source_in_ms": source_in,
                    "source_out_ms": source_out,
                }
            )
        elif media_type == "image":
            path, info = verified_media(media)
            still_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
            frame_count = video_stream(path)["frame_count"]
            if (
                not info.get("width")
                or not info.get("height")
                or path.suffix.lower() not in still_extensions
                or frame_count != 1
            ):
                raise ValueError(f"预览镜头 {index} 声明为静帧，但素材不是静态图像")
            item.update({"kind": "image", "path": str(path), "sha256": media["sha256"]})
        elif media_type == "placeholder":
            label = media.get("label")
            if not isinstance(label, str) or not label.strip() or len(label) > 240:
                raise ValueError(f"预览镜头 {index} 占位说明必须为 1～240 个字符")
            item.update({"kind": "placeholder", "label": label.strip()})
        else:
            raise ValueError(f"预览镜头 {index} 的 media.type 只能是 video、image 或 placeholder")
        normalized.append(item)
        expected_start += clip_duration
    if expected_start != duration:
        raise ValueError("预览时间段总时长必须覆盖采用歌曲窗口")

    events = value.get("text_events", [])
    if not isinstance(events, list):
        raise ValueError("text_events 必须是数组")
    window_start, window_end = timeline["window"]["start_ms"], timeline["window"]["end_ms"]
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("预览文字事件必须是对象")
        event_start = _integer(event.get("start_ms"), "文字起点")
        event_end = _integer(event.get("end_ms"), "文字终点")
        if event_end <= window_start or event_start >= window_end or event_end <= event_start:
            raise ValueError("预览文字事件不在采用歌曲窗口内")
        render_ass(
            [
                {
                    **event,
                    "start_ms": max(event_start, window_start) - window_start,
                    "end_ms": min(event_end, window_end) - window_start,
                }
            ],
            width=width,
            height=height,
        )
    source = timeline["source"]
    if _digest(Path(source["path"])) != source["sha256"]:
        raise ValueError("采用歌曲 SHA-256 已变化")
    return {
        "timeline": timeline,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_ms": duration,
        "segments": normalized,
        "text_events": events,
    }


def render_preview(
    value: dict[str, Any],
    output_path: Path,
    *,
    cache_dir: Path | None = None,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """Render an explicitly labelled rough cut with video, still, or placeholder slots."""
    validated = validate_preview(value)
    output = Path(output_path).resolve()
    source_paths = [
        Path(item["path"]).resolve() for item in validated["segments"] if item.get("path")
    ]
    timeline_path = Path(value["music_timeline"]).resolve()
    song_path = Path(validated["timeline"]["source"]["path"]).resolve()
    source_paths.extend([timeline_path, song_path])
    if output in source_paths or output.exists() or output.is_symlink():
        raise ValueError("预览输出路径会覆盖源素材或已有文件")
    output.parent.mkdir(parents=True, exist_ok=True)
    if any(item["kind"] == "placeholder" for item in validated["segments"]):
        _verify_ass_support()
    duration = validated["duration_ms"]
    cache = (
        Path(cache_dir) if cache_dir is not None else output.with_name(f".{output.stem}-segments")
    )
    with tempfile.TemporaryDirectory(prefix=".mv-preview-", dir=output.parent) as folder:
        work = Path(folder)
        rendered = render_visual_segments(
            validated["segments"],
            width=validated["width"],
            height=validated["height"],
            fps=validated["fps"],
            cache_dir=cache,
            work_dir=work,
            include_native_audio=False,
            timeout_s=timeout_s,
        )
        master = work / "master.flac"
        window = validated["timeline"]["window"]
        _trim_audio(song_path, master, window["start_ms"], window["end_ms"])
        mixed = work / "music-preview.mp4"
        mix = AudioMixer().mix(
            AudioMixRequest(
                native_audio_present=False,
                native_audio_strategy="replace",
                tracks=[AudioTrack(asset_key=str(master), role="music")],
                clip_duration_ms=duration,
                source_video_path=str(rendered["picture_path"]),
                output_path=str(mixed),
                normalize_inputs=False,
            ),
            timeout_s=timeout_s,
        )
        if not mix.success:
            raise ValueError(f"预览主音轨合成失败：{mix.error}")
        cues = []
        for event in validated["text_events"]:
            cues.append(
                {
                    **event,
                    "start_ms": max(window["start_ms"], event["start_ms"]) - window["start_ms"],
                    "end_ms": min(window["end_ms"], event["end_ms"]) - window["start_ms"],
                }
            )
        placeholder_count = 0
        for segment in validated["segments"]:
            if segment["kind"] != "placeholder":
                continue
            placeholder_count += 1
            absolute_start = window["start_ms"] + segment["timeline_start_ms"]
            absolute_end = absolute_start + segment["duration_ms"]
            cues.append(
                {
                    "start_ms": max(window["start_ms"], absolute_start) - window["start_ms"],
                    "end_ms": min(window["end_ms"], absolute_end) - window["start_ms"],
                    "text": f"MV 预览 · 待生成\n{segment['label']}",
                    "kind": "visual",
                }
            )
        candidate = mixed
        if cues:
            ass_path = work / "preview.ass"
            ass_path.write_text(
                render_ass(cues, width=validated["width"], height=validated["height"]),
                encoding="utf-8",
            )
            candidate = work / "labelled-preview.mp4"
            run_command(
                [
                    os.environ.get("LFO_FFMPEG") or "ffmpeg",
                    "-v",
                    "error",
                    "-xerror",
                    "-n",
                    "-i",
                    str(mixed),
                    "-vf",
                    f"ass={ass_path.name}",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    str(candidate),
                ],
                timeout_s=timeout_s,
                cwd=work,
            )
        video_info = _stream_info(candidate, "video")
        audio_info = _stream_info(candidate, "audio")
        if video_info["frame_count"] != rendered["video_frame_count"]:
            raise ValueError("MV 预览标签处理改变了画面帧数")
        if not probe(candidate)["has_audio"] or abs(audio_info["duration_ms"] - duration) > max(
            80, round(2000 / validated["fps"])
        ):
            raise ValueError("MV 预览主音轨核验失败")
        _publish_new_file(candidate, output)
    result = {
        "schema": PREVIEW_SCHEMA,
        "purpose": "rough-cut-preview",
        "path": str(output),
        "sha256": _digest(output),
        "duration_ms": probe(output)["duration_ms"],
        "video_frame_count": rendered["video_frame_count"],
        "audio_duration_ms": audio_info["duration_ms"],
        "source_music_sha256": validated["timeline"]["source"]["sha256"],
        "segment_count": len(validated["segments"]),
        "placeholder_count": placeholder_count,
        "cache_hits": rendered["cache_hits"],
        "cache_misses": rendered["cache_misses"],
        "cache_rebuilt": rendered["cache_rebuilt"],
        "cache_dir": rendered["cache_dir"],
        "segments": rendered["segments"],
    }
    return result
