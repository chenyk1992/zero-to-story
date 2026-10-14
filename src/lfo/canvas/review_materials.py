"""Prepare technical review aids for an existing video; never accept or generate it."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lfo.media._ffmpeg import run_command


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_video_review(output: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """One full decode creates a sheet and a stream-copy silent candidate.

    Failures belong to this preparation, not to the completed provider request.
    A cached receipt is reusable only for the same source and intact artifacts.
    """
    started = time.perf_counter()
    source = Path(output["path"]).resolve(strict=True)
    root = output_dir.resolve()
    if not source.is_relative_to(root):
        raise ValueError("待审素材必须位于原运行输出目录")
    source_hash = _digest(source)
    if source_hash != output["sha256"]:
        raise ValueError("待审素材与原始输出摘要不一致")
    metadata = {key: value for key, value in (output.get("metadata") or {}).items()
                if key != "review_materials"}
    duration = float(metadata["duration_ms"]) / 1000
    if duration <= 0:
        raise ValueError("待审视频缺少有效时长")
    receipt_path = root / (source.name + ".review-materials.json")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (isinstance(receipt, dict) and receipt.get("schema") == "canvas.review-materials.v1"
                and receipt.get("source_sha256") == source_hash
                and receipt.get("source_path") == str(source)
                and receipt.get("status") == "ready"):
            artifacts = receipt["artifacts"]
            if isinstance(artifacts, dict) and all(isinstance(item, dict)
                   and Path(item["path"]).resolve().is_relative_to(root)
                   and _digest(Path(item["path"])) == item["sha256"]
                   for item in artifacts.values()) and {"silent_video", "contact_sheet"} <= artifacts.keys():
                return {**receipt, "manifest_path": str(receipt_path)}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Publish a new directory on repair; keep any previously shown file intact.
    with tempfile.TemporaryDirectory(prefix="review-", dir=root) as temporary:
        folder = Path(temporary)
        silent = folder / "silent.mp4"
        sheet = folder / "contact-sheet.jpg"
        result = run_command([
            os.environ.get("LFO_FFMPEG") or "ffmpeg", "-v", "error", "-xerror",
            "-i", str(source), "-filter_complex",
            f"[0:v:0]split=2[full][sample];[sample]fps={5/duration:.12f},"
            "scale=240:-2,tile=5x1:nb_frames=5[sheet]",
            "-map", "[full]", "-map", "0:a?", "-progress", "pipe:1", "-nostats",
            "-f", "null", "-", "-map", "[sheet]", "-frames:v", "1", str(sheet),
            "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart", str(silent),
        ], timeout_s=120)
        frames = [int(line.partition("=")[2].strip()) for line in result.stdout.splitlines()
                  if line.startswith("frame=") and line.partition("=")[2].strip().isdigit()]
        if not frames or max(frames) <= 0 or not silent.is_file() or not sheet.is_file():
            raise ValueError("待审视频未完整解码或未产生检查材料")
        if _digest(source) != source_hash:
            raise ValueError("准备待审材料期间原视频发生变化")
        # tempfile's unique name also makes successful artifacts immutable to retries.
        published = root / (folder.name + "-ready")
        published.mkdir()
        artifacts = {}
        for key, file in (("silent_video", silent), ("contact_sheet", sheet)):
            destination = published / file.name
            file.replace(destination)
            artifacts[key] = {"path": str(destination), "sha256": _digest(destination)}
    receipt = {
        "schema": "canvas.review-materials.v1", "status": "ready",
        "created_at": datetime.now(UTC).isoformat(),
        "source_path": str(source), "source_sha256": source_hash,
        "metadata": metadata, "decode_verified": True, "decoded_frames": max(frames),
        "artifacts": artifacts, "elapsed_seconds": time.perf_counter() - started,
        "content_review": "NOT_REVIEWED",
        "note": "技术解码和抽样材料不代表连续视听或内容采用；原片保留，候选仅移除音轨。",
    }
    pending = root / (published.name + ".json")
    pending.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(receipt_path)
    return {**receipt, "manifest_path": str(receipt_path)}
