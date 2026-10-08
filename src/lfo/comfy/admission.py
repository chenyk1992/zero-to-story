# ruff: noqa: RUF001
"""One machine-wide Comfy submission guard for Canvas image, video and audio execution.

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
            raise LfoComfyError("原 Comfy 任务尚未核实结束。先查看 lfo.comfy.admission。不能再次提交")
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
            raise LfoComfyError("另一个 Comfy 任务正在提交或等待。本地生成必须串行") from exc

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
    """Read the original job through MCP; never infer completion from an empty queue."""
    from . import transport
    from .mcp_client import McpCallError

    guard = VideoSubmissionGuard("")
    guard._acquire()
    try:
        record = inspect_submission()
        if record is None or record["request_id"] != request_id:
            raise ValueError("原提交编号不匹配")
        task_id = record.get("provider_task_id")
        if not task_id:
            raise ValueError("原提交没有远端编号。无法自动证明远端结束。保持未知占用")
        config = transport.load_runtime_config(base_url=record["base_url"])
        try:
            with transport._session(config) as session:
                status = session.call("job", {"action": "status", "prompt_id": task_id})
        except McpCallError as exc:
            raise ValueError(f"无法经 MCP 核实原任务，保持未知占用：{exc}") from exc
        try:
            verdict = transport._status(status, task_id)
        except transport.ExecutorError as exc:
            raise ValueError("远端历史尚未证明该任务结束。保持未知占用") from exc
        if verdict not in {"completed", "complete", "success", "succeeded", "done", "error", "failed", "cancelled", "canceled"}:
            raise ValueError("远端历史尚未证明该任务结束。保持未知占用")
        guard.finished()
        return {"request_id": request_id, "provider_task_id": task_id, "remote_status": status}
    finally:
        guard._lock.close()


def reconcile_submission_operator(
    request_id: str,
    provider_task_id: str | None,
    terminal_status: str,
    reason: str,
    *,
    server_restarted_at: str | None = None,
) -> dict[str, Any]:
    """Release one receipt after an operator confirms the original job ended.

    This path is intentionally limited to failed/cancelled jobs. It requires
    both original identifiers, or explicit restart evidence for a receipt that
    never received a provider ID. Missing history alone is not confirmation.
    """
    if not request_id or not request_id.strip():
        raise ValueError("必须提供原 Canvas 请求编号和原 Comfy 任务编号")
    if provider_task_id is not None and not provider_task_id.strip():
        raise ValueError("原 Comfy 任务编号不能为空白")
    if (provider_task_id is None) != (server_restarted_at is not None):
        raise ValueError("无远端编号时必须提供已核实的服务重启时间；有编号时沿用原编号核实")
    if terminal_status not in {"failed", "cancelled"}:
        raise ValueError("操作员核实只允许 failed 或 cancelled，不能确认成功")
    clean_reason = reason.strip() if reason else ""
    if not clean_reason:
        raise ValueError("操作员核实必须填写非空原因")

    guard = VideoSubmissionGuard("")
    guard._acquire()
    try:
        receipt = inspect_submission()
        if receipt is None or receipt.get("request_id") != request_id:
            raise ValueError("原 Canvas 请求编号不匹配")
        if receipt.get("provider_task_id") != provider_task_id:
            raise ValueError("原 Comfy 任务编号不匹配")

        restart_evidence = None
        if server_restarted_at is not None:
            submitted_at = datetime.fromisoformat(receipt["updated_at"])
            restarted_at = datetime.fromisoformat(server_restarted_at)
            if submitted_at.tzinfo is None or restarted_at.tzinfo is None:
                raise ValueError("提交与重启时间必须包含时区")
            if not submitted_at < restarted_at <= datetime.now(UTC):
                raise ValueError("已核实的重启时间必须晚于原提交且不晚于当前时间")
            # A restart is an operator-observed lifecycle event, not a deduction
            # from an empty queue. Confirm that the same local endpoint is ready.
            from . import transport

            config = transport.load_runtime_config(base_url=receipt["base_url"])
            with transport._session(config) as session:
                info = session.call("server_info")
            if not transport._running(info, config):
                raise ValueError("重启后的原 Comfy 服务尚未就绪，保持未知占用")
            restart_evidence = {
                "server_restarted_at": restarted_at.astimezone(UTC).isoformat(),
                "base_url": config.base_url,
                "server": info["server"],
                "workspace": info.get("workspace"),
            }

        audit_directory = guard.folder / "reconciliations"
        audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = audit_directory / (
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid4().hex}.json"
        )
        audit = {
            "source": "operator_confirmation",
            "request_id": request_id,
            "provider_task_id": provider_task_id,
            "terminal_status": terminal_status,
            "reason": clean_reason,
            "confirmed_at": datetime.now(UTC).isoformat(),
            "receipt": receipt,
        }
        if restart_evidence is not None:
            audit["restart_evidence"] = restart_evidence
        temporary = audit_path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
            temporary.replace(audit_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        guard.finished()
        return {
            "request_id": request_id,
            "provider_task_id": provider_task_id,
            "remote_status": terminal_status,
            "source": "operator_confirmation",
            "audit_path": str(audit_path),
        }
    finally:
        guard._lock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="检查或核实原 Comfy 提交。不生成视频")
    reconciliation = parser.add_mutually_exclusive_group()
    reconciliation.add_argument("--reconcile", metavar="REQUEST_ID")
    reconciliation.add_argument("--operator-reconcile", metavar="REQUEST_ID")
    parser.add_argument("--provider-task-id")
    parser.add_argument(
        "--server-restarted-at",
        help="仅无远端编号：操作员已核实的原服务重启时间（含时区 ISO 8601）",
    )
    parser.add_argument("--terminal-status", choices=("failed", "cancelled"))
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.operator_reconcile:
        if (
            bool(args.provider_task_id) == bool(args.server_restarted_at)
            or not args.terminal_status or not args.reason
        ):
            parser.error(
                "--operator-reconcile 需要 --provider-task-id 或 --server-restarted-at（二选一）、--terminal-status "
                "和 --reason"
            )
        result = reconcile_submission_operator(
            args.operator_reconcile,
            args.provider_task_id,
            args.terminal_status,
            args.reason,
            server_restarted_at=args.server_restarted_at,
        )
    else:
        if args.provider_task_id or args.server_restarted_at or args.terminal_status or args.reason:
            parser.error("这些参数只用于 --operator-reconcile")
        result = reconcile_submission(args.reconcile) if args.reconcile else inspect_submission()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
