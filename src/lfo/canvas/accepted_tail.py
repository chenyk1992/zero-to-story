"""Extract the final decoded frame from a file-bound accepted Canvas result."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from pathlib import Path
from typing import Any

from lfo.canvas.client import CanvasClient
from lfo.media._ffmpeg import run_command


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_accepted_tail(client: CanvasClient, run_id: str) -> dict[str, Any]:
    """Create a new immutable tail asset; never submit, accept, or wire a run."""
    run = client.request("GET", f"/api/runs/{run_id}")
    review = run.get("review") or {}
    if run.get("status") != "succeeded" or review.get("decision") != "ACCEPT":
        raise ValueError("真实尾帧需要成功且已 ACCEPT 的原运行")
    if run.get("snapshot", {}).get("node_type") != "video":
        raise ValueError("真实尾帧只适用于视频运行")
    source = Path(review["output_path"]).resolve(strict=True)
    expected_digest = review["output_sha256"]
    if _digest(source) != expected_digest:
        raise ValueError("视频与 ACCEPT 记录的文件摘要不一致")
    output_dir = client.settings.output_dir(run["canvas_id"], run["id"]).resolve()
    if not output_dir.is_relative_to(client.settings.media_root.resolve()):
        raise ValueError("运行输出目录超出工作区")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"accepted-tail-{uuid.uuid4().hex}.png"
    with tempfile.TemporaryDirectory(prefix="lfo-accepted-tail-") as temporary:
        frame = Path(temporary) / "tail.png"
        # Decode every frame; image2 update leaves the actual final decoded frame.
        run_command(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0",
                     "-an", "-fps_mode", "passthrough", "-update", "1", "-y", str(frame)])
        latest = client.request("GET", f"/api/runs/{run_id}")
        if latest.get("review") != review or latest.get("status") != "succeeded" or _digest(source) != expected_digest:
            raise ValueError("提取期间来源或验收发生变化，请重新核实原运行")
        if not frame.is_file() or not frame.stat().st_size:
            raise ValueError("视频未解码出尾帧")
        with destination.open("xb") as target:
            target.write(frame.read_bytes())
    return {
        "id": destination.stem,
        "source_run_id": run_id,
        "asset": {"path": str(destination), "kind": "image", "sha256": _digest(destination)},
    }
