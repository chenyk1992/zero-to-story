"""Tests for the two-table canvas SQLite store."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from lfo.canvas.store import (
    CanvasStore,
    CanvasStoreError,
    RequestConflictError,
    RunStateError,
    VersionConflictError,
)


def _graph(prompt: str = "a scene") -> dict:
    return {
        "nodes": [
            {
                "id": "video-1",
                "type": "video",
                "position": {"x": 10, "y": 20},
                "data": {"prompt": prompt, "mode": "text_to_video"},
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }


def _snapshot(prompt: str = "a scene") -> dict:
    return {
        "node_id": "video-1",
        "node_type": "video",
        "provider": "comfy",
        "model": None,
        "mode": "text_to_video",
        "prompt": prompt,
        "parameters": {"duration": 5},
        "inputs": {
            "reference_images": [],
            "reference_videos": [],
            "reference_audios": [],
        },
    }


def test_canvas_version_is_compare_and_swap(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        assert canvas["version"] == 1
        saved = store.save_canvas(canvas["id"], 1, _graph("updated"))
        assert saved["version"] == 2
        assert saved["graph"]["nodes"][0]["data"]["prompt"] == "updated"

        with pytest.raises(VersionConflictError) as conflict:
            store.save_canvas(canvas["id"], 1, _graph("stale"))
        assert conflict.value.code == "version_conflict"
        assert conflict.value.status == 409


def test_request_id_is_idempotent_but_conflicting_intent_is_rejected(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        first = store.create_run(canvas["id"], "video-1", canvas["version"], "req-1", _snapshot())
        duplicate = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot()
        )
        assert duplicate["id"] == first["id"]
        assert store.get_run_by_request("req-1")["id"] == first["id"]

        with pytest.raises(RequestConflictError) as conflict:
            store.create_run(
                canvas["id"], "video-1", canvas["version"], "req-1", _snapshot("other")
            )
        assert conflict.value.code == "request_id_conflict"


def test_run_snapshot_does_not_change_when_draft_changes(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph("draft one"))
        run = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot("draft one")
        )
        store.save_canvas(canvas["id"], canvas["version"], _graph("draft two"))
        assert store.get_run(run["id"])["snapshot"]["prompt"] == "draft one"
        assert store.get_canvas(canvas["id"])["graph"]["nodes"][0]["data"]["prompt"] == "draft two"


def test_claim_run_is_serial_and_terminal_runs_cannot_be_overwritten(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        first = store.create_run(canvas["id"], "video-1", canvas["version"], "req-1", _snapshot())
        claimed = store.claim_run(first["id"])
        assert claimed["status"] == "running"
        with pytest.raises(RunStateError) as duplicate_claim:
            store.claim_run(first["id"])
        assert duplicate_claim.value.code == "run_not_claimable"

        # A second node is useful here even though the graph has one generation node;
        # the store's serial gate is intentionally independent of Skill capability rules.
        second = store.create_run(canvas["id"], "video-1", canvas["version"], "req-2", _snapshot())
        with pytest.raises(RunStateError) as busy:
            store.claim_run(second["id"])
        assert busy.value.code == "busy"

        completed = store.update_run(
            first["id"],
            status="succeeded",
            outputs=[{"path": "video.mp4", "kind": "video"}],
        )
        assert completed["status"] == "succeeded"
        with pytest.raises(RunStateError) as terminal:
            store.update_run(first["id"], status="failed")
        assert terminal.value.code == "run_terminal"

        claimed_second = store.claim_run(second["id"], owner_token="agent-token")
        assert claimed_second["owner_token"] == "agent-token"
        store.update_run(
            second["id"],
            status="unknown",
            error="remote status unavailable",
            stage="generation",
            evidence={"provider_task_id": "remote-2"},
        )
        with pytest.raises(CanvasStoreError) as unauthorized:
            store.reconcile_run(
                second["id"],
                "failed",
                {
                    "request_id": "req-2",
                    "remote_status": "failed",
                    "source": "provider_response",
                    "reason": "已在提供方控制台确认任务终止",
                },
            )
        assert unauthorized.value.code == "recovery_access_required"
        recovery_token = store.claim_recovery(second["id"], "已在提供方控制台确认任务终止")
        resolved = store.reconcile_run(
            second["id"],
            "failed",
            {
                "request_id": "req-2",
                "remote_status": "failed",
                "source": "provider_response",
                "reason": "已在提供方控制台确认任务终止",
            },
            recovery_token=recovery_token,
        )
        assert resolved["status"] == "failed"
        assert resolved["owner_token"] is None


def test_claim_run_blocks_a_second_canvas_in_the_same_database(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        first_canvas = store.create_canvas("first", _graph())
        second_canvas = store.create_canvas("second", _graph())
        first = store.create_run(
            first_canvas["id"], "video-1", first_canvas["version"], "req-1", _snapshot()
        )
        second = store.create_run(
            second_canvas["id"], "video-1", second_canvas["version"], "req-2", _snapshot()
        )
        store.claim_run(first["id"])
        with pytest.raises(RunStateError) as busy:
            store.claim_run(second["id"])
        assert busy.value.code == "busy"


def test_cancel_pending_is_atomic_and_cannot_overwrite_a_claimed_run(tmp_path) -> None:
    with CanvasStore(tmp_path / "canvas.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        queued = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-queued", _snapshot()
        )
        cancelled = store.cancel_pending(queued["id"])
        assert cancelled["status"] == "cancelled"
        assert cancelled["error"] == "用户取消了尚未开始的执行"

        running = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-running", _snapshot()
        )
        store.claim_run(running["id"])
        with pytest.raises(RunStateError) as claimed_error:
            store.cancel_pending(running["id"])
        assert claimed_error.value.code == "run_not_pending"
        assert store.get_run(running["id"])["status"] == "running"


def test_database_contains_schema_and_event_tables(tmp_path) -> None:
    db_path = tmp_path / "canvas.sqlite3"
    with CanvasStore(db_path):
        connection = sqlite3.connect(db_path)
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        connection.close()
    assert {
        "canvases",
        "node_runs",
        "canvas_schema_meta",
        "run_events",
        "event_cursors",
    }.issubset(names)


def test_old_node_runs_are_migrated_additively_and_history_is_preserved(tmp_path) -> None:
    db_path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE canvases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            graph_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE node_runs (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL UNIQUE,
            canvas_id TEXT NOT NULL REFERENCES canvases(id),
            node_id TEXT NOT NULL,
            canvas_version INTEGER NOT NULL,
            status TEXT NOT NULL,
            snapshot TEXT NOT NULL,
            outputs TEXT NOT NULL,
            provider_task_id TEXT,
            owner_token TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    graph = _graph()
    connection.execute(
        "INSERT INTO canvases VALUES (?, ?, ?, ?, ?, ?)",
        ("canvas-1", "old", 1, json.dumps(graph), "t", "t"),
    )
    connection.execute(
        "INSERT INTO node_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "run-1",
            "request-1",
            "canvas-1",
            "video-1",
            1,
            "failed",
            json.dumps(_snapshot()),
            "[]",
            "provider-1",
            "owner-1",
            json.dumps("old error"),
            "t",
            "t",
        ),
    )
    connection.commit()
    connection.close()

    with CanvasStore(db_path) as store:
        migrated = store.get_run("run-1")
        assert store.schema_version == 2
        assert migrated["status"] == "failed"
        assert migrated["provider_task_id"] == "provider-1"
        assert migrated["owner_token"] == "owner-1"
        assert migrated["error"] == "old error"
        assert migrated["attention_state"] == "active"
        assert migrated["resource_key"] == "legacy:unknown"
        assert migrated["resource_capacity"] == 1
        assert migrated["evidence"] == []
        assert store.list_events() == []


def test_identical_progress_writes_do_not_create_duplicate_events(tmp_path) -> None:
    with CanvasStore(tmp_path / "events.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        run = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )
        initial_events = store.list_events()
        store.update_run(run["id"], stage="input_validation", evidence=None)
        assert store.list_events() == initial_events

        store.update_run(
            run["id"],
            stage="upload",
            provider_task_id="provider-1",
            evidence={"provider_task_id": "provider-1"},
        )
        first_progress_events = store.list_events()
        store.update_run(
            run["id"],
            stage="upload",
            provider_task_id="provider-1",
            evidence={"provider_task_id": "provider-1"},
        )
        assert store.list_events() == first_progress_events


def test_resource_capacity_is_scoped_and_unknown_is_conservative(tmp_path) -> None:
    with CanvasStore(tmp_path / "resources.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())

        def create(request_id: str, key: str, capacity: int) -> dict:
            return store.create_run(
                canvas["id"],
                "video-1",
                canvas["version"],
                request_id,
                _snapshot(),
                resource_key=key,
                resource_capacity=capacity,
            )

        image_one = create("image-1", "image:provider", 2)
        image_two = create("image-2", "image:provider", 2)
        image_three = create("image-3", "image:provider", 2)
        video = create("video-1", "video", 1)
        store.claim_run(image_one["id"], owner_token="image-one")
        store.claim_run(image_two["id"], owner_token="image-two")
        with pytest.raises(RunStateError) as image_busy:
            store.claim_run(image_three["id"], owner_token="image-three")
        assert image_busy.value.code == "busy"
        # A different resource can proceed while the image capacity is full.
        assert store.claim_run(video["id"], owner_token="video")["status"] == "running"

        unknown = create("unknown-1", "legacy:unknown", 1)
        with pytest.raises(RunStateError) as unknown_busy:
            store.claim_run(unknown["id"], owner_token="unknown")
        assert unknown_busy.value.code == "busy"


def test_paused_and_abandoned_attention_do_not_release_execution_occupancy(tmp_path) -> None:
    with CanvasStore(tmp_path / "attention.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        first = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )
        store.set_attention(first["id"], "paused", "等待操作员")
        with pytest.raises(RunStateError) as paused:
            store.claim_run(first["id"], owner_token="owner")
        assert paused.value.code == "attention_inactive"
        store.set_attention(first["id"], "active")
        store.claim_run(first["id"], owner_token="owner")
        store.set_attention(first["id"], "abandoned", "本地会话已放弃跟进")
        assert store.get_run(first["id"])["status"] == "running"


def test_reconcile_requires_bound_evidence_and_preserves_original_error(tmp_path) -> None:
    with CanvasStore(tmp_path / "reconcile.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        run = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )
        store.claim_run(run["id"], owner_token="owner")
        store.update_run(run["id"], status="unknown", stage="generation", error="original")
        evidence = {
            "request_id": "req-1",
            "remote_status": "failed",
            "source": "provider_response",
            "reason": "提供方明确返回失败",
        }
        with pytest.raises(CanvasStoreError) as mismatch:
            store.reconcile_run(
                run["id"],
                "failed",
                {**evidence, "request_id": "other"},
                owner_token="owner",
            )
        assert mismatch.value.code == "reconcile_request_mismatch"
        token = store.claim_recovery(run["id"], "读取提供方响应")
        reconciled = store.reconcile_run(run["id"], "failed", evidence, recovery_token=token)
        assert reconciled["status"] == "failed"
        assert reconciled["error"] == "original"
        assert len(reconciled["evidence"]) == 2
        with pytest.raises(RunStateError):
            store.reconcile_run(run["id"], "failed", evidence, recovery_token=token)


def test_failed_collection_can_reconcile_same_provider_result_once(tmp_path) -> None:
    with CanvasStore(tmp_path / "collection-recovery.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        run = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )
        store.claim_run(run["id"], owner_token="owner")
        store.update_run(
            run["id"],
            status="failed",
            stage="collection",
            evidence={"remote_finished": True, "provider_task_id": "provider-1"},
            provider_task_id="provider-1",
            error="download failed",
        )
        recovery = store.claim_recovery(run["id"], "提供方已完成，仅回收失败")
        output = {"path": "video.mp4", "kind": "video", "sha256": "a" * 64}
        evidence = {
            "request_id": "req-1",
            "remote_status": "succeeded",
            "source": "provider_history",
            "reason": "重新取回同一已完成结果",
        }
        reconciled = store.reconcile_run(
            run["id"], "succeeded", evidence, outputs=[output], recovery_token=recovery
        )
        assert reconciled["status"] == "succeeded"
        assert reconciled["outputs"] == [output]
        assert reconciled["provider_task_id"] == "provider-1"


@pytest.mark.parametrize("original_owner", ["generation-owner", None])
def test_review_is_bound_to_review_claim_and_output_identity(tmp_path, original_owner) -> None:
    with CanvasStore(tmp_path / "review.sqlite3") as store:
        canvas = store.create_canvas("demo", _graph())
        run = store.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )
        if original_owner:
            store.claim_run(run["id"], owner_token=original_owner)
        output = {"path": "video.mp4", "kind": "video", "sha256": "b" * 64}
        store.update_run(run["id"], status="succeeded", outputs=[output])
        with pytest.raises(CanvasStoreError) as missing_claim:
            store.review_run(
                run["id"],
                {
                    "decision": "ACCEPT",
                    "output_path": "video.mp4",
                    "output_sha256": "b" * 64,
                    "evidence": ["画面连续"],
                    "end_state": {},
                    "unverified": [],
                },
            )
        assert missing_claim.value.code == "review_owner_required"
        review_token = store.claim_review(run["id"])
        reviewed = store.review_run(
            run["id"],
            {
                "decision": "ACCEPT",
                "output_path": "video.mp4",
                "output_sha256": "b" * 64,
                "evidence": ["画面连续"],
                "end_state": {},
                "unverified": [],
            },
            owner_token=review_token,
        )
        assert reviewed["review"]["decision"] == "ACCEPT"
        assert reviewed["review"]["output_sha256"] == "b" * 64
        with pytest.raises(RunStateError) as terminal:
            store.review_run(
                run["id"],
                {
                    "decision": "REJECT",
                    "output_path": "video.mp4",
                    "output_sha256": "b" * 64,
                    "evidence": ["需要修复"],
                    "end_state": {},
                    "unverified": [],
                },
                owner_token=review_token,
            )
        assert terminal.value.code == "review_terminal"


def test_competing_store_connections_only_claim_one_run(tmp_path) -> None:
    db_path = tmp_path / "competition.sqlite3"
    with CanvasStore(db_path) as setup:
        canvas = setup.create_canvas("demo", _graph())
        run = setup.create_run(
            canvas["id"], "video-1", canvas["version"], "req-1", _snapshot(), resource_key="video"
        )

    barrier = Barrier(2)
    stores = [CanvasStore(db_path), CanvasStore(db_path)]

    def claim(index: int) -> str:
        barrier.wait()
        try:
            stores[index].claim_run(run["id"], owner_token=f"owner-{index}")
        except RunStateError as exc:
            return exc.code
        return "claimed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, (0, 1)))
    for store in stores:
        store.close()
    assert results.count("claimed") == 1
    assert sum(result in {"busy", "run_not_claimable"} for result in results) == 1
