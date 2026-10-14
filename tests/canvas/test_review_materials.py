from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from lfo.canvas.review_materials import prepare_video_review
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings
from lfo.media._ffmpeg import probe, run_command

PROJECT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clip(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("real FFmpeg is required for media integration")
    path = tmp_path / "source.mp4"
    run_command(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x288:rate=24",
                 "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)])
    return path


def _output(path):
    return {"kind": "video", "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "metadata": probe(path)}


def test_preparation_preserves_original_and_stream_and_reuses_verified_receipt(clip, monkeypatch):
    original = clip.read_bytes()
    output = _output(clip)
    receipt = prepare_video_review(output, clip.parent)
    assert receipt["status"] == "ready" and receipt["decoded_frames"] == 24
    assert receipt["decode_verified"] and receipt["content_review"] == "NOT_REVIEWED"
    silent = Path(receipt["artifacts"]["silent_video"]["path"])
    assert probe(silent)["has_audio"] is False
    def video_hash(path):
        return run_command(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
                            "-c:v", "copy", "-f", "streamhash", "-hash", "sha256", "-"]).stdout
    assert video_hash(clip) == video_hash(silent)
    assert clip.read_bytes() == original
    def unexpected_decode(*_args, **_kwargs):
        pytest.fail("intact receipt must not decode the same source again")
    monkeypatch.setattr("lfo.canvas.review_materials.run_command", unexpected_decode)
    assert prepare_video_review(output, clip.parent)["artifacts"] == receipt["artifacts"]
    json.dumps(receipt)  # persisted metadata must not contain circular references


def test_tampered_candidate_is_repaired_but_changed_source_is_rejected(clip):
    output = _output(clip)
    first = prepare_video_review(output, clip.parent)
    old_sheet = Path(first["artifacts"]["contact_sheet"]["path"])
    old_sheet.write_bytes(b"damaged preview")
    repaired = prepare_video_review(output, clip.parent)
    assert repaired["artifacts"] != first["artifacts"]
    assert old_sheet.read_bytes() == b"damaged preview"  # never replace shown files
    clip.write_bytes(clip.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="摘要不一致"):
        prepare_video_review(output, clip.parent)


def _service_run(tmp_path):
    service = CanvasService(CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media"),
                            start_worker=False)
    canvas = service.store.create_canvas("test", {"nodes": [{"id": "v", "type": "video",
        "position": {"x": 0, "y": 0}, "data": {"provider": "comfy", "model": "h3",
        "mode": "t2v", "prompt": "test", "duration": 1, "aspect_ratio": "9:16",
        "megapixels": .4, "options": {"comfy": {"sampler_profile": "native", "steps": 8}}}}],
        "edges": []})
    run = service.confirm(canvas["id"], "v", canvas["version"], "one-request")
    service.store.claim_run(run["id"], owner_token="owner")
    return service, run


def test_success_automatically_exposes_materials_without_content_acceptance(tmp_path, clip):
    service, run = _service_run(tmp_path)
    try:
        result = service.complete_agent(run["id"], "owner", outputs=[{"path": str(clip), "kind": "video"}])
        assert result["status"] == "succeeded" and result["review"] is None
        materials = result["outputs"][0]["metadata"]["review_materials"]
        assert materials["status"] == "ready" and materials["decoded_frames"] == 24
        packet = service.read_canvas(run["canvas_id"], node_id="v")
        assert packet["production"]["v"]["latest_run"]["outputs"] == result["outputs"]
        assert service.store.list_runs(run["canvas_id"])[0]["id"] == run["id"]
    finally:
        service.close()


def test_material_failure_keeps_successful_run_and_does_not_hold_confirmation_lock(tmp_path, clip, monkeypatch):
    service, run = _service_run(tmp_path)
    calls = []
    def fail(*_args):
        assert service._confirm_lock.acquire(blocking=False)
        service._confirm_lock.release()
        calls.append(1)
        raise RuntimeError("preview encoder unavailable")
    monkeypatch.setattr("lfo.canvas.service.prepare_video_review", fail)
    try:
        result = service.complete_agent(run["id"], "owner", outputs=[{"path": str(clip), "kind": "video"}])
        assert result["status"] == "succeeded" and result["review"] is None
        assert result["outputs"][0]["metadata"]["review_materials"]["status"] == "failed"
        assert calls == [1] and len(service.store.list_runs(run["canvas_id"])) == 1
        with pytest.raises(Exception):
            service.complete_agent(run["id"], "wrong-owner", outputs=[])
    finally:
        service.close()
