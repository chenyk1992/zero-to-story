"""Incremental, frame-accounted rendering for cut-based music videos."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError, probe, probe_audio, run_command

_CACHE_SCHEMA = "lfo.mv.segment-cache.v1"
_VIDEO_CODEC = "libx264"
_VIDEO_PRESET = "fast"
_VIDEO_CRF = 18
_VIDEO_B_FRAMES = 0


class MVRenderError(RuntimeError):
    """A stage-labelled MV rendering failure with the complete command detail."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        command: list[str] | None = None,
        diagnostic: str | None = None,
    ) -> None:
        self.stage = stage
        self.command = command
        self.diagnostic = diagnostic
        details = [f"{stage}: {message}"]
        if command:
            details.append("command: " + subprocess.list2cmdline(command))
        if diagnostic:
            details.append(diagnostic.strip())
        super().__init__("\n".join(details))


@dataclass(frozen=True)
class FrameSpan:
    """Half-open output-frame interval assigned to one timeline item."""

    start_frame: int
    end_frame: int

    @property
    def frame_count(self) -> int:
        return self.end_frame - self.start_frame


def frame_schedule(durations_ms: list[int], fps: float) -> list[FrameSpan]:
    """Quantize contiguous durations from cumulative time, avoiding per-cut drift."""
    if not durations_ms or not math.isfinite(fps) or fps <= 0:
        raise ValueError("MV 帧计划需要正时长镜头和有效输出帧率")
    elapsed_ms = 0
    previous_frame = 0
    result: list[FrameSpan] = []
    for index, duration_ms in enumerate(durations_ms, start=1):
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
            raise ValueError(f"镜头 {index} 时长无效")
        elapsed_ms += duration_ms
        end_frame = round(elapsed_ms * fps / 1000)
        if end_frame <= previous_frame:
            raise ValueError(f"镜头 {index} 短于一个可渲染视频帧")
        result.append(FrameSpan(previous_frame, end_frame))
        previous_frame = end_frame
    return result


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _run(command: list[str], *, stage: str, timeout_s: float) -> None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise MVRenderError(f"找不到媒体程序：{command[0]}", stage=stage, command=command) from exc
    except subprocess.TimeoutExpired as exc:
        diagnostic = "\n".join(
            value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            for value in (exc.stdout, exc.stderr)
        )
        raise MVRenderError(
            f"媒体处理超过 {timeout_s:g} 秒",
            stage=stage,
            command=command,
            diagnostic=diagnostic,
        ) from exc
    if result.returncode:
        raise MVRenderError(
            f"媒体处理退出码 {result.returncode}",
            stage=stage,
            command=command,
            diagnostic=(result.stderr or result.stdout or "没有提供诊断文本").strip(),
        )


def _stream_count(path: Path, kind: str) -> tuple[int, int]:
    command = [
        os.environ.get("LFO_FFPROBE") or "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        "stream=codec_type,nb_read_frames,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = run_command(command, timeout_s=60)
        streams = json.loads(result.stdout).get("streams", [])
        stream = next((item for item in streams if item.get("codec_type") == kind), None)
        if stream is None or stream.get("nb_read_frames") in (None, "N/A"):
            raise ValueError(f"文件没有可计数的 {kind} 帧：{path}")
        return int(stream["nb_read_frames"]), int(stream.get("width") or 0)
    except (MediaCommandError, ValueError, KeyError, TypeError) as exc:
        raise MVRenderError(
            f"无法核实 {kind} 帧数：{path}",
            stage="输出核验",
            command=command,
            diagnostic=str(exc),
        ) from exc


def _fps_token(fps: float) -> str:
    return f"{fps:.12g}"


def _source_metadata(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    kind = item["kind"]
    path = Path(item["path"]).resolve(strict=True) if item.get("path") else None
    if kind == "placeholder":
        return {"path": None, "fps": None, "has_audio": False, "metadata": None}
    if path is None:
        raise ValueError(f"镜头 {index} 缺少媒体路径")
    metadata = probe(path)
    if not metadata.get("width") or not metadata.get("height"):
        raise ValueError(f"镜头 {index} 输入不是可用图像或视频：{path}")
    if kind == "video" and (metadata.get("fps") is None or metadata["fps"] <= 0):
        raise ValueError(f"镜头 {index} 源视频帧率无法核实：{path}")
    return {
        "path": path,
        "fps": float(metadata["fps"]) if kind == "video" and metadata.get("fps") else None,
        "has_audio": bool(metadata.get("has_audio")) if kind == "video" else False,
        "metadata": metadata,
    }


def _source_frame_range(item: dict[str, Any], source_fps: float | None) -> tuple[int, int, int]:
    if item["kind"] != "video" or source_fps is None:
        return 0, 0, int(item.get("source_in_ms", 0))
    source_in_ms = int(item["source_in_ms"])
    source_out_ms = int(item["source_out_ms"])
    start_frame = math.floor(source_in_ms * source_fps / 1000)
    end_frame = math.ceil(source_out_ms * source_fps / 1000 - 1e-9)
    if end_frame <= start_frame:
        raise ValueError("镜头时间范围短于一个源视频帧")
    applied_in_ms = math.floor(start_frame * 1000 / source_fps)
    return start_frame, end_frame, applied_in_ms


def _cache_key(
    item: dict[str, Any],
    *,
    source_fps: float | None,
    source_audio: bool,
    span: FrameSpan,
    width: int,
    height: int,
    fps: float,
    include_native_audio: bool,
) -> str:
    identity = {
        "cache_schema": _CACHE_SCHEMA,
        "kind": item["kind"],
        "source_sha256": item.get("sha256"),
        "source_in_ms": item.get("source_in_ms", 0),
        "source_out_ms": item.get("source_out_ms"),
        "source_fps": source_fps,
        "source_audio": source_audio,
        "label": item.get("label"),
        "duration_ms": item["duration_ms"],
        # A cached segment is local to its own timeline item. Absolute placement
        # changes do not alter its pixels when the required frame count is stable.
        "output_frame_count": span.frame_count,
        "output_size": [width, height],
        "output_fps": fps,
        "native_audio": include_native_audio,
        "video_encoder": [_VIDEO_CODEC, _VIDEO_PRESET, _VIDEO_CRF, _VIDEO_B_FRAMES],
        "audio_encoder": "pcm-s16le-wav-48k-stereo" if include_native_audio else None,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _manifest_load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") == _CACHE_SCHEMA and isinstance(payload.get("entries"), dict):
            return payload["entries"]
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass
    return {}


def _manifest_save(path: Path, entries: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps({"schema": _CACHE_SCHEMA, "entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _cache_valid(
    video_path: Path,
    audio_path: Path | None,
    entry: dict[str, Any] | None,
    *,
    expected_frames: int,
    width: int,
    height: int,
    fps: float,
    expected_audio_ms: int,
) -> tuple[bool, str | None]:
    if not isinstance(entry, dict):
        return False, "缓存清单缺少当前片段记录"
    try:
        if not video_path.is_file() or entry.get("video_sha256") != _digest(video_path):
            return False, "视频缓存缺失或哈希不匹配"
        actual_frames, _ = _stream_count(video_path, "video")
        metadata = probe(video_path)
        if (
            actual_frames != expected_frames
            or metadata.get("width") != width
            or metadata.get("height") != height
            or metadata.get("fps") is None
            or abs(float(metadata["fps"]) - fps) > 0.01
        ):
            return False, "视频缓存帧数或输出规格不匹配"
        if audio_path is not None:
            if not audio_path.is_file() or entry.get("audio_sha256") != _digest(audio_path):
                return False, "原始音轨缓存缺失或哈希不匹配"
            audio = probe_audio(audio_path)
            if abs(audio["duration_ms"] - expected_audio_ms) > max(80, round(2000 / fps)):
                return False, "原始音轨缓存时长不匹配"
            with wave.open(str(audio_path), "rb") as audio_stream:
                expected_samples = round(expected_frames * 48000 / fps)
                if (
                    audio_stream.getnchannels() != 2
                    or audio_stream.getframerate() != 48000
                    or audio_stream.getsampwidth() != 2
                    or audio_stream.getnframes() != expected_samples
                ):
                    return False, "原始音轨缓存采样数不匹配"
        return True, None
    except (OSError, MediaCommandError, MVRenderError, ValueError, KeyError, TypeError) as exc:
        return False, f"缓存核验失败：{exc}"


def _filter_scale(width: int, height: int, fps: float) -> str:
    return ",".join(
        [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
            f"fps={_fps_token(fps)}",
            "setsar=1",
            "format=yuv420p",
        ]
    )


def _render_segment(
    item: dict[str, Any],
    source: dict[str, Any],
    span: FrameSpan,
    video_temp: Path,
    audio_temp: Path | None,
    *,
    width: int,
    height: int,
    fps: float,
    source_frame_start: int,
    source_frame_end: int,
    applied_source_in_ms: int,
    timeout_s: float,
    index: int,
) -> None:
    frame_count = span.frame_count
    output_duration_s = frame_count / fps
    source_duration_s = (
        max(0, int(item.get("source_out_ms", item.get("duration_ms", 0))) - applied_source_in_ms)
        / 1000
    )
    if item["kind"] == "video":
        video_input = str(source["path"])
        video_chain = [
            f"trim=start_frame={source_frame_start}:end_frame={source_frame_end}",
            "setpts=PTS-STARTPTS",
            _filter_scale(width, height, fps),
            f"trim=end_frame={frame_count}",
            "setpts=PTS-STARTPTS",
        ]
        input_args = ["-i", video_input]
    elif item["kind"] == "image":
        input_args = ["-loop", "1", "-framerate", _fps_token(fps), "-i", str(source["path"])]
        video_chain = [
            _filter_scale(width, height, fps),
            f"trim=end_frame={frame_count}",
            "setpts=PTS-STARTPTS",
        ]
    else:
        input_args = [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:r={_fps_token(fps)}:d={output_duration_s:.12f}",
        ]
        video_chain = [
            f"trim=end_frame={frame_count}",
            "setpts=PTS-STARTPTS",
            "setsar=1",
            "format=yuv420p",
        ]

    filter_parts = [f"[0:v]{','.join(video_chain)}[vout]"]
    input_index = 1
    audio_label: str | None = None
    if audio_temp is not None:
        if item["kind"] == "video" and source["has_audio"]:
            audio_input = 0
            audio_input_label = "0:a:0"
        else:
            input_args += [
                "-f",
                "lavfi",
                "-t",
                f"{output_duration_s:.12f}",
                "-i",
                "anullsrc=r=48000:cl=stereo",
            ]
            audio_input = input_index
            input_index += 1
            audio_input_label = f"{audio_input}:a:0"
        if audio_input == 0:
            audio_start_s = applied_source_in_ms / 1000
            audio_chain = [
                f"atrim=start={audio_start_s:.9f}:duration={source_duration_s:.9f}",
                "asetpts=PTS-STARTPTS",
                "aresample=48000",
                "aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo",
                f"apad=whole_dur={output_duration_s:.12f}",
                f"atrim=duration={output_duration_s:.12f}",
            ]
        else:
            audio_chain = [
                f"atrim=duration={output_duration_s:.12f}",
                "asetpts=PTS-STARTPTS",
                "aresample=48000",
                "aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo",
                f"atrim=duration={output_duration_s:.12f}",
            ]
        audio_label = "aout"
        filter_parts.append(f"[{audio_input_label}]{','.join(audio_chain)}[{audio_label}]")

    command = [
        os.environ.get("LFO_FFMPEG") or "ffmpeg",
        "-v",
        "error",
        "-xerror",
        "-n",
        *input_args,
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[vout]",
        "-an",
        "-c:v",
        _VIDEO_CODEC,
        "-preset",
        _VIDEO_PRESET,
        "-crf",
        str(_VIDEO_CRF),
        "-bf",
        str(_VIDEO_B_FRAMES),
        "-pix_fmt",
        "yuv420p",
        "-r",
        _fps_token(fps),
        "-frames:v",
        str(frame_count),
        "-movflags",
        "+faststart",
        str(video_temp),
    ]
    if audio_temp is not None and audio_label is not None:
        command += [
            "-map",
            f"[{audio_label}]",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-f",
            "wav",
            str(audio_temp),
        ]
    _run(command, stage=f"镜头 {index} 分段编码", timeout_s=timeout_s)
    actual_frames, _ = _stream_count(video_temp, "video")
    if actual_frames != frame_count:
        raise MVRenderError(
            f"源区间只能产生 {actual_frames} 帧，计划要求 {frame_count} 帧；未进行冻结补帧",
            stage=f"镜头 {index} 帧数核验",
            command=command,
        )
    metadata = probe(video_temp)
    if metadata.get("width") != width or metadata.get("height") != height:
        raise MVRenderError(
            "分段输出尺寸与计划不符",
            stage=f"镜头 {index} 规格核验",
            command=command,
        )
    if audio_temp is not None:
        audio = probe_audio(audio_temp)
        if abs(audio["duration_ms"] - round(output_duration_s * 1000)) > max(80, round(2000 / fps)):
            raise MVRenderError(
                "原始音轨分段时长与画面帧数不符",
                stage=f"镜头 {index} 音轨核验",
                command=command,
            )
        with wave.open(str(audio_temp), "rb") as audio_stream:
            expected_samples = round(frame_count * 48000 / fps)
            if (
                audio_stream.getnchannels() != 2
                or audio_stream.getframerate() != 48000
                or audio_stream.getsampwidth() != 2
                or audio_stream.getnframes() != expected_samples
            ):
                raise MVRenderError(
                    f"音轨分段采样数为 {audio_stream.getnframes()}，计划为 {expected_samples}",
                    stage=f"镜头 {index} 音轨核验",
                    command=command,
                )


def _concat_list(paths: list[Path], list_path: Path) -> None:
    lines = []
    for path in paths:
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'\n")
    list_path.write_text("".join(lines), encoding="utf-8")


def _concat(
    paths: list[Path],
    output: Path,
    *,
    stream: str,
    timeout_s: float,
) -> None:
    with tempfile.TemporaryDirectory(prefix=".mv-concat-", dir=output.parent) as folder:
        list_path = Path(folder) / "concat.txt"
        _concat_list(paths, list_path)
        if stream == "video":
            selection = ["-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart"]
        elif stream == "audio":
            selection = ["-map", "0:a:0", "-vn", "-c:a", "copy"]
        else:
            raise ValueError(f"不支持的连接流：{stream}")
        command = [
            os.environ.get("LFO_FFMPEG") or "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-n",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            *selection,
            str(output),
        ]
        _run(
            command,
            stage=f"连接{('画面' if stream == 'video' else '原始音轨')}分段",
            timeout_s=timeout_s,
        )


def _concat_pcm_audio(paths: list[Path], output: Path) -> None:
    """Concatenate validated, identical PCM WAV segments without container timestamps."""
    if not paths:
        raise ValueError("没有可连接的原始音轨分段")
    try:
        with wave.open(str(output), "wb") as destination:
            destination.setnchannels(2)
            destination.setsampwidth(2)
            destination.setframerate(48000)
            for index, path in enumerate(paths, start=1):
                with wave.open(str(path), "rb") as source:
                    if (
                        source.getnchannels() != 2
                        or source.getsampwidth() != 2
                        or source.getframerate() != 48000
                    ):
                        raise ValueError(f"音轨分段 {index} 的 PCM 规格不一致：{path}")
                    destination.writeframes(source.readframes(source.getnframes()))
    except (OSError, wave.Error) as exc:
        output.unlink(missing_ok=True)
        raise MVRenderError(
            "无法连接 PCM 原音分段", stage="原生音轨连接", diagnostic=str(exc)
        ) from exc


def render_visual_segments(
    items: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    fps: float,
    cache_dir: Path,
    work_dir: Path | None = None,
    include_native_audio: bool = False,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """Render a contiguous visual timeline into reusable, verified segments.

    Each item has ``kind`` (video, image, or placeholder), timeline_start_ms,
    duration_ms, and, for media items, an absolute path and SHA-256. Video items
    also provide source_in_ms/source_out_ms. Placeholder labels are descriptive
    only and never imply a generated video run.
    """
    if not items:
        raise ValueError("MV 画面时间线不能为空")
    if width < 64 or height < 64 or width % 2 or height % 2 or not 1 <= fps <= 120:
        raise ValueError("MV 输出尺寸或帧率无效")
    durations: list[int] = []
    expected_start = 0
    normalized: list[dict[str, Any]] = []
    verified_digests: dict[Path, str] = {}
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict) or raw.get("kind") not in {"video", "image", "placeholder"}:
            raise ValueError(f"MV 镜头 {index} 类型无效")
        start = raw.get("timeline_start_ms")
        duration = raw.get("duration_ms")
        if isinstance(start, bool) or not isinstance(start, int) or start != expected_start:
            raise ValueError("MV 画面时间线有空洞、重叠或不连续")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            raise ValueError(f"MV 镜头 {index} 时长无效")
        item = dict(raw)
        item["kind"] = raw["kind"]
        if item["kind"] == "placeholder":
            if not isinstance(item.get("label"), str) or not item["label"].strip():
                raise ValueError(f"MV 占位镜头 {index} 必须写明待生成内容")
            item["sha256"] = None
        else:
            path_value, digest = item.get("path"), item.get("sha256")
            if not isinstance(path_value, str) or not Path(path_value).is_absolute():
                raise ValueError(f"MV 镜头 {index} 媒体路径必须为绝对路径")
            source_path = Path(path_value).resolve(strict=True)
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"MV 镜头 {index} 媒体 SHA-256 不匹配")
            if source_path not in verified_digests:
                verified_digests[source_path] = _digest(source_path)
            if verified_digests[source_path] != digest:
                raise ValueError(f"MV 镜头 {index} 媒体 SHA-256 不匹配")
            item["path"] = str(source_path)
            if item["kind"] == "video":
                source_in = item.get("source_in_ms")
                source_out = item.get("source_out_ms")
                if (
                    isinstance(source_in, bool)
                    or not isinstance(source_in, int)
                    or isinstance(source_out, bool)
                    or not isinstance(source_out, int)
                    or source_in < 0
                    or source_out <= source_in
                    or source_out - source_in != duration
                ):
                    raise ValueError(f"MV 视频镜头 {index} 的素材区间须与成片时长一致")
            elif "source_in_ms" in item or "source_out_ms" in item:
                raise ValueError(f"MV 静帧镜头 {index} 不应带视频裁切区间")
        item["timeline_start_ms"] = start
        item["duration_ms"] = duration
        normalized.append(item)
        durations.append(duration)
        expected_start += duration
    spans = frame_schedule(durations, fps)
    metadata_by_source: dict[tuple[str, str], dict[str, Any]] = {}
    metadata = []
    for index, item in enumerate(normalized, start=1):
        identity = (item["kind"], item.get("path", ""))
        if identity not in metadata_by_source:
            metadata_by_source[identity] = _source_metadata(item, index=index)
        metadata.append(metadata_by_source[identity])
    has_native_audio = include_native_audio and any(item["has_audio"] for item in metadata)
    root = Path(cache_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    working = Path(work_dir).resolve() if work_dir is not None else root
    working.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    entries = _manifest_load(manifest_path)
    segment_video_paths: list[Path] = []
    segment_audio_paths: list[Path] = []
    cache_hits = 0
    cache_rebuilt: list[dict[str, Any]] = []
    receipt_segments: list[dict[str, Any]] = []
    for index, (item, source, span) in enumerate(
        zip(normalized, metadata, spans, strict=True), start=1
    ):
        source_start_frame, source_end_frame, applied_in_ms = _source_frame_range(
            item, source["fps"]
        )
        key = _cache_key(
            item,
            source_fps=source["fps"],
            source_audio=source["has_audio"],
            span=span,
            width=width,
            height=height,
            fps=fps,
            include_native_audio=has_native_audio,
        )
        video_path = root / f"segment-{key}.mp4"
        audio_path = root / f"segment-{key}.wav" if has_native_audio else None
        valid, reason = _cache_valid(
            video_path,
            audio_path,
            entries.get(key),
            expected_frames=span.frame_count,
            width=width,
            height=height,
            fps=fps,
            expected_audio_ms=round(span.frame_count * 1000 / fps),
        )
        if valid:
            cache_hits += 1
        else:
            if reason and (video_path.exists() or (audio_path is not None and audio_path.exists())):
                cache_rebuilt.append({"segment_index": index, "key": key, "reason": reason})
            video_temp = root / f".segment-{key}.{uuid4().hex}.tmp.mp4"
            audio_temp = root / f".segment-{key}.{uuid4().hex}.tmp.wav" if audio_path else None
            try:
                _render_segment(
                    item,
                    source,
                    span,
                    video_temp,
                    audio_temp,
                    width=width,
                    height=height,
                    fps=fps,
                    source_frame_start=source_start_frame,
                    source_frame_end=source_end_frame,
                    applied_source_in_ms=applied_in_ms,
                    timeout_s=timeout_s,
                    index=index,
                )
                os.replace(video_temp, video_path)
                if audio_temp is not None and audio_path is not None:
                    os.replace(audio_temp, audio_path)
                entry = {
                    "video_sha256": _digest(video_path),
                    "audio_sha256": _digest(audio_path) if audio_path is not None else None,
                    "frame_count": span.frame_count,
                    "width": width,
                    "height": height,
                    "fps": fps,
                }
                entries[key] = entry
                _manifest_save(manifest_path, entries)
            finally:
                video_temp.unlink(missing_ok=True)
                if audio_temp is not None:
                    audio_temp.unlink(missing_ok=True)
        segment_video_paths.append(video_path)
        if audio_path is not None:
            segment_audio_paths.append(audio_path)
        receipt_segments.append(
            {
                "kind": item["kind"],
                "source_sha256": item.get("sha256"),
                "source_in_ms": item.get("source_in_ms"),
                "source_out_ms": item.get("source_out_ms"),
                "source_fps": source["fps"],
                "source_trim_in_ms": applied_in_ms,
                "source_frame_start": source_start_frame if item["kind"] == "video" else None,
                "source_frame_end": source_end_frame if item["kind"] == "video" else None,
                "output_start_frame": span.start_frame,
                "output_end_frame": span.end_frame,
                "output_frame_count": span.frame_count,
                "output_start_ms": round(span.start_frame * 1000 / fps),
                "output_end_ms": round(span.end_frame * 1000 / fps),
                "cache_key": key,
                "cache_hit": valid,
                "label": item.get("label") if item["kind"] == "placeholder" else None,
            }
        )

    picture_path = working / f"picture-{uuid4().hex}.mp4"
    _concat(segment_video_paths, picture_path, stream="video", timeout_s=timeout_s)
    expected_frames = spans[-1].end_frame
    actual_frames, _ = _stream_count(picture_path, "video")
    if actual_frames != expected_frames:
        picture_path.unlink(missing_ok=True)
        raise MVRenderError(
            f"连接后为 {actual_frames} 帧，累计计划为 {expected_frames} 帧",
            stage="画面连接核验",
        )
    native_audio_path: Path | None = None
    if has_native_audio:
        native_audio_path = working / f"native-{uuid4().hex}.wav"
        _concat_pcm_audio(segment_audio_paths, native_audio_path)
        try:
            native_info = probe_audio(native_audio_path)
        except (MediaCommandError, ValueError) as exc:
            raise MVRenderError(
                "连接后的原生音轨不可用", stage="原生音轨连接核验", diagnostic=str(exc)
            ) from exc
        expected_audio_ms = round(expected_frames * 1000 / fps)
        if native_info["duration_ms"] < max(1, expected_audio_ms - max(80, round(2000 / fps))):
            raise MVRenderError(
                f"连接后的原生音轨为 {native_info['duration_ms']}ms，画面计划为 {expected_audio_ms}ms",
                stage="原生音轨连接核验",
            )
    return {
        "picture_path": picture_path,
        "native_audio_path": native_audio_path,
        "video_frame_count": expected_frames,
        "cache_hits": cache_hits,
        "cache_misses": len(items) - cache_hits,
        "cache_rebuilt": cache_rebuilt,
        "cache_dir": str(root),
        "segments": receipt_segments,
        "native_audio_segment_count": len(segment_audio_paths),
    }
