# ruff: noqa: RUF001 -- Chinese interface messages intentionally use Chinese punctuation.
"""Canvas-only SeedVR2 video upscaling through the shared Comfy MCP transport."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.media._ffmpeg import MediaCommandError, run_command

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-upscale-executor"
MODEL_NAME = "seedvr2_3b_int8_convrot.safetensors"
VAE_NAME = "seedvr2_ema_vae_fp16.safetensors"
MAX_DURATION_SECONDS = 15.0
MAX_WIDTH = 1920
MAX_HEIGHT = 1080


def probe_video(path: Path) -> dict[str, Any]:
    """Read stream metadata and count video frames without trusting the file suffix."""
    source = path.resolve(strict=True)
    command = [
        os.environ.get("LFO_FFPROBE") or "ffprobe",
        "-v", "error", "-count_frames",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration",
        "-of", "json", str(source),
    ]
    try:
        result = run_command(command, timeout_s=120)
        payload = json.loads(result.stdout)
    except (MediaCommandError, ValueError) as exc:
        raise ValueError(f"无法读取视频素材：{source.name}") from exc
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise ValueError("ffprobe 没有返回视频流信息")
    video_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    if len(video_streams) != 1:
        raise ValueError("超分输入必须包含且仅包含一条视频流")
    stream = video_streams[0]
    width, height = stream.get("width"), stream.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 1:
        raise ValueError("视频尺寸无效")
    fps = _parse_rate(stream.get("avg_frame_rate")) or _parse_rate(stream.get("r_frame_rate"))
    nominal_fps = _parse_rate(stream.get("r_frame_rate"))
    if not fps or not math.isfinite(fps) or fps <= 0:
        raise ValueError("视频帧率无效")
    if nominal_fps and abs(fps - nominal_fps) > max(0.01, nominal_fps * 0.0005):
        raise ValueError("当前超分切片要求恒定帧率视频")
    raw_frames = stream.get("nb_read_frames")
    frame_count = int(raw_frames) if isinstance(raw_frames, str) and raw_frames.isdigit() else None
    duration = _positive_float(stream.get("duration"))
    if duration is None:
        fmt = payload.get("format")
        duration = _positive_float(fmt.get("duration")) if isinstance(fmt, dict) else None
    if frame_count is None:
        if duration is None:
            raise ValueError("无法确认源视频的总帧数")
        estimated = duration * fps
        frame_count = round(estimated)
        if frame_count < 1 or abs(estimated - frame_count) > 0.05:
            raise ValueError("无法可靠地按帧裁切该视频")
    if frame_count < 1:
        raise ValueError("源视频不含有效画面帧")
    return {
        "path": str(source),
        "codec": stream.get("codec_name"),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": frame_count / fps,
        "has_audio": any(isinstance(item, dict) and item.get("codec_type") == "audio" for item in streams),
    }


def _parse_rate(value: Any) -> float | None:
    if not isinstance(value, str) or not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        den = float(denominator)
        rate = float(numerator) / den if den else 0.0
    except (ValueError, ZeroDivisionError):
        return None
    return rate if math.isfinite(rate) and rate > 0 else None


def _positive_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def normalize_snapshot(snapshot: dict[str, Any], *, probe_fn=None) -> dict[str, Any]:
    """Validate one frozen request and resolve its bounded source-frame interval."""
    if not isinstance(snapshot, dict):
        raise ValueError("超分运行快照必须是对象")
    if (snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model"), snapshot.get("mode")) != (
        "video", "comfy-upscale", "seedvr2-3b-int8", "upscale"
    ):
        raise ValueError("不是已选择 SeedVR2 3B INT8 的画布超分任务")
    if not isinstance(snapshot.get("parameters"), dict) or not isinstance(snapshot.get("inputs"), dict):
        raise ValueError("超分参数与输入必须是对象")
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    validate_input_contract(snapshot, capability)
    request_id = snapshot.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("超分任务缺少画布 request_id")
    refs = snapshot["inputs"].get("reference_videos")
    if not isinstance(refs, list) or len(refs) != 1:
        raise ValueError("超分任务必须且只能连接一个 reference_video")
    reference = refs[0]
    if not isinstance(reference, dict) or reference.get("kind") != "video" or not isinstance(reference.get("path"), str):
        raise ValueError("超分参考素材必须是带实际路径的视频")
    source_path = Path(reference["path"]).resolve(strict=True)
    if not source_path.is_file():
        raise ValueError("超分源素材不是普通文件")
    probe_fn = probe_fn or probe_video
    source = probe_fn(source_path)
    params = snapshot["parameters"]
    start_frame = _strict_int(_default_if_unset(params.get("start_frame"), 0), "start_frame", minimum=0)
    if start_frame >= source["frame_count"]:
        raise ValueError("start_frame 已超出源视频范围")
    raw_count = params.get("frame_count")
    frame_count = source["frame_count"] - start_frame if raw_count in (None, "") else _strict_int(raw_count, "frame_count", minimum=1)
    if start_frame + frame_count > source["frame_count"]:
        raise ValueError("start_frame + frame_count 超出源视频范围")
    duration = frame_count / source["fps"]
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(f"单次超分最长支持 {MAX_DURATION_SECONDS:g} 秒；请在工作流内裁短片段")

    width = _strict_int(_default_if_unset(params.get("target_width"), 1920), "target_width", minimum=2)
    height = _strict_int(_default_if_unset(params.get("target_height"), 1066), "target_height", minimum=2)
    if width > MAX_WIDTH or height > MAX_HEIGHT or width % 2 or height % 2:
        raise ValueError(f"目标尺寸须为偶数且不超过 {MAX_WIDTH}×{MAX_HEIGHT}")
    source_ratio = source["width"] / source["height"]
    target_ratio = width / height
    if abs(target_ratio / source_ratio - 1.0) > 0.002:
        raise ValueError("目标尺寸需保持源视频画幅比例；请在后期补边")
    if width < source["width"] or height < source["height"]:
        raise ValueError("目标尺寸必须大于或等于源视频尺寸")

    chunk_mode = _default_if_unset(params.get("chunk_mode"), "auto")
    if chunk_mode not in {"auto", "manual"}:
        raise ValueError("chunk_mode 只支持 auto 或 manual")
    raw_chunk_frames = params.get("temporal_chunk_frames")
    chunk_frames = _strict_int(9 if raw_chunk_frames in (None, "") else raw_chunk_frames,
                               "temporal_chunk_frames", minimum=9)
    if chunk_mode == "manual" and chunk_frames != 9:
        raise ValueError("为控制显存，manual temporal chunk 目前固定为 9 个像素帧")
    if chunk_mode == "auto" and params.get("temporal_chunk_frames") not in (None, "", 9):
        raise ValueError("auto 模式不接受 temporal_chunk_frames 覆盖")

    prefix = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:24]
    try:
        with source_path.open("rb") as stream:
            source_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise ValueError("无法计算超分源素材校验值") from exc
    return {
        "request_id": request_id,
        "source": {**source, "sha256": source_sha256},
        "start_frame": start_frame,
        "frame_count": frame_count,
        "start_time": start_frame / source["fps"],
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "chunk_mode": chunk_mode,
        "temporal_chunk_frames": chunk_frames if chunk_mode == "manual" else None,
        "seed": int.from_bytes(hashlib.sha256(request_id.encode("utf-8")).digest()[:8], "big") % (2**53),
        "filename_prefix": f"canvas/upscale/{prefix}/upscaled",
    }


def _strict_int(value: Any, name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or value < minimum:
        raise ValueError(f"{name} 必须是大于或等于 {minimum} 的整数")
    return int(value)


def _default_if_unset(value: Any, default: Any) -> Any:
    return default if value is None or value == "" else value


def prepare_workflow(snapshot: dict[str, Any], upload_token: str, *, probe_fn=None) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = normalize_snapshot(snapshot, probe_fn=probe_fn)
    workflow: dict[str, Any] = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": upload_token}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        "3": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL_NAME, "weight_dtype": "default"}},
        "4": {"class_type": "CanvasSeedVR2BoundedUpscale", "inputs": {
            "video": ["1", 0], "vae": ["2", 0], "model": ["3", 0],
            "start_frame": normalized["start_frame"], "frame_count": normalized["frame_count"],
            "target_width": normalized["width"], "target_height": normalized["height"],
            "seed": normalized["seed"], "chunking_mode": normalized["chunk_mode"],
        }},
        "16": {"class_type": "SaveVideo", "inputs": {
            "video": ["4", 0], "filename_prefix": normalized["filename_prefix"],
            "format": "mp4", "format.codec": "h264",
            "format.codec.encoding": "auto",
        }},
    }
    if normalized["chunk_mode"] == "manual":
        workflow["4"]["inputs"]["chunking_mode.frames_per_chunk"] = normalized["temporal_chunk_frames"]
    return workflow, normalized


def materialize_video(result: transport.ComfyResult, output_dir: Path, normalized: dict[str, Any], *, probe_fn=None) -> dict[str, Any]:
    probe_fn = probe_fn or probe_video
    refs = [ref for ref in result.outputs
            if ref.file_type in {"output", "absolute"} and Path(ref.filename).suffix.lower() == ".mp4"]
    if not refs:
        raise ValueError("SeedVR2 没有返回 MP4 视频")
    expected = normalized
    explicit = [ref for ref in refs if ref.node_id == "16"]
    if len(explicit) > 1:
        raise ValueError("SeedVR2 的 SaveVideo 节点返回多个 MP4 视频")
    if explicit:
        selected = explicit[0]
        selected_source = Path(selected.filename).resolve(strict=True)
        metadata = probe_fn(selected_source)
        _validate_output_metadata(metadata, expected)
    else:
        matches: list[tuple[transport.OutputRef, dict[str, Any]]] = []
        for ref in refs:
            try:
                candidate_path = Path(ref.filename).resolve(strict=True)
                candidate_metadata = probe_fn(candidate_path)
            except Exception:
                # Fetch APIs may flatten input previews and outputs into the same
                # file category. Ignore a non-decodable preview while checking the
                # frozen output contract against every usable MP4.
                continue
            if _matches_output_metadata(candidate_metadata, expected):
                matches.append((ref, candidate_metadata))
        if len(matches) != 1:
            if not matches:
                raise ValueError("未找到与目标尺寸、帧数、帧率和音轨状态匹配的超分 MP4")
            raise ValueError("多个 MP4 均符合超分输出规格，拒绝猜测采用项")
        selected, metadata = matches[0]
        selected_source = Path(selected.filename).resolve(strict=True)

    target = output_dir / "upscaled.mp4"
    if target.exists():
        raise ValueError("超分交付文件已存在，拒绝覆盖")
    temporary = output_dir / ".upscaled-candidate.mp4"
    if temporary.exists():
        raise ValueError("超分临时候选已存在，拒绝覆盖")
    try:
        shutil.copyfile(selected_source, temporary)
        decode = subprocess.run(
            [os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-xerror", "-i", str(temporary), "-f", "null", "-"],
            capture_output=True, timeout=600, check=False,
        )
        if decode.returncode:
            raise ValueError("超分输出无法完整解码")
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    metadata.update(sha256=digest, selected_start_frame=expected["start_frame"],
                    selected_frame_count=expected["frame_count"],
                    model="SeedVR2 3B INT8", quality_status="INCONCLUSIVE")
    return {"path": str(target.resolve()), "kind": "video", "name": target.name, "metadata": metadata}


def _matches_output_metadata(metadata: dict[str, Any], expected: dict[str, Any]) -> bool:
    try:
        _validate_output_metadata(metadata, expected)
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _validate_output_metadata(metadata: dict[str, Any], expected: dict[str, Any]) -> None:
    if (metadata["width"], metadata["height"]) != (expected["width"], expected["height"]):
        raise ValueError("超分输出尺寸与请求不符")
    if metadata["frame_count"] != expected["frame_count"]:
        raise ValueError("超分输出帧数与所选源区间不符")
    if abs(metadata["fps"] - expected["source"]["fps"]) > max(0.01, expected["source"]["fps"] * 0.0005):
        raise ValueError("超分输出帧率与源视频不符")
    if metadata["has_audio"] != expected["source"]["has_audio"]:
        raise ValueError("超分输出音轨存在状态与源视频不符")


def execute_snapshot(snapshot: dict[str, Any], output_dir: Path, config: transport.RuntimeConfig, *, emit=None) -> dict[str, Any]:
    emit = emit or (lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        emit({"stage": stage})
        refs = snapshot.get("inputs", {}).get("reference_videos", [])
        normalized = normalize_snapshot(snapshot)
        from lfo.comfy.admission import VideoSubmissionGuard

        output_dir.mkdir(parents=True, exist_ok=True)
        with VideoSubmissionGuard(config.base_url, request_id=normalized["request_id"]) as guard, transport.ready_session(config) as session:
            workflow_path = output_dir / "workflow.json"
            conditions_path = output_dir / "conditions.json"
            if workflow_path.exists() or conditions_path.exists():
                raise ValueError("本次请求已有冻结工作流或条件记录，禁止重复提交")
            emit({"stage": "upload"})
            upload_token = transport.upload_input(Path(refs[0]["path"]).resolve(), session)
            workflow, normalized = prepare_workflow(snapshot, upload_token)
            if MODEL_NAME not in {Path(name).name for name in transport.model_files(session, "diffusion_models")}:
                raise ValueError(f"SeedVR2 模型未安装：{MODEL_NAME}")
            if VAE_NAME not in {Path(name).name for name in transport.model_files(session, "vae")}:
                raise ValueError(f"SeedVR2 VAE 未安装：{VAE_NAME}")
            workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
            conditions = {key: value for key, value in normalized.items() if key != "source"}
            conditions["source"] = {key: value for key, value in normalized["source"].items() if key != "path"}
            conditions["source_name"] = Path(normalized["source"]["path"]).name
            conditions_path.write_text(json.dumps(conditions, ensure_ascii=False, indent=2), encoding="utf-8")
            transport.preflight_workflow(workflow, workflow_path, session)
            stage = "submit"
            emit({"stage": stage})
            result = transport.run_workflow(workflow_path, output_dir, config, session, guard=guard, emit=emit)
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        output = materialize_video(result, output_dir, normalized)
        receipt = {"kind": "seedvr2-upscale-delivery.v1", "created_at": datetime.now(UTC).isoformat(),
                   "provider_task_id": result.provider_task_id, "config": {key: value for key, value in normalized.items() if key != "source"},
                   "source": {key: value for key, value in normalized["source"].items() if key != "path"}, "outputs": [output]}
        (output_dir / "delivery.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "succeeded", "stage": "media_validation", "outputs": [output], "provider_task_id": result.provider_task_id}
    except Exception as exc:
        if not isinstance(exc, transport.ExecutorError):
            exc = transport.ExecutorError(str(exc), status="unknown" if stage == "submit" and result is None else "failed")
        exc.stage = stage
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Internal Canvas SeedVR2 upscaling worker")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = execute_snapshot(snapshot, args.output_dir, transport.load_runtime_config())
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "status": getattr(exc, "status", "failed"),
                          "stage": getattr(exc, "stage", "input_validation"),
                          "provider_task_id": getattr(exc, "provider_task_id", None)}, ensure_ascii=False), flush=True)
        return 1
