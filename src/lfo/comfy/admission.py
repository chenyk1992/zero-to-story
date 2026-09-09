"""One machine-wide Comfy submission guard shared by both project entrypoints.

The OS lock protects concurrent processes. A small receipt survives a lost
process so unknown remote work does not silently release the submission slot.
It stores no prompt, credentials, or media and never resubmits work.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .exceptions import LfoComfyError


def state_directory() -> Path:
    override = os.environ.get("LFO_VIDEO_STATE")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "zero-to-story" / "video"


class VideoSubmissionGuard:
    """Acquire once before submitting; clear only on proven remote completion."""

    def __init__(self, base_url: str, *, request_id: str | None = None):
        self.folder = state_directory()
        self.receipt = self.folder / "submission.json"
        self.request_id = request_id or uuid4().hex
        self.base_url = base_url
        self._lock: Any = None

    def __enter__(self) -> VideoSubmissionGuard:
        self._acquire()
        if self.receipt.exists():
            self._lock.close()
            raise LfoComfyError("原视频任务尚未核实结束。先查看 lfo.comfy.admission。不能再次提交")
        return self

    def _acquire(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = (self.folder / "submission.lock").open("a+b")
        self._lock.seek(0, 2)
        if self._lock.tell() == 0:
            self._lock.write(b"0")
            self._lock.flush()
        self._lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            raise LfoComfyError("另一个视频正在提交或等待。视频生成必须串行") from exc

    def submitted(self, provider_task_id: str | None = None) -> None:
        record = {
            "request_id": self.request_id,
            "base_url": self.base_url,
            "provider_task_id": provider_task_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        # All writers hold the OS lock. Atomic replace also makes inspection safe.
        temporary = self.receipt.with_suffix(".tmp")
        temporary.write_text(json.dumps(record), encoding="utf-8")
        temporary.replace(self.receipt)

    def finished(self) -> None:
        self.receipt.unlink(missing_ok=True)

    def __exit__(self, *_args: object) -> None:
        self._lock.close()


def inspect_submission() -> dict[str, Any] | None:
    path = state_directory() / "submission.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def reconcile_submission(request_id: str) -> dict[str, Any]:
    """Read the original Comfy history; never infer cancellation from an empty queue."""
    from urllib.parse import quote
    from urllib.request import urlopen

    guard = VideoSubmissionGuard("")
    guard._acquire()
    try:
        record = inspect_submission()
        if record is None or record["request_id"] != request_id:
            raise ValueError("原提交编号不匹配")
        task_id = record.get("provider_task_id")
        if not task_id:
            raise ValueError("原提交没有远端编号。无法自动证明远端结束。保持未知占用")
        with urlopen(
            record["base_url"].rstrip("/") + "/history/" + quote(task_id, safe=""), timeout=15
        ) as response:
            history = json.load(response)
        item = history.get(task_id, {})
        status = item.get("status", {})
        if status.get("completed") is not True and status.get("status_str") != "error":
            raise ValueError("远端历史尚未证明该任务结束。保持未知占用")
        guard.finished()
        return {"request_id": request_id, "provider_task_id": task_id, "remote_status": status}
    finally:
        guard._lock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="检查或核实原 Comfy 提交。不生成视频")
    parser.add_argument("--reconcile", metavar="REQUEST_ID")
    args = parser.parse_args()
    result = reconcile_submission(args.reconcile) if args.reconcile else inspect_submission()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
