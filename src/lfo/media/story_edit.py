"""Deterministic narrative/short-drama/ad editing, animatic preview, and rendering."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe, run_command
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack, parse_ducking_windows
from lfo.media.mv_edit import (
    _check_still,
    _integer,
    _media,
    _media_provenance,
    _publish_new_file,
    _real,
    _render_image_overlays,
    _stream_info,
    _trim_audio,
)
from lfo.media.mv_preview import _verify_ass_support
from lfo.media.mv_render import render_visual_segments, validate_cache_directory
from lfo.media.mv_subtitles import _text as _ass_text
from lfo.media.mv_subtitles import _time as _ass_time
from lfo.media.subtitles import SubtitleCue, _validate_cues, cues_to_srt

EDIT_SCHEMA = "lfo.story.edit.v1"
PREVIEW_SCHEMA = "lfo.story.preview.v1"
RECEIPT_SCHEMA = "lfo.story.render-receipt.v1"
NATIVE_AUDIO_STRATEGIES = frozenset({"keep", "mix", "replace", "mute"})
AUDIO_ROLES = frozenset({"bgm", "music", "voiceover", "dialogue", "sfx", "ambience"})
DUCKABLE_ROLES = frozenset({"bgm", "music", "ambience"})
_DEFAULT_SEAM_FADE_MS = 40
_MAX_SEAM_FADE_MS = 250


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _nonneg_int(value: Any, label: str, *, default: int = 0) -> int:
    if value is None:
        return default
    parsed = _integer(value, label)
    if parsed < 0:
        raise ValueError(f"{label} 不能为负数")
    return parsed


def _optional_real(value: Any, label: str, *, default: float, minimum: float, maximum: float) -> float:
    if value is None:
        return default
    parsed = _real(value, label)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label} 必须在 {minimum} 到 {maximum} 之间")
    return parsed


def _validate_loudness(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("loudness 必须是对象")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("loudness.enabled 必须是布尔值")
    target_i = _optional_real(
        raw.get("target_i"), "响度目标 (LUFS)", default=-16.0, minimum=-36.0, maximum=-8.0
    )
    return {"enabled": enabled, "target_i": target_i}


def _validate_subtitles(raw: Any, duration_ms: int) -> list[SubtitleCue]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("subtitles 必须是数组")
    cues: list[SubtitleCue] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"字幕 {index} 必须是对象")
        start = _integer(item.get("start_ms"), f"字幕 {index} 起点")
        end = _integer(item.get("end_ms"), f"字幕 {index} 终点")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"字幕 {index} 缺少文本")
        cues.append(SubtitleCue(start, end, text))
    errors = _validate_cues(cues, duration_ms)
    if errors:
        raise ValueError("; ".join(errors))
    return cues


def _validate_text_events(raw: Any, duration_ms: int) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("text_events 必须是数组")
    events: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"文字事件 {index} 必须是对象")
        start = _integer(item.get("start_ms"), f"文字事件 {index} 起点")
        end = _integer(item.get("end_ms"), f"文字事件 {index} 终点")
        if not 0 <= start < end <= duration_ms:
            raise ValueError(f"文字事件 {index} 超出成片时长范围")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"文字事件 {index} 缺少原文")
        effect = item.get("effect", "none")
        if effect not in {"none", "fade", "scale"}:
            raise ValueError(f"文字事件 {index} 动效不受支持")
        events.append({"start_ms": start, "end_ms": end, "text": text, "effect": effect})
    return events


def _validate_audio_tracks(
    raw: Any,
    duration_ms: int,
    verified_media: Any,
    *,
    require_provenance: bool = True,
) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("audio_tracks 必须是数组")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"音频轨 {index} 必须是对象")
        role = item.get("role")
        if not isinstance(role, str) or role not in AUDIO_ROLES:
            raise ValueError(f"音频轨 {index} 的 role 不受支持")
        if require_provenance:
            _media_provenance(item)
        path, info = verified_media(item.get("path"), item.get("sha256"), audio=True)
        source_in = _integer(item.get("source_in_ms", 0), f"音频轨 {index} 入点")
        source_out_raw = item.get("source_out_ms")
        source_out = info["duration_ms"] if source_out_raw is None else _integer(source_out_raw, f"音频轨 {index} 出点")
        if not 0 <= source_in < source_out <= info["duration_ms"]:
            raise ValueError(f"音频轨 {index} 范围超出源文件")
        timeline_start = _integer(item.get("timeline_start_ms", 0), f"音频轨 {index} 时间轴起点")
        clip_dur = source_out - source_in
        if not 0 <= timeline_start < duration_ms or timeline_start + clip_dur > duration_ms:
            raise ValueError(f"音频轨 {index} 超出成片时间轴")
        gain_db = _optional_real(item.get("gain_db"), f"音频轨 {index} 增益", default=0.0, minimum=-60.0, maximum=24.0)
        fade_in_ms = _nonneg_int(item.get("fade_in_ms"), f"音频轨 {index} 淡入")
        fade_out_ms = _nonneg_int(item.get("fade_out_ms"), f"音频轨 {index} 淡出")
        ducking_raw = item.get("ducking_windows")
        ducking = parse_ducking_windows(ducking_raw, duration_ms) if ducking_raw is not None else None
        normalized.append(
            {
                "path": str(path),
                "sha256": item["sha256"],
                "run_id": item.get("run_id"),
                "source_note": item.get("source_note"),
                "role": role,
                "source_in_ms": source_in,
                "source_out_ms": source_out,
                "timeline_start_ms": timeline_start,
                "duration_ms": clip_dur,
                "gain_db": gain_db,
                "fade_in_ms": fade_in_ms,
                "fade_out_ms": fade_out_ms,
                "ducking_windows": ducking,
            }
        )
    return normalized


def _make_media_caches():
    checked_media: dict[tuple[str, str, bool], tuple[Path, dict[str, Any]]] = {}
    checked_streams: dict[tuple[Path, str], dict[str, Any]] = {}

    def verified_media(path_value: Any, digest_value: Any, *, audio: bool) -> tuple[Path, dict[str, Any]]:
        if (
            not isinstance(path_value, str)
            or not Path(path_value).is_absolute()
            or not isinstance(digest_value, str)
        ):
            return _media(path_value, digest_value, audio=audio)
        resolved = str(Path(path_value).resolve(strict=True))
        key = (resolved, digest_value, audio)
        if key not in checked_media:
            checked_media[key] = _media(path_value, digest_value, audio=audio)
        return checked_media[key]

    def stream_info(path: Path, kind: str) -> dict[str, Any]:
        key = (path, kind)
        if key not in checked_streams:
            checked_streams[key] = _stream_info(path, kind)
        return checked_streams[key]

    return verified_media, stream_info


def validate_story_edit(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a narrative/short-drama/ad edit manifest (`lfo.story.edit.v1`)."""
    if not isinstance(value, dict) or value.get("schema") != EDIT_SCHEMA:
        raise ValueError("不是受支持的叙事成片编辑清单 (lfo.story.edit.v1)")
    width = _integer(value.get("width"), "画幅宽度")
    height = _integer(value.get("height"), "画幅高度")
    fps = _real(value.get("fps"), "帧率")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("输出画幅或帧率无效")
    strategy = value.get("native_audio_strategy", "keep")
    if not isinstance(strategy, str) or strategy not in NATIVE_AUDIO_STRATEGIES:
        raise ValueError("原生声音策略必须为 keep、mix、replace 或 mute")
    seam_fade_ms = _nonneg_int(value.get("seam_fade_ms"), "音频接缝过渡时长", default=_DEFAULT_SEAM_FADE_MS)
    if seam_fade_ms > _MAX_SEAM_FADE_MS:
        raise ValueError(f"音频接缝过渡时长不能超过 {_MAX_SEAM_FADE_MS} 毫秒")
    loudness = _validate_loudness(value.get("loudness"))

    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("成片清单至少需要一个画面段")

    verified_media, stream_info = _make_media_caches()
    expected = 0
    preliminary: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise ValueError(f"镜头 {index} 必须是对象")
        kind = segment.get("kind", "video")
        if not isinstance(kind, str) or kind not in {"video", "image"}:
            raise ValueError("正式画面段 kind 仅支持 video 或 image，不接受占位")
        _media_provenance(segment)
        if segment.get("transition", "cut") != "cut":
            raise ValueError("当前画面剪辑仅支持硬切转场")
        path, info = verified_media(segment.get("path"), segment.get("sha256"), audio=False)
        if info.get("width") is None or info.get("height") is None:
            raise ValueError(f"源片不是有效视觉媒体：{path}")

        audio_mode = segment.get("audio_mode", "keep")
        if audio_mode not in {"keep", "mute"}:
            raise ValueError(f"镜头 {index} audio_mode 必须为 keep 或 mute")
        audio_gain_db = _optional_real(
            segment.get("audio_gain_db"), f"镜头 {index} 原声增益", default=0.0, minimum=-60.0, maximum=24.0
        )
        lead_ms = _nonneg_int(segment.get("audio_lead_ms"), f"镜头 {index} J-cut 提前量")
        tail_ms = _nonneg_int(segment.get("audio_tail_ms"), f"镜头 {index} L-cut 延后量")
        fade_in_ms = segment.get("audio_fade_in_ms")
        fade_out_ms = segment.get("audio_fade_out_ms")
        if fade_in_ms is not None:
            fade_in_ms = _nonneg_int(fade_in_ms, f"镜头 {index} 音频淡入")
        if fade_out_ms is not None:
            fade_out_ms = _nonneg_int(fade_out_ms, f"镜头 {index} 音频淡出")

        if kind == "image":
            _check_still(path, info)
            if "source_in_ms" in segment or "source_out_ms" in segment:
                raise ValueError("静态图片段使用 duration_ms，不接受视频裁切字段")
            if lead_ms or tail_ms or audio_mode != "keep":
                raise ValueError(f"镜头 {index} 为静态图片，不支持原声 J/L-cut 或音频选项")
            clip_duration = _integer(segment.get("duration_ms"), "图片时长")
            if clip_duration <= 0:
                raise ValueError("图片时长必须大于零")
            entry: dict[str, Any] = {
                "kind": "image",
                "path": str(path),
                "sha256": segment["sha256"],
                "run_id": segment.get("run_id"),
                "source_note": segment.get("source_note"),
                "node_id": segment.get("node_id"),
                "shot_id": segment.get("shot_id"),
                "duration_ms": clip_duration,
                "has_audio": False,
            }
        else:
            source_in = _integer(segment.get("source_in_ms"), "源片入点")
            source_out = _integer(segment.get("source_out_ms"), "源片出点")
            video_duration = stream_info(path, "video")["duration_ms"]
            if not 0 <= source_in < source_out <= video_duration:
                raise ValueError(f"镜头 {index} 源片范围越界")
            clip_duration = source_out - source_in
            has_audio = bool(info.get("has_audio"))
            if (lead_ms or tail_ms) and audio_mode == "mute":
                raise ValueError(f"镜头 {index} 已静音，不支持设置 J/L-cut 偏移")
            if (lead_ms or tail_ms) and not has_audio:
                raise ValueError(f"镜头 {index} 无原生音轨，不能设置 J/L-cut")
            if lead_ms > source_in:
                raise ValueError(f"镜头 {index} audio_lead_ms 超出源片入点可用前缘")
            if has_audio and tail_ms > 0:
                audio_dur = stream_info(path, "audio")["duration_ms"]
                if source_out + tail_ms > audio_dur:
                    raise ValueError(f"镜头 {index} audio_tail_ms 超出源片音轨总时长")
            entry = {
                "kind": "video",
                "path": str(path),
                "sha256": segment["sha256"],
                "run_id": segment.get("run_id"),
                "source_note": segment.get("source_note"),
                "node_id": segment.get("node_id"),
                "shot_id": segment.get("shot_id"),
                "source_in_ms": source_in,
                "source_out_ms": source_out,
                "duration_ms": clip_duration,
                "has_audio": has_audio,
                "audio_mode": audio_mode,
                "audio_gain_db": audio_gain_db,
                "audio_lead_ms": lead_ms,
                "audio_tail_ms": tail_ms,
                "audio_fade_in_ms": fade_in_ms,
                "audio_fade_out_ms": fade_out_ms,
            }
        start = _integer(segment.get("timeline_start_ms"), "成片起点")
        if start != expected:
            raise ValueError("成片镜头时间轴有空洞、重叠或不连续")
        end = start + clip_duration
        if round(end * fps / 1000) <= round(start * fps / 1000):
            raise ValueError("镜头短于一个可渲染视频帧")
        entry["timeline_start_ms"] = start
        entry["timeline_end_ms"] = end
        preliminary.append(entry)
        expected = end

    total_duration_ms = expected
    for index, entry in enumerate(preliminary, start=1):
        if entry["kind"] == "video":
            if entry["timeline_start_ms"] - entry["audio_lead_ms"] < 0:
                raise ValueError(f"镜头 {index} J-cut 提前量超出成片起点 0")
            if entry["timeline_end_ms"] + entry["audio_tail_ms"] > total_duration_ms:
                raise ValueError(f"镜头 {index} L-cut 延后量超出成片总时长")

    parse_ducking_windows(value.get("music_ducking", []), total_duration_ms)
    tracks = _validate_audio_tracks(value.get("audio_tracks"), total_duration_ms, verified_media)
    if strategy == "replace" and not tracks:
        raise ValueError("native_audio_strategy=replace 时必须提供至少一条外部 audio_tracks")

    overlays = value.get("image_overlays", [])
    if not isinstance(overlays, list):
        raise ValueError("image_overlays 必须是数组")
    for overlay in overlays:
        if not isinstance(overlay, dict):
            raise ValueError("图片叠加必须是对象")
        _media_provenance(overlay)
        path, info = verified_media(overlay.get("path"), overlay.get("sha256"), audio=False)
        _check_still(path, info)
        begin = _integer(overlay.get("start_ms"), "叠加起点")
        end = _integer(overlay.get("end_ms"), "叠加终点")
        x, y = _integer(overlay.get("x"), "叠加横位置"), _integer(overlay.get("y"), "叠加纵位置")
        w, h = _integer(overlay.get("width"), "叠加宽度"), _integer(overlay.get("height"), "叠加高度")
        opacity = _real(overlay.get("opacity", 1), "图片不透明度")
        if (
            not 0 <= begin < end <= total_duration_ms
            or min(x, y) < 0
            or min(w, h) <= 0
            or x + w > width
            or y + h > height
            or not 0 <= opacity <= 1
        ):
            raise ValueError("图片叠加时间、位置、尺寸或不透明度越界")

    subtitles = _validate_subtitles(value.get("subtitles"), total_duration_ms)
    text_events = _validate_text_events(value.get("text_events"), total_duration_ms)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_ms": total_duration_ms,
        "native_audio_strategy": strategy,
        "seam_fade_ms": seam_fade_ms,
        "loudness": loudness,
        "segments": preliminary,
        "audio_tracks": tracks,
        "music_ducking": parse_ducking_windows(value.get("music_ducking", []), total_duration_ms),
        "image_overlays": overlays,
        "subtitles": subtitles,
        "text_events": text_events,
    }


def _render_story_ass(
    subtitles: list[SubtitleCue],
    text_events: list[dict[str, Any]],
    *,
    width: int,
    height: int,
) -> str:
    if min(width, height) < 64:
        raise ValueError("字幕画幅无效")
    font_size = max(22, round(height * 0.043))
    margin_x = round(width * 0.07)
    margin_y = round(height * 0.07)
    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Dialogue,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFFFFF,&H90000000,&H60000000,"
        f"0,0,0,0,100,100,0,0,1,2,0,2,{margin_x},{margin_x},{margin_y},1\n"
        f"Style: Visual,Microsoft YaHei,{round(font_size * 1.15)},&H00FFFFFF,&H00FFFFFF,&H90000000,&H60000000,"
        f"0,0,0,0,100,100,0,0,1,2,0,5,{margin_x},{margin_x},{margin_y},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines: list[str] = []
    for cue in subtitles:
        lines.append(
            f"Dialogue: 0,{_ass_time(cue.start_ms)},{_ass_time(cue.end_ms)},Dialogue,,0,0,0,,{_ass_text(cue.text)}"
        )
    for event in text_events:
        start, end = event["start_ms"], event["end_ms"]
        duration = end - start
        effect = event.get("effect", "none")
        if effect == "none":
            tag = ""
        elif effect == "fade":
            fade = min(180, duration // 4)
            tag = r"{\fad(" + f"{fade},{fade}" + ")}"
        else:
            tag = r"{\fscx90\fscy90\t(0," + str(duration) + r",\fscx100\fscy100)}"
        lines.append(
            f"Dialogue: 1,{_ass_time(start)},{_ass_time(end)},Visual,,0,0,0,,{tag}{_ass_text(event['text'])}"
        )
    return header + "\n".join(lines) + ("\n" if lines else "")


def _extract_pcm_segment(source: Path, output: Path, begin_ms: int, end_ms: int, *, timeout_s: float) -> None:
    run_command(
        [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v", "error", "-xerror", "-n",
            "-i", str(source),
            "-ss", f"{begin_ms / 1000:.6f}",
            "-t", f"{(end_ms - begin_ms) / 1000:.6f}",
            "-map", "0:a:0",
            "-af", "aresample=48000,aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo",
            "-c:a", "pcm_s16le",
            str(output),
        ],
        timeout_s=timeout_s,
    )


def _assemble_native_audio_pcm(
    segments: list[dict[str, Any]],
    *,
    expected_frames: int,
    fps: float,
    total_duration_ms: int,
    seam_fade_ms: int,
    work_dir: Path,
    timeout_s: float,
) -> Path | None:
    """Mix per-segment native audio with J/L-cut offsets and boundary fades."""
    total_samples = max(1, round(expected_frames * 48000 / fps))
    accumulator = array("i", [0]) * (total_samples * 2)
    contributed = False
    for index, segment in enumerate(segments, start=1):
        if segment["kind"] != "video" or not segment.get("has_audio") or segment.get("audio_mode") == "mute":
            continue
        lead_ms = segment["audio_lead_ms"]
        tail_ms = segment["audio_tail_ms"]
        src_in = segment["source_in_ms"] - lead_ms
        src_out = segment["source_out_ms"] + tail_ms
        tl_start = segment["timeline_start_ms"] - lead_ms
        tl_end = segment["timeline_end_ms"] + tail_ms

        wav_path = work_dir / f"native-seg-{index}.wav"
        _extract_pcm_segment(Path(segment["path"]), wav_path, src_in, src_out, timeout_s=timeout_s)
        with wave.open(str(wav_path), "rb") as stream:
            if stream.getnchannels() != 2 or stream.getsampwidth() != 2 or stream.getframerate() != 48000:
                raise ValueError(f"镜头 {index} 提取的原声 PCM 格式不符")
            raw_frames = stream.readframes(stream.getnframes())
        samples = array("h")
        samples.frombytes(raw_frames)
        if sys.byteorder == "big":
            samples.byteswap()
        nframes = len(samples) // 2
        if nframes <= 0:
            continue

        gain = 10.0 ** (segment["audio_gain_db"] / 20.0)
        fade_in_ms = (
            segment["audio_fade_in_ms"]
            if segment["audio_fade_in_ms"] is not None
            else (seam_fade_ms if tl_start > 0 else 0)
        )
        fade_out_ms = (
            segment["audio_fade_out_ms"]
            if segment["audio_fade_out_ms"] is not None
            else (seam_fade_ms if tl_end < total_duration_ms else 0)
        )
        fade_in_samples = round(fade_in_ms * 48000 / 1000)
        fade_out_samples = round(fade_out_ms * 48000 / 1000)
        if fade_in_samples + fade_out_samples > nframes:
            scale = nframes / max(1, fade_in_samples + fade_out_samples)
            fade_in_samples = math.floor(fade_in_samples * scale)
            fade_out_samples = math.floor(fade_out_samples * scale)

        dst_start = max(0, round(tl_start * 48000 / 1000))
        usable = min(nframes, total_samples - dst_start)
        for frame_idx in range(usable):
            envelope = gain
            if fade_in_samples > 0 and frame_idx < fade_in_samples:
                envelope *= (frame_idx + 1) / fade_in_samples
            if fade_out_samples > 0 and frame_idx >= nframes - fade_out_samples:
                remaining = nframes - frame_idx
                envelope *= max(0.0, remaining / fade_out_samples)
            src_pos = frame_idx * 2
            dst_pos = (dst_start + frame_idx) * 2
            accumulator[dst_pos] += round(samples[src_pos] * envelope)
            accumulator[dst_pos + 1] += round(samples[src_pos + 1] * envelope)
        contributed = True

    if not contributed:
        return None
    clamped = array("h", (max(-32768, min(32767, sample)) for sample in accumulator))
    if sys.byteorder == "big":
        clamped.byteswap()
    master = work_dir / "native-master.wav"
    with wave.open(str(master), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(clamped.tobytes())
    return master


def _write_silent_wav(path: Path, *, total_frames: int, fps: float) -> Path:
    total_samples = max(1, round(total_frames * 48000 / fps))
    silence = b"\x00" * (total_samples * 4)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(silence)
    return path


def _burn_ass(
    source: Path,
    ass_path: Path,
    output: Path,
    *,
    work_dir: Path,
    timeout_s: float,
) -> None:
    run_command(
        [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v", "error", "-xerror", "-n",
            "-i", str(source),
            "-vf", f"ass={ass_path.name}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-bf", "0",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output),
        ],
        timeout_s=timeout_s,
        cwd=work_dir,
    )


def _publish_new_file_safe(temp_path: Path, output_path: Path) -> None:
    """Publish a new file without overwriting any existing target (sandbox-safe)."""
    if not temp_path.is_file() or temp_path.stat().st_size == 0:
        raise ValueError(f"候选成片不存在或为空：{temp_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _publish_new_file(temp_path, output_path)
        return
    except ValueError as exc:
        if isinstance(exc.__cause__, FileExistsError) or "会覆盖已有文件" in str(exc):
            raise
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("输出路径会覆盖已有文件")
    try:
        with temp_path.open("rb") as src, output_path.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    except FileExistsError as exc:
        raise ValueError("输出路径会覆盖已有文件") from exc
    temp_path.unlink()


def render_story_edit(
    value: dict[str, Any],
    output_path: Path,
    *,
    clean_output_path: Path | None = None,
    srt_output_path: Path | None = None,
    cache_dir: Path | None = None,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """Render a validated `lfo.story.edit.v1` manifest with seam fades, J/L-cuts, loudness, and subtitles."""
    validated = validate_story_edit(value)
    output = Path(output_path).resolve()
    clean_target = Path(clean_output_path).resolve() if clean_output_path is not None else None
    srt_target = Path(srt_output_path).resolve() if srt_output_path is not None else None

    sources = [Path(item["path"]).resolve() for item in validated["segments"]]
    sources.extend(Path(item["path"]).resolve() for item in validated["audio_tracks"])
    sources.extend(Path(item["path"]).resolve() for item in validated["image_overlays"])
    for target in (output, clean_target, srt_target):
        if target is None:
            continue
        if target in sources or target.exists() or target.is_symlink():
            raise ValueError(f"输出路径会覆盖源素材或已有文件：{target}")
    if clean_target is not None and clean_target == output:
        raise ValueError("净版输出路径不能与主成片路径相同")

    duration_ms = validated["duration_ms"]
    fps = validated["fps"]
    width = validated["width"]
    height = validated["height"]
    cache = Path(cache_dir) if cache_dir is not None else output.with_name(f".{output.stem}-segments")
    cache = validate_cache_directory(cache, [*sources, Path(output_path)])
    output.parent.mkdir(parents=True, exist_ok=True)

    render_items = [
        {
            "kind": item["kind"],
            "timeline_start_ms": item["timeline_start_ms"],
            "duration_ms": item["duration_ms"],
            "path": item["path"],
            "sha256": item["sha256"],
            **({"source_in_ms": item["source_in_ms"], "source_out_ms": item["source_out_ms"]}
               if item["kind"] == "video" else {}),
        }
        for item in validated["segments"]
    ]

    with tempfile.TemporaryDirectory(prefix=".story-render-", dir=output.parent) as folder:
        temp = Path(folder)
        rendered = render_visual_segments(
            render_items,
            width=width,
            height=height,
            fps=fps,
            cache_dir=cache,
            work_dir=temp,
            include_native_audio=False,
            timeout_s=timeout_s,
        )
        base = Path(rendered["picture_path"])
        expected_frames = rendered["video_frame_count"]

        tracks: list[AudioTrack] = []
        if validated["native_audio_strategy"] in {"keep", "mix"}:
            native_master = _assemble_native_audio_pcm(
                validated["segments"],
                expected_frames=expected_frames,
                fps=fps,
                total_duration_ms=duration_ms,
                seam_fade_ms=validated["seam_fade_ms"],
                work_dir=temp,
                timeout_s=timeout_s,
            )
            if native_master is not None:
                tracks.append(AudioTrack(asset_key=str(native_master), role="native"))

        if validated["native_audio_strategy"] in {"mix", "replace"} or validated["audio_tracks"]:
            for index, item in enumerate(validated["audio_tracks"], start=1):
                selected = temp / f"track-{index}.flac"
                _trim_audio(Path(item["path"]), selected, item["source_in_ms"], item["source_out_ms"])
                ducking = item["ducking_windows"]
                if ducking is None and item["role"] in DUCKABLE_ROLES and validated["music_ducking"]:
                    ducking = validated["music_ducking"]
                elif ducking is None:
                    ducking = []
                tracks.append(
                    AudioTrack(
                        asset_key=str(selected),
                        role=item["role"],
                        offset_ms=item["timeline_start_ms"],
                        gain_db=item["gain_db"],
                        fade_in_ms=item["fade_in_ms"],
                        fade_out_ms=item["fade_out_ms"],
                        duration_ms=item["duration_ms"],
                        ducking_windows=ducking,
                    )
                )

        has_active_audio = bool(tracks)
        if not tracks:
            silent_wav = _write_silent_wav(temp / "silent.wav", total_frames=expected_frames, fps=fps)
            tracks.append(AudioTrack(asset_key=str(silent_wav), role="native"))

        loudness = validated["loudness"]
        target_loudness_db = (
            loudness["target_i"]
            if has_active_audio and loudness is not None and loudness.get("enabled")
            else None
        )
        mixed = temp / "mixed.mp4"
        mix_result = AudioMixer().mix(
            AudioMixRequest(
                native_audio_present=False,
                native_audio_strategy="mix",
                tracks=tracks,
                target_loudness_db=target_loudness_db,
                clip_duration_ms=duration_ms,
                source_video_path=str(base),
                output_path=str(mixed),
                normalize_inputs=False,
            ),
            timeout_s=timeout_s,
        )
        if not mix_result.success:
            raise ValueError(f"成片音轨合成失败：{mix_result.error}")

        visual_stage = mixed
        if validated["image_overlays"]:
            visual_stage = temp / "overlaid.mp4"
            _render_image_overlays(
                mixed, visual_stage, validated["image_overlays"], fps=fps, duration_ms=duration_ms
            )

        if clean_target is not None:
            clean_copy = temp / "clean-copy.mp4"
            run_command(
                [
                    os.environ.get("LFO_FFMPEG") or "ffmpeg",
                    "-v", "error", "-xerror", "-n",
                    "-i", str(visual_stage),
                    "-c", "copy", "-movflags", "+faststart",
                    str(clean_copy),
                ],
                timeout_s=timeout_s,
            )
            _publish_new_file_safe(clean_copy, clean_target)

        final_candidate = visual_stage
        if validated["subtitles"] or validated["text_events"]:
            _verify_ass_support()
            ass_path = temp / "story.ass"
            ass_path.write_text(
                _render_story_ass(
                    validated["subtitles"], validated["text_events"], width=width, height=height
                ),
                encoding="utf-8",
            )
            final_candidate = temp / "subtitled.mp4"
            _burn_ass(visual_stage, ass_path, final_candidate, work_dir=temp, timeout_s=timeout_s)

        final_info = probe(final_candidate)
        final_video = _stream_info(final_candidate, "video")
        final_audio = _stream_info(final_candidate, "audio")
        if (
            not final_info["has_audio"]
            or final_video["frame_count"] != expected_frames
            or abs(final_audio["duration_ms"] - duration_ms) > max(80, round(2000 / fps))
        ):
            raise ValueError("成片音轨或时长核验失败")
        _publish_new_file_safe(final_candidate, output)

    if srt_target is not None and validated["subtitles"]:
        srt_target.parent.mkdir(parents=True, exist_ok=True)
        with srt_target.open("x", encoding="utf-8") as stream:
            stream.write(cues_to_srt(validated["subtitles"]))

    return {
        "schema": RECEIPT_SCHEMA,
        "purpose": "final-render",
        "path": str(output),
        "sha256": _digest(output),
        "clean_output_path": str(clean_target) if clean_target is not None else None,
        "clean_output_sha256": _digest(clean_target) if clean_target is not None else None,
        "srt_output_path": str(srt_target) if srt_target is not None and validated["subtitles"] else None,
        "duration_ms": probe(output)["duration_ms"],
        "video_frame_count": final_video["frame_count"],
        "audio_duration_ms": final_audio["duration_ms"],
        "native_audio_strategy": validated["native_audio_strategy"],
        "seam_fade_ms": validated["seam_fade_ms"],
        "loudness": validated["loudness"],
        "output_width": width,
        "output_height": height,
        "output_fps": fps,
        "cache_dir": rendered["cache_dir"],
        "cache_hits": rendered["cache_hits"],
        "cache_misses": rendered["cache_misses"],
        "cache_rebuilt": rendered["cache_rebuilt"],
        "subtitle_count": len(validated["subtitles"]),
        "text_event_count": len(validated["text_events"]),
        "segments": [
            {
                "kind": item["kind"],
                "path": item["path"],
                "run_id": item.get("run_id"),
                "source_note": item.get("source_note"),
                "sha256": item["sha256"],
                "output_start_frame": rendered_seg["output_start_frame"],
                "output_end_frame": rendered_seg["output_end_frame"],
                "output_frame_count": rendered_seg["output_frame_count"],
                "cache_hit": rendered_seg["cache_hit"],
            }
            for item, rendered_seg in zip(validated["segments"], rendered["segments"], strict=True)
        ],
        "listening_status": "INCONCLUSIVE",
    }


def validate_story_preview(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a narrative animatic preview manifest (`lfo.story.preview.v1`)."""
    if not isinstance(value, dict) or value.get("schema") != PREVIEW_SCHEMA:
        raise ValueError("不是受支持的故事板预览清单 (lfo.story.preview.v1)")
    if any(value.get(key) for key in ("image_overlays", "music_ducking", "loudness")):
        raise ValueError("故事板预览不消费正式后期字段；请使用 lfo.story.edit.v1 的 render")

    width = _integer(value.get("width"), "画幅宽度")
    height = _integer(value.get("height"), "画幅高度")
    fps = _real(value.get("fps"), "帧率")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("输出画幅或帧率无效")
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("故事板预览至少需要一个时间段")

    verified_media, stream_info = _make_media_caches()
    expected_start = 0
    normalized: list[dict[str, Any]] = []
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
            path, info = verified_media(media.get("path"), media.get("sha256"), audio=False)
            if not info.get("width") or not info.get("height") or not info.get("fps"):
                raise ValueError(f"预览镜头 {index} 视频规格无效")
            source_in = _integer(media.get("source_in_ms", 0), "预览视频入点")
            source_out = _integer(media.get("source_out_ms"), "预览视频出点")
            stream_duration = stream_info(path, "video")["duration_ms"]
            if not 0 <= source_in < source_out <= stream_duration or source_out - source_in != clip_duration:
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
            path, info = verified_media(media.get("path"), media.get("sha256"), audio=False)
            _check_still(path, info)
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

    duration_ms = expected_start
    audio_tracks = _validate_audio_tracks(
        value.get("audio_tracks"), duration_ms, verified_media, require_provenance=False
    )
    subtitles = _validate_subtitles(value.get("subtitles"), duration_ms)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_ms": duration_ms,
        "segments": normalized,
        "audio_tracks": audio_tracks,
        "subtitles": subtitles,
    }


def render_story_preview(
    value: dict[str, Any],
    output_path: Path,
    *,
    cache_dir: Path | None = None,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """Render an explicitly labelled narrative animatic rough cut (`lfo.story.preview.v1`)."""
    validated = validate_story_preview(value)
    output = Path(output_path).resolve()
    source_paths = [Path(item["path"]).resolve() for item in validated["segments"] if item.get("path")]
    source_paths.extend(Path(item["path"]).resolve() for item in validated["audio_tracks"])
    if output in source_paths or output.exists() or output.is_symlink():
        raise ValueError("预览输出路径会覆盖源素材或已有文件")

    placeholders = [item for item in validated["segments"] if item["kind"] == "placeholder"]
    if placeholders or validated["subtitles"]:
        _verify_ass_support()

    duration_ms = validated["duration_ms"]
    fps = validated["fps"]
    cache = Path(cache_dir) if cache_dir is not None else output.with_name(f".{output.stem}-segments")
    cache = validate_cache_directory(cache, [*source_paths, Path(output_path)])
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".story-preview-", dir=output.parent) as folder:
        work = Path(folder)
        rendered = render_visual_segments(
            validated["segments"],
            width=validated["width"],
            height=validated["height"],
            fps=fps,
            cache_dir=cache,
            work_dir=work,
            include_native_audio=True,
            timeout_s=timeout_s,
        )
        tracks: list[AudioTrack] = []
        if rendered["native_audio_path"] is not None:
            tracks.append(AudioTrack(asset_key=str(rendered["native_audio_path"]), role="native"))
        for index, item in enumerate(validated["audio_tracks"], start=1):
            selected = work / f"preview-track-{index}.flac"
            _trim_audio(Path(item["path"]), selected, item["source_in_ms"], item["source_out_ms"])
            tracks.append(
                AudioTrack(
                    asset_key=str(selected),
                    role=item["role"],
                    offset_ms=item["timeline_start_ms"],
                    gain_db=item["gain_db"],
                    duration_ms=item["duration_ms"],
                    ducking_windows=[],
                )
            )
        if not tracks:
            silent_wav = _write_silent_wav(
                work / "silent.wav", total_frames=rendered["video_frame_count"], fps=fps
            )
            tracks.append(AudioTrack(asset_key=str(silent_wav), role="native"))

        mixed = work / "preview-mixed.mp4"
        mix = AudioMixer().mix(
            AudioMixRequest(
                native_audio_present=False,
                native_audio_strategy="mix",
                tracks=tracks,
                clip_duration_ms=duration_ms,
                source_video_path=str(rendered["picture_path"]),
                output_path=str(mixed),
                normalize_inputs=False,
            ),
            timeout_s=timeout_s,
        )
        if not mix.success:
            raise ValueError(f"预览音频合成失败：{mix.error}")

        text_events = [
            {
                "start_ms": item["timeline_start_ms"],
                "end_ms": item["timeline_start_ms"] + item["duration_ms"],
                "text": f"故事板预览 · 待生成\n{item['label']}",
                "effect": "none",
            }
            for item in placeholders
        ]
        candidate = mixed
        if validated["subtitles"] or text_events:
            ass_path = work / "preview.ass"
            ass_path.write_text(
                _render_story_ass(
                    validated["subtitles"],
                    text_events,
                    width=validated["width"],
                    height=validated["height"],
                ),
                encoding="utf-8",
            )
            candidate = work / "labelled-preview.mp4"
            _burn_ass(mixed, ass_path, candidate, work_dir=work, timeout_s=timeout_s)

        video_info = _stream_info(candidate, "video")
        audio_info = _stream_info(candidate, "audio")
        if video_info["frame_count"] != rendered["video_frame_count"]:
            raise ValueError("故事板预览字幕处理改变了画面帧数")
        if not probe(candidate)["has_audio"] or abs(audio_info["duration_ms"] - duration_ms) > max(
            80, round(2000 / fps)
        ):
            raise ValueError("故事板预览音频核验失败")
        _publish_new_file_safe(candidate, output)

    return {
        "schema": PREVIEW_SCHEMA,
        "purpose": "story-animatic-preview",
        "path": str(output),
        "sha256": _digest(output),
        "duration_ms": probe(output)["duration_ms"],
        "video_frame_count": rendered["video_frame_count"],
        "audio_duration_ms": audio_info["duration_ms"],
        "segment_count": len(validated["segments"]),
        "placeholder_count": len(placeholders),
        "cache_hits": rendered["cache_hits"],
        "cache_misses": rendered["cache_misses"],
        "cache_rebuilt": rendered["cache_rebuilt"],
        "cache_dir": rendered["cache_dir"],
        "content_review": "NOT_REVIEWED",
    }


def _canvas_read(canvas_id: str, suffix: str) -> dict[str, Any]:
    from lfo.canvas.client import CanvasClient
    from lfo.canvas.settings import CanvasSettings

    project_root = Path(__file__).resolve().parents[3]
    return CanvasClient(CanvasSettings.resolve(project_root)).request(
        "GET", f"/api/canvases/{canvas_id}{suffix}"
    )


def _check_adopted_assets(edit: dict[str, Any], canvas_id: str) -> None:
    assets: list[dict[str, Any]] = []
    for key in ("segments", "image_overlays", "audio_tracks"):
        records = edit.get(key, [])
        if not isinstance(records, list):
            raise ValueError(f"{key} 必须是数组")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"{key} 条目必须是对象")
            for field in ("path", "sha256"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise ValueError(f"{key} 条目缺少有效 {field}")
            if record.get("run_id") is not None and not isinstance(record["run_id"], str):
                raise ValueError(f"{key} run_id 必须是字符串")
            assets.append(record)
    runs = {run["id"]: run for run in _canvas_read(canvas_id, "/runs")["runs"]}
    for item in assets:
        if not item.get("run_id") and isinstance(item.get("source_note"), str) and item["source_note"].strip():
            continue
        run = runs.get(item.get("run_id"), {})
        review = run.get("review") or {}
        if (
            run.get("status") != "succeeded"
            or review.get("decision") != "ACCEPT"
            or Path(review.get("output_path", "")).resolve() != Path(item["path"]).resolve()
            or review.get("output_sha256") != item["sha256"]
        ):
            raise ValueError(f"正式采用不匹配：{item.get('run_id', '缺少运行编号')}")


def _save_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Narrative/short-drama/ad deterministic finishing")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="校验 lfo.story.edit.v1 或 lfo.story.preview.v1 清单")
    check.add_argument("--edit", type=Path, required=True)
    render = commands.add_parser("render", help="按采用素材渲染叙事/短剧/广告成片")
    render.add_argument("--edit", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--clean-output", type=Path)
    render.add_argument("--srt-output", type=Path)
    render.add_argument("--cache-dir", type=Path)
    render.add_argument("--receipt", type=Path)
    render.add_argument("--canvas-id", help="正式交接时核对当前 Canvas 采用版本")
    preview = commands.add_parser("preview", help="渲染有声故事板粗剪预览 (Animatic)")
    preview.add_argument("--edit", type=Path, required=True)
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--cache-dir", type=Path)
    preview.add_argument("--receipt", type=Path)
    production = commands.add_parser("production", help="读取当前画布的制作统计与阶段耗时")
    production.add_argument("--canvas-id", required=True)
    production.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "production":
            value = _canvas_read(args.canvas_id, "/production")
            _save_new(args.output, value)
        elif args.command == "validate":
            raw = json.loads(args.edit.read_text(encoding="utf-8"))
            schema = raw.get("schema") if isinstance(raw, dict) else None
            if schema == PREVIEW_SCHEMA:
                validated = validate_story_preview(raw)
            else:
                validated = validate_story_edit(raw)
            value = {
                "ok": True,
                "schema": schema,
                "duration_ms": validated["duration_ms"],
                "segment_count": len(validated["segments"]),
            }
        else:
            raw = json.loads(args.edit.read_text(encoding="utf-8"))
            if args.receipt is not None:
                protected = {args.edit.resolve(), args.output.resolve()}
                if getattr(args, "clean_output", None) is not None:
                    protected.add(args.clean_output.resolve())
                if args.receipt.resolve() in protected or args.receipt.exists() or args.receipt.is_symlink():
                    raise ValueError("回执不得覆盖输入清单、输出或已有文件")
            if args.command == "render":
                if args.canvas_id:
                    _check_adopted_assets(raw, args.canvas_id)
                value = render_story_edit(
                    raw,
                    args.output,
                    clean_output_path=args.clean_output,
                    srt_output_path=args.srt_output,
                    cache_dir=args.cache_dir,
                )
            else:
                value = render_story_preview(raw, args.output, cache_dir=args.cache_dir)
            if args.receipt is not None:
                _save_new(args.receipt, value)
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
