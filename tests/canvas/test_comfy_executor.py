from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from contextlib import contextmanager
from typing import Any

import pytest

SKILL_ROOT = pathlib.Path(__file__).resolve().parents[2] / ".agents" / "skills" / "comfy-video-executor"
sys.path.insert(0, str(SKILL_ROOT))

from lfo.comfy import transport
from scripts import execute as executor


def _asset(tmp_path: pathlib.Path, name: str, kind: str) -> dict[str, str]:
    path = tmp_path / name
    path.write_bytes(name.encode("utf-8"))
    return {"path": str(path), "kind": kind}


def _snapshot(tmp_path: pathlib.Path, mode: str = "t2v") -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "first_frame": None,
        "last_frame": None,
        "reference_images": [],
        "reference_videos": [],
        "reference_audios": [],
    }
    if mode == "i2v":
        inputs["first_frame"] = _asset(tmp_path, "first.png", "image")
    elif mode == "fl2v":
        inputs["first_frame"] = _asset(tmp_path, "first.png", "image")
        inputs["last_frame"] = _asset(tmp_path, "last.png", "image")
    elif mode == "r2v":
        inputs["reference_images"] = [_asset(tmp_path, "reference.png", "image")]
    return {
        "node_id": "video node / 1",
        "node_type": "video",
        "provider": "comfy",
        "model": "h3",
        "mode": mode,
        "prompt": "Keep this approved prompt exactly as written.",
        "parameters": {
            "duration": 6.5,
            "aspect_ratio": "9:16",
            "megapixels": 0.6,
            "sampler_profile": "native",
            "steps": 12,
            "seed": 42,
        },
        "inputs": inputs,
    }


def _nodes(workflow: dict[str, Any], class_type: str) -> list[dict[str, Any]]:
    return [node for node in workflow.values() if node.get("class_type") == class_type]


def test_guard_rejection_is_reported_as_pre_submission_failure(tmp_path, monkeypatch):
    from lfo.comfy.admission import VideoSubmissionGuard
    from lfo.comfy.exceptions import LfoComfyError

    def reject(_self):
        raise LfoComfyError("another local generation holds the lock")

    monkeypatch.setattr(VideoSubmissionGuard, "__enter__", reject)
    with pytest.raises(executor.ExecutorError, match="holds the lock") as error:
        executor.execute_snapshot(_snapshot(tmp_path), tmp_path, transport.RuntimeConfig())
    assert error.value.status == "failed"
    assert error.value.stage == "input_validation"
    assert error.value.provider_task_id is None

def test_capability_keeps_example_values_out_of_defaults() -> None:
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    fields = {field["key"]: field for field in capability["fields"]}
    assert fields["duration"]["required"] is True
    assert fields["aspect_ratio"]["required"] is True
    assert fields["megapixels"]["required"] is True
    assert "default" not in fields["megapixels"]
    assert "default" not in fields["steps"]
    assert {mode["id"] for mode in capability["modes"]} == {"t2v", "i2v", "fl2v", "r2v"}

def test_prepare_t2v_applies_confirmed_values_without_uploading(tmp_path: pathlib.Path) -> None:
    calls: list[pathlib.Path] = []
    workflow, normalized = executor.prepare_workflow(
        _snapshot(tmp_path),
        uploader=lambda path: calls.append(path) or f"uploaded/{path.name}",
        request_id="request-1",
    )

    generator = _nodes(workflow, "MiniMaxH3ImageToVideo")[0]
    assert generator["inputs"]["prompt"] == "Keep this approved prompt exactly as written."
    assert _nodes(workflow, "PrimitiveFloat")[0]["inputs"]["value"] == 6.5
    assert _nodes(workflow, "ResolutionSelector")[0]["inputs"] == {
        "aspect_ratio": "9:16 (Portrait Widescreen)",
        "megapixels": 0.6,
        "multiple": 32,
    }
    assert _nodes(workflow, "BasicScheduler")[0]["inputs"]["steps"] == 12
    assert _nodes(workflow, "RandomNoise")[0]["inputs"]["noise_seed"] == 42
    assert _nodes(workflow, "SaveVideo")[0]["inputs"]["filename_prefix"].startswith(
        "canvas/video_node___1/request-1/"
    )
    assert normalized["mode"] == "t2v"
    assert calls == []

@pytest.mark.parametrize("mode", ["i2v", "fl2v"])
def test_prepare_frame_modes_bind_only_the_declared_frames(
    tmp_path: pathlib.Path, mode: str
) -> None:
    calls: list[pathlib.Path] = []
    workflow, _ = executor.prepare_workflow(
        _snapshot(tmp_path, mode),
        uploader=lambda path: calls.append(path) or f"canvas-input/{path.name}",
    )
    generator = _nodes(workflow, "MiniMaxH3ImageToVideo")[0]["inputs"]
    assert generator["first_frame"][0] in workflow
    assert workflow[generator["first_frame"][0]]["inputs"]["image"].startswith("canvas-input/")
    if mode == "i2v":
        assert "last_frame" not in generator
        assert len(calls) == 1
    else:
        assert generator["last_frame"][0] in workflow
        assert len(calls) == 2

def test_prepare_r2v_preserves_typed_reference_slots(tmp_path: pathlib.Path) -> None:
    snapshot = _snapshot(tmp_path, "r2v")
    snapshot["inputs"]["reference_videos"] = [_asset(tmp_path, "reference.mp4", "video")]
    snapshot["inputs"]["reference_audios"] = [_asset(tmp_path, "voice.wav", "audio")]
    workflow, _ = executor.prepare_workflow(
        snapshot,
        uploader=lambda path: f"canvas-input/{path.name}",
    )
    generator = _nodes(workflow, "MiniMaxH3ReferenceToVideo")[0]["inputs"]
    assert isinstance(generator["prompt"], list)
    assert _nodes(workflow, "PrimitiveStringMultiline")[0]["inputs"]["value"] == snapshot["prompt"]
    image_id = generator["ref_images.ref_image_0"][0]
    video_id = generator["ref_videos.ref_video_0"][0]
    audio_id = generator["ref_audios.ref_audio_0"][0]
    assert workflow[image_id]["class_type"] == "LoadImage"
    assert workflow[video_id]["class_type"] == "GetVideoComponents"
    video_load_id = workflow[video_id]["inputs"]["video"][0]
    assert workflow[video_load_id]["class_type"] == "LoadVideo"
    assert workflow[video_load_id]["inputs"] == {"file": "canvas-input/reference.mp4"}
    assert workflow[audio_id]["class_type"] == "LoadAudio"
    assert generator["ref_video_audios.ref_video_audio_0"] == [video_id, 1]
    assert not any(
        node.get("_meta", {}).get("title", "").startswith("LFO.Reference")
        for node in workflow.values()
        if isinstance(node, dict)
    )

@pytest.mark.parametrize("profile,steps", [("native", 12), ("vdn_turbo", 8)])
def test_r2v_frame_zero_guide_keeps_reference_and_audio_routes(tmp_path, profile, steps):
    snapshot = _snapshot(tmp_path, "r2v")
    snapshot["parameters"].update(sampler_profile=profile, steps=steps)
    snapshot["inputs"]["first_frame"] = _asset(tmp_path, "accepted-tail.png", "image")
    snapshot["inputs"]["reference_audios"] = [_asset(tmp_path, "voice.wav", "audio")]
    workflow, _ = executor.prepare_workflow(snapshot, uploader=lambda path: f"uploaded/{path.name}")
    generator_id = next(k for k, n in workflow.items() if n["class_type"] == "MiniMaxH3ReferenceToVideo")
    guide_id = next(k for k, n in workflow.items() if n["class_type"] == "MiniMaxH3AddGuide")
    guide = workflow[guide_id]["inputs"]
    generator = workflow[generator_id]["inputs"]
    assert guide["frame_idx"] == 0
    assert guide["positive"] == [generator_id, 0]
    assert guide["latent"] == [generator_id, 1]
    assert guide["vae"] == generator["vae"]
    assert workflow[guide["image"][0]]["inputs"]["image"] == "uploaded/accepted-tail.png"
    assert "audio" not in guide  # Voice identity must not become a forced soundtrack.
    assert workflow[generator["ref_images.ref_image_0"][0]]["inputs"]["image"] == "uploaded/reference.png"
    assert workflow[generator["ref_audios.ref_audio_0"][0]]["inputs"]["audio"] == "uploaded/voice.wav"
    assert _nodes(workflow, "BasicGuider")[0]["inputs"]["conditioning"] == [guide_id, 0]
    assert _nodes(workflow, "SamplerCustomAdvanced")[0]["inputs"]["latent_image"] == [generator_id, 1]

def test_r2v_frame_zero_video_guide_uses_first_video_with_its_audio(tmp_path: pathlib.Path) -> None:
    snapshot = _snapshot(tmp_path, "r2v")
    snapshot["parameters"]["frame_zero_video_guide"] = True
    snapshot["inputs"]["reference_videos"] = [_asset(tmp_path, "tail-22-frames.mp4", "video")]
    workflow, _ = executor.prepare_workflow(
        snapshot, uploader=lambda path: f"uploaded/{path.name}"
    )

    generator_id = next(
        key for key, node in workflow.items() if node["class_type"] == "MiniMaxH3ReferenceToVideo"
    )
    generator = workflow[generator_id]["inputs"]
    guide_id = next(
        key for key, node in workflow.items()
        if node.get("_meta", {}).get("title") == "Canvas.FrameZeroVideoGuide"
    )
    guide = workflow[guide_id]["inputs"]
    components_id = guide["image"][0]
    assert workflow[components_id]["class_type"] == "GetVideoComponents"
    assert guide["positive"] == [generator_id, 0]
    assert guide["latent"] == [generator_id, 1]
    assert guide["vae"] == generator["vae"]
    assert guide["audio_vae"] == generator["audio_vae"]
    assert guide["image"] == [components_id, 0]
    assert guide["audio"] == [components_id, 1]
    assert guide["frame_idx"] == 0
    assert "ref_videos.ref_video_0" not in generator
    assert "ref_video_audios.ref_video_audio_0" not in generator
    assert _nodes(workflow, "BasicGuider")[0]["inputs"]["conditioning"] == [guide_id, 0]

def test_r2v_without_first_frame_has_no_guide_and_rejects_last_frame(tmp_path):
    snapshot = _snapshot(tmp_path, "r2v")
    workflow, _ = executor.prepare_workflow(snapshot, uploader=lambda path: path.name)
    assert not _nodes(workflow, "MiniMaxH3AddGuide")
    snapshot["inputs"]["last_frame"] = _asset(tmp_path, "last.png", "image")
    with pytest.raises(executor.ExecutorError, match="last_frame"):
        executor.normalize_snapshot(snapshot)

def test_normalize_rejects_missing_required_values_before_upload(tmp_path: pathlib.Path) -> None:
    snapshot = _snapshot(tmp_path)
    del snapshot["parameters"]["megapixels"]
    with pytest.raises(executor.ExecutorError, match="megapixels"):
        executor.prepare_workflow(
            snapshot,
            uploader=lambda _: pytest.fail("upload must not run"),
        )

def test_normalize_rejects_conflicting_provider_option_copies(tmp_path: pathlib.Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["parameters"]["options"] = {"comfy": {"steps": 8}}
    with pytest.raises(executor.ExecutorError, match="Conflicting Comfy values"):
        executor.normalize_snapshot(snapshot)

def test_canvas_request_id_drives_a_safe_workflow_prefix(tmp_path: pathlib.Path) -> None:
    snapshot = _snapshot(tmp_path)
    snapshot["request_id"] = "../unsafe/request"

    workflow, normalized = executor.prepare_workflow(
        snapshot,
        uploader=lambda _path: pytest.fail("t2v must not upload media"),
    )

    prefix = _nodes(workflow, "SaveVideo")[0]["inputs"]["filename_prefix"]
    assert prefix == "canvas/video_node___1/___unsafe_request/video"
    assert normalized["request_id"] == "../unsafe/request"

def test_canvas_request_id_prefix_is_bounded_without_changing_the_id(
    tmp_path: pathlib.Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    request_id = "../unsafe/" + "r" * 300
    snapshot["request_id"] = request_id

    workflow, normalized = executor.prepare_workflow(
        snapshot,
        uploader=lambda _path: pytest.fail("t2v must not upload media"),
    )

    prefix = _nodes(workflow, "SaveVideo")[0]["inputs"]["filename_prefix"]
    assert prefix.split("/") == ["canvas", "video_node___1", "___unsafe_" + "r" * 70, "video"]
    assert normalized["request_id"] == request_id

def test_video_refs_rejects_two_distinct_video_outputs() -> None:
    result = executor.ComfyResult(
        "prompt-two-videos",
        (
            executor.OutputRef("first.mp4"),
            executor.OutputRef("second.mp4"),
        ),
    )

    with pytest.raises(executor.ExecutorError, match="multiple video outputs"):
        executor._video_refs(result)

def test_video_refs_ignores_load_video_intermediate_input() -> None:
    result = executor.ComfyResult(
        "prompt-guided-video",
        (
            executor.OutputRef("accepted-tail-22frames.mp4", file_type="input"),
            executor.OutputRef("video_00001_.mp4", "output"),
        ),
    )

    assert executor._video_refs(result) == [
        executor.OutputRef("video_00001_.mp4", "output")
    ]

def test_materialize_video_copies_absolute_provider_output(tmp_path: pathlib.Path) -> None:
    provider_output = tmp_path / "provider-output.mp4"
    provider_output.write_bytes(b"video bytes")
    target_dir = tmp_path / "run"
    result = executor.ComfyResult(
        "prompt-absolute",
        (executor.OutputRef(str(provider_output), file_type="absolute"),),
    )
    output = executor.materialize_video(
        result,
        target_dir,
        executor.RuntimeConfig(),
        probe_fn=lambda _path: {"duration_ms": 1000, "width": 64, "height": 64, "codec": "h264"},
    )
    assert pathlib.Path(output["path"]).read_bytes() == b"video bytes"
    assert output["kind"] == "video"

def test_project_probe_uses_lfo_ffprobe_override(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lfo.media import _ffmpeg

    video = tmp_path / "generated.mp4"
    video.write_bytes(b"video bytes")
    configured = tmp_path / "configured-ffprobe.exe"
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, timeout_s=timeout_s)
        payload = {
            "format": {"duration": "1.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 64,
                    "height": 64,
                    "r_frame_rate": "24/1",
                }
            ],
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setenv("LFO_FFPROBE", str(configured))
    monkeypatch.setattr(_ffmpeg, "run_command", fake_run)

    metadata = executor.validate_video_output(video)

    assert seen["command"][0] == str(configured)
    assert metadata["duration_ms"] == 1000

def test_explicit_ffprobe_bin_takes_priority_over_environment(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lfo.media import _ffmpeg

    video = tmp_path / "generated.mp4"
    video.write_bytes(b"video bytes")
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, timeout_s=timeout_s)
        payload = {"format": {"duration": "1.0"}, "streams": []}
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setenv("LFO_FFPROBE", str(tmp_path / "configured-ffprobe.exe"))
    monkeypatch.setattr(_ffmpeg, "run_command", fake_run)

    _ffmpeg.probe(video, ffprobe_bin="explicit-ffprobe")

    assert seen["command"][0] == "explicit-ffprobe"

def test_corrupt_provider_output_is_rejected_and_removed(tmp_path: pathlib.Path) -> None:
    provider_output = tmp_path / "broken.mp4"
    provider_output.write_bytes(b"not a video")
    target_dir = tmp_path / "run"
    result = executor.ComfyResult(
        "prompt-broken",
        (executor.OutputRef(str(provider_output), file_type="absolute"),),
    )

    with pytest.raises(executor.ExecutorError, match="not a readable video"):
        executor.materialize_video(
            result,
            target_dir,
            executor.RuntimeConfig(),
            probe_fn=lambda _path: (_ for _ in ()).throw(RuntimeError("moov atom not found")),
        )
    assert not (target_dir / "broken.mp4").exists()


@pytest.mark.parametrize("mode", ["t2v", "i2v", "fl2v", "r2v"])
def test_vdn_workflow_delegates_memory_policy_without_changing_generation(tmp_path, mode):
    snapshot = _snapshot(tmp_path, mode)
    snapshot["parameters"].update(sampler_profile="vdn_turbo", steps=8)
    workflow, _ = executor.prepare_workflow(snapshot, uploader=lambda path: path.name)
    vdn = _nodes(workflow, "ApplyVDNH3")[0]["inputs"]
    assert vdn["branch_weights"] == "auto"
    assert vdn["retain_buffers"] == "auto"
    assert vdn["vdn_checkpoint"] == "stage-dmd-step-250"
    assert vdn["lora_mode"] == "merge" and vdn["attention_backend"] == "grouped"
    assert _nodes(workflow, "BasicScheduler")[0]["inputs"]["steps"] == 8
    assert _nodes(workflow, "ResolutionSelector")[0]["inputs"]["megapixels"] == 0.6
    assert _nodes(workflow, "RandomNoise")[0]["inputs"]["noise_seed"] == 42


@pytest.mark.parametrize("mode", ["t2v", "r2v"])
def test_vdn_binds_explicit_quantized_checkpoint_and_policy_overrides(tmp_path, mode):
    snapshot = _snapshot(tmp_path, mode)
    snapshot["parameters"].update(sampler_profile="vdn_turbo", steps=8)
    snapshot["parameters"]["options"] = {"comfy": {
        "vdn_checkpoint": "quantized/stage-dmd-step-250-int8_convrot_comfyui",
        "vdn_branch_weights": "stream", "vdn_retain_buffers": "off",
    }}
    workflow, _ = executor.prepare_workflow(snapshot, uploader=lambda path: path.name)
    vdn = _nodes(workflow, "ApplyVDNH3")[0]["inputs"]
    assert vdn["vdn_checkpoint"] == "quantized/stage-dmd-step-250-int8_convrot_comfyui"
    assert vdn["branch_weights"] == "stream" and vdn["retain_buffers"] == "off"
    # Applying a checkpoint must not add a second acceleration or output chain.
    assert len(_nodes(workflow, "ApplyVDNH3")) == len(_nodes(workflow, "SaveVideo")) == 1


@pytest.mark.parametrize("key,value", [
    ("vdn_checkpoint", "../stage"), ("vdn_checkpoint", "C:/models/stage"),
    ("vdn_checkpoint", "/stage"), ("vdn_checkpoint", "a\\..\\stage"),
    ("vdn_checkpoint", 42), ("vdn_branch_weights", "gpu"),
    ("vdn_retain_buffers", True), ("video_decode", "fast"),
])
def test_invalid_execution_options_fail_before_any_upload(tmp_path, key, value):
    snapshot = _snapshot(tmp_path, "i2v")
    snapshot["parameters"].update(sampler_profile="vdn_turbo", steps=8)
    snapshot["parameters"][key] = value
    with pytest.raises(executor.ExecutorError):
        executor.prepare_workflow(snapshot, uploader=lambda _path: pytest.fail("must not upload"))


def test_vdn_options_cannot_be_ignored_by_native_profile(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["parameters"]["vdn_checkpoint"] = "quantized-stage"
    with pytest.raises(executor.ExecutorError, match="vdn_turbo"):
        executor.normalize_snapshot(snapshot)


def test_vdn_option_duplicates_cannot_change_frozen_selection(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["parameters"].update(sampler_profile="vdn_turbo", steps=8, vdn_checkpoint="chosen")
    snapshot["parameters"]["comfy"] = {"vdn_checkpoint": "different"}
    with pytest.raises(executor.ExecutorError, match="Conflicting"):
        executor.normalize_snapshot(snapshot)


@pytest.mark.parametrize("profile,steps", [("native", 12), ("vdn_turbo", 8)])
@pytest.mark.parametrize("mode", ["t2v", "r2v"])
def test_tiled_decode_replaces_only_video_decode_and_preserves_wiring(tmp_path, profile, steps, mode):
    snapshot = _snapshot(tmp_path, mode)
    snapshot["parameters"].update(sampler_profile=profile, steps=steps)
    original, _ = executor.prepare_workflow(snapshot, uploader=lambda path: path.name)
    snapshot["parameters"]["video_decode"] = "tiled"
    tiled, _ = executor.prepare_workflow(snapshot, uploader=lambda path: path.name)
    decode_id = next(key for key, node in original.items() if node["class_type"] == "VAEDecode")
    assert tiled[decode_id]["class_type"] == "VAEDecodeTiled"
    assert tiled[decode_id]["inputs"] == {
        **original[decode_id]["inputs"], "tile_size": 512, "overlap": 64,
        "temporal_size": 64, "temporal_overlap": 8,
    }
    assert _nodes(tiled, "CreateVideo") == _nodes(original, "CreateVideo")
    assert _nodes(tiled, "VAEDecodeAudio") == _nodes(original, "VAEDecodeAudio")
    assert not _nodes(tiled, "VAEDecode")


def test_successful_execution_keeps_report_in_run_and_does_not_fabricate_gpu_metrics(tmp_path, monkeypatch):
    from lfo.comfy import admission

    @contextmanager
    def guard(*_args, **_kwargs):
        yield object()

    @contextmanager
    def session(_config):
        yield object()

    source = tmp_path / "provider.mp4"
    source.write_bytes(b"provider-video")
    calls = []

    def run(path, output_dir, config, _session, **kwargs):
        calls.append(json.loads(path.read_text(encoding="utf-8")))
        return transport.ComfyResult("original-task", (transport.OutputRef(str(source)),),
                                     timings_seconds={"submit": 1.0, "provider_wait": 12.0, "fetch": 2.0})

    monkeypatch.setattr(admission, "VideoSubmissionGuard", guard)
    monkeypatch.setattr(executor, "ready_session", session)
    monkeypatch.setattr(executor, "preflight_workflow", lambda *args: None)
    monkeypatch.setattr(executor, "run_workflow", run)
    monkeypatch.setattr(executor, "_project_probe", lambda path: {
        "width": 320, "height": 240, "codec": "h264", "duration_ms": 1000,
    })
    snapshot = _snapshot(tmp_path)
    snapshot["request_id"] = "request-report"
    snapshot["parameters"].update(sampler_profile="vdn_turbo", steps=8)
    output_dir = tmp_path / "run"
    result = executor.execute_snapshot(snapshot, output_dir, transport.RuntimeConfig())
    report = json.loads((output_dir / "execution-report.json").read_text(encoding="utf-8"))
    assert result["provider_task_id"] == report["provider_task_id"] == "original-task"
    assert report["request_id"] == "request-report" and report["sampler_profile"] == "vdn_turbo"
    assert report["vdn"]["branch_weights"] == report["vdn"]["retain_buffers"] == "auto"
    assert report["timings_seconds"]["provider_wait"] == 12.0
    assert report["timings_seconds"]["total"] >= 0
    assert report["provider_stage_timings_seconds"] is None
    assert report["peak_vram_bytes"] is None and report["resolved_vdn_memory_policy"] is None
    assert len(calls) == len(result["outputs"]) == 1
    assert pathlib.Path(result["outputs"][0]["path"]).read_bytes() == b"provider-video"
