from __future__ import annotations

import pathlib

import pytest

from lfo.backends.comfy_h3 import (
    H3_BACKEND_ID,
    ComfyH3Config,
    ComfyH3VideoHandler,
    build_h3_backend_registry,
)


class FakeClient:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output
        self.uploaded: list[pathlib.Path] = []
        self.submitted: dict | None = None

    def upload_image(self, path: pathlib.Path) -> dict:
        self.uploaded.append(path)
        return {"name": path.name, "subfolder": "lfo-input"}

    def submit_prompt(self, workflow: dict, client_id: str) -> dict:
        self.submitted = workflow
        return {"prompt_id": "prompt-123"}

    def get_history(self, prompt_id: str) -> dict:
        return {}


class FakeMonitor:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

    def poll_until_done(self, prompt_id: str, **kwargs: object) -> dict:
        return {
            "completed": True,
            "status": "success",
            "outputs": {
                "17": {
                    "video": [
                        {
                            "filename": self.output.name,
                            "subfolder": self.output.parent.name,
                        }
                    ]
                }
            },
        }


def test_build_h3_backend_registry_uses_bundled_workflows() -> None:
    registry = build_h3_backend_registry()
    manifest = registry.get(H3_BACKEND_ID, "3.0.0")
    assert manifest is not None
    assert "video.reference_to_video" in manifest.operations
    assert "video.first_last_frame" not in manifest.operations
    assert len(manifest.workflow_hash) == 64
    assert manifest.max_references == 9


def test_select_workflow_by_operation_and_orientation() -> None:
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.text_to_video", "width": 864, "height": 480}
    ) == "h3_standard_t2v"
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.reference_to_video", "width": 448, "height": 800}
    ) == "h3_vertical_r2v"


@pytest.mark.parametrize("reference_count", [1, 2, 3, 4, 9])
def test_prepare_r2v_uses_only_declared_reference_slots(
    tmp_path: pathlib.Path,
    reference_count: int,
) -> None:
    references = []
    for index in range(reference_count):
        reference = tmp_path / f"reference-{index}.png"
        reference.write_bytes(b"image")
        references.append(reference)
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_vertical_r2v",
        {
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "seed": 42,
            "fps": 24,
            "resolved_references": [
                {"reference_id": f"reference-{index}", "blob_path": str(reference)}
                for index, reference in enumerate(references)
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    expected_uploaded = [f"lfo-input/{reference.name}" for reference in references]
    assert uploaded == expected_uploaded
    assert client.uploaded == [reference.resolve() for reference in references]
    generator_inputs = workflow["12"]["inputs"]
    assert [generator_inputs[f"ref_images.ref_image_{index}"] for index in range(min(reference_count, 3))] == [
        [str(node), 0] for node in range(6, 6 + min(reference_count, 3))
    ]
    assert all(f"ref_images.ref_image_{index}" in generator_inputs for index in range(reference_count))
    for index in range(reference_count, 3):
        assert f"ref_images.ref_image_{index}" not in generator_inputs
    for index in range(3, reference_count):
        node_id = generator_inputs[f"ref_images.ref_image_{index}"][0]
        assert workflow[node_id]["class_type"] == "LoadImage"
        assert workflow[node_id]["inputs"]["image"] == expected_uploaded[index]
    assert workflow["15"]["inputs"]["noise_seed"] == 42


def test_prepare_r2v_can_use_max_reference_image_size(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_vertical_r2v",
        {
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "reference_image_size": "max",
            "resolved_references": [{"blob_path": str(reference)}],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert workflow["12"]["inputs"]["ref_image_size"] == "max"


def test_execute_returns_durable_file_metadata(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    subfolder = output_root / "video"
    subfolder.mkdir(parents=True)
    output = subfolder / "clip.mp4"
    output.write_bytes(b"video-bytes")
    client = FakeClient(output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(output)
    )

    result = handler.execute(
        "task-1",
        "video.generate",
        "clip-1:video.generate",
        {
            "run_id": "run-1",
            "operation": "video.text_to_video",
            "prompt": "A quiet corridor at night",
            "duration_ms": 5_000,
        },
        "attempt-1",
    )

    assert result.success is True
    assert result.artifact_metadata["file_path"] == str(output.resolve())
    assert result.artifact_metadata["provider_job_id"] == "prompt-123"
    assert result.artifact_metadata["file_hash"]
    assert client.submitted is not None


def test_execute_rejects_missing_reference_without_submission(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )
    result = handler.execute(
        "task-1",
        "video.generate",
        "clip-1:video.generate",
        {
            "operation": "video.reference_to_video",
            "prompt": "Character turns to camera",
            "duration_ms": 5_000,
        },
        "attempt-1",
    )
    assert result.success is False
    assert result.retryable is False
    assert "requires at least one reference" in (result.error or "")
    assert client.submitted is None
