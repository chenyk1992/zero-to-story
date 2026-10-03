from __future__ import annotations

import json
import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest

from lfo.comfy import transport, upscale

PROJECT = Path(__file__).resolve().parents[2]


def snapshot(source: Path, *, start_frame=0, frame_count=120, chunk_mode="auto"):
    return {
        "node_type": "video",
        "provider": "comfy-upscale",
        "model": "seedvr2-3b-int8",
        "mode": "upscale",
        "prompt": "Upscale this source video, preserve motion and soundtrack.",
        "request_id": "seedvr2-test-request",
        "parameters": {
            "start_frame": start_frame,
            "frame_count": frame_count,
            "target_width": 1920,
            "target_height": 1066,
            "chunk_mode": chunk_mode,
            "temporal_chunk_frames": 9 if chunk_mode == "manual" else None,
        },
        "inputs": {"reference_videos": [{"path": str(source), "kind": "video"}]},
    }


def probe_for(*, frames=120, width=864, height=480, fps=24.0, has_audio=True):
    return lambda path: {
        "path": str(path), "codec": "h264", "width": width, "height": height,
        "fps": fps, "frame_count": frames, "duration_seconds": frames / fps,
        "has_audio": has_audio,
    }


def test_workflow_trims_exact_five_seconds_and_uses_bounded_seedvr_graph(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    workflow, normalized = upscale.prepare_workflow(
        snapshot(source, frame_count=120), "uploaded/source.mp4", probe_fn=probe_for(frames=300)
    )

    assert normalized["start_frame"] == 0
    assert normalized["frame_count"] == 120
    assert normalized["duration_seconds"] == 5.0
    assert workflow["2"]["inputs"]["vae_name"] == upscale.VAE_NAME
    assert workflow["3"]["inputs"]["unet_name"] == upscale.MODEL_NAME
    assert workflow["4"]["class_type"] == "CanvasSeedVR2BoundedUpscale"
    assert workflow["4"]["inputs"] == {
        "video": ["1", 0], "vae": ["2", 0], "model": ["3", 0],
        "start_frame": 0, "frame_count": 120, "target_width": 1920,
        "target_height": 1066, "seed": normalized["seed"], "chunking_mode": "auto",
    }
    assert workflow["16"]["class_type"] == "SaveVideo"
    assert workflow["16"]["inputs"]["video"] == ["4", 0]
    assert workflow["16"]["inputs"]["format.codec"] == "h264"
    assert workflow["16"]["inputs"]["format.codec.encoding"] == "auto"


def test_longest_panel_uses_precise_frame_duration_and_restores_source_frame_count(tmp_path):
    source = tmp_path / "long.mp4"
    source.write_bytes(b"source")
    value = snapshot(source, frame_count=293)
    workflow, normalized = upscale.prepare_workflow(value, "upload", probe_fn=probe_for(frames=500))

    assert normalized["duration_seconds"] == pytest.approx(293 / 24)
    assert workflow["4"]["inputs"]["frame_count"] == 293
    assert workflow["4"]["inputs"]["start_frame"] == 0


def test_manual_mode_uses_only_safe_nine_pixel_frame_chunks(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    workflow, _ = upscale.prepare_workflow(
        snapshot(source, chunk_mode="manual"), "upload", probe_fn=probe_for(frames=300)
    )
    assert workflow["4"]["inputs"]["chunking_mode"] == "manual"
    assert workflow["4"]["inputs"]["chunking_mode.frames_per_chunk"] == 9


@pytest.mark.parametrize("parameter,value", [
    ("start_frame", -1),
    ("frame_count", 0),
    ("frame_count", 301),
    ("target_height", 1080),  # conflicts with the locked aspect-preserving target
    ("temporal_chunk_frames", 13),
    ("chunk_mode", "disabled"),
])
def test_unsafe_range_or_oom_parameters_fail_before_provider(tmp_path, parameter, value):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    value_snapshot = snapshot(source)
    value_snapshot["parameters"][parameter] = value
    with pytest.raises(ValueError):
        upscale.normalize_snapshot(value_snapshot, probe_fn=probe_for(frames=300))


def test_duration_over_limit_and_non_cfr_source_are_rejected(tmp_path):
    source = tmp_path / "long.mp4"
    source.write_bytes(b"source")
    with pytest.raises(ValueError, match="15 秒"):
        upscale.normalize_snapshot(snapshot(source, frame_count=361), probe_fn=probe_for(frames=500))
    payload = {
        "streams": [{
            "codec_type": "video", "codec_name": "h264", "width": 864, "height": 480,
            "r_frame_rate": "24/1", "avg_frame_rate": "25/1", "nb_read_frames": "300",
            "duration": "12.5",
        }],
        "format": {"duration": "12.5"},
    }
    def fake_ffprobe(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")

    source.write_bytes(b"video")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(upscale, "run_command", fake_ffprobe)
        with pytest.raises(ValueError, match="恒定帧率"):
            upscale.probe_video(source)


def test_input_bounds_are_checked_before_upload_or_submission(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    with pytest.raises(ValueError, match="超出源视频范围"):
        upscale.normalize_snapshot(snapshot(source, start_frame=290, frame_count=20), probe_fn=probe_for(frames=300))


def test_only_one_matching_mp4_is_materialized_and_fully_decoded(tmp_path, monkeypatch):
    downloaded = tmp_path / "2c17cac0_000.mp4"
    downloaded.write_bytes(b"downloaded LoadVideo preview: 864x480, 175f")
    source = tmp_path / "2c17cac0_001.mp4"
    source.write_bytes(b"downloaded SaveVideo result: 1920x1066, 120f")
    out = tmp_path / "run"
    out.mkdir()
    normalized = {
        "width": 1920, "height": 1066, "frame_count": 120, "start_frame": 0,
        "source": {"fps": 24.0, "has_audio": True},
    }
    monkeypatch.setattr(upscale.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, b"", b""))
    source_infos = {
        downloaded.name: probe_for(frames=175, width=864, height=480)(downloaded),
        source.name: probe_for(frames=120, width=1920, height=1066)(source),
    }
    result = transport.ComfyResult("provider-task", (
        # The MCP normalizer may flatten both rows to absolute/output references and
        # omit node IDs. Selection must then follow the frozen media contract.
        transport.OutputRef(str(downloaded), file_type="absolute"),
        transport.OutputRef(str(source), file_type="absolute"),
    ))
    output = upscale.materialize_video(
        result, out, normalized,
        probe_fn=lambda path: source_infos[Path(path).name.removeprefix(".upscaled-candidate.mp4")]
        if Path(path).name != ".upscaled-candidate.mp4" else source_infos[source.name],
    )

    delivered = Path(output["path"])
    assert delivered.name == "upscaled.mp4"
    assert delivered.read_bytes() == source.read_bytes()
    assert output["metadata"]["sha256"]
    assert output["metadata"]["selected_frame_count"] == 120


def test_wrong_output_frame_count_is_rejected_without_publishing(tmp_path, monkeypatch):
    source = tmp_path / "provider-result.mp4"
    source.write_bytes(b"incorrect result")
    out = tmp_path / "run"
    out.mkdir()
    normalized = {
        "width": 1920, "height": 1066, "frame_count": 120, "start_frame": 0,
        "source": {"fps": 24.0, "has_audio": True},
    }
    monkeypatch.setattr(upscale.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, b"", b""))
    result = transport.ComfyResult("provider-task", (transport.OutputRef(str(source), node_id="16"),))

    with pytest.raises(ValueError, match="帧数"):
        upscale.materialize_video(result, out, normalized, probe_fn=probe_for(frames=119, width=1920, height=1066))
    assert not (out / "upscaled.mp4").exists()
    assert not (out / ".upscaled-candidate.mp4").exists()


def test_ambiguous_matching_downloads_are_rejected(tmp_path):
    first = tmp_path / "output-a.mp4"
    second = tmp_path / "output-b.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    out = tmp_path / "run"
    out.mkdir()
    normalized = {
        "width": 1920, "height": 1066, "frame_count": 120, "start_frame": 0,
        "source": {"fps": 24.0, "has_audio": True},
    }
    result = transport.ComfyResult("provider-task", (
        transport.OutputRef(str(first)), transport.OutputRef(str(second)),
    ))

    with pytest.raises(ValueError, match="多个 MP4"):
        upscale.materialize_video(result, out, normalized, probe_fn=probe_for(frames=120, width=1920, height=1066))
    assert not (out / "upscaled.mp4").exists()


def test_unknown_remote_request_cannot_be_submitted_twice(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(upscale, "probe_video", probe_for(frames=300))
    monkeypatch.setattr(transport, "ready_session", lambda *_: nullcontext(object()))
    monkeypatch.setattr(transport, "upload_input", lambda *_: "uploaded/source.mp4")
    monkeypatch.setattr(transport, "model_files", lambda _session, folder: [
        upscale.MODEL_NAME if folder == "diffusion_models" else upscale.VAE_NAME,
    ])
    monkeypatch.setattr(transport, "preflight_workflow", lambda *_: None)
    submissions = []

    def lose_submit_reply(*_args, **kwargs):
        submissions.append(1)
        kwargs["guard"].submitted("original-seedvr-task")
        raise transport.ExecutorError("connection lost", status="unknown", provider_task_id="original-seedvr-task")

    monkeypatch.setattr(transport, "run_workflow", lose_submit_reply)
    request = snapshot(source)
    output_dir = tmp_path / "run"
    config = transport.RuntimeConfig()

    with pytest.raises(transport.ExecutorError) as first:
        upscale.execute_snapshot(request, output_dir, config, emit=lambda _: None)
    assert first.value.status == "unknown"
    with pytest.raises(transport.ExecutorError):
        upscale.execute_snapshot(request, output_dir, config, emit=lambda _: None)
    assert submissions == [1]


def test_capability_is_canvas_worker_only_and_shares_video_resource():
    capability = json.loads((PROJECT / ".agents/skills/comfy-upscale-executor/capability.json").read_text(encoding="utf-8"))
    assert capability["execution"] == "script"
    assert capability["entrypoint"] == "scripts/execute.py"
    assert capability["resource"] == {"key": "video", "capacity": 1}
    assert capability["input_rules"]["upscale"]["max_counts"]["reference_videos"] == 1
    assert capability["input_rules"]["upscale"]["file_extensions"]["reference_videos"] == [".mp4", ".mov", ".mkv", ".webm"]
