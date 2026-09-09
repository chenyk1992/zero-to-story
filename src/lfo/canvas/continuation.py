"""Bounded, read-only checks for canvas production continuation.

The continuation record is deliberately separate from execution.  This module
only turns a persisted plan, the current canvas and existing run records into a
small hand-off summary.  It never creates a run, claims an agent or touches a
media path.  The store owns validation and persistence; the service supplies
the existing read-only ``readiness`` callback.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .graph import validate_graph

CONTINUATION_STATES = frozenset({"active", "paused"})
CONTINUATION_UNIT_STATES = frozenset({"dispatched", "result_ready", "handled", "blocked"})
CONTINUATION_EVENTS = frozenset({"Stop", "SessionStart", "SubagentStop", "Interrupt"})

# The plan is an opt-in hand-off aid, so it must remain small enough to pass
# through a hook context.  Persistence rejects values above these limits and
# the summary applies a second bound to the number of returned records.
MAX_NODE_IDS = 256
MAX_UNITS = 512
MAX_ACTIONS = 128
MAX_BLOCKED_ITEMS = 128
MAX_REASON_LENGTH = 320


def continuation_fingerprint(summary: Mapping[str, Any]) -> str:
    """Return a stable digest for repeated-stop detection.

    The digest intentionally excludes the plan revision and stop counters.  A
    run, review or unit state change therefore changes the digest, while a
    read-only GET cannot reset persisted counters as a side effect.
    """

    value = {
        key: summary.get(key)
        for key in ("status", "actions", "blocked_items", "nodes", "allow_stop", "reason")
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def public_continuation(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the public plan shape without internal stop state."""

    units: list[dict[str, Any]] = []
    raw_units = plan.get("units", [])
    if isinstance(raw_units, Sequence) and not isinstance(raw_units, (str, bytes, bytearray)):
        for raw in raw_units[:MAX_UNITS]:
            if not isinstance(raw, Mapping):
                continue
            item: dict[str, Any] = {}
            for key in (
                "unit_id",
                "agent_id",
                "node_id",
                "run_id",
                "turn_id",
                "state",
                "reason",
                "created_at",
                "updated_at",
            ):
                if key in raw and raw[key] is not None:
                    item[key] = raw[key]
            units.append(item)
    return {
        "id": plan.get("id"),
        "canvas_id": plan.get("canvas_id"),
        "session_id": plan.get("session_id"),
        "node_ids": list(plan.get("node_ids", [])),
        "authorization": plan.get("authorization"),
        "canvas_version": plan.get("canvas_version"),
        "state": plan.get("state"),
        "revision": plan.get("revision"),
        "units": units,
        "created_at": plan.get("created_at"),
        "updated_at": plan.get("updated_at"),
    }


def build_continuation_summary(
    plan: Mapping[str, Any],
    canvas: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    readiness: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a bounded continuation check without changing durable state.

    ``readiness`` is expected to be the canvas service's existing read-only
    check.  It is called only for nodes which do not already have a current
    run or an explicit continuity blocker.
    """

    plan_id = str(plan.get("id") or "")
    canvas_id = str(plan.get("canvas_id") or canvas.get("id") or "")
    session_id = str(plan.get("session_id") or "")
    node_ids = [str(value) for value in plan.get("node_ids", [])][:MAX_NODE_IDS]
    common: dict[str, Any] = {
        "continuation_id": plan_id,
        "canvas_id": canvas_id,
        "session_id": session_id,
        "canvas_version": plan.get("canvas_version"),
        "revision": plan.get("revision"),
        "actions": [],
        "blocked_items": [],
        "nodes": [],
        "allow_stop": True,
        "reason": "",
    }

    if plan.get("state") == "paused":
        common.update(
            {
                "status": "paused",
                "allow_stop": True,
                "reason": _short_reason(
                    plan.get("pause_reason") or "接续计划已暂停，恢复前不领取或提交新的工作单元"
                ),
            }
        )
        return common

    try:
        graph = validate_graph(canvas.get("graph", {}))
    except Exception as exc:
        # A canvas saved by an older version can still be inspected.  Keep the
        # failure local to this plan and do not expose graph contents.
        common["status"] = "blocked"
        common["allow_stop"] = True
        common["reason"] = _short_reason(f"当前画布无法检查：{exc}")
        common["blocked_items"] = [{"reason": common["reason"], "scope": "canvas"}]
        return common

    graph_nodes = {str(node.get("id")): node for node in graph.get("nodes", [])}
    run_list = [run for run in runs if isinstance(run, Mapping)]
    units = _normal_units(plan.get("units"))
    actions: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []
    node_records: list[dict[str, Any]] = []

    # A completed child unit is the first thing the host should handle.  This
    # priority keeps an earlier result from being mistaken for an idle plan.
    for unit in units:
        if unit.get("state") == "result_ready":
            action = _action(
                "handle_unit",
                reason="先处理已返回的执行单元结果；只使用已有授权范围",
                unit=unit,
            )
            actions.append(action)
        elif unit.get("state") == "blocked":
            item: dict[str, Any] = {
                "unit_id": unit.get("unit_id"),
                "reason": _short_reason(unit.get("reason") or "执行单元被标记为阻塞，需要人工处理"),
            }
            _copy_optional(item, unit, "agent_id")
            _copy_optional(item, unit, "node_id")
            blocked_items.append(item)

    for node_id in node_ids:
        node = graph_nodes.get(node_id)
        node_runs = [run for run in run_list if run.get("node_id") == node_id]
        bound_unit = next(
            (
                unit
                for unit in reversed(units)
                if unit.get("node_id") == node_id and unit.get("run_id")
            ),
            None,
        )
        latest = (
            next((run for run in node_runs if run.get("id") == bound_unit["run_id"]), None)
            if bound_unit
            else _latest_run(node_runs)
        )
        node_units = [unit for unit in units if unit.get("node_id") in {None, node_id}]
        explicit_block = next((unit for unit in node_units if unit.get("state") == "blocked"), None)
        dependent_block = (
            None if node is None else _dependency_block(node_id, node, graph, run_list)
        )

        record: dict[str, Any] = {"node_id": node_id, "state": "blocked"}
        if latest is not None:
            record["run_id"] = latest.get("id")
            record["run_status"] = latest.get("status")
            review_decision = _review_decision(latest.get("review"))
            if review_decision is not None:
                record["review"] = review_decision

        # A successful and accepted run remains complete even when the draft
        # later changes.  Continuation never creates a replacement run merely
        # because the current draft no longer matches that frozen snapshot.
        # An explicit blocked unit still belongs in blocked_items, but it does
        # not turn an already ACCEPTed run back into review work.  For every
        # other successful result, the explicit blocker wins so the same node
        # is not offered a fresh review/prepare/execute action.
        if latest is not None and latest.get("status") == "succeeded":
            decision = _review_decision(latest.get("review"))
            if decision == "ACCEPT":
                record["state"] = "complete"
                record["reason"] = "已有运行已通过 ACCEPT"
            elif explicit_block is not None:
                record["state"] = "blocked"
                record["reason"] = _short_reason(
                    explicit_block.get("reason") or "该节点的执行单元被明确标记为阻塞"
                )
                blocked_items.append(
                    {
                        "node_id": node_id,
                        "unit_id": explicit_block.get("unit_id"),
                        "reason": record["reason"],
                    }
                )
            elif decision is None:
                record["state"] = "actionable"
                action = _action(
                    "review",
                    node_id=node_id,
                    run_id=latest.get("id"),
                    reason="先审查实际产物并记录 ACCEPT/REJECT/INCONCLUSIVE",
                )
                actions.append(action)
                record["reason"] = action["reason"]
            else:
                record["state"] = "blocked"
                record["reason"] = _short_reason(
                    f"该运行的审查结果为 {decision}，需要人工处理后才能继续"
                )
                blocked_items.append(
                    {
                        "node_id": node_id,
                        "run_id": latest.get("id"),
                        "reason": record["reason"],
                    }
                )
        elif latest is not None and latest.get("status") in {
            "queued",
            "pending_agent",
            "running",
        }:
            record["state"] = "waiting"
            if latest.get("status") == "pending_agent":
                action = _action(
                    "claim_agent",
                    node_id=node_id,
                    run_id=latest.get("id"),
                    reason="等待具备当前能力的宿主领取 pending_agent 单元",
                )
                actions.append(action)
                record["reason"] = action["reason"]
            else:
                record["reason"] = "已有执行正在排队或运行，等待它返回实际结果"
        elif latest is not None and latest.get("status") in {
            "unknown",
            "failed",
            "cancelled",
        }:
            record["state"] = "blocked"
            record["reason"] = _short_reason(
                f"运行 {latest.get('status')}，先核实或处理该运行，不能自动重新生成"
            )
            blocked_items.append(
                {
                    "node_id": node_id,
                    "run_id": latest.get("id"),
                    "reason": record["reason"],
                }
            )
        elif bound_unit is not None and latest is None:
            record["state"] = "blocked"
            record["reason"] = "已绑定的运行记录不可用，先核实原请求，不能重新生成"
            blocked_items.append(
                {"node_id": node_id, "run_id": bound_unit["run_id"], "reason": record["reason"]}
            )
        elif explicit_block is not None:
            record["state"] = "blocked"
            record["reason"] = _short_reason(
                explicit_block.get("reason") or "该节点的执行单元被明确标记为阻塞"
            )
            blocked_items.append(
                {
                    "node_id": node_id,
                    "unit_id": explicit_block.get("unit_id"),
                    "reason": record["reason"],
                }
            )
        elif dependent_block is not None:
            record["state"] = "blocked"
            record["reason"] = dependent_block["reason"]
            blocked_items.append({"node_id": node_id, **dependent_block})
        elif any(unit.get("state") == "dispatched" for unit in node_units):
            record["state"] = "waiting"
            pending = next(unit for unit in node_units if unit.get("state") == "dispatched")
            record["reason"] = "执行单元已派发，等待 SubagentStop 后处理结果"
            _copy_optional(record, pending, "unit_id")
        elif node is None:
            record["state"] = "blocked"
            record["reason"] = "范围中的节点已不存在，需要人工更新接续范围"
            blocked_items.append({"node_id": node_id, "reason": record["reason"]})
        else:
            try:
                ready = dict(readiness(node_id))
            except Exception as exc:
                ready = {"ready": False, "reason": str(exc)}
            if ready.get("ready") is True:
                record["state"] = "actionable"
                action = _action(
                    "execute_after_authorization_check",
                    node_id=node_id,
                    reason="节点已具备输入，执行前再次核对已有授权；本检查不会自动生成",
                )
                actions.append(action)
                record["reason"] = action["reason"]
            else:
                # Missing prompt/materials are preparation work.  It is useful
                # to expose that as actionable preparation instead of marking
                # the node complete or asking a hook to wait forever.
                record["state"] = "actionable"
                reason = _short_reason(ready.get("reason") or "输入尚未齐全，需要先准备")
                action = _action("prepare", node_id=node_id, reason=f"先准备当前节点输入：{reason}")
                actions.append(action)
                record["reason"] = action["reason"]

        node_records.append(record)

    # Keep the response deterministic and bounded even if a caller supplied a
    # large but valid plan.  The persisted records remain available for the
    # explicit unit API; the check response is intentionally concise.
    actions = actions[:MAX_ACTIONS]
    blocked_items = blocked_items[:MAX_BLOCKED_ITEMS]
    common["actions"] = actions
    common["blocked_items"] = blocked_items
    common["nodes"] = node_records[:MAX_NODE_IDS]

    has_waiting = any(record.get("state") == "waiting" for record in node_records) or any(
        unit.get("state") == "dispatched" for unit in units
    )
    has_blocked = bool(blocked_items) or any(
        record.get("state") == "blocked" for record in node_records
    )
    all_nodes_complete = bool(node_records) and all(
        record.get("state") == "complete" for record in node_records
    )
    all_units_handled = all(unit.get("state") == "handled" for unit in units)

    actionable_types = {
        "handle_unit",
        "claim_agent",
        "prepare",
        "execute_after_authorization_check",
        "review",
    }
    has_actionable_action = any(
        isinstance(action, Mapping) and action.get("type") in actionable_types for action in actions
    )
    if has_actionable_action:
        status = "actionable"
        first_action = next(
            (
                action
                for action in actions
                if isinstance(action, Mapping) and action.get("type") in actionable_types
            ),
            actions[0],
        )
        reason = first_action.get("reason") or "有可交接的下一步"
        allow_stop = False
    elif has_waiting:
        status = "waiting"
        reason = "等待宿主长等待或已验证原线程 heartbeat；当前不自动声称后台唤醒"
        allow_stop = False
    elif has_blocked:
        # Independent ready nodes already make a plan actionable because their
        # actions are present above.  If no such action remains, stopping is
        # safe while the blocked item stays visible for a later host.
        status = "blocked"
        reason = blocked_items[0].get("reason") if blocked_items else "范围中有节点被阻塞"
        allow_stop = True
    elif all_nodes_complete and all_units_handled:
        status = "complete"
        reason = "范围内节点均已接受，接续单元也已处理"
        allow_stop = True
    else:
        status = "blocked"
        reason = "接续状态需要人工接手"
        allow_stop = True

    common.update({"status": status, "allow_stop": allow_stop, "reason": _short_reason(reason)})
    return common


def _normal_units(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[dict[str, Any]] = []
    for raw in value[:MAX_UNITS]:
        if not isinstance(raw, Mapping):
            continue
        item = {
            key: raw.get(key)
            for key in (
                "unit_id",
                "agent_id",
                "node_id",
                "run_id",
                "state",
                "reason",
                "created_at",
                "updated_at",
            )
            if raw.get(key) is not None
        }
        result.append(item)
    return result


def _latest_run(runs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    if not runs:
        return None
    return max(
        runs,
        key=lambda run: (
            str(run.get("created_at") or run.get("updated_at") or ""),
            str(run.get("id") or ""),
        ),
    )


def _review_decision(review: Any) -> str | None:
    if isinstance(review, Mapping):
        decision = review.get("decision")
        if isinstance(decision, str):
            value = decision.upper()
            if value in {"ACCEPT", "REJECT", "INCONCLUSIVE"}:
                return value
    return None


def _dependency_block(
    node_id: str,
    node: Mapping[str, Any],
    graph: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Find an unaccepted explicit or tail continuity dependency."""

    graph_nodes = {str(item.get("id")): item for item in graph.get("nodes", [])}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if isinstance(edge, Mapping) and edge.get("target") == node_id
    ]
    dependencies: list[tuple[str, str | None, bool]] = []
    for edge in edges:
        source_id = edge.get("source")
        if not isinstance(source_id, str):
            continue
        # last_frame is an input slot, not proof that the source is a tail.
        # Actual continuity edges declare require_accept/source_run_id.
        if edge.get("require_accept"):
            dependencies.append((source_id, _optional_string(edge.get("source_run_id")), True))

    data = node.get("data") if isinstance(node.get("data"), Mapping) else {}
    dependencies.extend(_planned_tail_dependencies(data.get("planned_inputs")))
    planned_tail = data.get("last_frame_source")
    if isinstance(planned_tail, str) and planned_tail.strip():
        dependencies.append((planned_tail.strip(), None, True))

    for source_id, source_run_id, _required in dependencies:
        if source_id.startswith("__panel__:"):
            panel_id = source_id.split(":", 1)[1]
            matches = []
            for candidate_id, candidate in graph_nodes.items():
                candidate_data = (
                    candidate.get("data") if isinstance(candidate.get("data"), Mapping) else {}
                )
                if candidate.get("type") == "video" and candidate_data.get("panel_id") == panel_id:
                    matches.append(candidate_id)
            if len(matches) != 1:
                return {
                    "source_node_id": panel_id,
                    "source_run_id": source_run_id,
                    "reason": _short_reason(f"尾帧依赖未能按实际 panel_id 唯一定位：{panel_id}"),
                }
            source_id = matches[0]
        source_runs = [run for run in runs if run.get("node_id") == source_id]
        selected = None
        if source_run_id is not None:
            selected = next((run for run in source_runs if run.get("id") == source_run_id), None)
        else:
            selected = _latest_run(source_runs)
        if selected is None or selected.get("status") != "succeeded":
            return {
                "source_node_id": source_id,
                "source_run_id": source_run_id,
                "reason": _short_reason(f"前段 {source_id} 尚未有可采用的 ACCEPT 产物"),
            }
        if _review_decision(selected.get("review")) != "ACCEPT":
            return {
                "source_node_id": source_id,
                "source_run_id": selected.get("id") or source_run_id,
                "reason": _short_reason(f"前段 {source_id} 尚未 ACCEPT，先采用实际产物再继续"),
            }
    return None


def _planned_tail_dependencies(value: Any) -> list[tuple[str, str | None, bool]]:
    result: list[tuple[str, str | None, bool]] = []
    if isinstance(value, Mapping):
        entries: list[tuple[Any, Any]] = list(value.items())
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        entries = [(None, item) for item in value]
    else:
        return result
    for key, raw in entries:
        marker = str(key or "")
        item = raw if isinstance(raw, Mapping) else {}
        marker = " ".join(
            [
                marker,
                str(item.get("handle") or ""),
                str(item.get("target_handle") or ""),
                str(item.get("slot") or ""),
                str(item.get("kind") or ""),
                str(item.get("semantic_usage") or ""),
                str(raw) if isinstance(raw, str) else "",
            ]
        ).lower()
        if not any(token in marker for token in ("tail", "last_frame", "last frame", "尾帧")):
            continue
        source = next(
            (
                item.get(name)
                for name in ("source_node_id", "node_id", "source_id", "source")
                if isinstance(item.get(name), str) and item.get(name).strip()
            ),
            None,
        )
        if source is None and isinstance(raw, str) and raw.strip():
            raw_source = raw.strip()
            if raw_source.lower().startswith("tail:"):
                source = "__panel__:" + raw_source.split(":", 1)[1].strip()
            else:
                source = raw_source
        if not isinstance(source, str) or not source.strip():
            continue
        run_id = next(
            (
                item.get(name)
                for name in ("source_run_id", "run_id", "source_run")
                if isinstance(item.get(name), str) and item.get(name).strip()
            ),
            None,
        )
        result.append((source.strip(), run_id, True))
    return result


def _action(
    action_type: str,
    *,
    reason: str,
    node_id: str | None = None,
    run_id: Any = None,
    unit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {"type": action_type, "reason": _short_reason(reason)}
    if node_id is not None:
        value["node_id"] = node_id
    if run_id is not None:
        value["run_id"] = run_id
    if unit is not None:
        for key in ("unit_id", "agent_id", "node_id", "run_id"):
            if key in unit and unit[key] is not None:
                value[key] = unit[key]
    return value


def _copy_optional(target: dict[str, Any], source: Mapping[str, Any], key: str) -> None:
    if source.get(key) is not None:
        target[key] = source[key]


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _short_reason(value: Any) -> str:
    text = str(value or "需要人工接手")
    return text if len(text) <= MAX_REASON_LENGTH else text[: MAX_REASON_LENGTH - 1] + "…"
