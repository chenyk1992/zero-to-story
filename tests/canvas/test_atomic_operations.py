"""Tests for single-step atomic canvas operations (bind-accepted-tail and batch confirm)."""

from __future__ import annotations

import json
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from lfo.canvas.graph import CanvasError, GraphValidationError, resolve_snapshot
from lfo.canvas.server import CanvasHTTPServer
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import VersionConflictError

PROJECT = Path(__file__).resolve().parents[2]


def _make_image(path: Path, *, color: str = "navy") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=96x64",
            "-frames:v",
            "1",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return path


def _make_mp4(path: Path, *, color: str = "teal") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=96x64:r=12:d=0.5",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return path


def _video_node(node_id: str, *, prompt: str = "镜头持续推进") -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "video",
        "position": {"x": 100, "y": 100},
        "data": {
            "label": node_id,
            "prompt": prompt,
            "provider": "aistudio-video",
            "model": "gemini-omni-1.2-flash",
            "mode": "i2v" if node_id == "v2" else "t2v",
            "duration": 5,
            "aspect_ratio": "16:9",
        },
    }


def test_bind_accepted_tail_is_atomic_reuses_tail_and_preserves_other_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", "http://127.0.0.1:2048")
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    try:
        ref_file = _make_image(settings.media_root / "projects" / "demo" / "ref.png")
        ref_asset = service.media.import_file(str(ref_file))
        existing_derived_img = _make_image(settings.media_root / "projects" / "demo" / "keep.png", color="red")
        v1_node = {
            **_video_node("v1"),
            "data": {
                **_video_node("v1")["data"],
                "derived_outputs": [
                    {
                        "id": "existing-derived",
                        "label": "既有派生",
                        "asset": {"path": str(existing_derived_img), "kind": "image"},
                    }
                ],
            },
        }
        v2_node = _video_node("v2")
        audio_node = {
            "id": "aud",
            "type": "audio",
            "position": {"x": 300, "y": 100},
            "data": {"prompt": "旁白", "provider": "comfy-qwen-tts", "mode": "custom_voice"},
        }
        graph = {
            "nodes": [
                {"id": "ref", "type": "asset", "position": {"x": 0, "y": 0}, "data": {"asset": ref_asset}},
                v1_node,
                v2_node,
                audio_node,
            ],
            "edges": [
                {"id": "old-ff", "source": "ref", "sourceHandle": "output", "target": "v2", "targetHandle": "first_frame"},
                {"id": "keep-ref", "source": "ref", "sourceHandle": "output", "target": "v2", "targetHandle": "reference_image"},
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": ["v1"],
        }
        canvas = service.store.create_canvas("tail-bind", graph)
        run = service.confirm(canvas["id"], "v1", canvas["version"], "req-v1")
        claimed = service.store.claim_run(run["id"], owner_token="tok-v1")
        clip = _make_mp4(tmp_path / "v1.mp4")
        collected = service._collect_outputs(
            [{"path": str(clip), "kind": "video"}], canvas["id"], claimed["id"]
        )
        succeeded = service.store.update_run(
            claimed["id"],
            status="succeeded",
            outputs=collected,
            stage="media_validation",
        )

        # Un-accepted run is rejected with no side effects
        with pytest.raises(ValueError, match="ACCEPT"):
            service.bind_accepted_tail(canvas["id"], succeeded["id"], "v2", canvas["version"])

        # Accept the output
        rev_token = service.store.claim_review(succeeded["id"])
        service.review_output(
            succeeded["id"],
            rev_token,
            "ACCEPT",
            succeeded["outputs"][0]["path"],
            ["画面与末态核对通过"],
            end_state={"pose": "standing"},
        )

        # Version conflict does not write any tail file
        out_dir = settings.output_dir(canvas["id"], succeeded["id"])
        before_tails = list(out_dir.glob("accepted-tail-*.png"))
        with pytest.raises(VersionConflictError):
            service.bind_accepted_tail(canvas["id"], succeeded["id"], "v2", canvas["version"] + 99)
        assert list(out_dir.glob("accepted-tail-*.png")) == before_tails

        # Incompatible target node (audio) does not leave stray tail file
        with pytest.raises(GraphValidationError):
            service.bind_accepted_tail(canvas["id"], succeeded["id"], "aud", canvas["version"])
        assert list(out_dir.glob("accepted-tail-*.png")) == before_tails

        # Atomic bind succeeds
        receipt = service.bind_accepted_tail(canvas["id"], succeeded["id"], "v2", canvas["version"])
        assert receipt["version"] == canvas["version"] + 1
        assert receipt["edge"]["targetHandle"] == "first_frame"
        assert receipt["edge"]["source_run_id"] == succeeded["id"]
        assert receipt["edge"]["require_accept"] is True

        # No new runs created by draft binding
        assert len(service.store.list_runs(canvas["id"])) == 1

        saved = service.store.get_canvas(canvas["id"])
        saved_v1 = next(n for n in saved["graph"]["nodes"] if n["id"] == "v1")
        derived_ids = [d["id"] for d in saved_v1["data"]["derived_outputs"]]
        assert derived_ids == ["existing-derived", receipt["tail"]["id"]]
        edge_ids = [e["id"] for e in saved["graph"]["edges"]]
        assert "old-ff" not in edge_ids
        assert "keep-ref" in edge_ids

        # Target snapshot resolves accepted_sha256 from bound tail
        v2_snap = resolve_snapshot(saved, "v2", service.store.list_runs(canvas["id"]))
        assert v2_snap["inputs"]["first_frame"]["accepted_sha256"] == receipt["tail"]["asset"]["sha256"]
    finally:
        service.close()


def test_confirm_batch_all_or_nothing_and_idempotency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", "http://127.0.0.1:2048")
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    try:
        frame = _make_image(settings.media_root / "projects" / "demo" / "start.png")
        asset = service.media.import_file(str(frame))
        graph = {
            "nodes": [
                {"id": "a1", "type": "asset", "position": {"x": 0, "y": 0}, "data": {"asset": asset}},
                _video_node("v1"),
                _video_node("v_bad", prompt="   "),  # missing prompt fails preflight
                {
                    "id": "v3",
                    "type": "video",
                    "position": {"x": 200, "y": 0},
                    "data": {
                        "prompt": "第三镜独立空镜",
                        "provider": "aistudio-video",
                        "model": "gemini-omni-1.2-flash",
                        "mode": "t2v",
                        "duration": 5,
                        "aspect_ratio": "16:9",
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "a1", "sourceHandle": "output", "target": "v1", "targetHandle": "reference_image"}
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": [],
        }
        # Adjust v1 mode to r2v since ref edge exists
        graph["nodes"][1]["data"]["mode"] = "r2v"
        canvas = service.store.create_canvas("batch", graph)

        # Item 2 fails preflight -> ZERO runs created and ZERO frozen input dirs left behind
        with pytest.raises(ValueError):
            service.confirm_batch(
                canvas["id"],
                canvas["version"],
                [
                    {"node_id": "v1", "request_id": "b-req-1"},
                    {"node_id": "v_bad", "request_id": "b-req-2"},
                ],
            )
        assert service.store.list_runs(canvas["id"]) == []
        assert not (settings.data_dir / "inputs").exists() or list((settings.data_dir / "inputs").iterdir()) == []

        # Valid batch creates both runs atomically
        result = service.confirm_batch(
            canvas["id"],
            canvas["version"],
            [
                {"node_id": "v1", "request_id": "b-req-1"},
                {"node_id": "v3", "request_id": "b-req-3"},
            ],
        )
        assert len(result["runs"]) == 2
        assert [r["node_id"] for r in result["runs"]] == ["v1", "v3"]

        # Idempotent retry returns the exact same runs
        retried = service.confirm_batch(
            canvas["id"],
            canvas["version"],
            [
                {"node_id": "v1", "request_id": "b-req-1"},
                {"node_id": "v3", "request_id": "b-req-3"},
            ],
        )
        assert [r["id"] for r in retried["runs"]] == [r["id"] for r in result["runs"]]

        # Request conflict across nodes rejected
        with pytest.raises(CanvasError) as exc_info:
            service.confirm_batch(
                canvas["id"],
                canvas["version"],
                [{"node_id": "v3", "request_id": "b-req-1"}],
            )
        assert exc_info.value.code == "request_conflict"
    finally:
        service.close()


def test_http_routes_for_atomic_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", "http://127.0.0.1:2048")
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    service = CanvasService(settings, start_worker=False)
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        canvas = service.store.create_canvas(
            "http-batch",
            {
                "nodes": [_video_node("v1")],
                "edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "selection": [],
            },
        )
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/canvases/{canvas['id']}/runs/batch",
            data=json.dumps(
                {"version": canvas["version"], "items": [{"node_id": "v1", "request_id": "http-req-1"}]}
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "X-Canvas-Request": "1"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 201
            payload = json.loads(resp.read().decode("utf-8"))
        assert len(payload["runs"]) == 1
        assert payload["runs"][0]["request_id"] == "http-req-1"
    finally:
        server.shutdown()
        server.server_close()
        service.close()
