"""Canvas worker implementation of the H3 single-subject and two-subject face refinement graph."""

# ruff: noqa: RUF001 -- Chinese user-facing messages intentionally use Chinese punctuation.
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.comfy.admission import VideoSubmissionGuard
from lfo.comfy.upscale import probe_video
from lfo.media._ffmpeg import run_command

CAPABILITY = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-h3-face-refine-executor/capability.json"
MODEL = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
LORA = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
MAX_WINDOW_FRAMES = 96


def _optional_int(params: Mapping[str, Any], key: str) -> int | None:
    value = params.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ValueError(f"{key} 必须是整数")
    return int(value)


def resolve_refine_window(details: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve an aligned 17k+5 working window within one continuous 24fps shot."""
    fps = float(details["fps"])
    if abs(fps - 24.0) > 0.02:
        raise ValueError("FaceRefine 当前仅支持 24 fps 恒定帧率视频")
    total = int(details["frame_count"])
    if total < 5:
        raise ValueError("FaceRefine 输入至少需要 5 帧")

    start_frame = _optional_int(params, "start_frame")
    frame_count = _optional_int(params, "frame_count")
    shot_start_param = _optional_int(params, "shot_start_frame")
    shot_end_param = _optional_int(params, "shot_end_frame")
    windowed = (
        any(item is not None for item in (start_frame, frame_count, shot_start_param, shot_end_param))
        or total > MAX_WINDOW_FRAMES
    )

    if not windowed:
        shot_start, shot_end = 0, total
        target_start, target_end = 0, total
        keep_frames = total
        work_start, work_end, work_frames = 0, total, total
        trim_offset = 0
    else:
        if total > MAX_WINDOW_FRAMES and start_frame is None and frame_count is None:
            raise ValueError(
                "超过 96 帧的长镜头请填写 start_frame 与 frame_count（单窗最多 90 帧）以在同镜头内对齐局部修脸"
            )
        shot_start = shot_start_param if shot_start_param is not None else 0
        shot_end = shot_end_param if shot_end_param is not None else total
        if not 0 <= shot_start < shot_end <= total:
            raise ValueError("shot_start_frame / shot_end_frame 超出源视频范围")
        target_start = start_frame if start_frame is not None else shot_start
        keep_frames = frame_count if frame_count is not None else (shot_end - target_start)
        target_end = target_start + keep_frames
        if keep_frames <= 0 or target_start < shot_start or target_end > shot_end:
            raise ValueError("目标修脸窗口必须在同一连续镜头 [shot_start_frame, shot_end_frame) 内")

        work_frames = 5 + 17 * max(0, math.ceil((keep_frames - 5) / 17))
        if work_frames > MAX_WINDOW_FRAMES:
            raise ValueError("对齐后的单次修脸窗口超过 96 帧上限，请缩小 frame_count（最多 90 帧）")
        if work_frames > (shot_end - shot_start):
            raise ValueError("同一连续镜头可用帧数不足以完成 17k+5 对齐（拒绝跨切点或补帧）")
        work_start = min(target_start, shot_end - work_frames)
        work_end = work_start + work_frames
        trim_offset = target_start - work_start

    anchor_frame = _optional_int(params, "anchor_frame")
    if anchor_frame is None or not work_start <= anchor_frame < work_end:
        raise ValueError(f"anchor_frame 必须落在对齐工作窗口 [{work_start}, {work_end}) 内")

    return {
        "windowed": windowed,
        "total_frames": total,
        "shot_start": shot_start,
        "shot_end": shot_end,
        "target_start": target_start,
        "target_end": target_end,
        "keep_frames": keep_frames,
        "work_start": work_start,
        "work_end": work_end,
        "work_frames": work_frames,
        "trim_offset": trim_offset,
        "anchor_frame": anchor_frame,
        "local_anchor_frame": anchor_frame - work_start,
    }


def prepare_workflow(
    source: str,
    references: list[str],
    prompt: str,
    prefix: str,
    anchor: dict[str, int],
    *,
    mode: str = "duet",
) -> dict[str, Any]:
    if mode not in {"solo", "duet"}:
        raise ValueError(f"不支持的 FaceRefine 模式：{mode}")
    if mode == "solo" and len(references) != 1:
        raise ValueError("单人修脸需要 1 张角色参考图")
    if mode == "duet" and len(references) != 2:
        raise ValueError("双人修脸需要按左右顺序连接 2 张角色参考图")

    workflow: dict[str, Any] = {}

    def add(kind: str, **inputs: Any) -> list:
        node_id = str(len(workflow) + 1)
        workflow[node_id] = {"class_type": kind, "inputs": inputs}
        return [node_id, 0]

    video = add("LoadVideo", file=source)
    frames = add("GetVideoComponents", video=video)
    vae = add("VAELoader", vae_name=VIDEO_VAE)
    audio_vae = add("VAELoader", vae_name=AUDIO_VAE)
    clip = add("CLIPLoader", clip_name=ENCODER, type="minimax", device="default")
    base_model = add("UNETLoader", unet_name=MODEL, weight_dtype="default")
    model = add("LoraLoaderModelOnly", model=base_model, lora_name=LORA, strength_model=1.0)
    sampler = add("KSamplerSelect", sampler_name="er_sde")
    sigmas = add("BasicScheduler", model=model, scheduler="simple", steps=8, denoise=0.40)
    stitched = frames

    subjects = (
        [("solo", anchor["face_x"], anchor["face_y"])]
        if mode == "solo"
        else [
            ("left", anchor["left_x"], anchor["anchor_y"]),
            ("right", anchor["right_x"], anchor.get("right_y", anchor["anchor_y"])),
        ]
    )

    for index, (label, coord_x, coord_y) in enumerate(subjects):
        reference = add("LoadImage", image=references[index])
        track, _ = add(
            "H3FaceTrackCrop", images=frames, detector="face_yolov8m.pt", confidence=0.35,
            crop_factor=3.0, canvas_width=512, canvas_height=512, canvas_mode="manual",
            smooth_window=21, size_smooth_window=51, smooth_method="gaussian", size_mode="per_frame",
            select="closest_to_xy", X=coord_x, Y=coord_y,
            frame_index=anchor["anchor_frame"], identity_track=False, cut_detection="none",
        )
        transform = [track, 1]
        condition, _ = add(
            "MiniMaxH3ReferenceToVideo", clip=clip, vae=vae, audio_vae=audio_vae,
            prompt=f"{prompt} Preserve the target person's existing gaze, expression and head motion. "
                   "<Picture 1> is the identity reference for the face being refined.",
            width=[track, 4], height=[track, 5], length=[track, 6], ref_image_size="match",
            **{"ref_images.ref_image_0": reference},
        )
        injected = add("H3InjectVideoLatent", av_latent=[condition, 1], images=[track, 0], vae=vae)
        weighted, _ = add(
            "H3PerFrameDenoise", model=model, av_latent=injected, transform=transform,
            denoise_multiplier_small_face=1.0, denoise_multiplier_large_face=0.35,
            scale_mode="absolute_px", face_px_small=30.0, face_px_large=120.0,
            gamma=1.0, smooth_frames=9,
        )
        guide = add("BasicGuider", model=[weighted, 2], conditioning=[condition, 0])
        noise = add("RandomNoise", noise_seed=42 + index)
        sample = add("SamplerCustomAdvanced", noise=noise, guider=guide, sampler=sampler,
                     sigmas=sigmas, latent_image=[weighted, 0])
        decoded = add("VAEDecode", samples=sample, vae=vae)
        stitched = add("H3FaceStitch", base_images=stitched, refined_crops=decoded, transform=transform,
                       paste_region="face_ellipse", mask_dilation=16, feather=6, colour_match=1.0,
                       blend=1.0, undetected_frames="fade_out")
        preview = add("CreateVideo", images=[track, 2], fps=24.0)
        add("SaveVideo", video=preview, filename_prefix=f"{prefix}/track-{label}",
            format="mp4", **{"format.codec": "h264", "format.codec.encoding": "auto"})

    final = add("CreateVideo", images=stitched, fps=24.0)
    add("SaveVideo", video=final, filename_prefix=f"{prefix}/refined",
        format="mp4", **{"format.codec": "h264", "format.codec.encoding": "auto"})
    return workflow


def _slice_work_window(source: Path, destination: Path, work_start: int, work_end: int) -> None:
    ffmpeg = os.environ.get("LFO_FFMPEG") or "ffmpeg"
    run_command(
        [
            ffmpeg,
            "-nostdin", "-v", "error", "-xerror", "-n",
            "-i", str(source),
            "-an",
            "-vf", f"trim=start_frame={work_start}:end_frame={work_end},setpts=PTS-STARTPTS",
            "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", "-bf", "0",
            str(destination),
        ],
        timeout_s=120,
    )


def _splice_refined_window(
    source: Path,
    refined: Path,
    target: Path,
    window: Mapping[str, Any],
) -> None:
    ffmpeg = os.environ.get("LFO_FFMPEG") or "ffmpeg"
    target_start = int(window["target_start"])
    target_end = int(window["target_end"])
    total = int(window["total_frames"])
    trim_offset = int(window["trim_offset"])
    keep_frames = int(window["keep_frames"])

    if target_start == 0 and target_end == total and trim_offset == 0 and keep_frames == int(window["work_frames"]):
        run_command(
            [
                ffmpeg, "-nostdin", "-v", "error", "-n",
                "-i", str(refined), "-i", str(source),
                "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy",
                str(target),
            ],
            timeout_s=120,
        )
        return

    filters: list[str] = []
    concat_inputs: list[str] = []
    if target_start > 0:
        filters.append(f"[0:v:0]trim=start_frame=0:end_frame={target_start},setpts=PTS-STARTPTS[pre]")
        concat_inputs.append("[pre]")
    filters.append(
        f"[1:v:0]trim=start_frame={trim_offset}:end_frame={trim_offset + keep_frames},setpts=PTS-STARTPTS[mid]"
    )
    concat_inputs.append("[mid]")
    if target_end < total:
        filters.append(f"[0:v:0]trim=start_frame={target_end}:end_frame={total},setpts=PTS-STARTPTS[post]")
        concat_inputs.append("[post]")
    filters.append("".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=1:a=0[vout]")

    run_command(
        [
            ffmpeg, "-nostdin", "-v", "error", "-xerror", "-n",
            "-i", str(source), "-i", str(refined),
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "0:a:0?",
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-bf", "0",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(target),
        ],
        timeout_s=300,
    )


def execute(snapshot: dict[str, Any], output: Path, config: transport.RuntimeConfig) -> dict:
    stage = "input_validation"
    result = None
    try:
        mode = snapshot.get("mode")
        if (snapshot.get("node_type"), snapshot.get("provider"), snapshot.get("model")) != (
            "video", "comfy-h3-face-refine", "minimax-h3-fl2va"
        ) or mode not in {"solo", "duet"}:
            raise ValueError("不是已确认的 H3 局部修脸快照")
        validate_input_contract(snapshot, json.loads(CAPABILITY.read_text(encoding="utf-8")))
        inputs = snapshot["inputs"]
        source = Path(inputs["reference_videos"][0]["path"]).resolve(strict=True)
        references = [Path(item["path"]).resolve(strict=True) for item in inputs["reference_images"]]
        details = probe_video(source)
        window = resolve_refine_window(details, snapshot["parameters"])

        params = {
            key: int(value)
            for key, value in snapshot["parameters"].items()
            if value is not None and value != ""
        }
        if mode == "solo":
            if len(references) != 1:
                raise ValueError("单人修脸需要 1 张角色定妆图")
            if not (0 <= params["face_x"] < details["width"] and 0 <= params["face_y"] < details["height"]):
                raise ValueError("目标脸坐标必须在画面尺寸范围内")
            anchor = {
                "anchor_frame": window["local_anchor_frame"],
                "face_x": params["face_x"],
                "face_y": params["face_y"],
            }
            preview_labels = ("solo",)
        else:
            if len(references) != 2 or references[0] == references[1]:
                raise ValueError("需要按画面左右顺序连接两张不同的角色定妆图")
            right_y = params.get("right_y", params["anchor_y"])
            if not (
                0 <= params["left_x"] < params["right_x"] < details["width"]
                and 0 <= params["anchor_y"] < details["height"]
                and 0 <= right_y < details["height"]
            ):
                raise ValueError("两组选脸坐标必须在画面内且左脸横坐标小于右脸")
            anchor = {
                "anchor_frame": window["local_anchor_frame"],
                "left_x": params["left_x"],
                "right_x": params["right_x"],
                "anchor_y": params["anchor_y"],
                "right_y": right_y,
            }
            preview_labels = ("left", "right")

        request_id = snapshot["request_id"]
        prefix = f"canvas/face-refine/{hashlib.sha256(request_id.encode()).hexdigest()[:20]}"
        output.mkdir(parents=True, exist_ok=True)
        workflow_path = output / "workflow.json"
        with VideoSubmissionGuard(config.base_url, request_id=request_id) as guard, transport.ready_session(config) as session:
            stage = "upload"
            emit({"stage": stage})
            if workflow_path.exists():
                raise ValueError("本次请求已有冻结工作流。禁止重复提交")
            work_input = source
            if window["windowed"] and (window["work_start"], window["work_end"]) != (0, window["total_frames"]):
                work_input = output / "window-input.mp4"
                _slice_work_window(source, work_input, window["work_start"], window["work_end"])
                sliced_info = probe_video(work_input)
                if sliced_info["frame_count"] != window["work_frames"]:
                    raise ValueError("局部修脸工作窗口裁切帧数与预期不符")
            source_token = transport.upload_input(work_input, session)
            ref_tokens = [transport.upload_input(path, session) for path in references]
            workflow = prepare_workflow(
                source_token, ref_tokens, snapshot["prompt"], prefix, anchor, mode=mode
            )
            with workflow_path.open("x", encoding="utf-8") as stream:
                json.dump(workflow, stream, ensure_ascii=False, indent=2)
            transport.preflight_workflow(workflow, workflow_path, session)
            stage = "submit"
            emit({"stage": stage})
            result = transport.run_workflow(workflow_path, output, config, session, guard=guard, emit=emit)
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        paths = collect_outputs(result.outputs, prefix, mode=mode)
        target = output / "refined.mp4"
        _splice_refined_window(source, paths["refined"], target, window)
        actual = probe_video(target)
        keys = ("width", "height", "fps", "frame_count", "has_audio")
        if any(details[key] != actual[key] for key in keys):
            raise ValueError("FaceRefine 结果的分辨率、帧率、帧数或音轨状态与原片不符")
        previews = {label: str(paths[f"track-{label}"].resolve()) for label in preview_labels}
        delivery = {
            "kind": "h3-face-refine-delivery.v1",
            "created_at": datetime.now(UTC).isoformat(),
            "mode": mode,
            "provider_task_id": result.provider_task_id,
            "window": window,
            "face_track_previews": previews,
        }
        (output / "delivery.json").write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "status": "succeeded",
            "stage": "media_validation",
            "provider_task_id": result.provider_task_id,
            "outputs": [
                {
                    "path": str(target.resolve()),
                    "kind": "video",
                    "name": target.name,
                    "metadata": {
                        "mode": mode,
                        "window": window,
                        "face_track_previews": previews,
                    },
                }
            ],
        }
    except Exception as exc:
        if not isinstance(exc, transport.ExecutorError):
            exc = transport.ExecutorError(str(exc), status="unknown" if stage == "submit" else "failed")
        exc.stage = stage
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def collect_outputs(
    outputs: tuple[transport.OutputRef, ...], prefix: str, *, mode: str = "duet"
) -> dict[str, Path]:
    """Use provider filenames, which the MCP downloader may replace locally."""
    labels = ("refined", "track-solo") if mode == "solo" else ("refined", "track-left", "track-right")
    candidates: dict[str, list[Path]] = {key: [] for key in labels}
    for ref in outputs:
        if ref.file_type != "output" or not ref.source_url:
            continue
        query = parse_qs(urlsplit(ref.source_url).query)
        folder = query.get("subfolder", [])
        names = query.get("filename", [])
        if len(folder) != 1 or folder[0].replace("\\", "/") != prefix or len(names) != 1:
            continue
        name = Path(names[0])
        if name.suffix.lower() != ".mp4":
            continue
        for label, paths in candidates.items():
            if name.name.startswith(f"{label}_"):
                paths.append(Path(ref.filename))
    for label, paths in candidates.items():
        if len(paths) != 1:
            raise ValueError(f"无法唯一定位 FaceRefine 的 {label} 输出")
    return {label: paths[0] for label, paths in candidates.items()}


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        emit(execute(snapshot, args.output_dir, transport.load_runtime_config()))
        return 0
    except Exception as exc:
        emit({"status": getattr(exc, "status", "failed"), "error": str(exc),
              "stage": getattr(exc, "stage", "input_validation"),
              "provider_task_id": getattr(exc, "provider_task_id", None)})
        return 1
