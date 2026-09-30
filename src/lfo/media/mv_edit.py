"""Validate and deterministically render a cut-based MV against its adopted song."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe, probe_audio, run_command
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.music_timeline import validate_music_timeline
from lfo.media.mv_render import render_visual_segments
from lfo.media.mv_subtitles import render_ass

SCHEMA = "lfo.mv.edit.v1"


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} 必须是整数毫秒")
    return value


def _real(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} 必须是有效数值")
    return float(value)


def _media(path_value: Any, digest_value: Any, *, audio: bool) -> tuple[Path, dict[str, Any]]:
    if not isinstance(path_value, str) or not Path(path_value).is_absolute():
        raise ValueError("媒体路径必须是绝对路径")
    path = Path(path_value).resolve(strict=True)
    if not isinstance(digest_value, str) or len(digest_value) != 64:
        raise ValueError("媒体 SHA-256 无效")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != digest_value:
        raise ValueError(f"源媒体 SHA-256 不匹配：{path}")
    info = probe_audio(path) if audio else probe(path)
    return path, info


def _stream_info(path: Path, kind: str) -> dict[str, Any]:
    result = run_command(
        [
            os.environ.get("LFO_FFPROBE") or "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,duration,nb_read_frames,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    streams = json.loads(result.stdout).get("streams", [])
    stream = next((item for item in streams if item.get("codec_type") == kind), None)
    if stream is None:
        raise ValueError(f"媒体缺少{kind}流：{path}")
    count = stream.get("nb_read_frames")
    frame_count = int(count) if count not in (None, "N/A") else None
    duration = stream.get("duration")
    if duration not in (None, "N/A"):
        duration_ms = round(float(duration) * 1000)
    elif kind == "video" and frame_count is not None:
        numerator, denominator = str(stream.get("r_frame_rate", "0/1")).split("/", 1)
        rate = float(numerator) / float(denominator)
        duration_ms = round(frame_count * 1000 / rate) if rate > 0 else None
    else:
        duration_ms = None
    if duration_ms is None or duration_ms <= 0:
        raise ValueError(f"媒体{kind}流时长无法核实：{path}")
    return {"duration_ms": duration_ms, "frame_count": frame_count}


def _timeline(value: dict[str, Any]) -> dict[str, Any]:
    path_value = value.get("music_timeline")
    if not isinstance(path_value, str) or not Path(path_value).is_absolute():
        raise ValueError("music_timeline 必须是绝对路径")
    path = Path(path_value).resolve(strict=True)
    timeline = json.loads(path.read_text(encoding="utf-8"))
    return validate_music_timeline(timeline)


def validate_edit(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("不是受支持的 MV 编辑清单")
    timeline = _timeline(value)
    width, height = (
        _integer(value.get("width"), "画幅宽度"),
        _integer(value.get("height"), "画幅高度"),
    )
    fps = _real(value.get("fps"), "帧率")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("输出画幅或帧率无效")
    if value.get("native_audio_strategy") not in {"replace", "mix"}:
        raise ValueError("原生声音策略必须明确为 replace 或 mix")
    checked_media: dict[tuple[str, str, bool], tuple[Path, dict[str, Any]]] = {}

    def verified_media(
        path_value: Any, digest_value: Any, *, audio: bool
    ) -> tuple[Path, dict[str, Any]]:
        if (
            not isinstance(path_value, str)
            or not Path(path_value).is_absolute()
            or not isinstance(digest_value, str)
        ):
            return _media(path_value, digest_value, audio=audio)
        resolved = str(Path(path_value).resolve(strict=True))
        key = resolved, digest_value, audio
        if key not in checked_media:
            checked_media[key] = _media(path_value, digest_value, audio=audio)
        return checked_media[key]

    checked_video_streams: dict[Path, dict[str, Any]] = {}

    def video_stream(path: Path) -> dict[str, Any]:
        if path not in checked_video_streams:
            checked_video_streams[path] = _stream_info(path, "video")
        return checked_video_streams[path]

    duration = timeline["window"]["end_ms"] - timeline["window"]["start_ms"]
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("MV 至少需要一个源片镜头")
    expected = 0
    for index, segment in enumerate(segments, start=1):
        if (
            not isinstance(segment, dict)
            or not isinstance(segment.get("run_id"), str)
            or not segment["run_id"].strip()
        ):
            raise ValueError(f"镜头 {index} 缺少 run_id")
        if segment.get("transition", "cut") != "cut":
            raise ValueError("当前 MV 渲染仅支持硬切转场")
        path, info = verified_media(segment.get("path"), segment.get("sha256"), audio=False)
        if info.get("width") is None or info.get("height") is None:
            raise ValueError(f"源片不是视频：{path}")
        source_in = _integer(segment.get("source_in_ms"), "源片入点")
        source_out = _integer(segment.get("source_out_ms"), "源片出点")
        start = _integer(segment.get("timeline_start_ms"), "成片起点")
        video_duration = video_stream(path)["duration_ms"]
        if not 0 <= source_in < source_out <= video_duration:
            raise ValueError(f"镜头 {index} 源片范围越界")
        if start != expected:
            raise ValueError("成片镜头时间轴有空洞、重叠或不连续")
        end = start + source_out - source_in
        if round(end * fps / 1000) <= round(start * fps / 1000):
            raise ValueError("镜头短于一个可渲染视频帧")
        expected = end
    if expected != duration:
        raise ValueError("镜头总时长与采用歌曲窗口不一致")
    effects = value.get("sound_effects", [])
    if not isinstance(effects, list):
        raise ValueError("sound_effects 必须是数组")
    for effect in effects:
        if not isinstance(effect, dict):
            raise ValueError("音效必须是对象")
        _, info = verified_media(effect.get("path"), effect.get("sha256"), audio=True)
        begin = _integer(effect.get("source_in_ms"), "音效入点")
        end = _integer(effect.get("source_out_ms"), "音效出点")
        start = _integer(effect.get("timeline_start_ms"), "音效位置")
        _real(effect.get("gain_db"), "音效增益")
        if (
            not 0 <= begin < end <= info["duration_ms"]
            or not 0 <= start < duration
            or start + end - begin > duration
        ):
            raise ValueError("音效范围超出源文件或成片")
    events = value.get("text_events", [])
    if not isinstance(events, list):
        raise ValueError("text_events 必须是数组")
    start, end = timeline["window"]["start_ms"], timeline["window"]["end_ms"]
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("文字事件必须是对象")
        event_start = _integer(event.get("start_ms"), "文字起点")
        event_end = _integer(event.get("end_ms"), "文字终点")
        if event_end <= start or event_start >= end or event_end <= event_start:
            raise ValueError("文字事件不在采用歌曲窗口内")
        render_ass(
            [
                {
                    **event,
                    "start_ms": max(event_start, start) - start,
                    "end_ms": min(event_end, end) - start,
                }
            ],
            width=width,
            height=height,
        )
    return value


def _trim_audio(source: Path, output: Path, begin_ms: int, end_ms: int) -> None:
    run_command(
        [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-n",
            "-i",
            str(source),
            "-ss",
            f"{begin_ms / 1000:.3f}",
            "-t",
            f"{(end_ms - begin_ms) / 1000:.3f}",
            "-map",
            "0:a:0",
            "-c:a",
            "flac",
            str(output),
        ]
    )
    actual = probe_audio(output)["duration_ms"]
    if abs(actual - (end_ms - begin_ms)) > 25:
        raise ValueError("音轨裁切结果与已核对时间窗口不符")


def _publish_new_file(temp_path: Path, output_path: Path) -> None:
    """Atomically create a new directory entry without replacing an existing file."""
    if not temp_path.is_file() or temp_path.stat().st_size == 0:
        raise ValueError(f"候选成片不存在或为空：{temp_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(temp_path, output_path)
    except FileExistsError as exc:
        raise ValueError("输出路径会覆盖已有文件") from exc
    except OSError as exc:
        raise ValueError(f"无法以不覆盖方式原子发布成片：{exc}") from exc
    temp_path.unlink()


def render_edit(
    value: dict[str, Any],
    output_path: Path,
    *,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    validate_edit(value)
    output = Path(output_path).resolve()
    sources = [Path(item["path"]).resolve() for item in value["segments"]]
    sources.extend(Path(item["path"]).resolve() for item in value.get("sound_effects", []))
    sources.append(Path(value["music_timeline"]).resolve())
    timeline = _timeline(value)
    sources.append(Path(timeline["source"]["path"]).resolve())
    if output in sources or output.exists() or output.is_symlink():
        raise ValueError("输出路径会覆盖源素材或已有成片")
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = timeline["window"]["end_ms"] - timeline["window"]["start_ms"]
    fps = float(value["fps"])
    cache = (
        Path(cache_dir) if cache_dir is not None else output.with_name(f".{output.stem}-segments")
    )
    render_items = [
        {
            "kind": "video",
            "timeline_start_ms": item["timeline_start_ms"],
            "duration_ms": item["source_out_ms"] - item["source_in_ms"],
            "path": item["path"],
            "sha256": item["sha256"],
            "source_in_ms": item["source_in_ms"],
            "source_out_ms": item["source_out_ms"],
        }
        for item in value["segments"]
    ]
    with tempfile.TemporaryDirectory(prefix=".mv-render-", dir=output.parent) as folder:
        temp = Path(folder)
        rendered = render_visual_segments(
            render_items,
            width=value["width"],
            height=value["height"],
            fps=fps,
            cache_dir=cache,
            work_dir=temp,
            include_native_audio=value["native_audio_strategy"] == "mix",
        )
        base = Path(rendered["picture_path"])
        expected_frames = rendered["video_frame_count"]
        master = temp / "master.flac"
        _trim_audio(
            Path(timeline["source"]["path"]),
            master,
            timeline["window"]["start_ms"],
            timeline["window"]["end_ms"],
        )
        tracks = [AudioTrack(asset_key=str(master), role="music")]
        for index, item in enumerate(value.get("sound_effects", []), start=1):
            selected = temp / f"effect-{index}.flac"
            _trim_audio(Path(item["path"]), selected, item["source_in_ms"], item["source_out_ms"])
            tracks.append(
                AudioTrack(
                    asset_key=str(selected),
                    role="effect",
                    offset_ms=item["timeline_start_ms"],
                    gain_db=item["gain_db"],
                )
            )
        if rendered["native_audio_path"] is not None:
            tracks.insert(
                0, AudioTrack(asset_key=str(rendered["native_audio_path"]), role="native")
            )
        mixed = temp / "mixed.mp4"
        mix_result = AudioMixer().mix(
            AudioMixRequest(
                # The visual intermediate has no embedded audio. Accepted source
                # audio is already represented as an explicit, synchronized track.
                native_audio_present=False,
                native_audio_strategy=value["native_audio_strategy"],
                tracks=tracks,
                clip_duration_ms=duration,
                source_video_path=str(base),
                output_path=str(mixed),
                normalize_inputs=False,
            )
        )
        if not mix_result.success:
            raise ValueError(f"主音轨合成失败：{mix_result.error}")
        events = []
        window_start, window_end = timeline["window"]["start_ms"], timeline["window"]["end_ms"]
        for event in value.get("text_events", []):
            events.append(
                {
                    **event,
                    "start_ms": max(window_start, event["start_ms"]) - window_start,
                    "end_ms": min(window_end, event["end_ms"]) - window_start,
                }
            )
        final_candidate = mixed
        if events:
            ass_path = temp / "lyrics.ass"
            ass_path.write_text(
                render_ass(events, width=value["width"], height=value["height"]), encoding="utf-8"
            )
            final_candidate = temp / "subtitled.mp4"
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
                    str(final_candidate),
                ],
                cwd=temp,
            )
        final_info = probe(final_candidate)
        final_video = _stream_info(final_candidate, "video")
        final_audio = _stream_info(final_candidate, "audio")
        if (
            not final_info["has_audio"]
            or final_video["frame_count"] != expected_frames
            or abs(final_audio["duration_ms"] - duration) > max(80, 2000 / fps)
        ):
            raise ValueError("成片音轨或时长核验失败")
        _publish_new_file(final_candidate, output)
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "schema": "lfo.mv.render-receipt.v1",
        "purpose": "final-render",
        "path": str(output),
        "sha256": digest,
        "duration_ms": probe(output)["duration_ms"],
        "video_frame_count": final_video["frame_count"],
        "video_duration_ms": final_video["duration_ms"],
        "audio_duration_ms": final_audio["duration_ms"],
        "source_music_sha256": timeline["source"]["sha256"],
        "native_audio_strategy": value["native_audio_strategy"],
        "output_width": value["width"],
        "output_height": value["height"],
        "output_fps": fps,
        "render_method": "verified-segment-cache-and-concat",
        "cache_dir": rendered["cache_dir"],
        "cache_hits": rendered["cache_hits"],
        "cache_misses": rendered["cache_misses"],
        "cache_rebuilt": rendered["cache_rebuilt"],
        "native_audio_segment_count": rendered["native_audio_segment_count"],
        "segments": [
            {
                "run_id": item["run_id"],
                "sha256": item["sha256"],
                "source_in_ms": item["source_in_ms"],
                "source_out_ms": item["source_out_ms"],
                "source_trim_in_ms": rendered_segment["source_trim_in_ms"],
                "source_trim_out_ms": item["source_out_ms"],
                "source_fps": rendered_segment["source_fps"],
                "source_frame_start": rendered_segment["source_frame_start"],
                "source_frame_end": rendered_segment["source_frame_end"],
                "output_start_frame": rendered_segment["output_start_frame"],
                "output_end_frame": rendered_segment["output_end_frame"],
                "output_frame_count": rendered_segment["output_frame_count"],
                "output_start_ms": rendered_segment["output_start_ms"],
                "output_end_ms": rendered_segment["output_end_ms"],
                "cache_key": rendered_segment["cache_key"],
                "cache_hit": rendered_segment["cache_hit"],
            }
            for item, rendered_segment in zip(value["segments"], rendered["segments"], strict=True)
        ],
        "lyric_count": sum(item.get("kind", "lyric") == "lyric" for item in events),
        "listening_status": "INCONCLUSIVE",
    }


def render_preview(
    value: dict[str, Any],
    output_path: Path,
    *,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Render an MV rough cut. Preview-only stills and placeholders cannot enter edit.v1."""
    from lfo.media.mv_preview import render_preview as render_mv_preview

    return render_mv_preview(value, output_path, cache_dir=cache_dir)
