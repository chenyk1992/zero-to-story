from __future__ import annotations

import pathlib

import pytest

from lfo.backends.comfy_h3 import (
    H3_BACKEND_ID,
    H3_BACKEND_REVISION,
    H3_MAX_DURATION_MS,
    H3_PRESENTER_BACKEND_ID,
    ComfyH3Config,
    ComfyH3VideoHandler,
    build_h3_backend_registry,
)
from lfo.comfy.cli import ComfyCliOutput, ComfyCliRunResult
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError
from lfo.comfy.workflow import WorkflowLoader


class FakeClient:
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output
        self.uploaded: list[pathlib.Path] = []
        self.uploaded_files: list[pathlib.Path] = []
        self.interrupt_calls = 0

    def get_object_info(self) -> dict:
        info: dict = {
            kind: {"input": {"required": {}}}
            for kind in ("LoadImage", "LoadVideo", "GetVideoComponents", "LoadAudio")
        }
        for name in ("h3_standard_fl2va", "h3_standard_r2v", "h3_presenter_r2v"):
            path = ComfyH3Config().workflow_dir / f"{name}.json"
            for node in WorkflowLoader.load(path).values():
                fields = info.setdefault(node["class_type"], {"input": {"required": {}}})
                for name, value in node["inputs"].items():
                    kind = (
                        "BOOLEAN" if isinstance(value, bool) else
                        "INT" if isinstance(value, int) else
                        "FLOAT" if isinstance(value, float) else
                        "STRING" if isinstance(value, str) else "ANY"
                    )
                    fields["input"]["required"][name] = [kind, {}]
        return info

    def upload_image(self, path: pathlib.Path) -> dict:
        self.uploaded.append(path)
        return {"name": path.name, "subfolder": "lfo-input"}

    def upload_file(self, path: pathlib.Path, subfolder: str = "") -> dict:
        self.uploaded_files.append(path)
        return {"name": path.name, "subfolder": "lfo-input"}

    def interrupt(self) -> None:
        self.interrupt_calls += 1


class FakeDownloadClient(FakeClient):
    def __init__(self, output: pathlib.Path, payload: bytes = b"downloaded-video") -> None:
        super().__init__(output)
        self.payload = payload
        self.downloads: list[tuple[str, str, str]] = []

    def download_output(
        self,
        filename: str,
        destination: pathlib.Path,
        *,
        subfolder: str = "",
        file_type: str = "output",
        timeout: float = 300.0,
    ) -> pathlib.Path:
        self.downloads.append((filename, subfolder, file_type))
        destination.write_bytes(self.payload)
        return destination

class FakeRunner:
    def __init__(self, output: pathlib.Path, *, url: str | None = None) -> None:
        self.output = output
        self.url = url
        self.submitted: dict | None = None

    def run_workflow(
        self,
        workflow: dict,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> ComfyCliRunResult:
        self.submitted = workflow
        return ComfyCliRunResult(
            prompt_id="prompt-123",
            outputs=(
                ComfyCliOutput(
                    filename=self.output.name,
                    subfolder=self.output.parent.name,
                    url=self.url,
                ),
            ),
        )


class TimeoutRunner:
    def __init__(self, *, prompt_id: str | None = None) -> None:
        self.prompt_id = prompt_id

    def run_workflow(
        self,
        workflow: dict,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> ComfyCliRunResult:
        raise ComfyCliTimeoutError(
            "comfy-cli workflow timed out",
            prompt_id=self.prompt_id,
        )


def test_build_h3_backend_registry_uses_bundled_workflows() -> None:
    registry = build_h3_backend_registry()
    manifest = registry.get(H3_BACKEND_ID, H3_BACKEND_REVISION)
    assert manifest is not None
    assert "video.reference_to_video" in manifest.operations
    assert "video.first_last_frame" in manifest.operations
    assert "video.image_to_video" in manifest.operations
    assert "audio" in manifest.accepted_media_types
    assert len(manifest.workflow_hash) == 64
    assert manifest.max_references == 15
    assert manifest.duration_constraints["max_ms"] == H3_MAX_DURATION_MS == 15_000
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
    standard = registry.get(H3_BACKEND_ID, H3_BACKEND_REVISION)
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "seed": 42,
            "fps": 24,
            "resolved_references": [
                {
                    "reference_id": f"reference-{index}",
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": f"ref_image_{index}",
                    "blob_path": str(reference),
                }
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
        assert str(6 + index) not in workflow
    for index in range(3, reference_count):
        node_id = generator_inputs[f"ref_images.ref_image_{index}"][0]
        assert workflow[node_id]["class_type"] == "LoadImage"
        assert workflow[node_id]["inputs"]["image"] == expected_uploaded[index]
    assert workflow["14"]["inputs"]["steps"] == 8
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A cinematic reference-to-video shot",
            "duration_ms": 5_000,
            "resolved_references": [
                {
                    "reference_id": "motion-reference",
                    "media_type": "video",
                    "placement": "fixed",
                    "slot": "ref_video_0",
                    "blob_path": str(video),
                },
                {
                    "reference_id": "character-reference",
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_presenter_r2v",
        {
            "operation": "video.virtual_presenter",
            "prompt": "Picture 1 speaks with Video 1 while Audio 1 is heard",
            "duration_ms": 5_000,
            "resolved_references": [
                {"reference_id": "voice", "slot": "ref_audio_0", "placement": "fixed", "media_type": "audio", "blob_path": str(audio)},
                {"reference_id": "motion", "slot": "ref_video_0", "placement": "fixed", "media_type": "video", "blob_path": str(video)},
                {"reference_id": "identity", "slot": "ref_image_0", "placement": "fixed", "media_type": "image", "blob_path": str(image)},
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
    assert workflow["12"]["inputs"]["steps"] == 20
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "reference_image_size": "max",
            "resolved_references": [
                {
                    "blob_path": str(reference),
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
                }
            ],
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    with pytest.raises(ValueError, match="aspect_ratio and megapixels"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            {
                "operation": "video.reference_to_video",
                "prompt": "A cinematic 768p shot",
                "duration_ms": 5_000,
                "width": 1344,
                "height": 768,
                "resolved_references": [
                    {
                        "blob_path": str(reference),
                        "media_type": "image",
                        "placement": "fixed",
                        "slot": "ref_image_0",
                    }
                ],
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A cinematic portrait",
            "duration_ms": 5_000,
            "aspect_ratio": "9:16",
            "megapixels": 0.4,
            "resolved_references": [
                {
                    "blob_path": str(reference),
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
                }
            ],
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A cinematic low-resolution shot",
            "duration_ms": 5_000,
            "aspect_ratio": "16:9",
            "megapixels": 0.3,
            "resolved_references": [
                {
                    "blob_path": str(reference),
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
                }
            ],
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
    runner = FakeRunner(output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, runner=runner
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
    assert runner.submitted is not None


def test_execute_interrupts_comfy_once_after_cli_timeout(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,
        runner=TimeoutRunner(prompt_id="prompt-timeout"),
    )

    result = handler.execute(
        "task-1",
        "video.generate",
        "clip-1:video.generate",
        {
            "operation": "video.text_to_video",
            "prompt": "A quiet corridor at night",
            "duration_ms": 5_000,
        },
        "attempt-1",
    )

    assert result.success is False
    assert result.retryable is False
    assert result.artifact_metadata["provider_job_id"] == "prompt-timeout"
    assert client.interrupt_calls == 1


def test_execute_downloads_cli_url_when_output_root_is_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    provider_output = pathlib.Path("provider") / "clip.mp4"
    client = FakeDownloadClient(provider_output)
    runner = FakeRunner(
        provider_output,
        url="http://127.0.0.1:8188/view?filename=clip.mp4&subfolder=provider&type=output",
    )
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=None), client=client, runner=runner
    )
    output_path = (
        tmp_path
        / "workspace"
        / "projects"
        / "test-project"
        / "outputs"
        / "run-1"
        / "clips"
        / "clip-1"
        / "generated.mp4"
    ).resolve()

    result = handler.execute(
        "task-1",
        "video.generate",
        "clip-1:video.generate",
        {
            "run_id": "run-1",
            "output_path": str(output_path),
            "artifact_layout": {
                "workspace_root": str((tmp_path / "workspace").resolve()),
                "project_root": str(
                    (tmp_path / "workspace" / "projects" / "test-project").resolve()
                ),
            },
            "operation": "video.text_to_video",
            "prompt": "A quiet corridor at night",
            "duration_ms": 5_000,
        },
        "attempt-1",
    )

    assert result.success is True
    assert output_path.read_bytes() == b"downloaded-video"
    assert client.downloads == [("clip.mp4", "provider", "output")]


def test_materialize_cli_output_rejects_non_video_output(tmp_path: pathlib.Path) -> None:
    client = FakeDownloadClient(tmp_path / "preview.png")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=None),
        client=client,
        runner=FakeRunner(client.output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-image",
        outputs=(ComfyCliOutput(filename="preview.png"),),
    )

    with pytest.raises(LfoComfyError, match="did not report a video output"):
        handler._materialize_cli_output(result, tmp_path / "managed.mp4")
    assert client.downloads == []


def test_materialize_cli_output_rejects_ambiguous_video_outputs(
    tmp_path: pathlib.Path,
) -> None:
    client = FakeDownloadClient(tmp_path / "first.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=None),
        client=client,
        runner=FakeRunner(client.output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-many",
        outputs=(
            ComfyCliOutput(filename="first.mp4"),
            ComfyCliOutput(filename="second.mp4"),
        ),
    )

    with pytest.raises(LfoComfyError, match="ambiguous video outputs"):
        handler._materialize_cli_output(result, tmp_path / "managed.mp4")
    assert client.downloads == []


@pytest.mark.parametrize("file_type", ["output", "temp"])
def test_materialize_cli_output_rejects_distinct_absolute_and_downloadable_video(
    tmp_path: pathlib.Path,
    file_type: str,
) -> None:
    output_root = tmp_path / "output"
    absolute = output_root / "absolute.mp4"
    downloadable = output_root / "provider" / "provider.mp4"
    downloadable.parent.mkdir(parents=True)
    absolute.write_bytes(b"absolute-video")
    downloadable.write_bytes(b"downloadable-video")
    client = FakeDownloadClient(downloadable)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,
        runner=FakeRunner(downloadable),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-distinct",
        outputs=(
            ComfyCliOutput(filename=str(absolute), file_type="absolute"),
            ComfyCliOutput(
                filename=downloadable.name,
                subfolder="provider",
                file_type=file_type,
            ),
        ),
    )

    with pytest.raises(LfoComfyError, match="ambiguous video outputs"):
        handler._materialize_cli_output(result, tmp_path / "managed.mp4")
    assert client.downloads == []


def test_materialize_cli_output_allows_same_absolute_and_downloadable_video(
    tmp_path: pathlib.Path,
) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    output = output_root / "provider" / "clip.mp4"
    output.parent.mkdir()
    output.write_bytes(b"same-video")
    client = FakeDownloadClient(output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,
        runner=FakeRunner(output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-equivalent",
        outputs=(
            ComfyCliOutput(filename=str(output), file_type="absolute"),
            ComfyCliOutput(filename=output.name, subfolder="provider"),
        ),
    )

    handler._materialize_cli_output(result, tmp_path / "managed.mp4")

    assert (tmp_path / "managed.mp4").read_bytes() == b"same-video"
    assert client.downloads == []


def test_materialize_cli_output_allows_same_output_and_temp_video(
    tmp_path: pathlib.Path,
) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    output = output_root / "provider" / "clip.mp4"
    output.parent.mkdir()
    output.write_bytes(b"same-video")
    client = FakeDownloadClient(output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,
        runner=FakeRunner(output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-output-temp",
        outputs=(
            ComfyCliOutput(filename=output.name, subfolder="provider"),
            ComfyCliOutput(
                filename=str(output),
                file_type="temp",
            ),
        ),
    )

    handler._materialize_cli_output(result, tmp_path / "managed.mp4")

    assert (tmp_path / "managed.mp4").read_bytes() == b"same-video"
    assert client.downloads == []


def test_materialize_cli_output_accepts_temp_video_without_absolute_record(
    tmp_path: pathlib.Path,
) -> None:
    client = FakeDownloadClient(tmp_path / "temp.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=None),
        client=client,
        runner=FakeRunner(client.output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-temp-only",
        outputs=(ComfyCliOutput(filename="temp.mp4", file_type="temp"),),
    )

    handler._materialize_cli_output(result, tmp_path / "managed.mp4")

    assert (tmp_path / "managed.mp4").read_bytes() == b"downloaded-video"
    assert client.downloads == [("temp.mp4", "", "temp")]


def test_materialize_cli_output_rejects_path_outside_output_root(
    tmp_path: pathlib.Path,
) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeDownloadClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root),
        client=client,
        runner=FakeRunner(client.output),
    )
    result = ComfyCliRunResult(
        prompt_id="prompt-escape",
        outputs=(ComfyCliOutput(filename="../outside.mp4"),),
    )

    with pytest.raises(LfoComfyError, match="escaped the configured output root"):
        handler._materialize_cli_output(result, tmp_path / "managed.mp4")
    assert client.downloads == []


def test_execute_rejects_missing_reference_without_submission(tmp_path: pathlib.Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    runner = FakeRunner(client.output)
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, runner=runner
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
    assert runner.submitted is None


def test_prepare_fl2va_text_to_video_rejects_images(tmp_path: pathlib.Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
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
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
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
    assert workflow["11"]["inputs"]["steps"] == 8


def test_prepare_r2v_optional_standalone_audio(tmp_path: pathlib.Path) -> None:
    image = tmp_path / "reference.png"
    audio = tmp_path / "voice.wav"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    handler = ComfyH3VideoHandler(
        ComfyH3Config(output_root=output_root), client=client, runner=FakeRunner(client.output)
    )

    workflow, uploaded = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "Picture 1 listens to Audio 1",
            "duration_ms": 5_000,
            "resolved_references": [
                {
                    "reference_id": "identity",
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
                    "blob_path": str(image),
                },
                {
                    "reference_id": "voice",
                    "media_type": "audio",
                    "placement": "fixed",
                    "slot": "ref_audio_0",
                    "blob_path": str(audio),
                },
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


def _h3_test_handler(tmp_path: pathlib.Path) -> tuple[ComfyH3VideoHandler, FakeClient]:
    output_root = tmp_path / "output"
    output_root.mkdir()
    client = FakeClient(output_root / "unused.mp4")
    return (
        ComfyH3VideoHandler(
            ComfyH3Config(output_root=output_root),
            client=client,
            runner=FakeRunner(client.output),
        ),
        client,
    )


def test_prepare_i2va_requires_and_wires_one_explicit_first_frame(
    tmp_path: pathlib.Path,
) -> None:
    first = tmp_path / "first.png"
    first.write_bytes(b"first")
    handler, _ = _h3_test_handler(tmp_path)

    workflow, _ = handler._prepare_workflow(
        "h3_standard_fl2va",
        {
            "operation": "video.image_to_video",
            "prompt": "The scholar begins to turn",
            "resolved_references": [
                {"blob_path": str(first), "placement": "first", "media_type": "image"}
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    generator = workflow["8"]["inputs"]
    first_node = generator["first_frame"][0]
    assert workflow[first_node]["inputs"]["image"] == "lfo-input/first.png"
    assert "last_frame" not in generator


@pytest.mark.parametrize(
    "references",
    [
        [{"blob_path": "missing.png", "media_type": "image"}],
        [
            {"blob_path": "missing-first.png", "media_type": "image", "placement": "first"},
            {"blob_path": "missing-extra.png", "media_type": "image", "placement": "any"},
        ],
    ],
)
def test_prepare_i2va_rejects_missing_or_unconsumable_frame_binding(
    tmp_path: pathlib.Path,
    references: list[dict[str, str]],
) -> None:
    for reference in references:
        reference["blob_path"] = str(tmp_path / pathlib.Path(reference["blob_path"]).name)
        pathlib.Path(reference["blob_path"]).write_bytes(b"image")
    handler, client = _h3_test_handler(tmp_path)
    with pytest.raises(ValueError, match=r"explicitly bound|exactly (?:one|1)"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            {
                "operation": "video.image_to_video",
                "prompt": "No ambiguous start",
                "resolved_references": [
                    {**reference, "blob_path": str(pathlib.Path(reference["blob_path"]).resolve())}
                    for reference in references
                ],
            },
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []


def test_select_workflow_rejects_operation_workflow_mismatch() -> None:
    with pytest.raises(ValueError, match="does not implement operation"):
        ComfyH3VideoHandler._select_workflow(
            {
                "operation": "video.reference_to_video",
                "workflow_id": "h3_standard_fl2va",
            }
        )


def test_prepare_fl2va_rejects_ordinary_required_reference_in_first_last_mode(
    tmp_path: pathlib.Path,
) -> None:
    first = tmp_path / "first.png"
    last = tmp_path / "last.png"
    extra = tmp_path / "identity.png"
    for image in (first, last, extra):
        image.write_bytes(b"image")
    handler, client = _h3_test_handler(tmp_path)
    with pytest.raises(ValueError, match="exactly 2|ordinary references"):
        handler._prepare_workflow(
            "h3_standard_fl2va",
            {
                "operation": "video.first_last_frame",
                "prompt": "A bounded motion",
                "resolved_references": [
                    {"blob_path": str(first), "placement": "first"},
                    {"blob_path": str(last), "placement": "last"},
                    {"blob_path": str(extra), "placement": "any"},
                ],
            },
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []


@pytest.mark.parametrize(
    "reference",
    [
        {
            "placement": "fixed",
            "slot": "ref_image_0",
            "semantic_usage": "continuity.exact_previous_last_frame",
        },
        {
            "placement": "fixed",
            "slot": "ref_image_0",
            "instruction": "hard first frame continuity",
        },
        {
            "placement": "fixed",
            "slot": "ref_image_0",
            "semantic_usage": "exact_previous_last_frame",
        },
        {
            "placement": "fixed",
            "slot": "ref_image_0",
            "instruction": "hard previous last frame",
        },
    ],
)
def test_prepare_r2v_rejects_fake_first_frame_guarantee(
    tmp_path: pathlib.Path,
    reference: dict[str, str],
) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    handler, client = _h3_test_handler(tmp_path)
    with pytest.raises(ValueError, match="exact/hard|first/last-frame"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            {
                "operation": "video.reference_to_video",
                "prompt": "A continuous shot",
                "resolved_references": [{"blob_path": str(image), **reference}],
            },
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []


def test_prepare_r2v_preserves_fixed_typed_reference_slot(tmp_path: pathlib.Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    handler, _ = _h3_test_handler(tmp_path)

    workflow, _ = handler._prepare_workflow(
        "h3_standard_r2v",
        {
            "operation": "video.reference_to_video",
            "prompt": "A composed reference shot",
            "resolved_references": [
                {
                    "blob_path": str(second),
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_1",
                },
                {
                    "blob_path": str(first),
                    "media_type": "image",
                    "placement": "fixed",
                    "slot": "ref_image_0",
                },
            ],
        },
        output_prefix="lfo/run/task/attempt/video",
    )

    generator = workflow["12"]["inputs"]
    first_node = generator["ref_images.ref_image_0"][0]
    second_node = generator["ref_images.ref_image_1"][0]
    assert workflow[first_node]["inputs"]["image"] == "lfo-input/first.png"
    assert workflow[second_node]["inputs"]["image"] == "lfo-input/second.png"


def test_prepare_r2v_rejects_untyped_reference_slot(
    tmp_path: pathlib.Path,
) -> None:
    any_image = tmp_path / "any.png"
    fixed_image = tmp_path / "fixed.png"
    any_image.write_bytes(b"any")
    fixed_image.write_bytes(b"fixed")
    handler, _ = _h3_test_handler(tmp_path)

    with pytest.raises(ValueError, match="typed fixed slots"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            {
                "operation": "video.reference_to_video",
                "prompt": "A composed reference shot",
                "resolved_references": [
                    {
                        "blob_path": str(any_image),
                        "media_type": "image",
                        "placement": "any",
                    },
                    {
                        "blob_path": str(fixed_image),
                        "media_type": "image",
                        "placement": "fixed",
                        "slot": "ref_image_0",
                    },
                ],
            },
            output_prefix="lfo/run/task/attempt/video",
        )


@pytest.mark.parametrize(
    "claim",
    [
        {"semantic_usage": "exact_previous_last_frame"},
        {"instruction": "hard previous last frame"},
    ],
)
def test_prepare_presenter_rejects_fake_first_frame_guarantee(
    tmp_path: pathlib.Path,
    claim: dict[str, str],
) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    handler, client = _h3_test_handler(tmp_path)
    with pytest.raises(ValueError, match="exact/hard first-frame continuity"):
        handler._prepare_workflow(
            "h3_presenter_r2v",
            {
                "operation": "video.virtual_presenter",
                "prompt": "Presenter",
                "resolved_references": [
                    {
                        "reference_id": "tail",
                        "slot": "ref_image_0",
                        "media_type": "image",
                        "blob_path": str(image),
                        **claim,
                    }
                ],
            },
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []
    assert client.uploaded_files == []


def test_prepare_h3_rejects_duration_over_local_limit(tmp_path: pathlib.Path) -> None:
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    handler, client = _h3_test_handler(tmp_path)
    with pytest.raises(ValueError, match="15000"):
        handler._prepare_workflow(
            "h3_standard_r2v",
            {
                "operation": "video.reference_to_video",
                "prompt": "Too long",
                "duration_ms": H3_MAX_DURATION_MS + 1,
                "resolved_references": [
                    {
                        "blob_path": str(image),
                        "media_type": "image",
                        "placement": "fixed",
                        "slot": "ref_image_0",
                    }
                ],
            },
            output_prefix="lfo/run/task/attempt/video",
        )
    assert client.uploaded == []
