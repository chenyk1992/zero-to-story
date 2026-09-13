"""One canvas service for browser, CLI and Agent tools."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.continuation import (
    CONTINUATION_EVENTS,
    build_continuation_summary,
    continuation_fingerprint,
    public_continuation,
)
from lfo.canvas.graph import CanvasError, resolve_snapshot
from lfo.canvas.media import CanvasMedia, creative_snapshot
from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import CanvasStore, ContinuationRevisionError
from lfo.media._ffmpeg import probe, run_command


class CanvasService:
    def __init__(self, settings: CanvasSettings, *, start_worker: bool = True) -> None:
        self.settings = settings
        self.store = CanvasStore(settings.database)
        self.catalog = CapabilityCatalog(settings.project_root)
        self.media = CanvasMedia(settings)
        self._confirm_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        self._executions: dict[str, threading.Thread] = {}
        self._execution_lock = threading.Lock()
        self._changes = threading.Condition()
        if start_worker:
            self.start_worker()

    def start_worker(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(target=self._work, name="canvas-execution", daemon=True)
            self._worker.start()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._worker is not None:
            self._worker.join(timeout=1)
        with self._execution_lock:
            executing = list(self._executions.values())
        for worker in executing:
            worker.join(timeout=1)
        if (self._worker is None or not self._worker.is_alive()) and not any(
            worker.is_alive() for worker in executing
        ):
            self.store.close()

    def runs(self, canvas_id: str | None = None) -> list[dict[str, Any]]:
        runs = self.store.list_runs(canvas_id)
        canvases: dict[str, Any] = {}
        snapshots: dict[tuple[str, str], dict[str, Any]] = {}
        result = []
        for original in runs:
            run = copy.deepcopy(self._public_run(original))
            run["matches_current"] = False
            try:
                if run["canvas_id"] not in canvases:
                    canvases[run["canvas_id"]] = self.store.get_canvas(run["canvas_id"])
                key = (run["canvas_id"], run["node_id"])
                if key not in snapshots:
                    snapshots[key] = resolve_snapshot(canvases[run["canvas_id"]], run["node_id"], runs)
                current = snapshots[key]
                run["matches_current"] = creative_snapshot(current) == creative_snapshot(
                    run["snapshot"]
                ) and self.media.inputs_unchanged(run["snapshot"])
            except (ValueError, KeyError):
                pass
            result.append(run)
        return result

    def confirm(
        self, canvas_id: str, node_id: str, version: int, request_id: str
    ) -> dict[str, Any]:
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 200:
            raise ValueError("执行请求编号无效")
        with self._confirm_lock:
            existing = self.store.get_run_by_request(request_id)
            if existing is not None:
                if (existing["canvas_id"], existing["node_id"], existing["canvas_version"]) != (
                    canvas_id,
                    node_id,
                    version,
                ):
                    raise CanvasError(
                        "该执行请求编号已用于另一份配置", code="request_conflict", status=409
                    )
                return self._public_run(existing)
            canvas = self.store.get_canvas(canvas_id)
            if canvas["version"] != version:
                raise CanvasError(
                    "画布已有新修改，请先同步并保存后再确认", code="version_conflict", status=409
                )
            runs = self.store.list_runs(canvas_id)
            if any(
                run["node_id"] == node_id
                and run["status"] in {"queued", "pending_agent", "running", "unknown"}
                for run in runs
            ):
                raise CanvasError(
                    "这个组件已有待处理任务，请先处理该任务", code="node_busy", status=409
                )
            snapshot = resolve_snapshot(canvas, node_id, runs)
            capability = self.catalog.validate(snapshot)
            frozen = self.media.freeze(snapshot, request_id)
            status = "pending_agent" if capability["execution"] == "agent" else "queued"
            resource = capability.get("resource", {})
            # Undeclared providers share a conservative resource. Media type
            # alone is not evidence that an image uses a different GPU.
            key = "video" if snapshot["node_type"] == "video" else resource.get("key", "video")
            capacity = (
                1
                if key == "video"
                else min(self.settings.image_concurrency, max(1, int(resource.get("capacity", 1))))
            )
            run = self.store.create_run(
                canvas_id,
                node_id,
                version,
                request_id,
                frozen,
                status=status,
                resource_key=key,
                resource_capacity=capacity,
            )
            self._notify()
            return self._public_run(run)

    @staticmethod
    def _public_run(run: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in run.items() if not k.endswith("_token")}

    @staticmethod
    def _provider_task_id(run: dict[str, Any], value: str | None) -> str | None:
        current = run.get("provider_task_id")
        if current and value and current != value:
            raise ValueError("远端任务编号与原请求不一致")
        return value or current

    def _validate_output_payload(self, outputs: Any, expected_kind: str) -> list[dict[str, Any]]:
        """Validate every returned output before any file is copied."""

        if isinstance(outputs, (str, bytes, bytearray)) or not isinstance(outputs, Sequence):
            raise ValueError("outputs 必须是数组")
        if not outputs:
            raise ValueError("执行没有返回可用媒体文件")
        checked: list[dict[str, Any]] = []
        for index, output in enumerate(outputs):
            if not isinstance(output, Mapping):
                raise ValueError(f"输出 {index} 需要对象")
            if output.get("kind") != expected_kind:
                raise ValueError("生成结果类型与组件不一致")
            path = output.get("path")
            if not isinstance(path, str) or not path.strip():
                raise ValueError(f"输出 {index} 缺少有效路径")
            resolved = self.media.resolve(path, external=True)
            if self.media.asset(resolved)["kind"] != expected_kind:
                raise ValueError("输出媒体类型与文件不一致")
            item = dict(output)
            if expected_kind == "video":
                item["metadata"] = self._verify_video_output(path)
            checked.append(item)
        return checked

    def _verify_video_output(self, value: str) -> dict[str, Any]:
        """Require a decodable video before it can become a run output."""

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.settings.project_root / path
        try:
            metadata = probe(path.resolve())
        except Exception as exc:
            raise ValueError(f"视频输出无法读取：{exc}") from exc
        if not isinstance(metadata, Mapping):
            raise ValueError("视频输出无法读取：探测结果无效")
        duration = metadata.get("duration_ms")
        width = metadata.get("width")
        height = metadata.get("height")
        codec = metadata.get("codec")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
            or isinstance(width, bool)
            or not isinstance(width, int)
            or width <= 0
            or isinstance(height, bool)
            or not isinstance(height, int)
            or height <= 0
            or not isinstance(codec, str)
            or not codec.strip()
        ):
            raise ValueError("视频输出无法读取：缺少有效时长、尺寸或编码信息")
        return dict(metadata)

    def claim_agent(self, run_id: str, host_tools: list[str] | None = None) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        capability = self.catalog.validate(run["snapshot"], host_tools, for_claim=True)
        if capability["execution"] != "agent" or not capability["available"]:
            raise ValueError("当前会话不能接手这个生成任务")
        effective = self.media.execution_snapshot(run["snapshot"])
        token = uuid.uuid4().hex
        claimed = self.store.claim_run(run_id, owner_token=token)
        self._notify()
        return {
            **self._public_run(claimed),
            "owner_token": token,
            "execution_snapshot": effective,
            "skill": capability["skill"],
            "output_dir": str(self.settings.output_dir(run["canvas_id"], run_id)),
            "instructions": capability.get(
                "handoff", "消费确认后的输入，通过完成接口回填实际产物。"
            ),
        }

    def complete_agent(
        self,
        run_id: str,
        owner_token: str,
        *,
        outputs: list[dict[str, Any]] | None = None,
        status: str = "succeeded",
        error: str | None = None,
        provider_task_id: str | None = None,
        stage: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._confirm_lock:
            run = self.store.get_run(run_id)
            if not owner_token or run.get("owner_token") != owner_token:
                raise CanvasError("此执行请求不属于当前接手方", code="owner_conflict", status=409)
            if run["status"] != "running":
                raise CanvasError(
                    "此任务已结束或状态已改变，不能重复完成", code="run_conflict", status=409
                )
            if status not in {"succeeded", "failed", "unknown"}:
                raise ValueError("只能回填成功、失败或状态未知")
            provider_task_id = self._provider_task_id(run, provider_task_id)
            checked_outputs = (
                self._validate_output_payload(outputs, run["snapshot"]["node_type"])
                if status == "succeeded"
                else None
            )
            collected = (
                self.media.collect_outputs(checked_outputs, run["canvas_id"], run_id)
                if checked_outputs is not None
                else []
            )
            updated = self.store.update_run(
                run_id,
                status=status,
                outputs=collected,
                error=error,
                provider_task_id=provider_task_id,
                stage=stage
                or ("media_validation" if status == "succeeded" else run.get("stage", "submit")),
                evidence=evidence,
            )
            self._notify()
            return self._public_run(updated)

    def handoff_recovery(
        self, run_id: str, reason: str, expected_updated_at: str
    ) -> dict[str, Any]:
        with self._confirm_lock:
            token = self.store.handoff_recovery(run_id, reason, expected_updated_at)
        self._notify()
        return {"run_id": run_id, "owner_token": token}

    def reconcile_run(
        self,
        run_id: str,
        owner_token: str,
        status: str,
        evidence: dict[str, Any],
        outputs: list[dict[str, Any]] | None = None,
        provider_task_id: str | None = None,
    ) -> dict[str, Any]:
        with self._confirm_lock:
            return self._reconcile_run(
                run_id, owner_token, status, evidence, outputs, provider_task_id
            )

    def _reconcile_run(
        self,
        run_id: str,
        owner_token: str,
        status: str,
        evidence: dict[str, Any],
        outputs: list[dict[str, Any]] | None,
        provider_task_id: str | None,
    ) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if not owner_token or owner_token not in {
            run.get("owner_token"),
            run.get("recovery_token"),
        }:
            raise CanvasError("核实需要原任务的接手令牌", code="owner_conflict", status=409)
        if run["status"] != "unknown" and not (
            run["status"] == "failed" and run.get("stage") in {"collection", "media_validation"}
        ):
            raise CanvasError("这个任务当前不需要结果核实", code="run_conflict", status=409)
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("核实结果需要 succeeded、failed 或 cancelled")
        is_owner = run.get("owner_token") == owner_token
        is_recovery = run.get("recovery_token") == owner_token
        candidate_outputs = outputs if status == "succeeded" else None
        # Validate proof, task identity and ownership while no files have yet
        # been copied.  reconcile_run repeats this atomically at commit time.
        self.store.preflight_reconcile(
            run_id,
            status=status,
            evidence=evidence,
            outputs=candidate_outputs,
            provider_task_id=provider_task_id,
            owner_token=owner_token if is_owner else None,
            recovery_token=owner_token if is_recovery else None,
        )
        checked_outputs = (
            self._validate_output_payload(outputs, run["snapshot"]["node_type"])
            if status == "succeeded"
            else None
        )
        collected = (
            self.media.collect_outputs(checked_outputs, run["canvas_id"], run_id)
            if checked_outputs is not None
            else None
        )
        result = self.store.reconcile_run(
            run_id,
            status=status,
            evidence=evidence,
            outputs=collected,
            provider_task_id=provider_task_id,
            owner_token=owner_token if run.get("owner_token") == owner_token else None,
            recovery_token=owner_token if run.get("recovery_token") == owner_token else None,
        )
        self._notify()
        return self._public_run(result)

    def cancel_pending(self, run_id: str) -> dict[str, Any]:
        result = self._public_run(self.store.cancel_pending(run_id))
        self._notify()
        return result

    def _notify(self) -> None:
        self._wake.set()
        with self._changes:
            self._changes.notify_all()

    def run_summary(self, run_id: str) -> dict[str, Any]:
        run = self._public_run(self.store.get_run(run_id))
        return {
            key: run.get(key)
            for key in (
                "id",
                "request_id",
                "canvas_id",
                "node_id",
                "status",
                "stage",
                "attention_state",
                "attention_reason",
                "provider_task_id",
                "outputs",
                "review",
                "error",
                "created_at",
                "updated_at",
            )
        }

    def readiness(self, canvas_id: str, node_id: str) -> dict[str, Any]:
        """Check a draft's dependencies without freezing, claiming or generating."""
        canvas = self.store.get_canvas(canvas_id)
        try:
            runs = self.store.list_runs(canvas_id)
            if any(
                run["node_id"] == node_id
                and run["status"]
                in {
                    "queued",
                    "pending_agent",
                    "running",
                    "unknown",
                }
                for run in runs
            ):
                raise ValueError("该组件已有待处理请求")
            snapshot = resolve_snapshot(canvas, node_id, runs)
            self.catalog.validate(snapshot)

            def inspect(value: Any) -> None:
                if isinstance(value, list):
                    for item in value:
                        inspect(item)
                elif isinstance(value, dict):
                    if "path" in value and "kind" in value:
                        self.media.validate_input(value)
                    else:
                        for item in value.values():
                            inspect(item)

            inspect(snapshot["inputs"])
        except (ValueError, KeyError) as exc:
            return {"ready": False, "version": canvas["version"], "reason": str(exc)}
        return {"ready": True, "version": canvas["version"], "provider": snapshot["provider"]}

    # ------------------------------------------------------------------
    # Opt-in continuation hand-off
    # ------------------------------------------------------------------
    def _continuation_summary(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Build a bounded, read-only summary for one persisted plan."""

        canvas = self.store.get_canvas(str(plan["canvas_id"]))
        runs = self.store.list_runs(str(plan["canvas_id"]))
        return build_continuation_summary(
            plan,
            canvas,
            runs,
            lambda node_id: self.readiness(str(plan["canvas_id"]), node_id),
        )

    def _continuation_payload(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Return the shared public plan plus its current read-only check."""

        public = public_continuation(plan)
        summary = self._continuation_summary(plan)
        fingerprint = continuation_fingerprint(summary)
        attempts = (
            int(plan.get("stop_count") or 0) if plan.get("stop_fingerprint") == fingerprint else 0
        )
        summary["stop_attempts"] = attempts
        summary["stalled"] = bool(
            attempts >= 3
            and plan.get("stop_warning")
            and plan.get("stop_fingerprint") == fingerprint
        )
        if summary["stalled"]:
            summary["warning"] = "接续摘要连续 3 次无进展，需要人工接手；计划未标记完成"
        public["summary"] = summary
        return public

    def configure_continuation(
        self,
        canvas_id: str,
        session_id: str,
        node_ids: Sequence[str],
        authorization: str,
        canvas_version: int,
        revision: int | None = None,
    ) -> dict[str, Any]:
        """Opt in one host session to a bounded canvas production scope."""

        existing = self.store.get_continuation_for_scope(canvas_id, session_id)
        plan = self.store.configure_continuation(
            canvas_id,
            session_id,
            node_ids,
            authorization,
            canvas_version,
            revision=revision,
        )
        payload = self._continuation_payload(plan)
        payload["created"] = existing is None
        return payload

    def read_continuations(
        self,
        session_id: str | None = None,
        canvas_id: str | None = None,
    ) -> dict[str, Any]:
        """Read plans and checks without changing stop counters or units."""

        return {
            "plans": [
                self._continuation_payload(plan)
                for plan in self.store.list_continuations(
                    session_id=session_id, canvas_id=canvas_id
                )
            ]
        }

    def update_continuation_state(
        self, continuation_id: str, revision: int, state: str, reason: str | None = None
    ) -> dict[str, Any]:
        plan = self.store.update_continuation_state(continuation_id, revision, state, reason)
        return self._continuation_payload(plan)

    def update_continuation_unit(
        self,
        continuation_id: str,
        revision: int,
        unit_id: str,
        state: str,
        *,
        agent_id: str | None = None,
        node_id: str | None = None,
        run_id: str | None = None,
        turn_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        plan = self.store.update_continuation_unit(
            continuation_id,
            revision,
            unit_id,
            state,
            agent_id=agent_id,
            node_id=node_id,
            run_id=run_id,
            turn_id=turn_id,
            reason=reason,
        )
        return self._continuation_payload(plan)

    def continuation_hook(
        self,
        session_id: str,
        event: str,
        agent_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """Handle a host lifecycle signal without scheduling or generating.

        Stop reads a summary and records only its bounded repeat counter.
        SubagentStop and Interrupt mutate the durable hand-off ledger through
        explicit CAS updates; neither event starts a model call.
        """

        if not isinstance(event, str) or event not in CONTINUATION_EVENTS:
            raise ValueError(
                "continuation hook event must be Stop, SessionStart, SubagentStop or Interrupt"
            )
        if event == "SessionStart":
            plans = self.store.list_continuations(session_id=session_id)
            # SessionStart only carries a small routing hint.  Detailed plan
            # data (including authorization and unit notes) stays behind the
            # explicit read endpoint and is never injected as hook context.
            context = {
                "kind": "canvas_continuation_state",
                "session_id": session_id,
                "plans": [{"id": plan["id"], "state": plan["state"]} for plan in plans[:16]],
                "message": ("按需读取当前会话的画布接续计划；没有计划时无需生产"),
            }
            return {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": json.dumps(
                        context, ensure_ascii=False, separators=(",", ":")
                    ),
                }
            }
        if event == "SubagentStop":
            self.store.mark_subagent_result_ready(session_id, agent_id, turn_id)
            return {}
        if event == "Interrupt":
            changed = self.store.pause_continuations_for_session(
                session_id, "宿主中断，已暂停画布接续计划"
            )
            if not changed:
                return {}
            return {"systemMessage": "已暂停当前会话的画布接续计划；恢复前不会领取或提交新单元"}
        return self._continuation_stop_hook(session_id)

    def _continuation_stop_hook(self, session_id: str) -> dict[str, Any]:
        plans = self.store.list_continuations(session_id=session_id)
        if not plans:
            return {}
        exhausted = False
        for plan in plans:
            current = plan
            for _attempt in range(3):
                summary = self._continuation_summary(current)
                if summary.get("allow_stop"):
                    break
                fingerprint = continuation_fingerprint(summary)
                try:
                    updated = self.store.record_continuation_stop(
                        current["id"], int(current["revision"]), fingerprint
                    )
                except ContinuationRevisionError:
                    current = self.store.get_continuation(current["id"])
                    continue
                attempts = int(updated.get("stop_count") or 0)
                if attempts >= 3:
                    exhausted = True
                    break
                return {
                    "decision": "block",
                    "reason": self._continuation_hook_reason(summary),
                }
            else:
                # Concurrent progress is not the same as three unchanged
                # checks. Re-read pause/completion before asking for handoff.
                latest = self._continuation_summary(self.store.get_continuation(current["id"]))
                if not latest.get("allow_stop"):
                    return {
                        "decision": "block",
                        "reason": "接续记录正在更新，请重读当前任务的接续计划后处理已授权工作。",
                    }
        if exhausted:
            return {"systemMessage": "接续摘要连续 3 次无进展，需要人工接手；计划未标记完成"}
        return {}

    @staticmethod
    def _continuation_hook_reason(summary: Mapping[str, Any]) -> str:
        """Make a short fixed hook instruction from structured state only."""

        actions = summary.get("actions")
        action = actions[0] if isinstance(actions, Sequence) and actions else {}
        action_type = action.get("type") if isinstance(action, Mapping) else None
        if action_type == "handle_unit":
            return "请先处理已返回执行单元的结果，只在已有授权范围内继续"
        if action_type == "claim_agent":
            return "请先领取 pending_agent 单元，只在已有授权范围内继续"
        if action_type == "review":
            return "请先审查当前实际产物并记录结论，只在已有授权范围内继续"
        if action_type == "prepare":
            return "请先准备当前节点的输入，只在已有授权范围内继续"
        if action_type == "execute_after_authorization_check":
            return "请先核对已有授权后处理已就绪节点"
        return "请先处理画布接续的下一步，只在已有授权范围内继续"

    def events(
        self, after: int = 0, canvas_id: str | None = None, wait_seconds: float = 0
    ) -> dict[str, Any]:
        if not 0 <= wait_seconds <= 25:
            raise ValueError("变更等待时间必须在 0 到 25 秒之间")
        deadline = time.monotonic() + wait_seconds
        with self._changes:
            while True:
                events = self.store.list_events(after=after, canvas_id=canvas_id)
                if events or time.monotonic() >= deadline:
                    return {"events": events, "cursor": events[-1]["id"] if events else after}
                self._changes.wait(max(0, deadline - time.monotonic()))

    def set_attention(self, run_id: str, state: str, reason: str) -> dict[str, Any]:
        result = self.store.set_attention(run_id, state, reason)
        self._notify()
        return self._public_run(result)

    def progress_agent(
        self,
        run_id: str,
        owner_token: str,
        stage: str,
        provider_task_id: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if not owner_token or run.get("owner_token") != owner_token or run["status"] != "running":
            raise CanvasError("进度不属于当前接手任务", code="owner_conflict", status=409)
        result = self.store.update_run(
            run_id,
            stage=stage,
            provider_task_id=self._provider_task_id(run, provider_task_id),
            evidence=evidence,
        )
        self._notify()
        return self._public_run(result)

    def reopen_review(self, run_id: str, reason: str, expected_updated_at: str) -> dict[str, Any]:
        token = self.store.reopen_review(run_id, reason, expected_updated_at)
        self._notify()
        return {"run_id": run_id, "owner_token": token}

    def review_derived(
        self,
        run_id: str,
        reason: str,
        expected_updated_at: str,
        decision: str,
        output_path: str,
        evidence: list[str],
        end_state: dict[str, Any] | None = None,
        unverified: list[str] | None = None,
    ) -> dict[str, Any]:
        """Review one actual video derivation without rewriting its rejected source."""
        with self._confirm_lock:
            run = self.store.get_run(run_id)
            previous = run.get("review")
            if run["updated_at"] != expected_updated_at:
                raise CanvasError(
                    "run changed; read it again", code="review_derived_conflict", status=409
                )
            if (
                run["status"] != "succeeded"
                or not previous
                or previous.get("decision") != "REJECT"
                or not run.get("reviewed_at")
            ):
                raise CanvasError(
                    "derived review requires a completed REJECT",
                    code="review_derived_not_ready",
                    status=409,
                )
            if run["snapshot"]["node_type"] != "video":
                raise ValueError("派生审片当前仅支持视频")
            path = self.media.resolve(output_path)
            if not path.is_relative_to(
                self.settings.output_dir(run["canvas_id"], run_id).resolve()
            ):
                raise ValueError("派生审片必须绑定本次运行目录中的新文件")
            if self.media.asset(path)["kind"] != "video":
                raise ValueError("派生审片产物必须是视频")

            def digest_file(source: Path) -> str:
                with source.open("rb") as stream:
                    return hashlib.file_digest(stream, "sha256").hexdigest()

            rejected = [previous] + [
                item["review"]
                for item in run["review_history"]
                if item["review"].get("decision") == "REJECT"
            ]
            for item in rejected:
                source = self.media.resolve(item["output_path"])
                if digest_file(source) != item["output_sha256"]:
                    raise ValueError("被拒绝的源文件发生变化，必须保留原媒体")
            before = path.stat()
            digest = digest_file(path)
            if any(
                path == Path(item["output_path"]).resolve() or digest == item["output_sha256"]
                for item in rejected
            ) or any(path == Path(item["path"]).resolve() for item in run["outputs"]):
                raise ValueError("必须提供不同路径和内容的新派生，不能重新标记被拒绝的原片")
            self._verify_video_output(str(path))
            # Probe alone can succeed on a header whose frame payload is corrupt.
            decoded = run_command(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-xerror",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                    "-f",
                    "null",
                    "-",
                ],
                timeout_s=120,
            )
            if not any(
                line.startswith("frame=")
                and line.partition("=")[2].strip().isdigit()
                and int(line.partition("=")[2]) > 0
                for line in decoded.stdout.splitlines()
            ):
                raise ValueError("派生视频未解码出有效画面")
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ) or digest_file(path) != digest:
                raise ValueError("派生文件在审片登记期间发生变化")
            for item in rejected:
                if digest_file(self.media.resolve(item["output_path"])) != item["output_sha256"]:
                    raise ValueError("被拒绝的源文件在审片登记期间发生变化")
            result = self.store.review_derived(
                run_id,
                reason,
                expected_updated_at,
                dict(
                    decision=decision,
                    output_path=str(path),
                    output_sha256=digest,
                    evidence=evidence,
                    end_state=end_state or {},
                    unverified=unverified or [],
                ),
            )
        self._notify()
        return self._public_run(result)

    def review_output(
        self,
        run_id: str,
        owner_token: str,
        decision: str,
        output_path: str,
        evidence: list[str],
        end_state: dict[str, Any] | None = None,
        unverified: list[str] | None = None,
    ) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        path = self.media.resolve(output_path)
        if not path.is_relative_to(self.settings.output_dir(run["canvas_id"], run_id).resolve()):
            raise ValueError("审片必须绑定本次运行目录中的实际产物")
        if self.media.asset(path)["kind"] != run["snapshot"]["node_type"]:
            raise ValueError("审片产物类型与任务不一致")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        review = dict(
            decision=decision,
            output_path=str(path),
            output_sha256=digest,
            evidence=evidence,
            end_state=end_state or {},
            unverified=unverified or [],
        )
        result = self.store.review_run(run_id, review, owner_token=owner_token)
        self._notify()
        return self._public_run(result)

    def _work(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=1)
            self._wake.clear()
            if self._stop.is_set():
                return
            for run in self.store.list_queued_runs():
                if self._stop.is_set():
                    return
                if run["status"] != "queued" or run.get("attention_state", "active") != "active":
                    continue
                try:
                    claimed = self.store.claim_run(run["id"], owner_token=uuid.uuid4().hex)
                except CanvasError:
                    continue
                worker = threading.Thread(
                    target=self._execute_in_worker, args=(claimed,), daemon=True
                )
                with self._execution_lock:
                    self._executions[claimed["id"]] = worker
                worker.start()

    def _execute_in_worker(self, run: dict[str, Any]) -> None:
        try:
            self._execute(run)
        finally:
            with self._execution_lock:
                self._executions.pop(run["id"], None)
            self._notify()

    def _execute(self, run: dict[str, Any]) -> None:
        task_id: str | None = None
        launched = False
        stage = "input_validation"
        remote_finished = False
        try:
            self.store.update_run(run["id"], stage=stage)
            capability = self.catalog.validate(run["snapshot"])
            if capability["execution"] != "script":
                raise ValueError("该 Skill 当前不提供本地执行入口")
            snapshot = {
                **self.media.execution_snapshot(run["snapshot"]),
                "request_id": run["request_id"],
            }
            entrypoint = Path(capability["_skill_dir"]) / capability["entrypoint"]
            output_dir = self.settings.output_dir(run["canvas_id"], run["id"])
            output_dir.mkdir(parents=True, exist_ok=True)
            internal = self.settings.data_dir / "temporary"
            internal.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="execute-", dir=internal) as folder:
                input_path = Path(folder) / "input.json"
                input_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
                command = [
                    sys.executable,
                    str(entrypoint),
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                ]
                env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
                env["PYTHONPATH"] = str(self.settings.project_root / "src")
                if os.environ.get("PYTHONPATH"):
                    env["PYTHONPATH"] += os.pathsep + os.environ["PYTHONPATH"]
                result: dict[str, Any] = {}
                # Skill scripts own provider timeouts. Streaming preserves submitted task IDs.
                with subprocess.Popen(
                    command,
                    cwd=self.settings.project_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ) as process:
                    launched = True
                    assert process.stdout is not None
                    for line in process.stdout:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if not isinstance(event, dict):
                            continue
                        if event.get("stage"):
                            new_stage = event["stage"]
                            finished = remote_finished or event.get("remote_finished") is True
                            if new_stage != stage or finished != remote_finished:
                                stage, remote_finished = new_stage, finished
                                self.store.update_run(
                                    run["id"],
                                    stage=stage,
                                    evidence={"remote_finished": remote_finished},
                                )
                                self._notify()
                        if (
                            event.get("provider_task_id")
                            and str(event["provider_task_id"]) != task_id
                        ):
                            task_id = str(event["provider_task_id"])
                            self.store.update_run(run["id"], provider_task_id=task_id)
                        if "outputs" in event or "error" in event:
                            result = event
                    code = process.wait()
                if code != 0:
                    unknown = not remote_finished and (
                        result.get("status") == "unknown" or not result
                    )
                    self.store.update_run(
                        run["id"],
                        status="unknown" if unknown else "failed",
                        error=str(result.get("error", "执行进程异常退出；确认远端状态后再继续")),
                        provider_task_id=task_id,
                        stage=stage,
                    )
                    return
                stage = "collection"
                remote_finished = True
                self.store.update_run(run["id"], stage=stage, evidence={"remote_finished": True})
                checked_outputs = self._validate_output_payload(
                    result.get("outputs", []), run["snapshot"]["node_type"]
                )
                outputs = self.media.collect_outputs(checked_outputs, run["canvas_id"], run["id"])
                self.store.update_run(
                    run["id"],
                    status="succeeded",
                    outputs=outputs,
                    provider_task_id=task_id,
                    stage="media_validation",
                )
        except Exception as exc:
            self.store.update_run(
                run["id"],
                status="unknown" if launched and not remote_finished else "failed",
                error=str(exc),
                provider_task_id=task_id,
                stage=stage,
            )
