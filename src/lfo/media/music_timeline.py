"""Version-bound, source-time music timeline for MV editing."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import probe_audio

SCHEMA = "lfo.mv.music-timeline.v1"
EVENT_STATUSES = {"candidate", "verified", "unknown"}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _millis(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} 必须是有效整数毫秒")
    return value


def inspect_music(path: Path, *, start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    metadata = probe_audio(source)
    duration = _millis(metadata["duration_ms"], "音频时长")
    start = _millis(start_ms, "窗口起点")
    end = duration if end_ms is None else _millis(end_ms, "窗口终点")
    if not 0 <= start < end <= duration:
        raise ValueError("歌曲窗口超出实际音频时长或为空")
    value = {
        "schema": SCHEMA,
        "source": {"path": str(source), "sha256": _sha256(source),
                   "duration_ms": duration, "sample_rate": metadata["sample_rate"],
                   "channels": metadata["channels"]},
        "window": {"start_ms": start, "end_ms": end},
        "sections": [], "lyrics": [], "beats": [],
        "analysis": {"bpm_candidates": [], "energy": []},
        "listening_status": "INCONCLUSIVE",
    }
    return validate_music_timeline(value, verify_source=False)


def _events(value: dict[str, Any], key: str, start: int, end: int) -> None:
    events = value.get(key)
    if not isinstance(events, list):
        raise ValueError(f"{key} 必须是数组")
    previous_start = -1
    last_by_layer: dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            raise ValueError(f"{key} 事件必须是对象")
        event_start = _millis(event.get("time_ms") if key == "beats" else event.get("start_ms"), f"{key} 起点")
        event_end = event_start + 1 if key == "beats" else _millis(event.get("end_ms"), f"{key} 终点")
        if not start <= event_start < event_end <= end:
            raise ValueError(f"{key} 事件超出采用窗口或时长为零")
        if event_start < previous_start:
            raise ValueError(f"{key} 事件须按原歌时间排序")
        previous_start = event_start
        if event.get("status", "candidate") not in EVENT_STATUSES:
            raise ValueError(f"{key} 核对状态无效")
        if key in {"lyrics", "sections"}:
            text_key = "text" if key == "lyrics" else "label"
            if not isinstance(event.get(text_key), str) or not event[text_key].strip():
                raise ValueError(f"{key} 缺少 {text_key}")
        if key == "lyrics":
            layer = event.get("layer", "lead")
            if not isinstance(layer, str) or not layer.strip():
                raise ValueError("歌词层无效")
            if event_start < last_by_layer.get(layer, -1):
                raise ValueError(f"歌词层 {layer} 时间重叠")
            last_by_layer[layer] = event_end


def validate_music_timeline(value: dict[str, Any], *, verify_source: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("不是受支持的 MV 音乐时间轴")
    source, window = value.get("source"), value.get("window")
    if not isinstance(source, dict) or not isinstance(window, dict):
        raise ValueError("缺少音频来源或窗口")
    path = source.get("path")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise ValueError("音频路径必须是绝对路径")
    digest = source.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("音频 SHA-256 无效")
    duration = _millis(source.get("duration_ms"), "音频时长")
    sample_rate = _millis(source.get("sample_rate"), "采样率")
    channels = _millis(source.get("channels"), "声道数")
    if min(duration, sample_rate, channels) <= 0:
        raise ValueError("音频元信息无效")
    start = _millis(window.get("start_ms"), "窗口起点")
    end = _millis(window.get("end_ms"), "窗口终点")
    if not 0 <= start < end <= duration:
        raise ValueError("歌曲窗口超出实际音频时长或为空")
    for key in ("sections", "lyrics", "beats"):
        _events(value, key, start, end)
    if value.get("listening_status") not in {"INCONCLUSIVE", "ACCEPT", "REJECT"}:
        raise ValueError("听审状态无效")
    analysis = value.get("analysis")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("bpm_candidates"), list) or not isinstance(analysis.get("energy"), list):
        raise ValueError("分析候选格式无效")
    if verify_source:
        actual = Path(path).resolve(strict=True)
        if _sha256(actual) != digest:
            raise ValueError("音频 SHA-256 已变化，旧时间轴失效")
        metadata = probe_audio(actual)
        if (metadata["duration_ms"], metadata["sample_rate"], metadata["channels"]) != (duration, sample_rate, channels):
            raise ValueError("音频元信息已变化，旧时间轴失效")
    return value
