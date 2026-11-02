"""Verify a local H3 video left behind after provider history is lost.

This verifier is deliberately read-only: it does not release admission,
change a Canvas run, or assert the provider's unknown terminal status.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _safe_component(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)[:80]


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _tool(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode:
        raise ValueError(f"media validation failed: {Path(command[0]).name}")
    return result.stdout


def verify_recovered_video(
    *,
    run: Mapping[str, Any],
    receipt: Mapping[str, Any],
    output_root: Path,
    video: Path,
    server_restarted_at: datetime,
    expected_sha256: str,
    ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    """Validate a single original output against a frozen, local R2V request.

    The caller must separately verify the old service stopped and the supplied
    restart time belongs to the live replacement at the original endpoint.
    A valid artifact is not evidence of the provider's final job status.
    """
    if run.get("status") != "unknown" or run.get("request_id") != receipt.get("request_id"):
        raise ValueError("unknown run and receipt request must match")
    task_id = run.get("provider_task_id")
    if not task_id or task_id != receipt.get("provider_task_id"):
        raise ValueError("provider task id must match the original receipt")
    snapshot = run.get("snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("provider") != "comfy":
        raise ValueError("a frozen Comfy snapshot is required")
    if snapshot.get("node_type") != "video" or snapshot.get("mode") != "r2v":
        raise ValueError("only R2V video recovery is supported")
    node_id, request_id = snapshot.get("node_id"), run.get("request_id")
    if (
        not isinstance(node_id, str)
        or node_id != run.get("node_id")
        or not isinstance(request_id, str)
    ):
        raise ValueError("run and frozen node identity must match")
    inputs = snapshot.get("inputs", {})
    if not isinstance(inputs, Mapping):
        raise ValueError("frozen input mapping is required")
    refs = inputs.get("reference_images", [])
    if not isinstance(refs, list) or not 1 <= len(refs) <= 9 or inputs.get("reference_videos") or inputs.get("reference_audios"):
        raise ValueError("only one to nine image references are supported")
    if inputs.get("first_frame") or inputs.get("last_frame") or any(
        not isinstance(ref, Mapping)
        or not isinstance(ref.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
        for ref in refs
    ):
        raise ValueError("reference hash or first-frame input is invalid")
    submitted_at = datetime.fromisoformat(str(receipt.get("updated_at")))
    if server_restarted_at.tzinfo is None or submitted_at.tzinfo is None:
        raise ValueError("restart and submission must include time zones")
    if not submitted_at < server_restarted_at <= datetime.now(UTC):
        raise ValueError("restart must follow submission and cannot be in the future")
    root = output_root.resolve(strict=True)
    directory = (
        root
        / "canvas"
        / (_safe_component(node_id) or "node")
        / (_safe_component(request_id) or "request")
    )
    directory = directory.resolve(strict=True)
    source = video.resolve(strict=True)
    if not directory.is_relative_to(root) or source.parent != directory:
        raise ValueError("video must be in the exact original request output directory")
    matches = sorted(p.resolve() for p in directory.glob("video_*.mp4") if p.is_file())
    if matches != [source] or source.suffix.lower() != ".mp4":
        raise ValueError("exactly one original MP4 output is required")
    if datetime.fromtimestamp(source.stat().st_mtime, UTC) >= server_restarted_at:
        raise ValueError("video must have been written before the observed restart")
    before = _digest(source)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) or before != expected_sha256.lower():
        raise ValueError("output digest does not match")
    probe = json.loads(
        _tool(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:format_tags=prompt:stream=codec_type,codec_name,width,height",
                "-of",
                "json",
                str(source),
            ]
        )
    )
    streams = probe.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if (
        len(video_streams) != 1
        or not video_streams[0].get("width")
        or not video_streams[0].get("height")
    ):
        raise ValueError("valid video stream required")
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise ValueError("video audio stream is missing")
    duration = float(probe.get("format", {}).get("duration", 0))
    expected_duration = float(snapshot.get("parameters", {}).get("duration", 0))
    if duration <= 0 or expected_duration <= 0 or abs(duration - expected_duration) > 0.25:
        raise ValueError("video duration does not match the frozen request")
    workflow = json.loads(probe.get("format", {}).get("tags", {}).get("prompt", "{}"))
    nodes = list(workflow.values()) if isinstance(workflow, dict) else []

    def titled(title: str) -> list[Mapping[str, Any]]:
        return [
            n for n in nodes if isinstance(n, Mapping) and n.get("_meta", {}).get("title") == title
        ]

    prompt_nodes, saves = (
        titled("LFO.Prompt"),
        titled("LFO.SaveVideo"),
    )
    prefix = f"canvas/{_safe_component(node_id) or 'node'}/{_safe_component(request_id) or 'request'}/video"
    if len(prompt_nodes) != 1 or prompt_nodes[0].get("inputs", {}).get("value") != snapshot.get(
        "prompt"
    ):
        raise ValueError("embedded prompt differs from the frozen request")
    if (
        len(saves) != 1
        or saves[0].get("class_type") != "SaveVideo"
        or saves[0].get("inputs", {}).get("filename_prefix") != prefix
    ):
        raise ValueError("embedded output prefix differs from the original request")
    all_image_nodes = [
        n for n in nodes
        if isinstance(n, Mapping)
        and str(n.get("_meta", {}).get("title", "")).startswith("Canvas.ReferenceImage")
    ]
    if len(all_image_nodes) != len(refs):
        raise ValueError("embedded image reference count differs from the frozen request")
    for index, ref in enumerate(refs, 1):
        image_nodes = titled(f"Canvas.ReferenceImage{index}")
        if len(image_nodes) != 1 or image_nodes[0].get("is_changed") != [ref["sha256"]]:
            raise ValueError("embedded image reference differs from the frozen request")
    _tool([ffmpeg, "-v", "error", "-i", str(source), "-f", "null", "-"])
    if _digest(source) != before:
        raise ValueError("video changed during verification")
    return {
        "request_id": request_id,
        "provider_task_id": task_id,
        "output_path": str(source),
        "sha256": before,
        "duration": duration,
        "provider_terminal_status": "unknown",
        "server_restarted_at": server_restarted_at.astimezone(UTC).isoformat(),
    }
