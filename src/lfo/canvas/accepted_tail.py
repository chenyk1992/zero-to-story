"""Extract the final decoded frame from a file-bound accepted Canvas result."""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from lfo.canvas.client import CanvasClient
from lfo.canvas.settings import CanvasSettings
from lfo.media._ffmpeg import run_command


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _reusable_tail_frame(
    run: Mapping[str, Any], source: Path, expected_digest: str, output_dir: Path
) -> tuple[Path, str] | None:
    """Return a verified cached tail frame from intact review_materials, if present."""
    candidates: list[Mapping[str, Any]] = []
    for output in run.get("outputs") or []:
        if not isinstance(output, Mapping):
            continue
        materials = (output.get("metadata") or {}).get("review_materials")
        if isinstance(materials, Mapping):
            candidates.append(materials)
    receipt_path = output_dir / (source.name + ".review-materials.json")
    try:
        disk_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if isinstance(disk_receipt, Mapping):
            candidates.append(disk_receipt)
    except (OSError, ValueError, TypeError):
        pass

    for receipt in candidates:
        if receipt.get("status") != "ready":
            continue
        if receipt.get("source_sha256") != expected_digest:
            continue
        source_path_value = receipt.get("source_path")
        if source_path_value is not None:
            try:
                if Path(str(source_path_value)).resolve() != source:
                    continue
            except OSError:
                continue
        artifacts = receipt.get("artifacts")
        if not isinstance(artifacts, Mapping):
            continue
        tail_entry = artifacts.get("tail_frame")
        if not isinstance(tail_entry, Mapping):
            continue
        tail_path_value = tail_entry.get("path")
        tail_sha256 = tail_entry.get("sha256")
        if not isinstance(tail_path_value, str) or not isinstance(tail_sha256, str) or not tail_sha256:
            continue
        try:
            candidate = Path(tail_path_value).resolve(strict=True)
            if (
                candidate.is_relative_to(output_dir)
                and candidate.is_file()
                and candidate.stat().st_size > 0
                and _digest(candidate) == tail_sha256
            ):
                return candidate, tail_sha256
        except OSError:
            continue
    return None


def extract_accepted_tail_for_run(
    run: Mapping[str, Any],
    *,
    settings: CanvasSettings,
    reload_run: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Create a new immutable tail asset for an already-loaded ACCEPT video run."""
    review = run.get("review") or {}
    if run.get("status") != "succeeded" or review.get("decision") != "ACCEPT":
        raise ValueError("真实尾帧需要成功且已 ACCEPT 的原运行")
    if run.get("snapshot", {}).get("node_type") != "video":
        raise ValueError("真实尾帧只适用于视频运行")
    run_id = str(run["id"])
    source = Path(review["output_path"]).resolve(strict=True)
    expected_digest = review["output_sha256"]
    if _digest(source) != expected_digest:
        raise ValueError("视频与 ACCEPT 记录的文件摘要不一致")
    output_dir = settings.output_dir(run["canvas_id"], run_id).resolve()
    if not output_dir.is_relative_to(settings.media_root.resolve()):
        raise ValueError("运行输出目录超出工作区")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"accepted-tail-{uuid.uuid4().hex}.png"
    reusable = _reusable_tail_frame(run, source, expected_digest, output_dir)
    if reusable is not None:
        cached_tail, cached_digest = reusable
        payload = cached_tail.read_bytes()
        if not payload or hashlib.sha256(payload).hexdigest() != cached_digest:
            raise ValueError("待审末帧候选在读取期间发生变化，请重试")
        latest = reload_run()
        if latest.get("review") != review or latest.get("status") != "succeeded" or _digest(source) != expected_digest:
            raise ValueError("提取期间来源或验收发生变化，请重新核实原运行")
        with destination.open("xb") as target:
            target.write(payload)
    else:
        with tempfile.TemporaryDirectory(prefix="lfo-accepted-tail-") as temporary:
            frame = Path(temporary) / "tail.png"
            # Decode every frame; image2 update leaves the actual final decoded frame.
            run_command(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0",
                         "-an", "-fps_mode", "passthrough", "-update", "1", "-y", str(frame)])
            latest = reload_run()
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


def extract_accepted_tail(client: CanvasClient, run_id: str) -> dict[str, Any]:
    """Create a new immutable tail asset; never submit, accept, or wire a run."""
    run = client.request("GET", f"/api/runs/{run_id}")
    return extract_accepted_tail_for_run(
        run,
        settings=client.settings,
        reload_run=lambda: client.request("GET", f"/api/runs/{run_id}"),
    )
