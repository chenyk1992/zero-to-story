"""Tests for the runtime generation-quality handler scope."""

from __future__ import annotations

import lfo.media.qc as qc_module
from lfo.media.handlers import QCHandler


def test_qc_handler_accepts_probeable_video(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "provider-output.mp4"
    artifact.write_bytes(b"provider output")
    monkeypatch.setattr(qc_module, "probe", lambda path: {
        "duration_ms": 5000,
        "width": 720,
        "height": 1280,
        "codec": "h264",
    })

    result = QCHandler().execute(
        task_id="run.clip.media.qc",
        task_type="media.qc",
        logical_key="clip:media.qc",
        metadata={"input_artifacts": {"video": {"file_path": str(artifact)}}},
        attempt_id="attempt-1",
    )

    assert result.success
    assert result.qc_passed is True
    assert result.artifact_metadata["qc_scope"] == [
        "decodable", "video_stream", "duration", "resolution",
    ]
    assert result.artifact_metadata["qc_results"][0]["rule"] == "decodable"


def test_qc_handler_rejects_unreadable_video(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "provider-output.mp4"
    artifact.write_bytes(b"provider output")
    monkeypatch.setattr(qc_module, "probe", lambda path: (_ for _ in ()).throw(ValueError("bad media")))

    result = QCHandler().execute(
        task_id="run.clip.media.qc",
        task_type="media.qc",
        logical_key="clip:media.qc",
        metadata={"input_artifacts": {"video": {"file_path": str(artifact)}}},
        attempt_id="attempt-1",
    )

    assert not result.success
    assert result.qc_passed is False
