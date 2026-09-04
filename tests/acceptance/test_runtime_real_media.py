from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess

import pytest

from lfo.application.video_runtime import VideoRuntime
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.media._ffmpeg import probe
from lfo.media.handlers import build_media_handler_registry


class SourceVideoHandler(TaskHandler):
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

    def execute(self, task_id, task_type, logical_key, metadata, attempt_id) -> HandlerResult:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=size=96x64:rate=24:duration=0.4",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.4",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(self.output),
            ],
            check=True,
            capture_output=True,
        )
        return HandlerResult(
            True,
            artifact_type="video",
            artifact_metadata={"file_path": str(self.output), "media_type": "video"},
        )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_persistent_runtime_executes_real_media_pipeline(tmp_path: pathlib.Path) -> None:
    registry = BackendRegistry()
    registry.register(
        CapabilityManifest(
            backend_id="test.video",
            revision="1",
            workflow_hash="test-workflow",
            operations=["video.text_to_video"],
            max_references=0,
            duration_constraints={"min_ms": 100, "max_ms": 10_000},
            fps_constraints=[24.0],
            native_audio_capability="optional",
        )
    )
    workspace = tmp_path / "workspace"
    handlers = build_media_handler_registry(workspace)
    handlers.register("video.generate", SourceVideoHandler(tmp_path / "provider" / "clip.mp4"))
    package = {
        "schema": "lfo.video-execution.v1",
        "package_id": "real-media-smoke",
        "revision": 1,
        "project": {"title": "Real media smoke", "project_id": "real-media-smoke"},
        "clips": [
            {
                "clip_id": "clip-001",
                "sequence": 1,
                "duration_ms": 400,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "test source",
                    "requirements": {"fps": 24},
                },
                "subtitles": {
                    "cues": [{"start_ms": 0, "end_ms": 250, "text": "Hello"}]
                },
            }
        ],
        "output": {
            "fps": 24,
            "subtitles_mode": "sidecar",
            "directory": "real-media-smoke",
        },
    }
    package_path = tmp_path / "execution-package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    runtime = VideoRuntime(
        registry,
        workspace_root=workspace,
        handler_registry=handlers,
    )

    approved_sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()
    result = runtime.execute(package_path, approved_sha256=approved_sha256)
    assert result.status == "COMPLETED", result.error
    assert result.file_path is not None
    current_video = pathlib.Path(result.file_path)
    assert current_video.is_file()
    final_metadata = probe(current_video)
    assert final_metadata["width"] == 96
    assert final_metadata["height"] == 64


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_runtime_assembles_passthrough_clips_with_audio_and_subtitles(
    tmp_path: pathlib.Path,
) -> None:
    """A final assembly normalizes heterogeneous clips and publishes captions."""
    source_a = tmp_path / "accepted" / "panel-a.mp4"
    source_b = tmp_path / "accepted" / "panel-b.mp4"
    external_audio = tmp_path / "assets" / "music.wav"
    subtitle_file = tmp_path / "assets" / "panel-b.srt"
    source_a.parent.mkdir(parents=True, exist_ok=True)
    external_audio.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=blue:s=96x64:r=24:d=0.8", "-f", "lavfi", "-i",
            "sine=frequency=440:duration=0.8", "-shortest", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(source_a),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=red:s=80x48:r=30:d=0.6", "-f", "lavfi", "-i",
            "sine=frequency=660:duration=0.6", "-shortest", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(source_b),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.8",
            "-c:a", "pcm_s16le", str(external_audio),
        ],
        check=True,
        capture_output=True,
    )
    subtitle_file.write_text(
        "1\n00:00:00,000 --> 00:00:00,500\nsecond panel\n",
        encoding="utf-8",
    )

    package = {
        "schema": "lfo.video-execution.v1",
        "package_id": "real-assembly",
        "revision": 1,
        "project": {"title": "Real assembly", "project_id": "real-assembly"},
        "assets": [
            {
                "asset_key": "accepted.a",
                "media_type": "video",
                "source": {"uri": "accepted/panel-a.mp4"},
                "provenance": {"source_type": "accepted_clip", "producer": "test", "operation": "video.capture"},
            },
            {
                "asset_key": "accepted.b",
                "media_type": "video",
                "source": {"uri": "accepted/panel-b.mp4"},
                "provenance": {"source_type": "accepted_clip", "producer": "test", "operation": "video.capture"},
            },
            {
                "asset_key": "music",
                "media_type": "audio",
                "source": {"uri": "assets/music.wav"},
                "provenance": {"source_type": "test", "producer": "test", "operation": "audio.generate"},
            },
            {
                "asset_key": "captions",
                "media_type": "subtitle",
                "source": {"uri": "assets/panel-b.srt"},
                "provenance": {"source_type": "test", "producer": "test", "operation": "subtitle.write"},
            },
        ],
        "clips": [
            {
                "clip_id": "panel-a",
                "sequence": 1,
                "duration_ms": 800,
                "generation": {
                    "operation": "video.passthrough",
                    "prompt": "accepted panel a",
                    "references": [{
                        "reference_id": "video-a",
                        "asset_key": "accepted.a",
                        "semantic_usage": "accepted.clip",
                        "binding": {"required": True},
                    }],
                },
                "audio": {"native_audio": "mute"},
                "subtitles": {"cues": [{"start_ms": 0, "end_ms": 500, "text": "first panel"}]},
            },
            {
                "clip_id": "panel-b",
                "sequence": 2,
                "duration_ms": 600,
                "generation": {
                    "operation": "video.passthrough",
                    "prompt": "accepted panel b",
                    "references": [{
                        "reference_id": "video-b",
                        "asset_key": "accepted.b",
                        "semantic_usage": "accepted.clip",
                        "binding": {"required": True},
                    }],
                },
                "audio": {
                    "native_audio": "preserve",
                    "tracks": [{"asset_key": "music", "role": "music"}],
                },
                "subtitles": {"asset_key": "captions"},
            },
        ],
        "output": {
            "width": 96,
            "height": 64,
            "fps": 24,
            "subtitles_mode": "both",
            "directory": "real-assembly",
        },
    }
    package_path = tmp_path / "assembly-package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    runtime = VideoRuntime(workspace_root=tmp_path / "workspace")

    approved_sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()
    result = runtime.execute(package_path, approved_sha256=approved_sha256)

    assert result.status == "COMPLETED", result.error
    assert result.file_path is not None
    final_path = pathlib.Path(result.file_path)
    final_metadata = probe(final_path)
    assert final_metadata["width"] == 96
    assert final_metadata["height"] == 64
    assert final_metadata["has_audio"]
    assert pathlib.Path(result.output_layout["subtitles_path"]).read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:00,500\nfirst panel\n\n"
        "2\n00:00:00,800 --> 00:00:01,300\nsecond panel\n"
    )
    exported = runtime.export(result.run_id)
    assert exported.status == "READY"
    assert exported.file_path == str(final_path)
    assert runtime.export(result.run_id).export_id == exported.export_id
