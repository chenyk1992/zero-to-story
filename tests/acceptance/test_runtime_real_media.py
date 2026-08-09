from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from lfo.application.video_runtime import VideoRuntime
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.media.handlers import build_media_handler_registry


class SourceVideoHandler(TaskHandler):
    def __init__(self, output: pathlib.Path) -> None:
        self.output = output

    def execute(self, task_id, task_type, logical_key, metadata, attempt_id) -> HandlerResult:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=size=96x64:rate=12:duration=0.4",
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
        "project": {"title": "Real media smoke"},
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
            "width": 64,
            "height": 64,
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

    result = runtime.execute(package_path, approval=True)
    assert result.status == "COMPLETED", result.error
    exported = runtime.export(result.run_id)
    assert exported.status == "READY", exported.error
    assert exported.file_path is not None
    final_path = pathlib.Path(exported.file_path)
    assert final_path.is_file()
    assert pathlib.Path(f"{final_path}.manifest.json").is_file()
    assert final_path.with_suffix(".srt").is_file()
