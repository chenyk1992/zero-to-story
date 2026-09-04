"""Behavior tests for the single-submission SeedVR2 comfy-cli handler."""
from __future__ import annotations

import pathlib
from urllib.parse import parse_qs, urlsplit

import pytest

from lfo.backends.comfy_seedvr2 import ComfyUpscaleConfig, ComfyUpscaleVideoHandler
from lfo.comfy.cli import ComfyCliOutput, ComfyCliRunResult
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError


class FakeClient:
    def __init__(self) -> None:
        self.uploaded: list[tuple[pathlib.Path, str]] = []
        self.free_calls = 0
        self.interrupt_calls = 0
        self.downloads: list[dict] = []

    def free_memory(self) -> None:
        self.free_calls += 1

    def upload_file(self, path: pathlib.Path, subfolder: str = "") -> dict:
        self.uploaded.append((path, subfolder))
        return {"name": path.name, "subfolder": subfolder}

    def interrupt(self) -> None:
        self.interrupt_calls += 1

    def download_output(self, filename, destination, **kwargs):
        self.downloads.append({"filename": filename, **kwargs})
        destination.write_bytes(b"downloaded-upscale")
        return destination


class FakeCli:
    def __init__(self, outputs=(), error=None) -> None:
        self.outputs = outputs
        self.error = error
        self.calls: list[dict] = []

    def run_workflow(self, workflow, **kwargs):
        self.calls.append({"workflow": workflow, **kwargs})
        if self.error:
            raise self.error
        return ComfyCliRunResult("upscale-prompt", tuple(self.outputs))


def _metadata(tmp_path, source):
    workspace = tmp_path / "workspace"
    project = workspace / "projects" / "project-1"
    return {
        "run_id": "run-1",
        "input_task_ids": ["generate-1"],
        "input_artifacts": {"generate-1": {"file_path": str(source)}},
        "upscale": {"enabled": True, "scale_multiplier": 1.5, "seed": 17},
        "output_path": str(project / "outputs" / "run-1" / "clips" / "clip-1" / "upscaled.mp4"),
        "artifact_layout": {"workspace_root": str(workspace), "project_root": str(project)},
    }


def _execute(handler, metadata):
    return handler.execute("task-1", "video.upscale", "clip-1:video.upscale", metadata, "attempt-1")


def test_execute_submits_once_and_copies_to_managed_artifact(tmp_path):
    source = tmp_path / "generated.mp4"
    source.write_bytes(b"source")
    output_root = tmp_path / "output"
    output_root.mkdir()
    output = output_root / "result.mp4"
    output.write_bytes(b"upscaled")
    client = FakeClient()
    cli = FakeCli([ComfyCliOutput(str(output), file_type="absolute")])
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output_root, base_url="http://localhost:9000", timeout_seconds=91),
        client=client, cli_runner=cli,
    )
    result = _execute(handler, _metadata(tmp_path, source))
    assert result.success, result.error
    assert len(cli.calls) == 1
    assert cli.calls[0]["base_url"] == "http://localhost:9000"
    assert cli.calls[0]["timeout_seconds"] == 91
    workflow = cli.calls[0]["workflow"]
    assert workflow["1"]["inputs"]["file"] == "lfo-input/generated.mp4"
    assert workflow["5"]["inputs"]["resize_type.multiplier"] == 1.5
    assert workflow["13"]["inputs"]["seed"] == 17
    assert workflow["11"]["inputs"]["switch"] is True
    assert workflow["15"]["inputs"]["switch"] is True
    assert workflow["8"]["inputs"]["chunking_mode"] == "auto"
    assert "chunking_mode.frames_per_chunk" not in workflow["8"]["inputs"]
    assert client.free_calls == 1
    assert client.uploaded == [(source.resolve(), "lfo-input")]
    assert pathlib.Path(result.artifact_metadata["file_path"]).read_bytes() == b"upscaled"
    assert result.artifact_metadata["provider_job_id"] == "upscale-prompt"
    assert source.read_bytes() == b"source"


@pytest.mark.parametrize("file_type", ["output", "temp"])
def test_upscale_downloads_without_machine_output_directory(tmp_path, file_type):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    client = FakeClient()
    cli = FakeCli([ComfyCliOutput("result & clip.mp4", subfolder="lfo/run one", file_type=file_type)])
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=None), client=client, cli_runner=cli,
    )
    result = _execute(handler, _metadata(tmp_path, source))
    assert result.success, result.error
    assert pathlib.Path(result.artifact_metadata["file_path"]).read_bytes() == b"downloaded-upscale"
    assert client.downloads[0]["filename"] == "result & clip.mp4"
    assert client.downloads[0]["subfolder"] == "lfo/run one"
    assert client.downloads[0]["file_type"] == file_type
    provider_url = urlsplit(result.artifact_metadata["provider_source_path"])
    assert provider_url.path == "/view"
    assert parse_qs(provider_url.query) == {
        "filename": ["result & clip.mp4"],
        "subfolder": ["lfo/run one"],
        "type": [file_type],
    }


def test_temporary_cli_video_is_downloaded_not_replaced_with_stale_output(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "output"
    output.mkdir()
    (output / "same.mp4").write_bytes(b"stale")
    client = FakeClient()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output), client=client,
        cli_runner=FakeCli([ComfyCliOutput("same.mp4", file_type="temp")]),
    )
    result = _execute(handler, _metadata(tmp_path, source))
    assert result.success, result.error
    assert pathlib.Path(result.artifact_metadata["file_path"]).read_bytes() == b"downloaded-upscale"
    assert client.downloads[0]["file_type"] == "temp"


@pytest.mark.parametrize("error,interrupts", [
    (LfoComfyError("CUDA out of memory"), 0),
    (LfoComfyError("workflow rejected"), 0),
    (ComfyCliTimeoutError("timed out", prompt_id="upscale-prompt"), 1),
])
def test_failure_never_resubmits_and_timeout_interrupts_once(tmp_path, error, interrupts):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    client = FakeClient()
    cli = FakeCli(error=error)
    handler = ComfyUpscaleVideoHandler(client=client, cli_runner=cli)
    metadata = _metadata(tmp_path, source)
    result = _execute(handler, metadata)
    assert not result.success
    assert not result.retryable
    assert str(error) in result.error
    assert len(cli.calls) == 1
    assert client.interrupt_calls == interrupts
    assert not pathlib.Path(metadata["output_path"]).exists()


@pytest.mark.parametrize("options", [
    {"enabled": True, "scale_multiplier": 0},
    {"enabled": True, "scale_multiplier": 1.5, "segment_seconds": 5},
    {"enabled": False},
])
def test_invalid_options_stop_before_provider_calls(tmp_path, options):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    client, cli = FakeClient(), FakeCli()
    handler = ComfyUpscaleVideoHandler(client=client, cli_runner=cli)
    metadata = _metadata(tmp_path, source)
    metadata["upscale"] = options
    result = _execute(handler, metadata)
    assert not result.success
    assert client.free_calls == 0
    assert client.uploaded == []
    assert cli.calls == []


@pytest.mark.parametrize("outputs", [
    [ComfyCliOutput("preview.png")],
    [ComfyCliOutput("one.mp4"), ComfyCliOutput("two.mp4")],
    [ComfyCliOutput("../outside.mp4")],
])
def test_unusable_outputs_are_not_published(tmp_path, outputs):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "output"
    output.mkdir()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output), client=FakeClient(), cli_runner=FakeCli(outputs),
    )
    metadata = _metadata(tmp_path, source)
    result = _execute(handler, metadata)
    assert not result.success
    assert not pathlib.Path(metadata["output_path"]).exists()


def test_missing_source_stops_before_provider_calls(tmp_path):
    client, cli = FakeClient(), FakeCli()
    handler = ComfyUpscaleVideoHandler(client=client, cli_runner=cli)
    result = _execute(handler, _metadata(tmp_path, tmp_path / "missing.mp4"))
    assert not result.success
    assert client.free_calls == 0
    assert cli.calls == []


def test_configured_cli_executable_is_used():
    handler = ComfyUpscaleVideoHandler(ComfyUpscaleConfig(cli_binary="custom-comfy"))
    assert handler.cli_runner.binary == "custom-comfy"
