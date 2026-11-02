from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from lfo.comfy import local_video_recovery as recovery


@pytest.fixture
def recovery_case(tmp_path, monkeypatch):
    root = tmp_path / "output"
    directory = root / "canvas" / "node-1" / "request-1"
    directory.mkdir(parents=True)
    video = directory / "video_00001_.mp4"
    video.write_bytes(b"original video")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    image_hash = "a" * 64
    snapshot = {
        "provider": "comfy",
        "node_type": "video",
        "mode": "r2v",
        "node_id": "node-1",
        "prompt": "exact prompt\n",
        "parameters": {"duration": 3},
        "inputs": {
            "reference_images": [{"sha256": image_hash}],
            "reference_videos": [],
            "reference_audios": [],
        },
    }
    run = {
        "status": "unknown",
        "node_id": "node-1",
        "request_id": "request-1",
        "provider_task_id": "task-1",
        "snapshot": snapshot,
    }
    now = datetime.now(UTC)
    receipt = {
        "request_id": "request-1",
        "provider_task_id": "task-1",
        "updated_at": (now - timedelta(minutes=2)).isoformat(),
    }
    workflow = {
        "1": {"_meta": {"title": "LFO.Prompt"}, "inputs": {"value": snapshot["prompt"]}},
        "2": {
            "_meta": {"title": "LFO.SaveVideo"},
            "class_type": "SaveVideo",
            "inputs": {"filename_prefix": "canvas/node-1/request-1/video"},
        },
        "3": {"_meta": {"title": "Canvas.ReferenceImage1"}, "is_changed": [image_hash]},
    }
    probe = {
        "format": {"duration": "3.042", "tags": {"prompt": json.dumps(workflow)}},
        "streams": [{"codec_type": "video", "width": 960, "height": 544}, {"codec_type": "audio"}],
    }
    monkeypatch.setattr(
        recovery, "_tool", lambda cmd: json.dumps(probe) if cmd[0] == "ffprobe" else ""
    )
    return {
        "run": run,
        "receipt": receipt,
        "output_root": root,
        "video": video,
        "server_restarted_at": now + timedelta(seconds=0.1),
        "expected_sha256": digest,
        "probe": probe,
    }


def check(case):
    args = {k: v for k, v in case.items() if k != "probe"}
    return recovery.verify_recovered_video(**args)


def test_verified_local_artifact_preserves_unknown_provider_status(recovery_case):
    # mtime predates a verified restart, which must itself not be in the future.
    import os

    case = recovery_case
    restarted = datetime.now(UTC) - timedelta(seconds=1)
    os.utime(case["video"], (restarted.timestamp() - 1, restarted.timestamp() - 1))
    case["server_restarted_at"] = restarted
    result = check(case)
    assert result["provider_terminal_status"] == "unknown"
    assert result["sha256"] == case["expected_sha256"]


def test_multiple_image_references_match_in_order(recovery_case):
    import os

    case = recovery_case
    restarted = datetime.now(UTC) - timedelta(seconds=1)
    os.utime(case["video"], (restarted.timestamp() - 1, restarted.timestamp() - 1))
    case["server_restarted_at"] = restarted
    refs = case["run"]["snapshot"]["inputs"]["reference_images"]
    refs.append({"sha256": "b" * 64})
    workflow = json.loads(case["probe"]["format"]["tags"]["prompt"])
    workflow["4"] = {"_meta": {"title": "Canvas.ReferenceImage2"}, "is_changed": ["b" * 64]}
    case["probe"]["format"]["tags"]["prompt"] = json.dumps(workflow)
    assert check(case)["provider_terminal_status"] == "unknown"
    workflow["4"]["is_changed"] = ["c" * 64]
    case["probe"]["format"]["tags"]["prompt"] = json.dumps(workflow)
    with pytest.raises(ValueError, match="reference differs"):
        check(case)


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_request",
        "wrong_task",
        "wrong_hash",
        "wrong_prompt",
        "wrong_reference",
        "wrong_prefix",
        "multiple_files",
        "restart_before_submit",
        "missing_audio",
        "wrong_duration",
        "outside_root",
        "extra_reference_node",
        "too_many_references",
        "unsupported_video_reference",
        "unsupported_first_frame",
    ],
)
def test_invalid_evidence_never_verifies(recovery_case, defect):
    import os

    case = recovery_case
    restarted = datetime.now(UTC) - timedelta(seconds=1)
    os.utime(case["video"], (restarted.timestamp() - 1, restarted.timestamp() - 1))
    case["server_restarted_at"] = restarted
    workflow = json.loads(case["probe"]["format"]["tags"]["prompt"])
    if defect == "wrong_request":
        case["receipt"]["request_id"] = "other"
    elif defect == "wrong_task":
        case["receipt"]["provider_task_id"] = "other"
    elif defect == "wrong_hash":
        case["expected_sha256"] = "b" * 64
    elif defect == "wrong_prompt":
        workflow["1"]["inputs"]["value"] = "different"
    elif defect == "wrong_reference":
        workflow["3"]["is_changed"] = ["b" * 64]
    elif defect == "wrong_prefix":
        workflow["2"]["inputs"]["filename_prefix"] = "other"
    elif defect == "multiple_files":
        (case["video"].parent / "video_00002_.mp4").write_bytes(b"other")
    elif defect == "restart_before_submit":
        case["server_restarted_at"] = datetime.now(UTC) - timedelta(days=1)
    elif defect == "missing_audio":
        case["probe"]["streams"].pop()
    elif defect == "wrong_duration":
        case["probe"]["format"]["duration"] = "8"
    elif defect == "outside_root":
        other = case["output_root"].parent / "other.mp4"
        other.write_bytes(case["video"].read_bytes())
        case["video"] = other
    elif defect == "extra_reference_node":
        workflow["4"] = {"_meta": {"title": "Canvas.ReferenceImage2"}, "is_changed": ["b" * 64]}
    elif defect == "too_many_references":
        case["run"]["snapshot"]["inputs"]["reference_images"] = [{"sha256": "a" * 64}] * 10
    elif defect == "unsupported_video_reference":
        case["run"]["snapshot"]["inputs"]["reference_videos"] = [{"sha256": "a" * 64}]
    elif defect == "unsupported_first_frame":
        case["run"]["snapshot"]["inputs"]["first_frame"] = {"sha256": "a" * 64}
    case["probe"]["format"]["tags"]["prompt"] = json.dumps(workflow)
    with pytest.raises(ValueError):
        check(case)
