from __future__ import annotations

from lfo.canvas.production_metrics import summarize_production

CANVAS = "canvas-a"
T0 = "2026-09-30T10:00:00Z"


def run(
    run_id: str = "r1",
    *,
    node_id: str = "video-a",
    status: str = "succeeded",
    attention: str = "active",
    review=None,
    created_at: str = T0,
    stage: str = "media_validation",
    reviewed_at=None,
) -> dict:
    return {
        "id": run_id,
        "canvas_id": CANVAS,
        "node_id": node_id,
        "status": status,
        "attention_state": attention,
        "attention_reason": "操作员暂停" if attention == "paused" else None,
        "review": review,
        "reviewed_at": reviewed_at,
        "created_at": created_at,
        "stage": stage,
        # This field is intentionally not trusted for duration calculation.
        "stage_updated_at": "2026-09-30T23:59:59Z",
        "updated_at": "2026-09-30T23:59:59Z",
    }


def event(
    event_id: int,
    run_id: str,
    event_type: str,
    at: str,
    *,
    status: str,
    stage: str,
    changed: dict | None = None,
    canvas_id: str = CANVAS,
) -> dict:
    payload = {"status": status, "stage": stage}
    if changed:
        payload["changed"] = changed
    return {
        "id": event_id,
        "run_id": run_id,
        "canvas_id": canvas_id,
        "event_type": event_type,
        "created_at": at,
        "payload": payload,
    }


def full_events(run_id: str = "r1", base_minute: int = 0) -> list[dict]:
    def t(seconds: int) -> str:
        minute = base_minute + seconds // 60
        second = seconds % 60
        return f"2026-09-30T10:{minute:02d}:{second:02d}Z"

    return [
        event(1, run_id, "run.created", t(0), status="queued", stage="input_validation"),
        event(2, run_id, "run.claimed", t(10), status="running", stage="input_validation"),
        event(
            3,
            run_id,
            "run.updated",
            t(20),
            status="running",
            stage="upload",
            changed={"stage": "upload"},
        ),
        event(
            4,
            run_id,
            "run.updated",
            t(30),
            status="running",
            stage="submit",
            changed={"stage": "submit"},
        ),
        event(
            5,
            run_id,
            "run.updated",
            t(35),
            status="running",
            stage="generation",
            changed={"stage": "generation"},
        ),
        event(
            6,
            run_id,
            "run.updated",
            t(65),
            status="running",
            stage="collection",
            changed={"stage": "collection"},
        ),
        event(
            7,
            run_id,
            "run.updated",
            t(70),
            status="succeeded",
            stage="media_validation",
            changed={"status": "succeeded", "stage": "media_validation"},
        ),
        event(8, run_id, "review.claimed", t(80), status="succeeded", stage="media_validation"),
        event(9, run_id, "review.recorded", t(100), status="succeeded", stage="media_validation"),
    ]


def metric(summary: dict, path: tuple[str, ...]) -> dict:
    value = summary
    for part in path:
        value = value[part]
    return value


def test_observes_explicit_stages_and_separates_timeline_from_task_time() -> None:
    runs = [run(review={"decision": "ACCEPT"}, reviewed_at="2026-09-30T10:01:40Z")]
    summary = summarize_production(
        runs,
        full_events(),
        canvas_id=CANVAS,
        now="2026-09-30T10:02:00Z",
    )

    assert metric(summary, ("timings", "phases", "queue"))["seconds"] == 10
    assert metric(summary, ("timings", "phases", "preparation"))["seconds"] == 10
    assert metric(summary, ("timings", "phases", "upload"))["seconds"] == 10
    assert metric(summary, ("timings", "phases", "submission"))["seconds"] == 5
    assert metric(summary, ("timings", "phases", "generation"))["seconds"] == 30
    assert metric(summary, ("timings", "phases", "collection_review"))["seconds"] == 5
    assert metric(summary, ("timings", "phases", "review"))["seconds"] == 20
    assert metric(summary, ("timings", "timeline_elapsed"))["seconds"] == 100
    assert metric(summary, ("timings", "cumulative_task_time"))["seconds"] == 60
    assert "人工等待" in metric(summary, ("timings", "phases", "review"))["note"]
    assert summary["review_counts"]["ACCEPT"]["value"] == 1


def test_missing_events_never_uses_mutable_updated_or_stage_fallback() -> None:
    summary = summarize_production(
        [run(status="succeeded", created_at=T0)],
        [],
        canvas_id=CANVAS,
        now="2026-09-30T10:05:00Z",
    )
    assert summary["timings"]["cumulative_task_time"]["state"] == "unknown"
    assert summary["timings"]["phases"]["generation"]["state"] == "unknown"
    assert summary["timings"]["timeline_elapsed"]["state"] == "unknown"
    assert summary["timings"]["phases"]["resource_wait"]["state"] == "unknown"


def test_paused_follow_up_does_not_rewrite_execution_status_or_end_time() -> None:
    events = [
        event(1, "r1", "run.created", T0, status="queued", stage="input_validation"),
        event(
            2,
            "r1",
            "run.claimed",
            "2026-09-30T10:00:10Z",
            status="running",
            stage="input_validation",
        ),
        event(
            3,
            "r1",
            "run.attention_changed",
            "2026-09-30T10:00:20Z",
            status="running",
            stage="input_validation",
        ),
    ]
    summary = summarize_production(
        [run(status="running", attention="paused", stage="input_validation")],
        events,
        continuation={
            "id": "c1",
            "node_ids": ["video-a"],
            "state": "paused",
            "pause_reason": "用户暂停",
        },
        now="2026-09-30T10:00:40Z",
    )
    assert summary["run_counts"]["by_status"]["running"]["value"] == 1
    assert summary["run_counts"]["by_status"]["failed"]["value"] == 0
    assert summary["run_counts"]["by_attention"]["paused"]["value"] == 1
    assert summary["continuation"] == {
        "state": "paused",
        "reason": "用户暂停",
        "scope_node_ids": ["video-a"],
    }
    assert summary["timings"]["cumulative_task_time"]["seconds"] == 30


def test_unknown_restart_gap_is_excluded_from_task_time_and_breaks_phase_span() -> None:
    events = [
        event(1, "r1", "run.created", T0, status="queued", stage="input_validation"),
        event(2, "r1", "run.claimed", "2026-09-30T10:00:10Z", status="running", stage="generation"),
        event(
            3,
            "r1",
            "run.updated",
            "2026-09-30T10:00:20Z",
            status="unknown",
            stage="generation",
            changed={"status": "unknown"},
        ),
        event(
            4,
            "r1",
            "run.reconciled",
            "2026-09-30T10:10:00Z",
            status="succeeded",
            stage="media_validation",
        ),
    ]
    summary = summarize_production(
        [run(status="succeeded", stage="media_validation")],
        events,
        now="2026-09-30T10:11:00Z",
    )
    assert summary["timings"]["cumulative_task_time"]["seconds"] == 10
    assert summary["timings"]["cumulative_task_time"]["state"] == "observed"
    assert summary["timings"]["phases"]["generation"]["state"] == "unknown"
    assert summary["run_counts"]["by_status"]["succeeded"]["value"] == 1


def test_unknown_run_includes_elapsed_wait_until_observation_but_not_in_task_time() -> None:
    events = [
        event(1, "r1", "run.created", T0, status="queued", stage="input_validation"),
        event(2, "r1", "run.claimed", "2026-09-30T10:00:10Z", status="running", stage="generation"),
        event(3, "r1", "run.updated", "2026-09-30T10:00:20Z", status="unknown", stage="generation", changed={"status": "unknown"}),
    ]
    summary = summarize_production(
        [run(status="unknown", stage="generation")],
        events,
        now="2026-09-30T10:05:00Z",
    )
    assert summary["timings"]["timeline_elapsed"]["seconds"] == 300
    assert summary["timings"]["cumulative_task_time"]["seconds"] == 10
    assert summary["run_counts"]["by_status"]["unknown"]["value"] == 1
    assert summary["current_stages"] == [{"stage": "unknown", "label": "原任务状态待核实", "count": 1}]


def test_node_and_canvas_scope_filters_foreign_runs_events_and_blockers() -> None:
    runs = [
        run("inside", node_id="video-a", status="queued"),
        run("outside", node_id="video-b", status="failed"),
        {**run("other-canvas", node_id="video-a"), "canvas_id": "canvas-b"},
    ]
    events = [
        event(1, "inside", "run.created", T0, status="queued", stage="input_validation"),
        event(2, "outside", "run.created", T0, status="failed", stage="failed"),
        event(
            3,
            "other-canvas",
            "run.updated",
            T0,
            status="failed",
            stage="failed",
            canvas_id="canvas-b",
        ),
    ]
    summary = summarize_production(
        runs,
        events,
        canvas_id=CANVAS,
        node_ids=["video-a"],
        continuation={
            "id": "c1",
            "node_ids": ["video-a"],
            "state": "active",
            "units": [{"node_id": "video-b", "state": "blocked", "reason": "越界阻塞"}],
        },
        blockers=[
            {"node_id": "video-a", "kind": "resource", "reason": "明确忙碌证据"},
            {"node_id": "video-b", "kind": "resource", "reason": "不计入范围"},
        ],
    )
    assert summary["run_counts"]["total"]["value"] == 1
    assert summary["run_counts"]["by_status"]["failed"]["value"] == 0
    assert summary["blockers"] == [
        {
            "node_id": "video-a",
            "reason": "明确忙碌证据",
            "kind": "resource",
            "source": "explicit blocker evidence",
            "started_at": None,
            "ended_at": None,
        }
    ]


def test_parallel_timeline_wall_span_and_cumulative_task_time_are_distinct() -> None:
    first = [
        event(1, "r1", "run.created", T0, status="queued", stage="input_validation"),
        event(2, "r1", "run.claimed", T0, status="running", stage="input_validation"),
        event(
            3,
            "r1",
            "run.updated",
            "2026-09-30T10:01:00Z",
            status="running",
            stage="input_validation",
        ),
    ]
    second = [
        event(1, "r2", "run.created", T0, status="queued", stage="input_validation"),
        event(2, "r2", "run.claimed", T0, status="running", stage="input_validation"),
        event(
            3,
            "r2",
            "run.updated",
            "2026-09-30T10:02:00Z",
            status="succeeded",
            stage="media_validation",
            changed={"status": "succeeded"},
        ),
    ]
    summary = summarize_production(
        [run("r1", status="running", created_at=T0), run("r2", status="succeeded", created_at=T0)],
        [*first, *second],
        now="2026-09-30T10:01:00Z",
    )
    assert summary["timings"]["timeline_elapsed"]["seconds"] == 120
    assert summary["timings"]["cumulative_task_time"]["seconds"] == 180


def test_content_reject_is_separate_from_execution_failure_and_unreviewed_is_not_ready() -> None:
    runs = [
        run("good-execution-reject", status="succeeded", review={"decision": "REJECT"}),
        run("execution-failure", status="failed", review=None),
    ]
    summary = summarize_production(runs, [], now="2026-09-30T10:05:00Z")
    assert summary["run_counts"]["by_status"]["failed"]["value"] == 1
    assert summary["review_counts"]["REJECT"]["value"] == 1
    assert summary["review_counts"]["pending"]["value"] == 0
    assert summary["review_counts"]["not_ready"]["value"] == 1


def test_manifest_counts_only_accepted_sources_and_segments_within_scope() -> None:
    runs = [
        run(
            "accepted",
            node_id="video-a",
            review={
                "decision": "ACCEPT",
                "output_path": r"E:\media\accepted.mp4",
                "output_sha256": "a" * 64,
            },
        ),
        run(
            "accepted-old-binding",
            node_id="video-a",
            review={
                "decision": "ACCEPT",
                "output_path": r"E:\media\old.mp4",
                "output_sha256": "b" * 64,
            },
        ),
        run(
            "rejected",
            node_id="video-a",
            review={
                "decision": "REJECT",
                "output_path": r"E:\media\rejected.mp4",
                "output_sha256": "c" * 64,
            },
        ),
        run(
            "outside",
            node_id="video-b",
            review={
                "decision": "ACCEPT",
                "output_path": r"E:\media\outside.mp4",
                "output_sha256": "d" * 64,
            },
        ),
    ]
    manifest = {
        "schema": "lfo.mv.edit.v1",
        "canvas_id": CANVAS,
        "segments": [
            {
                "shot_id": "S1",
                "node_id": "video-a",
                "run_id": "accepted",
                "path": r"E:\media\accepted.mp4",
                "sha256": "a" * 64,
            },
            {
                "shot_id": "S2",
                "node_id": "video-a",
                "run_id": "accepted",
                "path": r"E:\media\accepted.mp4",
                "sha256": "A" * 64,
            },
            {
                "shot_id": "S3",
                "node_id": "video-a",
                "run_id": "accepted-old-binding",
                "path": r"E:\media\old-edited.mp4",
                "sha256": "b" * 64,
            },
            {
                "shot_id": "S4",
                "node_id": "video-a",
                "run_id": "rejected",
                "path": r"E:\media\rejected.mp4",
                "sha256": "c" * 64,
            },
            {
                "shot_id": "S5",
                "node_id": "video-b",
                "run_id": "outside",
                "path": r"E:\media\outside.mp4",
                "sha256": "d" * 64,
            },
        ],
    }
    summary = summarize_production(
        runs, [], canvas_id=CANVAS, node_ids=["video-a"], edit_manifest=manifest
    )
    assert summary["production_counts"]["segments"]["value"] == 4
    assert summary["production_counts"]["accepted_sources"]["value"] == 1
    assert summary["production_counts"]["accepted_sources"]["state"] == "partial"


def test_missing_manifest_keeps_edit_counts_unknown_and_explicit_resource_wait_only() -> None:
    summary = summarize_production(
        [run(status="queued")],
        [],
        node_ids=["video-a"],
        blockers=[
            {
                "node_id": "video-a",
                "kind": "resource_wait",
                "reason": "本地视频资源忙",
                "started_at": T0,
                "ended_at": "2026-09-30T10:00:15Z",
                "source": "resource-event-1",
            },
            {
                "node_id": "video-a",
                "kind": "resource_wait",
                "reason": "第二段无结束时点",
                "started_at": T0,
                "source": "resource-event-2",
            },
        ],
        now="2026-09-30T10:01:00Z",
    )
    assert summary["production_counts"]["segments"]["state"] == "unknown"
    assert summary["production_counts"]["accepted_sources"]["state"] == "unknown"
    resource_wait = summary["timings"]["phases"]["resource_wait"]
    assert resource_wait["state"] == "partial"
    assert resource_wait["seconds"] == 15


def test_empty_scope_and_scope_cannot_be_widened_by_continuation() -> None:
    summary = summarize_production(
        [run()],
        full_events(),
        node_ids=["video-a", "video-b"],
        continuation={"id": "c1", "node_ids": ["video-b"], "state": "active"},
    )
    assert summary["scope_node_ids"] == ["video-b"]
    assert summary["run_counts"]["total"]["value"] == 0
    assert summary["timings"]["timeline_elapsed"]["state"] == "unknown"
