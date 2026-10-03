"""Pure frame planning for bounded SeedVR2 processing inside ComfyUI."""

from __future__ import annotations


def _integer(value: int, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def plan_windows(
    start_frame: int,
    frame_count: int,
    window_frames: int = 16,
    context_frames: int = 4,
) -> list[dict[str, int]]:
    """Partition an exact source range into unique keep ranges with context.

    Coordinates in source_* are absolute source-video frame indices.
    keep_start_frame is relative to the decoded source window; output_*
    coordinates are relative to the final selected-range video. Context never
    reads outside the selected range, and it is discarded before encoding.
    SeedVR preprocessing owns repeating tail frames to meet 4n+1 geometry.
    """
    start_frame = _integer(start_frame, "start_frame", 0)
    frame_count = _integer(frame_count, "frame_count", 1)
    window_frames = _integer(window_frames, "window_frames", 4)
    context_frames = _integer(context_frames, "context_frames", 0)
    if window_frames % 4 or window_frames > 48:
        raise ValueError("window_frames must be a multiple of 4 and <= 48")
    if context_frames % 4 or context_frames > 16:
        raise ValueError("context_frames must be a multiple of 4 and <= 16")
    if window_frames + 2 * context_frames > 56:
        raise ValueError("window_frames plus both contexts must not exceed 56 decoded frames")

    result: list[dict[str, int]] = []
    for output_start in range(0, frame_count, window_frames):
        output_end = min(output_start + window_frames, frame_count)
        read_start = max(0, output_start - context_frames)
        read_end = min(frame_count, output_end + context_frames)
        read_count = read_end - read_start
        padded_count = ((read_count - 1 + 3) // 4) * 4 + 1
        result.append({
            "index": len(result),
            "source_start_frame": start_frame + read_start,
            "source_frame_count": read_count,
            "keep_start_frame": output_start - read_start,
            "keep_frame_count": output_end - output_start,
            "output_start_frame": output_start,
            "output_end_frame": output_end,
            "padded_frame_count": padded_count,
            "padding_frames": padded_count - read_count,
        })
    return result
