# ruff: noqa: RUF001 -- Chinese interface messages intentionally use Chinese punctuation.
from __future__ import annotations

import gc
import logging
import shutil
import tempfile
import weakref
from fractions import Fraction
from pathlib import Path

import av
import comfy.model_management
import folder_paths
import nodes
import numpy as np
import torch
from comfy_api.latest import InputImpl, Types, io
from comfy_api.latest._input_impl.video_types import BT709_NCL, set_video_color_properties
from comfy_extras.nodes_post_processing import ResizeImageMaskNode
from comfy_extras.nodes_seedvr import (
    SeedVR2Conditioning,
    SeedVR2PostProcessing,
    SeedVR2Preprocess,
    SeedVR2TemporalChunk,
    SeedVR2TemporalMerge,
)

from .node_compat import node_output_value, video_frame_count, video_frame_sequence
from .window_plan import plan_windows

CORE_FRAMES = 16
CONTEXT_FRAMES = 4
MAX_DURATION_SECONDS = 15.0
VAE_TILE_SIZE = 512
VAE_TILE_OVERLAP = 128
VAE_TEMPORAL_SIZE = 16
VAE_TEMPORAL_OVERLAP = 4
MODEL_CHUNK_OVERLAP = 1
OUTPUT_CRF = 18


def _resize(images: torch.Tensor, width: int, height: int) -> torch.Tensor:
    result = ResizeImageMaskNode.execute(
        images,
        "lanczos",
        {"resize_type": "scale dimensions", "width": width, "height": height, "crop": "disabled"},
    )
    return node_output_value(result)


def _audio_window(video, start_time: float, duration: float) -> dict | None:
    """Decode only the selected audio interval; never materialize source video frames."""
    source = video.get_stream_source()
    if hasattr(source, "seek"):
        source.seek(0)
    with av.open(source, mode="r") as container:
        audio_stream = next((stream for stream in container.streams if stream.type == "audio"), None)
        if audio_stream is None:
            return None
        sample_rate = int(audio_stream.rate or audio_stream.codec_context.sample_rate or 0)
        if sample_rate < 1:
            raise ValueError("音轨缺少有效采样率，无法保留原音频")
        channels = int(audio_stream.codec_context.channels or len(audio_stream.layout.channels))
        if channels not in {1, 2, 6}:
            raise ValueError(f"暂不支持 {channels} 声道的超分伴音回封")
        layout = {1: "mono", 2: "stereo", 6: "5.1"}[channels]
        resampler = av.AudioResampler(format="fltp", layout=layout, rate=sample_rate)
        start_sample = round(start_time * sample_rate)
        end_sample = start_sample + round(duration * sample_rate)
        waveform = np.zeros((channels, end_sample - start_sample), dtype=np.float32)
        cursor_seconds = 0.0

        if start_time > 0 and audio_stream.time_base:
            container.seek(
                int(start_time / float(audio_stream.time_base)),
                stream=audio_stream,
                backward=True,
            )

        def copy_audio_frame(frame) -> bool:
            nonlocal cursor_seconds
            if frame.pts is not None and frame.time_base is not None:
                frame_start = float(frame.pts * frame.time_base)
            else:
                frame_start = cursor_seconds
            frame_array = frame.to_ndarray()
            if frame_array.ndim == 1:
                frame_array = frame_array.reshape(1, -1)
            frame_start_sample = round(frame_start * sample_rate)
            frame_end_sample = frame_start_sample + frame_array.shape[-1]
            source_start = max(0, start_sample - frame_start_sample)
            source_end = min(frame_array.shape[-1], end_sample - frame_start_sample)
            if source_end > source_start:
                target_start = max(0, frame_start_sample - start_sample)
                target_end = min(waveform.shape[-1], target_start + source_end - source_start)
                waveform[:, target_start:target_end] = frame_array[:, source_start:source_start + target_end - target_start]
            cursor_seconds = frame_end_sample / sample_rate
            return frame_start_sample >= end_sample

        for source_frame in container.decode(audio_stream):
            converted = resampler.resample(source_frame)
            if not isinstance(converted, list):
                converted = [converted] if converted is not None else []
            if any(copy_audio_frame(frame) for frame in converted):
                break
        else:
            for frame in resampler.resample(None):
                copy_audio_frame(frame)

    return {"waveform": torch.from_numpy(waveform).unsqueeze(0), "sample_rate": sample_rate}


def _open_segment(path: Path, fps: Fraction, width: int, height: int):
    container = av.open(str(path), mode="w", format="mp4")
    try:
        stream = container.add_stream("h264", rate=fps)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"
        # Each bounded window is independently encoded and then packet-concatenated
        # by Comfy's VideoFromList. B-frames add per-segment decode reordering that
        # can break DTS continuity at a one-frame final segment.
        stream.options = {"crf": str(OUTPUT_CRF), "preset": "medium", "bf": "0"}
        set_video_color_properties(stream.codec_context, "sRGB")
        return container, stream
    except Exception:
        container.close()
        path.unlink(missing_ok=True)
        raise


def _write_rgb_frame(container, stream, image: torch.Tensor) -> None:
    image = image[..., :3].contiguous()
    rgb = (image.clamp(0.0, 1.0) * 255.0).round().to(device="cpu", dtype=torch.uint8).numpy()
    frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
    frame = frame.reformat(format="yuv420p", dst_colorspace=BT709_NCL)
    set_video_color_properties(frame, "sRGB")
    for packet in stream.encode(frame):
        container.mux(packet)


def _finish_segment(container, stream) -> None:
    for packet in stream.encode(None):
        container.mux(packet)


def _frame_rate(video) -> Fraction:
    fps = Fraction(video.get_frame_rate())
    if fps <= 0:
        raise ValueError("超分源视频帧率无效")
    return fps


def _cuda_peak_mib() -> float | None:
    if not torch.cuda.is_available():
        return None
    try:
        device = comfy.model_management.get_torch_device()
        return torch.cuda.max_memory_allocated(device) / (1024 ** 2)
    except Exception:
        return None


def _reset_cuda_peak() -> None:
    if not torch.cuda.is_available():
        return
    try:
        torch.cuda.reset_peak_memory_stats(comfy.model_management.get_torch_device())
    except Exception:
        logging.exception("Could not reset CUDA peak-memory counter")


def _upscale_window(
    lowres_images: torch.Tensor,
    *,
    model,
    vae,
    width: int,
    height: int,
    seed: int,
    chunking_mode: dict,
):
    """Run the existing SeedVR2 graph stages for one bounded pixel window."""
    if lowres_images.ndim != 4 or lowres_images.shape[0] < 1:
        raise ValueError(f"超分窗口必须为有效的 IMAGE 帧序列，实际形状 {tuple(lowres_images.shape)}")
    resized = _resize(lowres_images[..., :3], width, height)
    padded = node_output_value(SeedVR2Preprocess.execute(resized))
    expected_padded_frames = lowres_images.shape[0] + (-(lowres_images.shape[0] - 1) % 4)
    padded_frames = video_frame_count(padded, "SeedVR2 预处理输出")
    if padded_frames != expected_padded_frames:
        raise ValueError(f"SeedVR2 预处理应补齐至 4n+1 帧，实际得到 {padded_frames}")
    latent = node_output_value(nodes.VAEEncodeTiled().encode(
        vae,
        padded,
        tile_size=VAE_TILE_SIZE,
        overlap=VAE_TILE_OVERLAP,
        temporal_size=VAE_TEMPORAL_SIZE,
        temporal_overlap=VAE_TEMPORAL_OVERLAP,
    ))
    del padded, resized
    comfy.model_management.soft_empty_cache()

    chunk_output = SeedVR2TemporalChunk.execute(
        latent,
        temporal_overlap=MODEL_CHUNK_OVERLAP,
        chunking_mode=chunking_mode,
    )
    latent_chunks, effective_overlap = chunk_output.result
    sampled_chunks = []
    sampler = nodes.KSampler()
    for latent_chunk in latent_chunks:
        positive, negative = SeedVR2Conditioning.execute(model, latent_chunk).result
        sampled = sampler.sample(
            model=model,
            seed=seed,
            steps=1,
            cfg=1.0,
            sampler_name="euler",
            scheduler="simple",
            positive=positive,
            negative=negative,
            latent_image=latent_chunk,
            denoise=1.0,
        )
        sampled_chunks.append(sampled[0])
        del positive, negative, sampled, latent_chunk
        comfy.model_management.soft_empty_cache()

    merged = node_output_value(SeedVR2TemporalMerge.execute(sampled_chunks, [effective_overlap]))
    decoded = node_output_value(nodes.VAEDecodeTiled().decode(
        vae,
        merged,
        tile_size=VAE_TILE_SIZE,
        overlap=VAE_TILE_OVERLAP,
        temporal_size=VAE_TEMPORAL_SIZE,
        temporal_overlap=VAE_TEMPORAL_OVERLAP,
    ))
    decoded_frames = video_frame_count(decoded, "SeedVR2 解码输出")
    decoded = video_frame_sequence(decoded, "SeedVR2 解码输出")
    if decoded_frames < lowres_images.shape[0]:
        raise ValueError(
            f"SeedVR2 解码帧数不足：输入窗口 {lowres_images.shape[0]} 帧，输出形状 {tuple(decoded.shape)}"
        )
    del latent, latent_chunks, sampled_chunks, merged
    return decoded


class CanvasSeedVR2BoundedUpscale(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="CanvasSeedVR2BoundedUpscale",
            display_name="Canvas SeedVR2 Bounded Video Upscale",
            category="video/upscale",
            description=(
                "Canvas-only SeedVR2 upscaling with a 16-frame output core and 4-frame context on each side. "
                "Each window reads at most 24 frames, pads to at most 25, then is color-corrected and H.264-encoded "
                "before its pixel tensors are released."
            ),
            inputs=[
                io.Video.Input("video"),
                io.Model.Input("model"),
                io.Vae.Input("vae"),
                io.Int.Input("start_frame", default=0, min=0, max=100000000),
                io.Int.Input("frame_count", default=120, min=1, max=360),
                io.Int.Input("target_width", default=1920, min=2, max=4096, step=2),
                io.Int.Input("target_height", default=1066, min=2, max=4096, step=2),
                io.Int.Input("seed", default=0, min=0, max=0x1FFFFFFFFFFFFF),
                io.DynamicCombo.Input(
                    "chunking_mode",
                    options=[
                        io.DynamicCombo.Option("auto", []),
                        io.DynamicCombo.Option("manual", [
                            io.Int.Input("frames_per_chunk", default=9, min=9, max=9, step=4),
                        ]),
                    ],
                ),
            ],
            outputs=[io.Video.Output(display_name="VIDEO")],
        )

    @classmethod
    def execute(
        cls,
        video,
        model,
        vae,
        start_frame: int,
        frame_count: int,
        target_width: int,
        target_height: int,
        seed: int,
        chunking_mode: dict,
    ) -> io.NodeOutput:
        fps = _frame_rate(video)
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (start_frame, frame_count, target_width, target_height, seed)):
            raise ValueError("SeedVR2 的帧范围、尺寸和 seed 必须是整数")
        if start_frame < 0 or frame_count < 1 or start_frame + frame_count > video.get_frame_count():
            raise ValueError("SeedVR2 请求帧范围超出源视频")
        if frame_count / float(fps) > MAX_DURATION_SECONDS:
            raise ValueError(f"单次 SeedVR2 超分范围不能超过 {MAX_DURATION_SECONDS:g} 秒")
        if min(target_width, target_height) < 2 or target_width % 2 or target_height % 2:
            raise ValueError("SeedVR2 输出尺寸必须为正偶数")
        if target_width > 4096 or target_height > 4096:
            raise ValueError("SeedVR2 输出尺寸超过上限")
        mode = chunking_mode.get("chunking_mode") if isinstance(chunking_mode, dict) else None
        if mode == "auto":
            sampler_chunks = {"chunking_mode": "auto"}
        elif mode == "manual" and chunking_mode.get("frames_per_chunk") == 9:
            sampler_chunks = {"chunking_mode": "manual", "frames_per_chunk": 9}
        else:
            raise ValueError("SeedVR2 Temporal Chunk 仅支持 auto 或安全的 9 像素帧 manual")

        total_frames = video.get_frame_count()
        if start_frame + frame_count > total_frames:
            raise ValueError("SeedVR2 请求帧范围超出源视频")
        selected_start = start_frame / float(fps)
        selected_duration = frame_count / float(fps)
        selected = video.as_trimmed(selected_start, selected_duration, strict_duration=True)
        if selected is None or selected.get_frame_count() != frame_count:
            raise ValueError("SeedVR2 无法按冻结帧范围精确裁切输入")
        audio = _audio_window(video, selected_start, selected_duration)
        window_plan = plan_windows(start_frame, frame_count, CORE_FRAMES, CONTEXT_FRAMES)
        scratch = Path(tempfile.mkdtemp(prefix="canvas-seedvr2-bounded-", dir=folder_paths.get_temp_directory()))
        encoded_videos = []

        try:
            for window in window_plan:
                window_index = window["index"]
                absolute_input_start = window["source_start_frame"]
                input_start_seconds = absolute_input_start / float(fps)
                input_duration = window["source_frame_count"] / float(fps)
                source_window = video.as_trimmed(input_start_seconds, input_duration, strict_duration=True)
                if source_window is None:
                    raise ValueError(f"SeedVR2 窗口 {window_index} 无法精确裁切")
                components = source_window.get_components()
                lowres_images = components.images[..., :3]
                if lowres_images.shape[0] != window["source_frame_count"]:
                    raise ValueError(
                        f"SeedVR2 窗口 {window_index} 实际解码 {lowres_images.shape[0]} 帧，"
                        f"期望 {window['source_frame_count']} 帧"
                    )
                components.audio = None
                lowres_mib = lowres_images.numel() * lowres_images.element_size() / (1024 ** 2)
                logging.info(
                    "Canvas SeedVR2 window %d/%d: output=[%d,%d), source=[%d,%d), input=%d, padded=%d, input_pixels=%.1f MiB",
                    window_index + 1, len(window_plan), window["output_start_frame"], window["output_end_frame"],
                    window["source_start_frame"], window["source_start_frame"] + window["source_frame_count"],
                    window["source_frame_count"], window["padded_frame_count"], lowres_mib,
                )
                _reset_cuda_peak()

                decoded = _upscale_window(
                    lowres_images,
                    model=model,
                    vae=vae,
                    width=target_width,
                    height=target_height,
                    seed=seed,
                    chunking_mode=sampler_chunks,
                )
                path = scratch / f"segment-{window_index:04d}.mp4"
                container, stream = _open_segment(path, fps, target_width, target_height)
                try:
                    keep_start = window["keep_start_frame"]
                    keep_end = keep_start + window["keep_frame_count"]
                    for local_frame in range(keep_start, keep_end):
                        original_reference = _resize(
                            lowres_images[local_frame:local_frame + 1], target_width, target_height
                        )
                        corrected = SeedVR2PostProcessing.execute(
                            decoded[local_frame:local_frame + 1],
                            original_reference,
                            "lab",
                        )
                        corrected = node_output_value(corrected)
                        _write_rgb_frame(container, stream, corrected[0])
                        del original_reference, corrected
                    _finish_segment(container, stream)
                except Exception:
                    try:
                        container.close()
                    except Exception:
                        logging.exception("Could not close failed SeedVR2 segment writer")
                    raise
                else:
                    container.close()

                encoded_videos.append(InputImpl.VideoFromFile(str(path)))
                peak_mib = _cuda_peak_mib()
                logging.info(
                    "Canvas SeedVR2 window %d/%d saved %d effective frames; peak allocated CUDA=%s MiB",
                    window_index + 1, len(window_plan), window["keep_frame_count"],
                    f"{peak_mib:.1f}" if peak_mib is not None else "unavailable",
                )
                del components, lowres_images, decoded, source_window
                comfy.model_management.soft_empty_cache()
                gc.collect()

            output = InputImpl.VideoFromList(
                encoded_videos,
                complete_audio=audio,
                codec=Types.VideoCodec.H264,
            )
            weakref.finalize(output, shutil.rmtree, str(scratch), ignore_errors=True)
            return io.NodeOutput(output)
        except torch.cuda.OutOfMemoryError as exc:
            shutil.rmtree(scratch, ignore_errors=True)
            comfy.model_management.soft_empty_cache(force=True)
            raise RuntimeError(
                f"SeedVR2 bounded window OOM at {CORE_FRAMES} core + {2 * CONTEXT_FRAMES} context frames; "
                "Canvas must record the original task failed before a safer follow-up is submitted."
            ) from exc
        except MemoryError as exc:
            shutil.rmtree(scratch, ignore_errors=True)
            comfy.model_management.soft_empty_cache(force=True)
            raise RuntimeError(
                f"SeedVR2 bounded window exceeded host memory at {CORE_FRAMES} core + "
                f"{2 * CONTEXT_FRAMES} context frames; Canvas must record the original task failed "
                "before a safer follow-up is submitted."
            ) from exc
        except Exception:
            shutil.rmtree(scratch, ignore_errors=True)
            raise
