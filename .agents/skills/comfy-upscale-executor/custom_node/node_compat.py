from __future__ import annotations

from typing import Any


def node_output_value(output: Any, index: int = 0) -> Any:
    """Read either a modern Comfy NodeOutput or a legacy node tuple."""
    result = getattr(output, "result", None)
    values = result if result is not None else output
    return values[index]


def video_frame_count(images: Any, name: str) -> int:
    """Read frame count from IMAGE sequences in either T,H,W,C or B,T,H,W,C layout."""
    shape = getattr(images, "shape", None)
    if shape is None:
        raise ValueError(f"{name} must be an IMAGE tensor with a shape")
    if len(shape) == 4:
        frame_count = shape[0]
    elif len(shape) == 5:
        if shape[0] != 1:
            raise ValueError(f"{name} must contain a single video batch; got shape {tuple(shape)}")
        frame_count = shape[1]
    else:
        raise ValueError(f"{name} must use T,H,W,C or B,T,H,W,C layout; got shape {tuple(shape)}")
    if frame_count < 1:
        raise ValueError(f"{name} must contain at least one frame; got shape {tuple(shape)}")
    return int(frame_count)


def video_frame_sequence(images: Any, name: str) -> Any:
    """Normalize one video batch to Comfy's frame-major T,H,W,C layout without dropping T."""
    video_frame_count(images, name)
    if len(images.shape) == 4:
        return images
    return images.squeeze(0)
