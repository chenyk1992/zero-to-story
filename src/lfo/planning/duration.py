"""Duration Planner — frame count calculation via FrameConstraints.

Uses the workflow manifest's FrameConstraints.align_frame_count() to ensure
all frame counts satisfy the H3 grid constraint (n % 17 == 5).
"""
from __future__ import annotations

import math

from lfo.core.workflow_registry import WorkflowManifest
from lfo.storyboard.storyboard import Shot


def compute_aligned_frames(
    shot: Shot,
    workflow_manifest: WorkflowManifest,
    pre_handle_ms: int = 0,
    post_handle_ms: int = 0,
) -> int:
    """Compute aligned frame count using FrameConstraints from the workflow manifest.

    Formula:
        requested_frames = ceil((desired_duration_ms + pre_handle_ms + post_handle_ms) * fps / 1000)
        aligned_frames = frame_constraints.align_frame_count(requested_frames)

    Args:
        shot: The shot (provides desired_duration_ms).
        workflow_manifest: The workflow manifest (provides frame_constraints with fps).
        pre_handle_ms: Additional frames before the shot (handle).
        post_handle_ms: Additional frames after the shot (handle).

    Returns:
        Aligned frame count satisfying the H3 grid.
    """
    fps = workflow_manifest.frame_constraints.fps
    total_ms = shot.desired_duration_ms + pre_handle_ms + post_handle_ms
    requested_frames = math.ceil(total_ms * fps / 1000)
    aligned_frames = workflow_manifest.frame_constraints.align_frame_count(requested_frames)
    return aligned_frames
