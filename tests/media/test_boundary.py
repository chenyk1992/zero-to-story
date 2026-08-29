"""Tests for objective adjacent-clip evidence generation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lfo.media._ffmpeg import probe
from lfo.media.boundary import BoundaryEvidenceBuilder, BoundaryEvidenceSpec
from lfo.media.handlers import build_media_handler_registry


def test_boundary_evidence_rejects_invalid_sampling_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="contact_sheet_fps"):
        BoundaryEvidenceSpec(
            boundary_id="a__b",
            previous_path="a.mp4",
            next_path="b.mp4",
            output_directory=str(tmp_path / "evidence"),
            contact_sheet_fps=0,
        ).validate()


def test_boundary_evidence_rejects_empty_boundary_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source paths"):
        BoundaryEvidenceSpec(
            boundary_id="a__b",
            previous_path=" ",
            next_path="b.mp4",
            output_directory=str(tmp_path / "evidence"),
        ).validate()


def test_boundary_evidence_allows_dotted_output_directory(tmp_path: Path) -> None:
    BoundaryEvidenceSpec(
        boundary_id="a__b",
        previous_path="a.mp4",
        next_path="b.mp4",
        output_directory=str(tmp_path / "evidence.v1"),
    ).validate()


def test_real_media_registry_exposes_boundary_evidence_handler(tmp_path: Path) -> None:
    assert build_media_handler_registry(tmp_path).has_handler("media.boundary_evidence")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_boundary_evidence_handler_writes_inside_run_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project = workspace / "projects" / "project"
    clips = project / "outputs" / "run" / "clips"
    previous = clips / "a" / "mixed.mp4"
    following = clips / "b" / "mixed.mp4"
    previous.parent.mkdir(parents=True)
    following.parent.mkdir(parents=True)
    _make_clip(previous, color="red", frequency=440)
    _make_clip(following, color="blue", frequency=880)
    output = project / "outputs" / "run" / "global" / "boundaries" / "a__b"
    handler = build_media_handler_registry(workspace).get("media.boundary_evidence")
    assert handler is not None

    result = handler.execute(
        "boundary-task",
        "media.boundary_evidence",
        "a__b:media.boundary_evidence",
        {
            "boundary_id": "a__b",
            "previous_input_task_id": "a.mix",
            "next_input_task_id": "b.mix",
            "input_artifacts": {
                "a.mix": {"file_path": str(previous)},
                "b.mix": {"file_path": str(following)},
            },
            "output_path": str(output),
            "next_source_in_ms": 100,
            "next_source_out_ms": 500,
            "artifact_layout": {
                "workspace_root": str(workspace),
                "project_root": str(project),
            },
        },
        "attempt",
    )

    assert result.success, result.error
    assert result.artifact_type == "boundary_evidence"
    assert Path(result.artifact_metadata["preview"]).is_file()
    assert Path(result.artifact_metadata["metrics"]).is_file()
    assert Path(result.artifact_metadata["preview"]).is_relative_to(output)
    metrics = json.loads(Path(result.artifact_metadata["metrics"]).read_text(encoding="utf-8"))
    assert metrics["window"]["next_head_start_ms"] == 100


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_boundary_preview_keeps_available_audio_when_one_clip_is_silent(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.mp4"
    following = tmp_path / "next.mp4"
    _make_clip(previous, color="red", frequency=440, with_audio=False)
    _make_clip(following, color="blue", frequency=880)

    evidence = BoundaryEvidenceBuilder().build(
        BoundaryEvidenceSpec(
            boundary_id="panel-001__panel-002",
            previous_path=str(previous),
            next_path=str(following),
            output_directory=str(tmp_path / "boundaries" / "panel-001__panel-002"),
            previous_tail_ms=300,
            next_head_ms=400,
        )
    )

    assert evidence.preview_has_audio
    assert probe(evidence.preview)["has_audio"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_boundary_evidence_builds_frames_preview_sheet_and_metrics(tmp_path: Path) -> None:
    previous = tmp_path / "previous.mp4"
    following = tmp_path / "next.mp4"
    _make_clip(previous, color="red", frequency=440)
    _make_clip(following, color="blue", frequency=880)

    evidence = BoundaryEvidenceBuilder().build(
        BoundaryEvidenceSpec(
            boundary_id="panel-001__panel-002",
            previous_path=str(previous),
            next_path=str(following),
            output_directory=str(tmp_path / "boundaries" / "panel-001__panel-002"),
            previous_tail_ms=300,
            next_head_ms=300,
            contact_sheet_fps=4,
            previous_source_in_ms=100,
            previous_source_out_ms=500,
            next_source_in_ms=100,
            next_source_out_ms=500,
        )
    )

    for path in (
        evidence.previous_tail_frame,
        evidence.next_head_frame,
        evidence.preview,
        evidence.contact_sheet,
        evidence.metrics,
    ):
        assert Path(path).is_file()
        assert Path(path).stat().st_size > 0
    assert evidence.preview_has_audio
    assert 0 <= (evidence.frame_ssim or 0) < 0.98
    assert 550 <= int(probe(evidence.preview)["duration_ms"]) <= 700

    metrics = json.loads(Path(evidence.metrics).read_text(encoding="utf-8"))
    assert metrics["version"] == "lfo.boundary-evidence.v1"
    assert metrics["measurements"]["exact_frame_candidate"] is False
    assert metrics["window"]["previous_tail_duration_ms"] == 300
    assert metrics["window"]["previous_tail_start_ms"] == 200
    assert metrics["window"]["next_head_start_ms"] == 100
    assert metrics["window"]["next_head_end_ms"] == 400
    assert metrics["window"]["next_head_duration_ms"] == 300
    assert len(metrics["sources"]["previous"]["sha256"]) == 64


def _make_clip(
    path: Path,
    *,
    color: str,
    frequency: int,
    with_audio: bool = True,
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=90x160:r=12:d=0.6",
    ]
    if with_audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=0.6",
                "-shortest",
            ]
        )
    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if with_audio:
        command.extend(["-c:a", "aac"])
    command.append(str(path))
    subprocess.run(command, check=True, capture_output=True)
