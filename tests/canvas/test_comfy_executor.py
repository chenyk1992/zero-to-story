from __future__ import annotations

import io
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

import pytest

SKILL_ROOT = pathlib.Path(__file__).resolve().parents[2] / ".agents" / "skills" / "comfy-video-executor"
sys.path.insert(0, str(SKILL_ROOT))

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
    assert workflow[audio_id]["class_type"] == "LoadAudio"
    assert generator["ref_video_audios.ref_video_audio_0"] == [video_id, 1]
    assert not any(
        node.get("_meta", {}).get("title", "").startswith("LFO.Reference")
        for node in workflow.values()
        if isinstance(node, dict)
    )


def test_http_uploader_uses_unique_root_names_without_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    first = tmp_path / "one" / "frame.png"
    second = tmp_path / "two" / "frame.png"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    requests: list[Any] = []
    uploaded_names: set[str] = set()

    class Response:
        def __init__(self, payload: dict[str, str]) -> None:
            self.payload = payload

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request: Any, *, timeout: float) -> Response:
        del timeout
        requests.append(request)
        match = re.search(rb'filename="([^"]+)"', request.data)
        assert match is not None
        name = match.group(1).decode("utf-8")
        assert name not in uploaded_names
        uploaded_names.add(name)
        return Response({"name": name, "subfolder": "", "type": "input"})

    monkeypatch.setattr(executor, "urlopen", fake_urlopen)
    upload = executor._http_uploader("http://127.0.0.1:8188", 5.0)

    first_token = upload(first)
    second_token = upload(second)

    assert first_token != second_token
    assert first_token.endswith("-frame.png")
    assert second_token.endswith("-frame.png")
    assert "/" not in first_token
    assert "/" not in second_token
    assert len(requests) == 2
    for request in requests:
        body = request.data
        assert b'name="type"' in body and b"\r\n\r\ninput\r\n" in body
        assert b'name="overwrite"' in body and b"\r\n\r\nfalse\r\n" in body
        assert b"canvas-input" not in body


def test_http_uploader_uses_response_name_subfolder_and_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    source = tmp_path / "frame.png"
    source.write_bytes(b"frame")

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"name": "server-renamed.png", "subfolder": "server-input", "type": "input"}
            ).encode("utf-8")

    monkeypatch.setattr(executor, "urlopen", lambda request, timeout: Response())
    upload = executor._http_uploader("http://127.0.0.1:8188", 5.0)

    assert upload(source) == "server-input/server-renamed.png"


def test_http_uploader_rejects_non_input_response_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    source = tmp_path / "frame.png"
    source.write_bytes(b"frame")

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"name":"frame.png","subfolder":"","type":"output"}'

    monkeypatch.setattr(executor, "urlopen", lambda request, timeout: Response())
    upload = executor._http_uploader("http://127.0.0.1:8188", 5.0)

    with pytest.raises(executor.ExecutorError, match="unexpected file type"):
        upload(source)


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


def test_runtime_config_accepts_legacy_timeout_sec_key(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LFO_COMFY_TIMEOUT", raising=False)
    config_path = tmp_path / "comfy.json"
    config_path.write_text(json.dumps({"timeout_sec": 321}), encoding="utf-8")

    config = executor.load_runtime_config(config_path=config_path)

    assert config.timeout_seconds == 321


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


def test_collect_outputs_prefers_nonempty_envelope_over_duplicate_executed_output(
    tmp_path: pathlib.Path,
) -> None:
    absolute_output = str(tmp_path / "clip.mp4")
    events = [
        {
            "type": "executed",
            "prompt_id": "prompt-absolute",
            "outputs": [
                {"filename": "clip.mp4", "subfolder": "canvas", "type": "output"}
            ],
        },
        {
            "type": "envelope",
            "ok": True,
            "data": {
                "status": "completed",
                "prompt_id": "prompt-absolute",
                "outputs": [absolute_output],
            },
        },
    ]

    outputs = executor._collect_outputs(events, "prompt-absolute")

    assert outputs == (executor.OutputRef(absolute_output, file_type="absolute"),)


def test_collect_outputs_falls_back_to_executed_when_envelope_outputs_empty() -> None:
    events = [
        {
            "type": "executed",
            "prompt_id": "prompt-fallback",
            "outputs": [
                {"filename": "clip.mp4", "subfolder": "canvas", "type": "output"}
            ],
        },
        {
            "type": "envelope",
            "ok": True,
            "data": {"status": "completed", "prompt_id": "prompt-fallback", "outputs": []},
        },
    ]

    outputs = executor._collect_outputs(events, "prompt-fallback")

    assert outputs == (executor.OutputRef("clip.mp4", "canvas", "output"),)


def test_video_refs_rejects_two_distinct_video_outputs() -> None:
    result = executor.CliResult(
        "prompt-two-videos",
        (
            executor.OutputRef("first.mp4"),
            executor.OutputRef("second.mp4"),
        ),
        (),
    )

    with pytest.raises(executor.ExecutorError, match="multiple video outputs"):
        executor._video_refs(result)


def test_run_comfy_cli_parses_one_terminal_result_and_command(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")
    captured: dict[str, Any] = {}
    events = [
        {"schema": "event/1", "type": "queued", "prompt_id": "prompt-1"},
        {
            "schema": "event/1",
            "type": "executed",
            "prompt_id": "prompt-1",
            "outputs": [{"filename": "clip.mp4", "subfolder": "canvas", "type": "output"}],
        },
        {
            "schema": "envelope/1",
            "type": "envelope",
            "ok": True,
            "data": {"status": "completed", "prompt_id": "prompt-1", "outputs": []},
        },
    ]

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("\n".join(json.dumps(item) for item in events))
            self.stderr = io.StringIO("")
            self.returncode = 0

        def poll(self) -> int:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    def fake_popen(command: list[str], **kwargs: Any) -> FakeProcess:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(executor.subprocess, "Popen", fake_popen)
    result = executor.run_comfy_cli(
        workflow_path,
        executor.RuntimeConfig(base_url="http://127.0.0.1:8188", timeout_seconds=120),
    )
    assert result.provider_task_id == "prompt-1"
    assert result.outputs[0].filename == "clip.mp4"
    assert "--wait" in captured["command"]
    assert captured["command"][captured["command"].index("--port") + 1] == "8188"
    assert captured["kwargs"]["text"] is True


def test_run_comfy_cli_uses_the_canvas_request_id_for_admission(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from lfo.comfy import admission

    captured: dict[str, Any] = {}

    class Guard:
        def __init__(self, base_url: str, *, request_id: str | None = None) -> None:
            captured.update(base_url=base_url, request_id=request_id)

        def __enter__(self) -> Guard:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def submitted(self, provider_task_id: str | None = None) -> None:
            captured["provider_task_id"] = provider_task_id

        def finished(self) -> None:
            captured["finished"] = True

    result = executor.CliResult(
        "prompt-request",
        (executor.OutputRef("clip.mp4"),),
        (),
    )
    monkeypatch.setattr(admission, "VideoSubmissionGuard", Guard)
    monkeypatch.setattr(executor, "_run_comfy_cli", lambda *_args, **_kwargs: result)
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")

    actual = executor.run_comfy_cli(
        workflow_path,
        executor.RuntimeConfig(),
        request_id="canvas-request-7",
    )

    assert actual is result
    assert captured["request_id"] == "canvas-request-7"
    assert captured["finished"] is True


def test_materialize_video_copies_absolute_provider_output(tmp_path: pathlib.Path) -> None:
    provider_output = tmp_path / "provider-output.mp4"
    provider_output.write_bytes(b"video bytes")
    target_dir = tmp_path / "run"
    result = executor.CliResult(
        "prompt-absolute",
        (executor.OutputRef(str(provider_output), file_type="absolute"),),
        (),
    )
    output = executor.materialize_video(
        result,
        target_dir,
        executor.RuntimeConfig(output_root=tmp_path),
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


def test_run_timeout_is_terminal_and_never_retries(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    calls = 0

    class HangingProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")
            self.returncode: int | None = None

        def poll(self) -> None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            if self.returncode is None:
                raise subprocess.TimeoutExpired("comfy", timeout or 0)
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    def fake_popen(*args: Any, **kwargs: Any) -> HangingProcess:
        nonlocal calls
        calls += 1
        return HangingProcess()

    monkeypatch.setattr(executor.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(executor, "PROCESS_EXIT_GRACE_SECONDS", 0.01)
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")
    with pytest.raises(executor.ExecutorError, match="wall-clock timeout"):
        executor.run_comfy_cli(
            workflow_path,
            executor.RuntimeConfig(timeout_seconds=0.01),
        )
    assert calls == 1


def test_timeout_preserves_early_provider_id_and_emits_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    class QueuedThenHangingProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO(
                json.dumps({"schema": "event/1", "type": "queued", "prompt_id": "prompt-early"})
            )
            self.stderr = io.StringIO("")
            self.returncode: int | None = None

        def poll(self) -> None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            if self.returncode is None:
                raise subprocess.TimeoutExpired("comfy", timeout or 0)
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(executor.subprocess, "Popen", lambda *args, **kwargs: QueuedThenHangingProcess())
    monkeypatch.setattr(executor, "PROCESS_EXIT_GRACE_SECONDS", 0.01)
    events: list[dict[str, Any]] = []
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")

    with pytest.raises(executor.ExecutorError) as raised:
        executor.run_comfy_cli(
            workflow_path,
            executor.RuntimeConfig(timeout_seconds=0.01),
            emit=events.append,
        )

    assert raised.value.status == "unknown"
    assert raised.value.provider_task_id == "prompt-early"
    assert events == [{"event": "queued", "status": "queued", "stage": "generation", "provider_task_id": "prompt-early"}]


def test_explicit_provider_failure_is_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    terminal = {
        "schema": "envelope/1",
        "type": "envelope",
        "ok": False,
        "prompt_id": "prompt-failed",
        "error": {"code": "execution_failed", "message": "custom node failed"},
    }

    class FailedProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO(json.dumps(terminal))
            self.stderr = io.StringIO("")
            self.returncode = 1

        def poll(self) -> int:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(executor.subprocess, "Popen", lambda *args, **kwargs: FailedProcess())
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")
    with pytest.raises(executor.ExecutorError) as raised:
        executor.run_comfy_cli(workflow_path, executor.RuntimeConfig(timeout_seconds=1))
    assert raised.value.status == "failed"
    assert raised.value.provider_task_id == "prompt-failed"


def test_corrupt_provider_output_is_rejected_and_removed(tmp_path: pathlib.Path) -> None:
    provider_output = tmp_path / "broken.mp4"
    provider_output.write_bytes(b"not a video")
    target_dir = tmp_path / "run"
    result = executor.CliResult(
        "prompt-broken",
        (executor.OutputRef(str(provider_output), file_type="absolute"),),
        (),
    )

    with pytest.raises(executor.ExecutorError, match="not a readable video"):
        executor.materialize_video(
            result,
            target_dir,
            executor.RuntimeConfig(output_root=tmp_path),
            probe_fn=lambda _path: (_ for _ in ()).throw(RuntimeError("moov atom not found")),
        )
    assert not (target_dir / "broken.mp4").exists()


def test_preflight_rejects_server_model_constraint_before_submit(tmp_path: pathlib.Path) -> None:
    workflow, _ = executor.prepare_workflow(
        _snapshot(tmp_path),
        uploader=lambda path: f"canvas-input/{path.name}",
    )
    object_info = {
        str(node["class_type"]): {"input": {"required": {}}}
        for node in workflow.values()
        if isinstance(node, dict)
    }
    object_info["UNETLoader"] = {
        "input": {"required": {"unet_name": [["some-other-model.safetensors"]]}}
    }
    with pytest.raises(executor.ExecutorError, match="rejected workflow inputs"):
        executor.preflight_workflow(
            workflow,
            executor.RuntimeConfig(),
            object_info=object_info,
        )
