from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from lfo.canvas.graph import CanvasError
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import CanvasStore


@pytest.fixture
def rejected_video(tmp_path, monkeypatch):
    service = CanvasService(
        CanvasSettings(Path(__file__).resolve().parents[2], tmp_path / "state", tmp_path / "media"),
        start_worker=False,
    )
    graph = {
        "nodes": [{"id": "v", "type": "video", "position": {"x": 0, "y": 0}, "data": {}}],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }
    canvas = service.store.create_canvas("derived", graph)
    run = service.store.create_run(
        canvas["id"],
        "v",
        canvas["version"],
        "source-request",
        {
            "node_id": "v",
            "node_type": "video",
            "provider": "comfy",
            "model": "h3",
            "mode": "t2v",
            "prompt": "fixed",
            "parameters": {},
            "inputs": {},
        },
        status="pending_agent",
    )
    service.store.claim_run(run["id"], owner_token="execution-owner")
    folder = service.settings.output_dir(canvas["id"], run["id"])
    folder.mkdir(parents=True)
    original = folder / "original.mp4"
    original.write_bytes(b"rejected video")
    run = service.store.update_run(
        run["id"],
        status="succeeded",
        outputs=[service.media.asset(original)],
        provider_task_id="original-provider-id",
    )
    token = service.store.claim_review(run["id"])
    service.review_output(run["id"], token, "REJECT", str(original), ["visible continuity error"])
    candidate = folder / "derived.mp4"
    candidate.write_bytes(b"repaired video")
    monkeypatch.setattr(
        "lfo.canvas.service.probe",
        lambda _: {"duration_ms": 1000, "width": 480, "height": 864, "codec": "h264"},
    )
    monkeypatch.setattr(
        "lfo.canvas.service.run_command",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, "frame=24\nprogress=end\n", ""),
    )
    yield service, run["id"], original, candidate, token
    service.close()


def submit(service, run_id, candidate, **overrides):
    body = dict(
        reason="Actual crop fixes visible continuity error",
        expected_updated_at=service.store.get_run(run_id)["updated_at"],
        decision="ACCEPT",
        output_path=str(candidate),
        evidence=["actual all-frame inspection"],
        end_state={"contact": "released"},
        unverified=[],
    )
    body.update(overrides)
    return service.review_derived(run_id, **body)


def test_derived_preserves_source_history_and_invalidates_old_owner(rejected_video):
    service, rid, original, candidate, token = rejected_video
    before = service.store.get_run(rid)
    accepted = submit(service, rid, candidate)
    assert accepted["review"]["decision"] == "ACCEPT"
    assert accepted["review"]["output_sha256"] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    entry = accepted["review_history"][0]
    assert entry["review"] == before["review"]
    assert entry["reviewed_at"] == before["reviewed_at"]
    assert entry["reason"] and entry["derived_output_path"] == str(candidate)
    assert "owner_token" not in str(entry)
    for field in ["outputs", "snapshot", "provider_task_id", "request_id"]:
        assert accepted[field] == before[field]
    assert original.read_bytes() == b"rejected video"
    assert len(service.store.list_runs()) == 1
    assert "review_owner_token" not in accepted
    with pytest.raises(CanvasError):
        service.store.review_run(rid, accepted["review"], owner_token=token)
    with CanvasStore(service.store.db_path) as other:
        assert other.get_run(rid)["review_history"] == accepted["review_history"]


@pytest.mark.parametrize(
    "case", ["same_path", "renamed", "outside", "missing", "image", "changed_source"]
)
def test_derived_rejects_invalid_files_without_mutation(rejected_video, tmp_path, case):
    service, rid, original, candidate, _ = rejected_video
    if case == "same_path":
        candidate = original
    elif case == "renamed":
        candidate.write_bytes(original.read_bytes())
    elif case == "outside":
        candidate = service.settings.media_root / "outside.mp4"
        candidate.write_bytes(b"different")
    elif case == "missing":
        candidate = candidate.with_name("missing.mp4")
    elif case == "image":
        candidate = candidate.with_suffix(".png")
        candidate.write_bytes(b"image")
    else:
        original.write_bytes(b"overwritten source")
    before = service.store.get_run(rid)
    with pytest.raises((ValueError, CanvasError)):
        submit(service, rid, candidate)
    assert service.store.get_run(rid) == before


@pytest.mark.parametrize("case", ["probe", "decode", "no_frames", "changed_candidate"])
def test_derived_requires_stable_decodable_video(rejected_video, monkeypatch, case):
    service, rid, _, candidate, _ = rejected_video
    if case == "probe":
        monkeypatch.setattr("lfo.canvas.service.probe", lambda _: {"duration_ms": 0})
    else:

        def decode(*args, **kwargs):
            if case == "decode":
                raise RuntimeError("corrupt frame payload")
            if case == "changed_candidate":
                candidate.write_bytes(b"file edited during decode")
            return subprocess.CompletedProcess(
                args[0], 0, "frame=0" if case == "no_frames" else "frame=24", ""
            )

        monkeypatch.setattr("lfo.canvas.service.run_command", decode)
    before = service.store.get_run(rid)
    with pytest.raises((ValueError, RuntimeError)):
        submit(service, rid, candidate)
    assert service.store.get_run(rid) == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": " "},
        {"expected_updated_at": "stale"},
        {"decision": "INCONCLUSIVE"},
        {"evidence": []},
        {"unverified": ["dialogue unknown"]},
    ],
)
def test_derived_input_guards(rejected_video, overrides):
    service, rid, _, candidate, _ = rejected_video
    before = service.store.get_run(rid)
    with pytest.raises(CanvasError):
        submit(service, rid, candidate, **overrides)
    assert service.store.get_run(rid) == before


def test_derived_cannot_reuse_earlier_rejected_content(rejected_video):
    service, rid, original, candidate, _ = rejected_video
    submit(service, rid, candidate, decision="REJECT")
    copy = candidate.with_name("original-renamed.mp4")
    copy.write_bytes(original.read_bytes())
    before = service.store.get_run(rid)
    with pytest.raises(ValueError):
        submit(service, rid, copy)
    assert service.store.get_run(rid) == before


def test_derived_cas_rechecks_after_media_validation(rejected_video, monkeypatch):
    service, rid, _, candidate, _ = rejected_video
    before = service.store.get_run(rid)

    def decode(*args, **kwargs):
        assert service._confirm_lock.locked()
        monkeypatch.setattr("lfo.canvas.store._now", lambda: "2099-01-01T00:00:00.000Z")
        service.store.set_attention(rid, "paused", "concurrent operator update")
        return subprocess.CompletedProcess(args[0], 0, "frame=24", "")

    monkeypatch.setattr("lfo.canvas.service.run_command", decode)
    with pytest.raises(CanvasError, match="run changed"):
        submit(service, rid, candidate)
    after = service.store.get_run(rid)
    assert after["review"] == before["review"] and after["review_history"] == []


def test_derived_non_succeeded_run_is_not_reviewable(rejected_video):
    service, rid, _, candidate, _ = rejected_video
    with service.store._lock, service.store._transaction():
        service.store._conn().execute("UPDATE node_runs SET status = 'failed' WHERE id = ?", (rid,))
    before = service.store.get_run(rid)
    with pytest.raises(CanvasError):
        submit(service, rid, candidate)
    assert service.store.get_run(rid) == before


def test_derived_actual_video_decode(rejected_video, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe required for real decode check")
    from lfo.media._ffmpeg import probe, run_command

    service, rid, _, candidate, _ = rejected_video
    run_command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=16x16:r=24",
            "-t",
            "0.25",
            "-c:v",
            "mpeg4",
            str(candidate),
        ]
    )
    monkeypatch.setattr("lfo.canvas.service.probe", probe)
    monkeypatch.setattr("lfo.canvas.service.run_command", run_command)
    assert submit(service, rid, candidate)["review"]["decision"] == "ACCEPT"


@pytest.mark.parametrize("review_state", [None, "INCONCLUSIVE", "ACCEPT"])
def test_derived_does_not_steal_other_review_states(rejected_video, review_state):
    service, rid, _, candidate, _ = rejected_video
    # Simulate states produced by the normal claim/review APIs, without changing their rules.
    row = service.store.get_run(rid)
    review = dict(row["review"], decision=review_state) if review_state else None
    with service.store._lock, service.store._transaction():
        service.store._conn().execute(
            "UPDATE node_runs SET review = ?, reviewed_at = ? WHERE id = ?",
            (json.dumps(review) if review else None, row["reviewed_at"] if review else None, rid),
        )
    before = service.store.get_run(rid)
    with pytest.raises(CanvasError):
        submit(service, rid, candidate)
    assert service.store.get_run(rid) == before


def test_derived_store_cas_and_history_are_atomic(rejected_video, monkeypatch):
    service, rid, _, candidate, _ = rejected_video
    before = service.store.get_run(rid)
    review = dict(
        before["review"],
        decision="REJECT",
        output_path=str(candidate),
        output_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
    )

    def attempt(_):
        with CanvasStore(service.store.db_path) as other:
            try:
                return other.review_derived(rid, "inspected new file", before["updated_at"], review)
            except CanvasError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(item is not None for item in results) == 1
    assert len(service.store.get_run(rid)["review_history"]) == 1

    current = service.store.get_run(rid)
    next_review = dict(
        review, output_path=str(candidate.with_name("next.mp4")), output_sha256="f" * 64
    )

    def broken_event(*args, **kwargs):
        raise RuntimeError("event write failed")

    monkeypatch.setattr(service.store, "_emit_event", broken_event)
    with pytest.raises(RuntimeError):
        service.store.review_derived(
            rid, "next checked derivation", current["updated_at"], next_review
        )
    assert service.store.get_run(rid) == current


def test_derived_mcp_uses_public_http_route(rejected_video):
    pytest.importorskip("mcp")
    import anyio

    from lfo.canvas.mcp_server import create_mcp
    from lfo.canvas.server import CanvasHTTPServer

    service, rid, _, candidate, _ = rejected_video
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    service.settings.discovery.write_text(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{server.server_address[1]}",
                "project_root": str(service.settings.project_root),
            }
        ),
        encoding="utf-8",
    )

    async def exercise():
        mcp = create_mcp(service.settings)
        tools = await mcp.list_tools()
        schema = next(t.inputSchema for t in tools if t.name == "canvas_review_derived")
        assert "owner_token" not in schema["properties"]
        args = dict(
            run_id=rid,
            reason="checked actual new file",
            expected_updated_at=service.store.get_run(rid)["updated_at"],
            decision="ACCEPT",
            output_path=str(candidate),
            evidence=["checked"],
        )
        await mcp.call_tool("canvas_review_derived", args)
        assert service.store.get_run(rid)["review"]["decision"] == "ACCEPT"
        with pytest.raises(Exception, match="run changed"):
            await mcp.call_tool("canvas_review_derived", args)

    try:
        anyio.run(exercise)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
