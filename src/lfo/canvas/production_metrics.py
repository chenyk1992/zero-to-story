"""Evidence-based, read-only production metrics for a scoped Canvas workflow.

The module deliberately consumes public run/event/continuation records and
does not read the database itself. Missing milestones stay unknown; in
particular, mutable ``updated_at`` and legacy ``stage_updated_at`` fallbacks
are never used as timing evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RUN_STATUSES = (
    "queued",
    "pending_agent",
    "running",
    "succeeded",
    "failed",
    "unknown",
    "cancelled",
)
_ATTENTION_STATES = ("active", "paused", "abandoned")
_REVIEW_DECISIONS = ("ACCEPT", "REJECT", "INCONCLUSIVE")
_STAGE_LABELS = {
    "unknown": "原任务状态待核实",
    "queued": "排队中",
    "pending_agent": "等待 Agent 接手",
    "input_validation": "准备输入",
    "reference_upload": "上传参考素材",
    "upload": "上传素材",
    "submit": "提交生成",
    "generation": "生成中",
    "collection": "回收结果",
    "media_validation": "检查媒体",
}
_TIMING_PHASES = (
    "queue",
    "preparation",
    "upload",
    "submission",
    "generation",
    "collection_review",
    "review",
)


def summarize_production(
    runs: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    *,
    canvas_id: str | None = None,
    node_ids: Iterable[str] | None = None,
    continuation: Mapping[str, Any] | None = None,
    blockers: Iterable[Mapping[str, Any]] | None = None,
    edit_manifest: Mapping[str, Any] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Summarize one Canvas and optional node scope from observed evidence.

    Args:
        runs: Current public run records for one Canvas.
        events: Complete or partial durable run-event history. Every event is
            filtered again by selected run id and Canvas id.
        canvas_id: Optional hard Canvas boundary for callers that may pass a
            wider run/event page.
        node_ids: Optional component scope. When a continuation is supplied,
            its node scope intersects this scope and can never widen it.
        continuation: Optional public continuation record. Only explicit
            pause state/reason and explicitly blocked units are surfaced.
        blockers: Optional explicit blockers supplied by an owning service.
            Each item needs a scoped node_id and a non-empty reason. Timings
            are counted only for kind ``resource_wait`` with explicit start
            and end timestamps.
        edit_manifest: A parsed, actual edit manifest. Only an explicit
            ``segments`` array from a versioned edit manifest yields segment
            and accepted-source counts.
        now: Clock value for still-open intervals. Defaults to current UTC.

    Returns a JSON-safe object with counts, evidence-backed elapsed spans,
    phase timings, blocker descriptions, and provenance. This function never
    infers retries/replacements, model compute time, or an ETA.
    """

    as_of = _parse_time(now) if now is not None else datetime.now(UTC)
    if as_of is None:
        as_of = datetime.now(UTC)
    allowed_nodes = _scope_nodes(node_ids, continuation)
    scoped_runs = _filter_runs(runs, canvas_id, allowed_nodes)
    run_by_id = {str(run["id"]): run for run in scoped_runs if _nonempty(run.get("id"))}
    scoped_run_ids = set(run_by_id)
    scoped_events = _filter_events(events, scoped_run_ids, canvas_id)
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in scoped_events:
        events_by_run[str(event["run_id"])].append(event)

    status_counts = Counter(_status(run.get("status")) for run in scoped_runs)
    attention_counts = Counter(_attention(run.get("attention_state")) for run in scoped_runs)
    review_counts: Counter[str] = Counter()
    for run in scoped_runs:
        review = run.get("review")
        decision = review.get("decision") if isinstance(review, Mapping) else None
        if decision in _REVIEW_DECISIONS:
            review_counts[str(decision)] += 1
        else:
            review_counts[
                "pending" if _status(run.get("status")) == "succeeded" else "not_ready"
            ] += 1

    stage_counts: Counter[str] = Counter()
    for run in scoped_runs:
        status = _status(run.get("status"))
        stage = run.get("stage")
        if status in {"queued", "pending_agent"}:
            stage_counts[status] += 1
        elif status == "unknown":
            stage_counts["unknown"] += 1
        elif status == "running" and _nonempty(stage):
            stage_counts[str(stage)] += 1

    blocker_rows = _collect_blockers(continuation, blockers, allowed_nodes)
    run_timing = {
        run_id: _run_timings(run, events_by_run.get(run_id, []), as_of)
        for run_id, run in run_by_id.items()
    }
    timeline = _timeline_elapsed(scoped_runs, run_timing, as_of)
    task_time = _cumulative_task_time(run_timing)
    phase_metrics = {phase: _aggregate_timing(phase, run_timing) for phase in _TIMING_PHASES}
    phase_metrics["resource_wait"] = _resource_wait_metric(blocker_rows)

    summary = {
        "as_of": _iso(as_of),
        "canvas_id": canvas_id,
        "scope_node_ids": sorted(allowed_nodes) if allowed_nodes is not None else None,
        "run_counts": {
            "total": _count_metric(
                len(scoped_runs), [f"run:{run_id}" for run_id in sorted(scoped_run_ids)]
            ),
            "by_status": _counter_metrics(status_counts, _RUN_STATUSES, scoped_runs, "status"),
            "by_attention": _counter_metrics(
                attention_counts, _ATTENTION_STATES, scoped_runs, "attention_state"
            ),
        },
        "review_counts": _counter_metrics(
            review_counts, (*_REVIEW_DECISIONS, "pending", "not_ready"), scoped_runs, "review"
        ),
        "current_stages": [
            {
                "stage": stage,
                "label": _STAGE_LABELS.get(stage, stage.replace("_", " ")),
                "count": count,
            }
            for stage, count in sorted(stage_counts.items())
        ],
        "continuation": _continuation_state(continuation, allowed_nodes),
        "blockers": blocker_rows,
        "timings": {
            "timeline_elapsed": timeline,
            "cumulative_task_time": task_time,
            "phases": phase_metrics,
        },
        "production_counts": _production_counts(
            edit_manifest, scoped_runs, allowed_nodes, canvas_id
        ),
    }
    return summary


def _scope_nodes(
    node_ids: Iterable[str] | None, continuation: Mapping[str, Any] | None
) -> set[str] | None:
    requested = (
        {str(value) for value in node_ids if _nonempty(value)} if node_ids is not None else None
    )
    continuation_nodes = None
    if isinstance(continuation, Mapping) and isinstance(continuation.get("node_ids"), Sequence):
        continuation_nodes = {str(value) for value in continuation["node_ids"] if _nonempty(value)}
    if requested is not None and continuation_nodes is not None:
        return requested & continuation_nodes
    return requested if requested is not None else continuation_nodes


def _filter_runs(
    runs: Iterable[Mapping[str, Any]], canvas_id: str | None, node_ids: set[str] | None
) -> list[dict[str, Any]]:
    result = []
    for value in runs:
        if not isinstance(value, Mapping) or not _nonempty(value.get("id")):
            continue
        if canvas_id is not None and value.get("canvas_id") != canvas_id:
            continue
        if node_ids is not None and value.get("node_id") not in node_ids:
            continue
        result.append(dict(value))
    return result


def _filter_events(
    events: Iterable[Mapping[str, Any]], run_ids: set[str], canvas_id: str | None
) -> list[dict[str, Any]]:
    result = []
    for value in events:
        if not isinstance(value, Mapping) or not _nonempty(value.get("run_id")):
            continue
        run_id = str(value["run_id"])
        if run_id not in run_ids:
            continue
        if canvas_id is not None and value.get("canvas_id") != canvas_id:
            continue
        timestamp = _parse_time(value.get("created_at"))
        if timestamp is None:
            continue
        item = dict(value)
        item["_time"] = timestamp
        result.append(item)
    return sorted(result, key=lambda item: (item["_time"], int(item.get("id") or 0)))


def _run_timings(
    run: Mapping[str, Any], events: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    run_id = str(run.get("id", ""))
    status = _status(run.get("status"))
    created = _parse_time(run.get("created_at"))
    claims = [event for event in events if event.get("event_type") == "run.claimed"]
    claim = claims[0]["_time"] if claims else None
    status_rows = _status_timeline(events)
    terminal = _last_status_time(status_rows, status)
    if status in {"queued", "pending_agent", "running", "unknown"}:
        terminal = now
    if terminal is None and status == "succeeded":
        # A completed review is explicit evidence that generation had already
        # ended, although it does not reveal the generation completion time.
        terminal = _parse_time(run.get("reviewed_at"))
    project_end = terminal
    if status == "succeeded":
        review_ends = [
            event["_time"]
            for event in events
            if event.get("event_type") in {"review.recorded", "review.derived_recorded"}
        ]
        reviewed_at = _parse_time(run.get("reviewed_at"))
        if reviewed_at is not None:
            review_ends.append(reviewed_at)
        if review_ends:
            latest_review = max(review_ends)
            project_end = (
                max(project_end, latest_review) if project_end is not None else latest_review
            )

    queue = _duration_metric(
        created,
        claim,
        source=[
            f"run:{run_id}:created_at",
            *([f"event:{claims[0].get('id')}:run.claimed"] if claims else []),
        ],
        label="创建到领取的排队跨度",
        ongoing_start=created if claim is None and status in {"queued", "pending_agent"} else None,
        now=now,
        unknown_note="缺少创建或领取时间事件",
    )

    stage_events = _stage_timeline(events, claim)
    phase_durations: dict[str, dict[str, Any]] = {}
    phase_durations["preparation"] = _stage_duration(
        stage_events,
        start_stages={"input_validation"},
        end_stages={"reference_upload", "upload", "submit"},
        run_id=run_id,
        phase="preparation",
        events=events,
    )
    phase_durations["upload"] = _stage_duration(
        stage_events,
        start_stages={"reference_upload", "upload"},
        end_stages={"submit"},
        run_id=run_id,
        phase="upload",
        events=events,
    )
    phase_durations["submission"] = _stage_duration(
        stage_events,
        start_stages={"submit"},
        end_stages={"generation"},
        run_id=run_id,
        phase="submission",
        events=events,
    )
    phase_durations["generation"] = _stage_duration(
        stage_events,
        start_stages={"generation"},
        end_stages={"collection"},
        run_id=run_id,
        phase="generation",
        events=events,
    )
    phase_durations["collection_review"] = _stage_duration(
        stage_events,
        start_stages={"collection"},
        end_stages={"media_validation"},
        run_id=run_id,
        phase="collection_review",
        terminal_events=events,
        events=events,
    )
    phase_durations["queue"] = queue
    phase_durations["review"] = _review_duration(events, run)

    task_segments = _execution_segments(events, status, now)
    task_seconds = sum(
        segment["seconds"] for segment in task_segments if segment["seconds"] is not None
    )
    task_unknown = not task_segments or any(segment["seconds"] is None for segment in task_segments)
    task_has_observation = any(segment["seconds"] is not None for segment in task_segments)
    task = {
        "state": "partial"
        if task_unknown and task_has_observation
        else "unknown"
        if task_unknown
        else "observed",
        "seconds": task_seconds if task_has_observation else None,
        "observed_runs": 1 if task_has_observation else 0,
        "unknown_runs": 1 if task_unknown else 0,
        "sources": [source for segment in task_segments for source in segment["sources"]],
        "note": "累计领取后运行跨度；并行单元分别计时，未知状态之间不补算。",
    }
    return {
        "run_id": run_id,
        "status": status,
        "created": created,
        "created_source": f"run:{run_id}:created_at" if created is not None else None,
        "end": project_end,
        "end_source": "as_of"
        if status in {"queued", "pending_agent", "running", "unknown"}
        else _terminal_source(events, status, run),
        "phases": phase_durations,
        "task_time": task,
    }


def _status_timeline(events: list[dict[str, Any]]) -> list[tuple[str, datetime, dict[str, Any]]]:
    rows = []
    for event in events:
        payload = event.get("payload")
        status = payload.get("status") if isinstance(payload, Mapping) else None
        if _nonempty(status):
            rows.append((str(status), event["_time"], event))
    return rows


def _last_status_time(
    rows: list[tuple[str, datetime, dict[str, Any]]], status: str
) -> datetime | None:
    matches = [timestamp for current, timestamp, _event in rows if current == status]
    return matches[-1] if matches else None


def _terminal_source(
    events: list[dict[str, Any]], status: str, run: Mapping[str, Any]
) -> str | None:
    if status == "unknown":
        rows = [
            event
            for event in events
            if isinstance(event.get("payload"), Mapping)
            and event["payload"].get("status") == "unknown"
        ]
        if rows:
            return f"event:{rows[-1].get('id')}:{rows[-1].get('event_type')}"
    rows = [
        event
        for event in events
        if isinstance(event.get("payload"), Mapping) and event["payload"].get("status") == status
    ]
    if rows:
        return f"event:{rows[-1].get('id')}:{rows[-1].get('event_type')}"
    if _parse_time(run.get("reviewed_at")) is not None:
        return f"run:{run.get('id')}:reviewed_at"
    return None


def _stage_timeline(events: list[dict[str, Any]], claim: datetime | None) -> list[dict[str, Any]]:
    timeline = []
    for event in events:
        if claim is not None and event["_time"] < claim:
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        stage = payload.get("stage")
        changed = payload.get("changed")
        stage_changed = isinstance(changed, Mapping) and _nonempty(changed.get("stage"))
        if not _nonempty(stage):
            continue
        # Run creation stores a default stage before execution. Only a claim or
        # a durable changed.stage event confirms a work-stage boundary.
        if event.get("event_type") != "run.claimed" and not stage_changed:
            continue
        if timeline and timeline[-1]["stage"] == stage:
            continue
        timeline.append(
            {
                "stage": str(stage),
                "time": event["_time"],
                "event_id": event.get("id"),
                "event_type": event.get("event_type"),
            }
        )
    return timeline


def _stage_duration(
    timeline: list[dict[str, Any]],
    *,
    start_stages: set[str],
    end_stages: set[str],
    run_id: str,
    phase: str,
    terminal_events: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    starts = [entry for entry in timeline if entry["stage"] in start_stages]
    if starts:
        start = starts[0]
        end = next(
            (
                entry
                for entry in timeline
                if entry["time"] > start["time"] and entry["stage"] in end_stages
            ),
            None,
        )
        if end is not None:
            seconds = _seconds(start["time"], end["time"])
            if seconds is not None:
                if _unknown_barrier(events or [], start["time"], end["time"]):
                    return _unknown_timing(f"{phase} 阶段跨过 unknown/重启边界。")
                return _timing_observed(
                    seconds,
                    [
                        f"event:{start['event_id']}:{start['stage']}",
                        f"event:{end['event_id']}:{end['stage']}",
                    ],
                )
        if phase == "collection_review":
            terminal = _collection_end_event(terminal_events or [], start["time"])
            if terminal is not None:
                seconds = _seconds(start["time"], terminal["_time"])
                if seconds is not None:
                    if _unknown_barrier(events or [], start["time"], terminal["_time"]):
                        return _unknown_timing(f"{phase} 阶段跨过 unknown/重启边界。")
                    return _timing_observed(
                        seconds,
                        [
                            f"event:{start['event_id']}:collection",
                            f"event:{terminal.get('id')}:{terminal.get('event_type')}",
                        ],
                    )
    return _unknown_timing(f"缺少 {phase} 阶段的完整事件边界（run {run_id}）")


def _unknown_barrier(events: list[dict[str, Any]], start: datetime, end: datetime) -> bool:
    for event in events:
        if not (start < event["_time"] < end):
            continue
        payload = event.get("payload")
        if isinstance(payload, Mapping) and payload.get("status") == "unknown":
            return True
    return False


def _collection_end_event(events: list[dict[str, Any]], start: datetime) -> dict[str, Any] | None:
    for event in events:
        if event["_time"] <= start:
            continue
        payload = event.get("payload")
        status = payload.get("status") if isinstance(payload, Mapping) else None
        if status in {"succeeded", "failed", "unknown", "cancelled"}:
            return event
    return None


def _review_duration(events: list[dict[str, Any]], run: Mapping[str, Any]) -> dict[str, Any]:
    starts = [event for event in events if event.get("event_type") == "review.claimed"]
    ends = [event for event in events if event.get("event_type") == "review.recorded"]
    if starts and ends:
        start = starts[-1]
        end = next((event for event in ends if event["_time"] >= start["_time"]), None)
        if end is not None:
            seconds = _seconds(start["_time"], end["_time"])
            if seconds is not None:
                return _timing_observed(
                    seconds,
                    [
                        f"event:{start.get('id')}:review.claimed",
                        f"event:{end.get('id')}:review.recorded",
                    ],
                    note="审查观察跨度，包含人工等待；不代表模型处理耗时。",
                )
    return _unknown_timing("缺少审查开始和完成事件；reviewed_at 只表示完成时点。")


def _execution_segments(
    events: list[dict[str, Any]], current_status: str, now: datetime
) -> list[dict[str, Any]]:
    segments = []
    running_start: tuple[datetime, str] | None = None
    for event in events:
        payload = event.get("payload")
        status = payload.get("status") if isinstance(payload, Mapping) else None
        if (
            event.get("event_type") == "run.claimed"
            and status == "running"
            and running_start is None
        ):
            running_start = (event["_time"], f"event:{event.get('id')}:run.claimed")
            continue
        if running_start is not None and status in {"unknown", "failed", "succeeded", "cancelled"}:
            seconds = _seconds(running_start[0], event["_time"])
            segments.append(
                {
                    "seconds": seconds,
                    "sources": [
                        running_start[1],
                        f"event:{event.get('id')}:{event.get('event_type')}",
                    ]
                    if seconds is not None
                    else [running_start[1]],
                }
            )
            running_start = None
    if running_start is not None:
        if current_status == "running":
            seconds = _seconds(running_start[0], now)
            segments.append({"seconds": seconds, "sources": [running_start[1], "as_of"]})
        else:
            # A process restart or incomplete event page can hide the stop
            # boundary. Do not stretch an active interval to a later snapshot.
            segments.append({"seconds": None, "sources": [running_start[1]]})
    elif current_status == "running":
        # The run may have been claimed before this event page begins.
        segments.append({"seconds": None, "sources": []})
    return segments


def _timeline_elapsed(
    runs: list[dict[str, Any]], timings: Mapping[str, Mapping[str, Any]], now: datetime
) -> dict[str, Any]:
    starts = [item["created"] for item in timings.values() if item.get("created") is not None]
    ends = [item["end"] for item in timings.values() if item.get("end") is not None]
    missing = len(starts) != len(runs) or len(ends) != len(runs)
    if not starts or not ends:
        return _unknown_timing("缺少所选范围内完整的创建和结束时间证据。")
    start = min(starts)
    end = max(ends)
    seconds = _seconds(start, end)
    if seconds is None:
        return _unknown_timing("事件时间顺序无效，无法计算时间线跨度。")
    sources = sorted(
        {
            source
            for timing in timings.values()
            for source in (timing.get("created_source"), timing.get("end_source"))
            if source
        }
    )
    metric = _timing_observed(seconds, sources)
    metric["state"] = "partial" if missing else "observed"
    metric["observed_runs"] = len(ends)
    metric["unknown_runs"] = max(0, len(runs) - len(ends))
    metric["note"] = (
        "所选范围从最早创建到最晚已观察结束/当前进行时点的日历跨度；并行任务只计算一次。"
    )
    return metric


def _cumulative_task_time(timings: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observed = []
    unknown = 0
    sources: list[str] = []
    for timing in timings.values():
        metric = timing["task_time"]
        if metric["seconds"] is not None:
            observed.append(int(metric["seconds"]))
            sources.extend(metric["sources"])
        if metric["seconds"] is None or metric["unknown_runs"]:
            unknown += 1
    if not observed:
        return _unknown_timing("缺少领取和结束事件边界。", unknown_runs=unknown)
    return {
        "state": "partial" if unknown else "observed",
        "seconds": sum(observed),
        "observed_runs": len(observed),
        "unknown_runs": unknown,
        "sources": sorted(set(sources)),
        "note": "已观察到的各单元领取后运行跨度之和；并行单元分别累计，未知间隔不补算。",
    }


def _aggregate_timing(phase: str, timings: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observed: list[int] = []
    unknown = 0
    sources: list[str] = []
    for timing in timings.values():
        metric = timing["phases"][phase]
        if metric["seconds"] is None:
            unknown += 1
        else:
            observed.append(int(metric["seconds"]))
            sources.extend(metric["sources"])
    if not observed:
        return _unknown_timing("缺少该阶段的完整边界事件。", unknown_runs=unknown)
    result = {
        "state": "partial" if unknown else "observed",
        "seconds": sum(observed),
        "observed_runs": len(observed),
        "unknown_runs": unknown,
        "sources": sorted(set(sources)),
        "note": f"{phase}阶段在可核实单元中的观察跨度累计；包含提供方等待，不等于纯计算时间。",
    }
    if phase == "review":
        result["note"] = "审查观察跨度累计，可能包含人工等待；不代表模型处理耗时。"
    return result


def _resource_wait_metric(blockers: list[dict[str, Any]]) -> dict[str, Any]:
    observed = []
    unknown = 0
    sources = []
    for blocker in blockers:
        if blocker.get("kind") != "resource_wait":
            continue
        start = _parse_time(blocker.get("started_at"))
        end = _parse_time(blocker.get("ended_at"))
        if start is None or end is None:
            unknown += 1
            continue
        seconds = _seconds(start, end)
        if seconds is None:
            unknown += 1
            continue
        observed.append(seconds)
        sources.append(str(blocker.get("source") or f"blocker:{blocker.get('node_id')}"))
    if not observed:
        return _unknown_timing("没有明确记录的资源等待起止事件。", unknown_runs=unknown)
    return {
        "state": "partial" if unknown else "observed",
        "seconds": sum(observed),
        "observed_runs": len(observed),
        "unknown_runs": unknown,
        "sources": sorted(set(sources)),
        "note": "仅累计显式记录了开始和结束时间的资源等待。",
    }


def _collect_blockers(
    continuation: Mapping[str, Any] | None,
    blockers: Iterable[Mapping[str, Any]] | None,
    allowed_nodes: set[str] | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(continuation, Mapping):
        units = continuation.get("units")
        if isinstance(units, Sequence) and not isinstance(units, (str, bytes)):
            for unit in units:
                if not isinstance(unit, Mapping) or unit.get("state") != "blocked":
                    continue
                node_id = unit.get("node_id")
                reason = unit.get("reason")
                if _in_scope(node_id, allowed_nodes) and _nonempty(reason):
                    result.append(
                        {
                            "node_id": node_id,
                            "reason": str(reason),
                            "kind": "continuation",
                            "source": f"continuation:{continuation.get('id')}",
                        }
                    )
        summary = continuation.get("summary")
        if isinstance(summary, Mapping):
            for key in ("blocked_items", "nodes"):
                values = summary.get(key)
                if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                    continue
                for item in values:
                    if not isinstance(item, Mapping):
                        continue
                    if key == "nodes" and item.get("state") != "blocked":
                        continue
                    node_id, reason = item.get("node_id"), item.get("reason")
                    if _in_scope(node_id, allowed_nodes) and _nonempty(reason):
                        result.append(
                            {
                                "node_id": node_id,
                                "reason": str(reason),
                                "kind": "continuation",
                                "source": f"continuation:{continuation.get('id')}",
                            }
                        )
    for blocker in blockers or ():
        if not isinstance(blocker, Mapping):
            continue
        node_id, reason = blocker.get("node_id"), blocker.get("reason")
        if not _in_scope(node_id, allowed_nodes) or not _nonempty(reason):
            continue
        result.append(
            {
                "node_id": node_id,
                "reason": str(reason),
                "kind": str(blocker.get("kind") or "explicit"),
                "source": str(blocker.get("source") or "explicit blocker evidence"),
                "started_at": _iso(value)
                if (value := _parse_time(blocker.get("started_at")))
                else None,
                "ended_at": _iso(value)
                if (value := _parse_time(blocker.get("ended_at")))
                else None,
            }
        )
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for blocker in result:
        key = (
            blocker.get("node_id"),
            blocker.get("kind"),
            blocker.get("reason"),
            blocker.get("source"),
        )
        unique[key] = blocker
    return list(unique.values())


def _continuation_state(
    continuation: Mapping[str, Any] | None, allowed_nodes: set[str] | None
) -> dict[str, Any]:
    if not isinstance(continuation, Mapping):
        return {"state": "unknown", "reason": None}
    state = continuation.get("state")
    if state not in {"active", "paused"}:
        return {"state": "unknown", "reason": None}
    return {
        "state": state,
        "reason": continuation.get("pause_reason") if state == "paused" else None,
        "scope_node_ids": sorted(allowed_nodes) if allowed_nodes is not None else None,
    }


def _production_counts(
    manifest: Mapping[str, Any] | None,
    runs: list[dict[str, Any]],
    allowed_nodes: set[str] | None,
    canvas_id: str | None,
) -> dict[str, Any]:
    result = {
        "requests": _count_metric(len(runs), [f"run:{run.get('id')}" for run in runs]),
        "accepted_sources": _unknown_count("没有提供实际编辑清单或清单格式不受支持。"),
        "segments": _unknown_count("没有提供实际编辑清单或清单格式不受支持。"),
    }
    if not isinstance(manifest, Mapping) or not str(manifest.get("schema", "")).startswith(
        "lfo.mv.edit."
    ):
        return result
    if canvas_id is not None and manifest.get("canvas_id") != canvas_id:
        return result
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        return result

    relevant = []
    uncertain_scope = False
    for segment in segments:
        if not isinstance(segment, Mapping):
            uncertain_scope = True
            continue
        node_id = segment.get("node_id")
        if allowed_nodes is not None:
            if not _nonempty(node_id):
                uncertain_scope = True
                continue
            if str(node_id) not in allowed_nodes:
                continue
        relevant.append(segment)

    segment_metric = _count_metric(
        len(relevant),
        [
            f"manifest:segment:{segment.get('shot_id') or index + 1}"
            for index, segment in enumerate(relevant)
        ],
    )
    if uncertain_scope:
        segment_metric["state"] = "partial"
        segment_metric["note"] = "部分段落缺少节点编号，未能判断是否属于当前范围。"
    result["segments"] = segment_metric

    run_by_id = {str(run.get("id")): run for run in runs if _nonempty(run.get("id"))}
    source_ids = {
        str(segment.get("run_id")) for segment in relevant if _nonempty(segment.get("run_id"))
    }
    unresolved = any(not _nonempty(segment.get("run_id")) for segment in relevant)
    accepted = []
    segments_by_source: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for segment in relevant:
        if _nonempty(segment.get("run_id")):
            segments_by_source[str(segment["run_id"])].append(segment)
    for source_id in source_ids:
        run = run_by_id.get(source_id)
        review = run.get("review") if isinstance(run, Mapping) else None
        if (
            not isinstance(run, Mapping)
            or run.get("status") != "succeeded"
            or not isinstance(review, Mapping)
            or review.get("decision") != "ACCEPT"
        ):
            unresolved = True
            continue
        reviewed_path = review.get("output_path")
        reviewed_digest = review.get("output_sha256")
        source_segments = segments_by_source.get(source_id, [])
        if not _nonempty(reviewed_path) or not _nonempty(reviewed_digest) or not source_segments:
            unresolved = True
            continue
        binding_matches = all(
            _same_path(segment.get("path"), reviewed_path)
            and _same_digest(segment.get("sha256"), reviewed_digest)
            for segment in source_segments
        )
        if binding_matches:
            accepted.append(source_id)
        else:
            unresolved = True
    accepted_metric = _count_metric(
        len(accepted), [f"run:{source_id}:review=ACCEPT" for source_id in sorted(accepted)]
    )
    if unresolved:
        accepted_metric["state"] = "partial"
        accepted_metric["note"] = "部分清单来源缺少 run_id、当前范围内运行记录或 ACCEPT 审查证据。"
    result["accepted_sources"] = accepted_metric
    return result


def _same_path(left: Any, right: Any) -> bool:
    if not _nonempty(left) or not _nonempty(right):
        return False
    try:
        return (
            str(Path(str(left)).resolve()).casefold() == str(Path(str(right)).resolve()).casefold()
        )
    except (OSError, RuntimeError, ValueError):
        return str(left).replace("/", "\\").casefold() == str(right).replace("/", "\\").casefold()


def _same_digest(left: Any, right: Any) -> bool:
    return (
        _nonempty(left)
        and _nonempty(right)
        and str(left).strip().casefold() == str(right).strip().casefold()
    )


def _counter_metrics(
    counts: Counter[str], keys: Sequence[str], runs: list[dict[str, Any]], field: str
) -> dict[str, Any]:
    return {
        key: {
            "value": int(counts.get(key, 0)),
            "state": "observed",
            "sources": [
                f"run:{run.get('id')}:{field}" for run in runs if _field_value(run, field) == key
            ],
        }
        for key in keys
    }


def _field_value(run: Mapping[str, Any], field: str) -> str:
    value = run.get(field)
    if field == "attention_state":
        return _attention(value)
    if field == "status":
        return _status(value)
    if field == "review":
        decision = value.get("decision") if isinstance(value, Mapping) else None
        if decision in _REVIEW_DECISIONS:
            return str(decision)
        return "pending" if _status(run.get("status")) == "succeeded" else "not_ready"
    return str(value)


def _count_metric(value: int, sources: list[str]) -> dict[str, Any]:
    return {"value": value, "state": "observed", "sources": sources}


def _unknown_count(note: str) -> dict[str, Any]:
    return {"value": None, "state": "unknown", "sources": [], "note": note}


def _timing_observed(seconds: int, sources: list[str], note: str | None = None) -> dict[str, Any]:
    return {
        "state": "observed",
        "seconds": seconds,
        "observed_runs": 1,
        "unknown_runs": 0,
        "sources": sources,
        **({"note": note} if note else {}),
    }


def _unknown_timing(note: str, *, unknown_runs: int = 1) -> dict[str, Any]:
    return {
        "state": "unknown",
        "seconds": None,
        "observed_runs": 0,
        "unknown_runs": unknown_runs,
        "sources": [],
        "note": note,
    }


def _duration_metric(
    start: datetime | None,
    end: datetime | None,
    *,
    source: list[str],
    label: str,
    ongoing_start: datetime | None,
    now: datetime,
    unknown_note: str,
) -> dict[str, Any]:
    actual_end = end
    ongoing = False
    if actual_end is None and ongoing_start is not None:
        actual_end = now
        start = ongoing_start
        source = [item for item in source if "run.claimed" not in item]
        source.append("as_of")
        ongoing = True
    if start is None or actual_end is None:
        return _unknown_timing(unknown_note)
    seconds = _seconds(start, actual_end)
    if seconds is None:
        return _unknown_timing("事件时间顺序无效。")
    result = _timing_observed(seconds, source, note=label)
    result["ongoing"] = ongoing
    return result


def _seconds(start: datetime, end: datetime) -> int | None:
    delta = (end - start).total_seconds()
    return int(delta) if delta >= 0 else None


def _parse_time(value: datetime | str | Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _status(value: Any) -> str:
    return str(value) if value in _RUN_STATUSES else "unknown"


def _attention(value: Any) -> str:
    return str(value) if value in _ATTENTION_STATES else "active"


def _in_scope(node_id: Any, allowed_nodes: set[str] | None) -> bool:
    return _nonempty(node_id) and (allowed_nodes is None or str(node_id) in allowed_nodes)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
