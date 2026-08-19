from __future__ import annotations

import hashlib
import pathlib

from lfo.backends.passthrough import (
    PASSTHROUGH_BACKEND_ID,
    PASSTHROUGH_BACKEND_REVISION,
    VideoPassthroughHandler,
    build_passthrough_backend_registry,
)


def _layout(workspace: pathlib.Path) -> dict[str, str]:
    project_root = workspace / "projects" / "project"
    return {
        "workspace_root": str(workspace),
        "project_root": str(project_root),
    }


def test_passthrough_capability_declares_one_video_reference() -> None:
    registry = build_passthrough_backend_registry()
    manifest = registry.get(PASSTHROUGH_BACKEND_ID, PASSTHROUGH_BACKEND_REVISION)
    assert manifest is not None
    assert manifest.operations == ["video.passthrough"]
    assert manifest.accepted_media_types == ["video"]
    assert manifest.max_references == 1


def test_passthrough_copies_to_managed_path(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"accepted-video")
    destination = tmp_path / "workspace" / "projects" / "project" / "outputs" / "run" / "clips" / "shot" / "generated.mp4"
    result = VideoPassthroughHandler().execute(
        "task",
        "video.generate",
        "shot:video.generate",
        {
            "resolved_references": [{"media_type": "video", "file_path": str(source)}],
            "output_path": str(destination),
            "artifact_layout": _layout(tmp_path / "workspace"),
        },
        "attempt",
    )
    assert result.success
    assert destination.read_bytes() == b"accepted-video"
    assert result.artifact_metadata["media_type"] == "video"
    assert result.artifact_metadata["size"] == len(b"accepted-video")
    assert result.artifact_metadata["file_hash"] == hashlib.sha256(b"accepted-video").hexdigest()
    assert result.artifact_metadata["file_path"] == str(destination.resolve())


def test_passthrough_rejects_non_video_or_wrong_reference_count(tmp_path: pathlib.Path) -> None:
    handler = VideoPassthroughHandler()
    base = {
        "output_path": str(tmp_path / "workspace" / "projects" / "p" / "generated.mp4"),
        "artifact_layout": _layout(tmp_path / "workspace"),
    }
    for refs in ([], [{"media_type": "image", "file_path": str(tmp_path / "x")}], [{"media_type": "video"}, {"media_type": "video"}]):
        result = handler.execute("task", "video.generate", "key", {**base, "resolved_references": refs}, "attempt")
        assert not result.success
        assert not result.retryable
