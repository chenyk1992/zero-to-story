"""Tests for the runtime generation-quality handler scope."""

from __future__ import annotations

from lfo.media.handlers import QCHandler


def test_qc_handler_accepts_non_empty_provider_artifact_without_media_probe(tmp_path) -> None:
    artifact = tmp_path / "provider-output.mp4"
    # Deliberately not a decodable MP4: media.qc no longer performs technical
    # decode, duration, resolution, fps, codec, or audio checks.
    artifact.write_bytes(b"provider output")

    result = QCHandler().execute(
        task_id="run.clip.media.qc",
        task_type="media.qc",
        logical_key="clip:media.qc",
        metadata={"input_artifacts": {"video": {"file_path": str(artifact)}}},
        attempt_id="attempt-1",
    )

    assert result.success
    assert result.qc_passed is True
    assert result.artifact_metadata["qc_scope"] == ["generation_quality"]
    assert result.artifact_metadata["qc_results"][0]["rule"] == "generation_artifact"
