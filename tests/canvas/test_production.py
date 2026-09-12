from __future__ import annotations

import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from lfo.canvas.graph import CanvasError, resolve_snapshot
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


@pytest.fixture
def production(tmp_path):
    service = CanvasService(
        CanvasSettings(Path(__file__).resolve().parents[2], tmp_path / "state", tmp_path / "media"),
        start_worker=False,
    )
    graph = {
        "nodes": [
            {
                "id": "one",
                "type": "image",
                "position": {"x": 0, "y": 0},
                "data": {
                    "prompt": "固定画面",
                    "provider": "codex-imagegen",
                    "model": "image_gen",
                    "mode": "create",
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }
    canvas = service.store.create_canvas("production", graph)
    yield service, canvas
    service.close()


def confirm(service, canvas, request_id="request-one"):
    return service.confirm(canvas["id"], "one", canvas["version"], request_id)


def complete(service, canvas, tmp_path):
    run = confirm(service, canvas)
    claim = service.claim_agent(run["id"], ["image_gen"])
    output = tmp_path / "result.png"
    output.write_bytes(b"test image")
    done = service.complete_agent(
        run["id"], claim["owner_token"], outputs=[{"path": str(output), "kind": "image"}]
    )
    return done


def video_run(service):
    graph = {
        "nodes": [
            {
                "id": "video-one",
                "type": "video",
                "position": {"x": 0, "y": 0},
                "data": {"prompt": "固定视频", "provider": "comfy", "mode": "t2v"},
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }
    canvas = service.store.create_canvas("video", graph)
    run = service.store.create_run(
        canvas["id"],
        "video-one",
        canvas["version"],
        "video-request",
        {
            "node_id": "video-one",
            "node_type": "video",
            "provider": "comfy",
            "model": "h3",
            "mode": "t2v",
            "prompt": "固定视频",
            "parameters": {},
            "inputs": {},
        },
        status="pending_agent",
        resource_key="video",
    )
    claimed = service.store.claim_run(run["id"], owner_token="video-owner")
    return canvas, claimed


def test_capability_is_scoped_to_receiving_session(production):
    service, canvas = production
    assert service.catalog.get("codex-imagegen", ["image_gen"])["available"]
    assert not service.catalog.get("codex-imagegen", ["terminal"])["available"]
    run = confirm(service, canvas)
    with pytest.raises(ValueError, match="核实工具"):
        service.claim_agent(run["id"], ["terminal"])
    assert service.store.get_run(run["id"])["status"] == "pending_agent"
    service.claim_agent(run["id"], ["image_gen"])
    assert not service.catalog.get("codex-imagegen")["available"]


def test_unknown_keeps_original_task_id_and_can_collect_late_result(production, tmp_path):
    service, canvas = production
    run = confirm(service, canvas)
    claim = service.claim_agent(run["id"], ["image_gen"])
    service.progress_agent(run["id"], claim["owner_token"], "generation", "remote-one")
    unknown = service.complete_agent(
        run["id"], claim["owner_token"], status="unknown", error="lost response"
    )
    assert unknown["provider_task_id"] == "remote-one"
    service.set_attention(run["id"], "abandoned", "停止本地等待")
    assert service.store.get_run(run["id"])["status"] == "unknown"
    token = service.store.claim_recovery(run["id"], "原接手方已退出，核实原任务")
    output = tmp_path / "late.png"
    output.write_bytes(b"late original output")
    proof = {
        "request_id": run["request_id"],
        "remote_status": "succeeded",
        "source": "provider_history",
        "reason": "原编号的历史记录已完成",
    }
    late = service.reconcile_run(
        run["id"], token, "succeeded", proof, [{"path": str(output), "kind": "image"}]
    )
    assert late["provider_task_id"] == "remote-one"
    assert late["review"] is None
    assert late["error"] == "lost response"
    assert len(service.store.list_runs()) == 1
    path = Path(late["outputs"][0]["path"])
    output.write_bytes(b"different candidate")
    with pytest.raises(CanvasError):
        service.reconcile_run(
            run["id"], token, "succeeded", proof, [{"path": str(output), "kind": "image"}]
        )
    assert path.read_bytes() == b"late original output"


def test_reconcile_proof_and_task_identity_are_checked_before_collection(production, tmp_path):
    service, canvas = production
    run = confirm(service, canvas)
    claim = service.claim_agent(run["id"], ["image_gen"])
    service.progress_agent(run["id"], claim["owner_token"], "generation", "remote-one")
    service.complete_agent(run["id"], claim["owner_token"], status="unknown", error="lost response")
    recovery = service.store.claim_recovery(run["id"], "读取提供方响应")
    output = tmp_path / "late.png"
    output.write_bytes(b"late output")
    output_ref = [{"path": str(output), "kind": "image"}]
    output_dir = service.settings.output_dir(run["canvas_id"], run["id"])
    proof = {
        "request_id": run["request_id"],
        "remote_status": "succeeded",
        "source": "provider_history",
        "reason": "原编号的历史记录已完成",
    }

    with pytest.raises(CanvasError) as bad_proof:
        service.reconcile_run(
            run["id"],
            recovery,
            "succeeded",
            {**proof, "request_id": "different-request"},
            output_ref,
        )
    assert bad_proof.value.code == "reconcile_request_mismatch"
    assert not output_dir.exists()

    with pytest.raises(CanvasError) as bad_task_id:
        service.reconcile_run(
            run["id"],
            recovery,
            "succeeded",
            proof,
            output_ref,
            provider_task_id="remote-two",
        )
    assert bad_task_id.value.code == "provider_task_conflict"
    assert not output_dir.exists()
    assert service.store.get_run(run["id"])["status"] == "unknown"


def test_complete_and_reconcile_validate_all_output_kinds_before_copying(production, tmp_path):
    service, canvas = production
    run = confirm(service, canvas)
    claim = service.claim_agent(run["id"], ["image_gen"])
    image = tmp_path / "image.png"
    video = tmp_path / "video.mp4"
    image.write_bytes(b"image")
    video.write_bytes(b"video")
    mixed = [
        {"path": str(image), "kind": "image"},
        {"path": str(video), "kind": "video"},
    ]
    output_dir = service.settings.output_dir(run["canvas_id"], run["id"])
    with pytest.raises(ValueError, match="类型"):
        service.complete_agent(run["id"], claim["owner_token"], outputs=mixed)
    assert not output_dir.exists()
    assert service.store.get_run(run["id"])["status"] == "running"

    service.complete_agent(run["id"], claim["owner_token"], status="unknown", error="lost response")
    recovery = service.store.claim_recovery(run["id"], "读取提供方响应")
    proof = {
        "request_id": run["request_id"],
        "remote_status": "succeeded",
        "source": "provider_history",
        "reason": "原编号的历史记录已完成",
    }
    with pytest.raises(ValueError, match="类型"):
        service.reconcile_run(run["id"], recovery, "succeeded", proof, mixed)
    assert not output_dir.exists()
    assert service.store.get_run(run["id"])["status"] == "unknown"


def test_confirmed_remote_finish_releases_generation_capacity_but_keeps_node_busy(production):
    service, canvas = production
    graph = copy.deepcopy(canvas["graph"])
    graph["nodes"].append(
        {
            "id": "video-one",
            "type": "video",
            "position": {"x": 1, "y": 0},
            "data": {"prompt": "第一个视频", "provider": "comfy", "mode": "t2v"},
        }
    )
    graph["nodes"].append(
        {
            "id": "video-two",
            "type": "video",
            "position": {"x": 2, "y": 0},
            "data": {"prompt": "第二个视频", "provider": "comfy", "mode": "t2v"},
        }
    )
    canvas = service.store.save_canvas(canvas["id"], canvas["version"], graph)
    first_snapshot = {
        "node_id": "video-one",
        "node_type": "video",
        "provider": "comfy",
        "model": "h3",
        "mode": "t2v",
        "prompt": "第一个视频",
        "parameters": {},
        "inputs": {},
    }
    first = service.store.create_run(
        canvas["id"],
        "video-one",
        canvas["version"],
        "video-one-request",
        first_snapshot,
        resource_key="video",
        resource_capacity=1,
    )
    first = service.store.claim_run(first["id"], owner_token="video-one-owner")
    service.store.update_run(
        first["id"],
        stage="collection",
        evidence={"remote_finished": True},
    )

    with pytest.raises(CanvasError, match="组件已有待处理任务"):
        service.confirm(canvas["id"], "video-one", canvas["version"], "same-node-request")

    second_snapshot = {**first_snapshot, "node_id": "video-two", "prompt": "第二个视频"}
    second = service.store.create_run(
        canvas["id"],
        "video-two",
        canvas["version"],
        "video-two-request",
        second_snapshot,
        resource_key="video",
        resource_capacity=1,
    )
    claimed = service.store.claim_run(second["id"], owner_token="video-two-owner")
    assert claimed["status"] == "running"


def test_complete_video_requires_readable_media_before_copying(production, tmp_path, monkeypatch):
    service, _ = production
    canvas, run = video_run(service)
    monkeypatch.setattr(
        "lfo.canvas.service.probe",
        lambda _path: {"duration_ms": 0, "width": 1920, "height": 1080, "codec": "h264"},
    )
    output = tmp_path / "bad.mp4"
    output.write_bytes(b"not a video")
    output_dir = service.settings.output_dir(canvas["id"], run["id"])
    with pytest.raises(ValueError, match="视频输出无法读取"):
        service.complete_agent(
            run["id"], "video-owner", outputs=[{"path": str(output), "kind": "video"}]
        )
    assert not output_dir.exists()
    assert service.store.get_run(run["id"])["status"] == "running"


@pytest.mark.parametrize("probe_failure", ["malformed", "missing"])
def test_reconcile_video_probe_failure_preserves_recovery(
    production, tmp_path, monkeypatch, probe_failure
):
    service, _ = production
    canvas, run = video_run(service)
    service.store.update_run(run["id"], status="unknown", stage="generation", error="lost response")
    recovery = service.store.claim_recovery(run["id"], "检查原提供方结果")
    if probe_failure == "malformed":
        monkeypatch.setattr(
            "lfo.canvas.service.probe",
            lambda _path: {"duration_ms": 0, "width": None, "height": None, "codec": None},
        )
    else:

        def missing_probe(_path):
            raise RuntimeError("ffprobe missing")

        monkeypatch.setattr("lfo.canvas.service.probe", missing_probe)
    output = tmp_path / "late.mp4"
    output.write_bytes(b"not a video")
    proof = {
        "request_id": run["request_id"],
        "remote_status": "succeeded",
        "source": "provider_history",
        "reason": "原编号的历史记录已完成",
    }
    output_dir = service.settings.output_dir(canvas["id"], run["id"])
    with pytest.raises(ValueError, match="视频输出无法读取"):
        service.reconcile_run(
            run["id"],
            recovery,
            "succeeded",
            proof,
            [{"path": str(output), "kind": "video"}],
        )
    current = service.store.get_run(run["id"])
    assert current["status"] == "unknown"
    assert current["recovery_token"] == recovery
    assert current["outputs"] == []
    assert not output_dir.exists()


def test_review_is_owned_and_pins_actual_media_not_latest_success(production, tmp_path):
    service, canvas = production
    run = complete(service, canvas, tmp_path)
    token = service.store.claim_review(run["id"])
    with pytest.raises(CanvasError):
        service.review_output(
            run["id"], "another-owner", "ACCEPT", run["outputs"][0]["path"], ["checked"]
        )
    with pytest.raises(ValueError):
        service.review_output(
            run["id"],
            token,
            "ACCEPT",
            run["outputs"][0]["path"],
            ["checked"],
            unverified=["关键手部动作看不清"],
        )
    reviewed = service.review_output(
        run["id"],
        token,
        "ACCEPT",
        run["outputs"][0]["path"],
        ["关键画面符合已定用途"],
        end_state={"prop": "纸略抬起"},
    )
    graph = copy.deepcopy(canvas["graph"])
    graph["nodes"].append(
        {
            "id": "next",
            "type": "image",
            "position": {"x": 1, "y": 1},
            "data": {
                "prompt": "沿用实际姿态",
                "provider": "codex-imagegen",
                "mode": "edit",
                "model": "image_gen",
            },
        }
    )
    graph["edges"].append(
        {
            "id": "continuity",
            "source": "one",
            "target": "next",
            "sourceHandle": "output",
            "targetHandle": "reference_image",
            "source_run_id": run["id"],
            "require_accept": True,
        }
    )
    updated = service.store.save_canvas(canvas["id"], canvas["version"], graph)
    assert service.readiness(canvas["id"], "next")["ready"]
    snapshot = resolve_snapshot(updated, "next", [reviewed])
    assert snapshot["inputs"]["reference_images"][0]["source_run_id"] == run["id"]
    Path(run["outputs"][0]["path"]).write_bytes(b"changed after review")
    assert not service.readiness(canvas["id"], "next")["ready"]
    with pytest.raises(ValueError, match="发生变化"):
        service.confirm(canvas["id"], "next", updated["version"], "next-request")
    assert len(service.store.list_runs()) == 1


def test_events_and_summary_do_not_leak_tokens_or_prompt(production, tmp_path):
    service, canvas = production
    run = complete(service, canvas, tmp_path)
    service.store.claim_review(run["id"])
    assert not any(key.endswith("_token") for key in service.runs()[0])
    assert "snapshot" not in service.run_summary(run["id"])
    events = service.events(wait_seconds=0)
    assert events["events"]
    cursor = events["cursor"]
    service.store.acknowledge_event("host-a-worker", cursor)
    service.store.acknowledge_event("host-a-worker", cursor)
    assert service.store.get_event_cursor("host-a-worker") == cursor
    assert service.events(after=cursor, wait_seconds=0)["events"] == []


def test_reopen_review_archives_and_adopts_derived_output(production, tmp_path):
    service, canvas = production
    run = complete(service, canvas, tmp_path)
    old_token = service.store.claim_review(run["id"])
    original = Path(run["outputs"][0]["path"])
    reviewed = service.review_output(
        run["id"],
        old_token,
        "INCONCLUSIVE",
        str(original),
        ["audio unclear"],
        end_state={"position": "standing"},
        unverified=["audio"],
    )
    reopened = service.reopen_review(
        run["id"], "Reviewed derived audio repair", reviewed["updated_at"]
    )
    token = reopened["owner_token"]
    assert token != old_token
    current = service._public_run(service.store.get_run(run["id"]))
    assert current["review"] is None and current["reviewed_at"] is None
    assert current["review_history"][0]["review"] == reviewed["review"]
    assert current["review_history"][0]["reviewed_at"] == reviewed["reviewed_at"]
    assert "owner_token" not in str(current["review_history"])
    with pytest.raises(CanvasError):
        service.store.claim_review(run["id"])
    with pytest.raises(CanvasError):
        service.review_output(run["id"], old_token, "ACCEPT", str(original), ["checked"])
    with pytest.raises(ValueError):
        service.review_output(run["id"], token, "ACCEPT", str(tmp_path / "result.png"), ["checked"])
    with pytest.raises(ValueError):
        service.review_output(
            run["id"], token, "ACCEPT", str(original.parent / "missing.png"), ["checked"]
        )
    derived = original.with_name("derived.png")
    derived.write_bytes(b"reviewed derived output")
    accepted = service.review_output(
        run["id"], token, "ACCEPT", str(derived), ["checked actual file"]
    )
    assert accepted["review"]["output_sha256"] == hashlib.sha256(derived.read_bytes()).hexdigest()
    assert accepted["review"]["output_path"] == str(derived)
    assert accepted["outputs"] == run["outputs"]
    assert original.read_bytes() == b"test image"
    with pytest.raises(CanvasError):
        service.review_output(run["id"], old_token, "ACCEPT", str(derived), ["checked actual file"])
    from lfo.canvas.store import CanvasStore

    with CanvasStore(service.store.db_path) as other:
        assert other.get_run(run["id"])["review_history"] == current["review_history"]


@pytest.mark.parametrize("decision", [None, "ACCEPT", "REJECT"])
def test_reopen_review_does_not_steal_unfinished_or_terminal(production, tmp_path, decision):
    service, canvas = production
    run = complete(service, canvas, tmp_path)
    token = service.store.claim_review(run["id"])
    if decision:
        service.review_output(run["id"], token, decision, run["outputs"][0]["path"], ["checked"])
    before = service.store.get_run(run["id"])
    with pytest.raises(CanvasError):
        service.reopen_review(run["id"], "Recheck local result", before["updated_at"])
    assert service.store.get_run(run["id"]) == before


def test_reopen_review_cas_has_single_winner_and_requires_reason(production, tmp_path):
    service, canvas = production
    run = complete(service, canvas, tmp_path)
    token = service.store.claim_review(run["id"])
    reviewed = service.review_output(
        run["id"], token, "INCONCLUSIVE", run["outputs"][0]["path"], ["unclear"]
    )
    for reason, version in [(" ", reviewed["updated_at"]), ("Recheck", ""), ("Recheck", "stale")]:
        with pytest.raises(CanvasError):
            service.reopen_review(run["id"], reason, version)
    from lfo.canvas.store import CanvasStore

    def attempt(_):
        with CanvasStore(service.store.db_path) as other:
            try:
                return other.reopen_review(
                    run["id"], "Additional evidence now available", reviewed["updated_at"]
                )
            except CanvasError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(result is not None for result in results) == 1
    current = service.store.get_run(run["id"])
    assert len(current["review_history"]) == 1
    assert current["review_owner_token"] in results
    with pytest.raises(CanvasError):
        service.reopen_review(run["id"], "Cannot steal unfinished new round", current["updated_at"])


def test_missing_provider_never_silently_selects_native_image_tool(production):
    service, canvas = production
    canvas["graph"]["nodes"][0]["data"].pop("provider")
    with pytest.raises(ValueError, match="请选择"):
        resolve_snapshot(canvas, "one")


def test_recovery_handoff_after_bad_proof_keeps_audit_and_invalidates_token(production):
    service, canvas = production
    run = confirm(service, canvas)
    owner = service.claim_agent(run["id"], ["image_gen"])["owner_token"]
    service.complete_agent(run["id"], owner, status="unknown", error="pre-submit import failure")
    old = service.store.claim_recovery(run["id"], "Verify no submission occurred")
    proof = {
        "request_id": run["request_id"],
        "remote_status": "failed",
        "source": "operator_confirmation",
        "reason": "Pre-submit failure verified",
    }
    with pytest.raises(CanvasError):
        service.reconcile_run(run["id"], old, "failed", [proof])
    before = service.store.get_run(run["id"])
    response = service.handoff_recovery(
        run["id"], "Previous recovery token lost", before["updated_at"]
    )
    token = response["owner_token"]
    assert token != old
    current = service.store.get_run(run["id"])
    for field in ("status", "outputs", "error", "provider_task_id", "owner_token", "resource_key"):
        assert current[field] == before[field]
    assert current["evidence"][:-1] == before["evidence"]
    audit = current["evidence"][-1]
    assert audit["kind"] == "recovery_handoff"
    assert audit["previous_reason"] == before["recovery_reason"]
    assert audit["previous_claimed_at"] == before["recovery_claimed_at"]
    assert old not in str(service._public_run(current))
    assert token not in str(service.events(wait_seconds=0))
    with pytest.raises(CanvasError):
        service.reconcile_run(run["id"], old, "failed", proof)
    done = service.reconcile_run(run["id"], token, "failed", proof)
    assert done["status"] == "failed" and done["recovery_resolved_at"]
    with pytest.raises(CanvasError):
        service.handoff_recovery(run["id"], "Cannot reopen resolved recovery", done["updated_at"])
    from lfo.canvas.store import CanvasStore

    with CanvasStore(service.store.db_path) as reopened:
        assert audit in reopened.get_run(run["id"])["evidence"]


@pytest.mark.parametrize(
    "status", ["pending_agent", "running", "succeeded", "failed", "cancelled", "unknown"]
)
def test_recovery_handoff_rejects_unclaimed_and_unrecoverable(production, status):
    service, canvas = production
    run = confirm(service, canvas)
    if status != "pending_agent":
        service.store.claim_run(run["id"], "execution-owner")
        if status != "running":
            service.store.update_run(run["id"], status=status)
    before = service.store.get_run(run["id"])
    with pytest.raises(CanvasError):
        service.handoff_recovery(run["id"], "Lost claim", before["updated_at"])
    assert service.store.get_run(run["id"]) == before


@pytest.mark.parametrize("status", ["unknown", "failed"])
def test_recovery_handoff_cas_single_winner(production, status):
    from threading import Barrier

    from lfo.canvas.store import CanvasStore

    service, canvas = production
    run = confirm(service, canvas)
    service.store.claim_run(run["id"], "execution-owner")
    service.store.update_run(
        run["id"], status=status, stage="collection", evidence={"remote_finished": True}
    )
    service.store.claim_recovery(run["id"], "Original result verification")
    before = service.store.get_run(run["id"])
    for reason, version in [(" ", before["updated_at"]), ("Recheck", ""), ("Recheck", "stale")]:
        with pytest.raises(CanvasError):
            service.handoff_recovery(run["id"], reason, version)
    barrier = Barrier(2)

    def attempt(_):
        with CanvasStore(service.store.db_path) as other:
            barrier.wait(timeout=5)
            try:
                return other.handoff_recovery(
                    run["id"], "Lost recovery claimant", before["updated_at"]
                )
            except CanvasError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(token is not None for token in results) == 1
    current = service.store.get_run(run["id"])
    assert current["recovery_token"] in results
    assert len(current["evidence"]) == len(before["evidence"]) + 1


def test_invalid_second_file_does_not_leave_first_file_copied(production, tmp_path):
    service, canvas = production
    run = confirm(service, canvas)
    claim = service.claim_agent(run["id"], ["image_gen"])
    first = tmp_path / "first.png"
    first.write_bytes(b"image")
    with pytest.raises(ValueError, match="素材不存在"):
        service.complete_agent(
            run["id"],
            claim["owner_token"],
            outputs=[
                {"path": str(first), "kind": "image"},
                {"path": str(tmp_path / "missing.png"), "kind": "image"},
            ],
        )
    assert not service.settings.output_dir(canvas["id"], run["id"]).exists()
