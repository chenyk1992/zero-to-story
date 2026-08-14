"""Tests for the local SeedVR2 post-generation upscale handler."""
from __future__ import annotations

import pathlib
from types import SimpleNamespace

import lfo.backends.comfy_seedvr2 as seedvr2
from lfo.backends.comfy_seedvr2 import (
    DEFAULT_SEGMENT_SECONDS,
    ComfyUpscaleConfig,
    ComfyUpscaleVideoHandler,
)
from lfo.comfy.exceptions import ComfyUnreachableError
from lfo.execution.handlers import HandlerResult
from lfo.media._ffmpeg import MediaCommandError


class FakeClient:
    def __init__(self) -> None:
        self.uploaded: list[tuple[pathlib.Path, str]] = []
        self.submitted: dict | None = None
        self.freed = False

    def free_memory(self) -> None:
        self.freed = True

    def upload_file(self, path: pathlib.Path, subfolder: str = "") -> dict:
        self.uploaded.append((path, subfolder))
        return {"name": path.name, "subfolder": subfolder}

    def submit_prompt(self, workflow: dict, client_id: str) -> dict:
        self.submitted = workflow
        return {"prompt_id": "prompt-123"}

    def get_history(self, prompt_id: str) -> dict:
        return {}


class UnreachableClient(FakeClient):
    def upload_file(self, path: pathlib.Path, subfolder: str = "") -> dict:
        raise ComfyUnreachableError("ComfyUI offline")


class FakeMonitor:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

    def poll_until_done(self, prompt_id: str, **kwargs: object) -> dict:
        return {
            "completed": True,
            "status": "success",
            "outputs": {
                "19": {
                    "video": [
                        {
                            "filename": self.output.name,
                            "subfolder": self.output.parent.name,
                        }
                    ]
                }
            },
        }


def _metadata(tmp_path: pathlib.Path, source: pathlib.Path) -> dict:
    workspace = tmp_path / "workspace"
    project = workspace / "projects" / "project-1"
    return {
        "run_id": "run-1",
        "input_task_ids": ["generate-1"],
        "input_artifacts": {"generate-1": {"file_path": str(source)}},
        "upscale": {
            "enabled": True,
            "scale_multiplier": 1.5,
            "seed": 17,
            "segment_seconds": None,
        },
        "output_path": str(project / "outputs" / "run-1" / "clips" / "clip-1" / "upscaled.mp4"),
        "artifact_layout": {
            "workspace_root": str(workspace),
            "project_root": str(project),
        },
    }


def test_prepare_workflow_binds_uploaded_video_and_options(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output_root),
        client=FakeClient(),
        monitor=FakeMonitor(output_root / "unused.mp4"),
    )

    workflow, scale = handler._prepare_workflow(
        {"upscale": {"enabled": True, "scale_multiplier": 1.5, "seed": 17}},
        "lfo-input/generated.mp4",
        output_prefix="lfo/run/task/attempt/upscaled",
    )

    assert scale == 1.5
    assert workflow["1"]["inputs"]["file"] == "lfo-input/generated.mp4"
    assert workflow["5"]["inputs"]["resize_type.multiplier"] == 1.5
    assert workflow["13"]["inputs"]["seed"] == 17
    assert workflow["19"]["inputs"]["filename_prefix"] == "lfo/run/task/attempt/upscaled"


def test_segment_ranges_split_fifteen_seconds_into_three_five_second_chunks() -> None:
    assert ComfyUpscaleVideoHandler._segment_ranges(15_000, 5.0) == [
        (0, 5_000),
        (5_000, 10_000),
        (10_000, 15_000),
    ]


def test_segment_ranges_absorb_a_short_tail_into_the_previous_chunk() -> None:
    assert ComfyUpscaleVideoHandler._segment_ranges(15_083, 5.0) == [
        (0, 5_000),
        (5_000, 10_000),
        (10_000, 15_083),
    ]


def test_segment_seconds_defaults_to_eight_seconds() -> None:
    assert DEFAULT_SEGMENT_SECONDS == 8.0
    assert ComfyUpscaleVideoHandler._segment_seconds({"upscale": {"enabled": True}}) == 8.0


def test_segment_ranges_use_the_fixed_eight_second_policy() -> None:
    assert ComfyUpscaleVideoHandler._segment_ranges(15_083, DEFAULT_SEGMENT_SECONDS) == [
        (0, 8_000),
        (8_000, 15_083),
    ]


def test_execute_copies_upscaled_video_to_managed_artifact(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "generated.mp4"
    source.write_bytes(b"generated-video")
    output_root = tmp_path / "output"
    provider_dir = output_root / "upscaled"
    provider_dir.mkdir(parents=True)
    provider_output = provider_dir / "result.mp4"
    provider_output.write_bytes(b"upscaled-video")
    client = FakeClient()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output_root),
        client=client,
        monitor=FakeMonitor(provider_output),
    )

    result = handler.execute(
        "task-1",
        "video.upscale",
        "clip-1:video.upscale",
        _metadata(tmp_path, source),
        "attempt-1",
    )

    assert result.success is True
    assert client.freed is True
    assert client.uploaded == [(source.resolve(), "lfo-input")]
    assert client.submitted is not None
    managed = pathlib.Path(result.artifact_metadata["file_path"])
    assert managed.name == "upscaled.mp4"
    assert managed.read_bytes() == b"upscaled-video"
    assert source.read_bytes() == b"generated-video"
    assert result.artifact_metadata["source_video_path"] == str(source.resolve())
    assert result.artifact_metadata["scale_multiplier"] == 1.5


def test_execute_rejects_missing_upstream_artifact_before_upload(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output_root),
        client=client,
        monitor=FakeMonitor(output_root / "unused.mp4"),
    )

    result = handler.execute(
        "task-1",
        "video.upscale",
        "clip-1:video.upscale",
        {"upscale": {"enabled": True}},
        "attempt-1",
    )

    assert result.success is False
    assert result.retryable is False
    assert "upstream video artifact" in (result.error or "")
    assert not client.uploaded


def test_comfy_unreachable_is_retryable(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "generated.mp4"
    source.write_bytes(b"generated-video")
    output_root = tmp_path / "output"
    output_root.mkdir()
    handler = ComfyUpscaleVideoHandler(
        ComfyUpscaleConfig(output_root=output_root),
        client=UnreachableClient(),
        monitor=FakeMonitor(output_root / "unused.mp4"),
    )

    result = handler.execute(
        "task-1",
        "video.upscale",
        "clip-1:video.upscale",
        _metadata(tmp_path, source),
        "attempt-1",
    )

    assert result.success is False
    assert result.retryable is True
    assert "offline" in (result.error or "")


def test_segmented_upscale_reuses_valid_segments_and_reports_progress(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    source = tmp_path / "generated.mp4"
    source.write_bytes(b"source-video")
    output = tmp_path / "workspace" / "projects" / "project-1" / "outputs" / "run-1" / "clips" / "clip-1" / "upscaled.mp4"
    metadata = _metadata(tmp_path, source)
    metadata["upscale"]["segment_seconds"] = 8.0
    metadata["output_path"] = str(output)

    def fake_probe(path: pathlib.Path) -> dict:
        if not path.is_file():
            raise MediaCommandError(f"missing: {path}")
        name = path.name
        if name == "generated.mp4":
            duration = 15_083
        elif "segment-001" in name:
            duration = 8_000
        elif "segment-002" in name:
            duration = 7_083
        else:
            duration = 15_083
        return {
            "duration_ms": duration,
            "width": 1728,
            "height": 960,
            "fps": 24.0,
            "codec": "h264",
            "has_audio": True,
        }

    class FakeAssembler:
        def assemble(self, spec, timeout_s):
            pathlib.Path(spec.output_path).write_bytes(b"assembled-video")
            return SimpleNamespace(success=True, error=None)

    monkeypatch.setattr(seedvr2, "probe", fake_probe)
    monkeypatch.setattr(seedvr2, "TimelineAssembler", FakeAssembler)
    monkeypatch.setattr(
        ComfyUpscaleVideoHandler,
        "_extract_segment",
        staticmethod(lambda source, destination, start, duration: destination.write_bytes(b"segment-source")),
    )

    calls: list[str] = []
    progress: list[dict] = []
    handler = ComfyUpscaleVideoHandler(
        client=FakeClient(),
        monitor=FakeMonitor(tmp_path / "unused.mp4"),
        progress_callback=progress.append,
    )

    def fake_execute_single(self, task_id, logical_key, metadata, attempt_id, source_video):
        calls.append(task_id)
        destination = pathlib.Path(metadata["output_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"upscaled-video")
        return HandlerResult(
            success=True,
            artifact_type="video",
            artifact_metadata={
                "file_path": str(destination),
                "provider_job_id": task_id,
                "scale_multiplier": 2.0,
            },
        )

    monkeypatch.setattr(ComfyUpscaleVideoHandler, "_execute_single", fake_execute_single)
    first = handler.execute("task-1", "video.upscale", "clip-1:video.upscale", metadata, "attempt-1")
    second = handler.execute("task-1", "video.upscale", "clip-1:video.upscale", metadata, "attempt-2")

    assert first.success is True
    assert second.success is True
    assert calls == ["task-1.segment-001", "task-1.segment-002"]
    assert any(event["status"] == "reused" for event in progress)
    assert second.artifact_metadata["segment_count"] == 2
