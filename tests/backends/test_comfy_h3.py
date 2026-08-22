from __future__ import annotations

import pathlib

import pytest

from lfo.backends.comfy_h3 import (
    H3_BACKEND_ID,
    H3_PRESENTER_BACKEND_ID,
    ComfyH3Config,
    ComfyH3VideoHandler,
    build_h3_backend_registry,
)


class FakeClient:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output
        self.uploaded: list[pathlib.Path] = []
        self.uploaded_files: list[pathlib.Path] = []
        self.submitted: dict | None = None

    def upload_image(self, path: pathlib.Path) -> dict:
        self.uploaded.append(path)
        return {"name": path.name, "subfolder": "lfo-input"}

    def upload_file(self, path: pathlib.Path, subfolder: str = "") -> dict:
        self.uploaded_files.append(path)
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
    assert "video.first_last_frame" in manifest.operations
    assert "video.image_to_video" in manifest.operations
    assert "audio" in manifest.accepted_media_types
    assert len(manifest.workflow_hash) == 64
    assert manifest.max_references == 15
    assert "seedvr2_3b_int8_convrot.safetensors" not in manifest.required_models
    assert "seedvr2_upscale" not in manifest.extensions["workflow_ids"]
    assert manifest.extensions["workflow_ids"] == ["h3_standard_fl2va", "h3_standard_r2v"]


def test_select_workflow_by_operation() -> None:
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.text_to_video"}
    ) == "h3_standard_fl2va"
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.image_to_video"}
    ) == "h3_standard_fl2va"
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.first_last_frame"}
    ) == "h3_standard_fl2va"
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.reference_to_video"}
    ) == "h3_standard_r2v"


def test_select_workflow_forces_virtual_presenter_workflow() -> None:
    assert ComfyH3VideoHandler._select_workflow(
        {"operation": "video.virtual_presenter"}
    ) == "h3_presenter_r2v"
    with pytest.raises(ValueError, match="fixed to h3_presenter_r2v"):
        ComfyH3VideoHandler._select_workflow(
            {"operation": "video.virtual_presenter", "workflow_id": "h3_standard_r2v"}
        )


def test_presenter_capability_is_independent() -> None:
    registry = build_h3_backend_registry()
    presenter = registry.get(H3_PRESENTER_BACKEND_ID, "3.0.0")
    standard = registry.get(H3_BACKEND_ID, "3.0.0")
    assert presenter is not None
    assert standard is not None
    assert presenter.operations == ["video.virtual_presenter"]
    assert presenter.accepted_media_types == ["image", "video", "audio"]
    assert presenter.max_references == 15
    assert presenter.duration_constraints == {"min_ms": 4_000, "max_ms": 15_000}
    assert "LoadVideo" in presenter.required_nodes
    assert "GetVideoComponents" in presenter.required_nodes
    assert "LoadAudio" in presenter.required_nodes
    assert "video.virtual_presenter" not in standard.operations


def test_h3_handler_rejects_non_h3_explicit_workflow() -> None:
    with pytest.raises(ValueError, match="Unknown H3 workflow_id"):
        ComfyH3VideoHandler._select_workflow({"workflow_id": "seedvr2_upscale"})


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
        "h3_standard_r2v",
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


def test_prepare_r2v_mixes_video_and_image_references(
    tmp_path: pathlib.Path,
) -> None:
    video = tmp_path / "reference-video.mp4"
    image = tmp_path / "reference-image.png"
    video.write_bytes(b"video")
    image.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "prompt": "A cinematic reference-to-video shot",
            "duration_ms": 5_000,
            "resolved_references": [
                {
                    "reference_id": "motion-reference",
                    "media_type": "video",
                    "blob_path": str(video),
                },
                {
                    "reference_id": "character-reference",
                    "media_type": "image",
                    "blob_path": str(image),
                },
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    expected_video = f"lfo-input/{video.name}"
    expected_image = f"lfo-input/{image.name}"
    assert client.uploaded_files == [video.resolve()]
    assert client.uploaded == [image.resolve()]
    assert set(uploaded) == {expected_video, expected_image}

    load_video_nodes = [
        (node_id, node)
        for node_id, node in workflow.items()
        if node.get("class_type") == "LoadVideo"
    ]
    component_nodes = [
        (node_id, node)
        for node_id, node in workflow.items()
        if node.get("class_type") == "GetVideoComponents"
    ]
    generator_nodes = [
        node
        for node in workflow.values()
        if node.get("class_type") == "MiniMaxH3ReferenceToVideo"
    ]
    assert len(load_video_nodes) == 1
    assert len(component_nodes) == 1
    assert len(generator_nodes) == 1

    load_video_id, load_video = load_video_nodes[0]
    component_id, components = component_nodes[0]
    assert load_video["inputs"]["file"] == expected_video
    assert components["inputs"]["video"] == [load_video_id, 0]
    generator_inputs = generator_nodes[0]["inputs"]
    assert generator_inputs["ref_videos.ref_video_0"] == [component_id, 0]


def test_prepare_presenter_uses_materialized_typed_slots(
    tmp_path: pathlib.Path,
) -> None:
    image = tmp_path / "picture.png"
    video = tmp_path / "motion.mp4"
    audio = tmp_path / "voice.wav"
    image.write_bytes(b"image")
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_presenter_r2v",
        {
            "prompt": "Picture 1 speaks with Video 1 while Audio 1 is heard",
            "duration_ms": 5_000,
            "resolved_references": [
                {"reference_id": "voice", "slot": "ref_audio_0", "media_type": "audio", "blob_path": str(audio)},
                {"reference_id": "motion", "slot": "ref_video_0", "media_type": "video", "blob_path": str(video)},
                {"reference_id": "identity", "slot": "ref_image_0", "media_type": "image", "blob_path": str(image)},
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert uploaded == [f"lfo-input/{image.name}", f"lfo-input/{video.name}", f"lfo-input/{audio.name}"]
    assert client.uploaded == [image.resolve()]
    assert client.uploaded_files == [video.resolve(), audio.resolve()]
    generator = workflow["9"]["inputs"]
    assert generator["ref_images.ref_image_0"][0] != "0"
    assert generator["ref_videos.ref_video_0"][1] == 0
    assert generator["ref_video_audios.ref_video_audio_0"][1] == 1
    assert generator["ref_audios.ref_audio_0"][1] == 0
    assert workflow["12"]["inputs"]["steps"] == 8
    assert workflow["17"]["inputs"]["fps"] == 24
    assert all(str(tmp_path) not in str(node) for node in workflow.values())


@pytest.mark.parametrize(
    ("slot", "media_type"),
    [
        ("ref_image_1", "image"),
        ("ref_image_0", "video"),
        ("ref_video_3", "video"),
        ("ref_audio_3", "audio"),
        ("ref_image_0", "image"),
    ],
)
def test_prepare_presenter_rejects_invalid_slots(
    tmp_path: pathlib.Path,
    slot: str,
    media_type: str,
) -> None:
    reference = tmp_path / "reference.bin"
    reference.write_bytes(b"reference")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )
    references = [{"reference_id": "ref", "slot": slot, "media_type": media_type, "blob_path": str(reference)}]
    if slot == "ref_image_0" and media_type == "image":
        references.append({"reference_id": "duplicate", "slot": slot, "media_type": media_type, "blob_path": str(reference)})
    with pytest.raises(ValueError):
        handler._prepare_workflow(
            "h3_presenter_r2v",
            {"prompt": "Presenter", "resolved_references": references},
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []
    assert client.uploaded_files == []


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
        "h3_standard_r2v",
        {
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "reference_image_size": "max",
            "resolved_references": [{"blob_path": str(reference)}],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert workflow["12"]["inputs"]["ref_image_size"] == "max"


def test_prepare_h3_rejects_pixel_dimensions(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    with pytest.raises(ValueError, match="aspect_ratio and megapixels"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            {
                "prompt": "A cinematic 768p shot",
                "duration_ms": 5_000,
                "width": 1344,
                "height": 768,
                "resolved_references": [{"blob_path": str(reference)}],
            },
            output_prefix="lfo/run/task/attempt/video",
        )


def test_prepare_h3_applies_requested_aspect_ratio(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "aspect_ratio": "9:16",
            "megapixels": 0.4,
            "resolved_references": [{"blob_path": str(reference)}],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert workflow["5"]["inputs"]["aspect_ratio"] == "9:16 (Portrait Widescreen)"
    assert workflow["5"]["inputs"]["megapixels"] == 0.4
    assert workflow["12"]["inputs"]["width"] == ["5", 0]
    assert workflow["12"]["inputs"]["height"] == ["5", 1]


def test_prepare_h3_applies_requested_megapixels(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "prompt": "A cinematic low-resolution shot",
            "duration_ms": 5_000,
            "aspect_ratio": "16:9",
            "megapixels": 0.3,
            "resolved_references": [{"blob_path": str(reference)}],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert workflow["5"]["inputs"]["megapixels"] == 0.3
    assert workflow["12"]["inputs"]["width"] == ["5", 0]
    assert workflow["12"]["inputs"]["height"] == ["5", 1]


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
            "output_path": str((tmp_path / "workspace" / "projects" / "test-project" / "outputs" / "run-1" / "clips" / "clip-1" / "generated.mp4").resolve()),
            "artifact_layout": {
                "workspace_root": str((tmp_path / "workspace").resolve()),
                "project_root": str((tmp_path / "workspace" / "projects" / "test-project").resolve()),
            },
            "operation": "video.text_to_video",
            "prompt": "A quiet corridor at night",
            "duration_ms": 5_000,
        },
        "attempt-1",
    )

    assert result.success is True
    managed = pathlib.Path(result.artifact_metadata["file_path"])
    assert managed.name == "generated.mp4"
    assert managed.read_bytes() == output.read_bytes()
    assert result.artifact_metadata["provider_source_path"] == str(output.resolve())
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


def test_prepare_fl2va_text_to_video_rejects_images(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )
    with pytest.raises(ValueError, match="does not accept image references"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            {
                "operation": "video.text_to_video",
                "prompt": "A quiet corridor",
                "resolved_references": [{"blob_path": str(reference)}],
            },
            output_prefix="lfo/run/task/attempt/video",
        )


def test_prepare_fl2va_wires_first_and_optional_last_frame(tmp_path: pathlib.Path) -> None:
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    first.write_bytes(b"first")
    last.write_bytes(b"last")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_fl2va",
        {
            "operation": "video.first_last_frame",
            "prompt": "Hold the pose then turn",
            "duration_ms": 5_000,
            "aspect_ratio": "16:9",
            "megapixels": 0.6,
            "resolved_references": [
                {"blob_path": str(first), "placement": "first"},
                {"blob_path": str(last), "placement": "last"},
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    generator = workflow["8"]["inputs"]
    first_node = generator["first_frame"][0]
    last_node = generator["last_frame"][0]
    assert workflow[first_node]["class_type"] == "LoadImage"
    assert workflow[first_node]["inputs"]["image"] == f"lfo-input/{first.name}"
    assert workflow[last_node]["class_type"] == "LoadImage"
    assert workflow[last_node]["inputs"]["image"] == f"lfo-input/{last.name}"
    assert workflow["5"]["inputs"]["aspect_ratio"] == "16:9 (Widescreen)"
    assert workflow["5"]["inputs"]["megapixels"] == 0.6


def test_prepare_r2v_optional_standalone_audio(tmp_path: pathlib.Path) -> None:
    image = tmp_path / "reference.png"
    audio = tmp_path / "voice.wav"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, monitor=FakeMonitor(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "prompt": "Picture 1 listens to Audio 1",
            "duration_ms": 5_000,
            "resolved_references": [
                {"reference_id": "identity", "media_type": "image", "blob_path": str(image)},
                {"reference_id": "voice", "media_type": "audio", "blob_path": str(audio)},
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    assert f"lfo-input/{audio.name}" in uploaded
    assert client.uploaded_files == [audio.resolve()]
    load_audio = [
        (node_id, node)
        for node_id, node in workflow.items()
        if node.get("class_type") == "LoadAudio"
    ]
    assert len(load_audio) == 1
    audio_id, audio_node = load_audio[0]
    assert audio_node["inputs"]["audio"] == f"lfo-input/{audio.name}"
    assert workflow["12"]["inputs"]["ref_audios.ref_audio_0"] == [audio_id, 0]
