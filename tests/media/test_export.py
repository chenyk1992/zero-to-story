"""Tests for exporter."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lfo.media.export import Exporter, ExportManifest, ExportSpec


class TestExporter:
    def test_successful_export(self, tmp_path: Path) -> None:
        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg is required for real export test")
        source = tmp_path / "timeline.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x64:d=0.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1",
            package_id="pkg-1",
            package_hash="pkg-hash",
            materialization_hash="mat-hash",
            output_path=str(tmp_path / "final.mp4"),
        )
        result = exporter.export(spec, str(source), qc_passed=True)
        assert result.success
        assert Path(result.file_path or "").is_file()
        assert Path(result.manifest_path or "").is_file()

    def test_qc_gate_fails(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1",
            package_id="pkg-1",
            package_hash="h",
            materialization_hash="m",
            output_path="/tmp/final.mp4",
        )
        result = exporter.export(spec, "/tmp/timeline.mp4", qc_passed=False)
        assert not result.success
        assert "QC" in result.error

    def test_export_does_not_run_media_playability_qc(self, tmp_path: Path) -> None:
        """Export only publishes the upstream artifact; decoding is not a gate."""
        source = tmp_path / "opaque-provider-output.mp4"
        source.write_bytes(b"provider output that is intentionally not decoded")
        spec = ExportSpec(
            run_id="run-1",
            package_id="pkg-1",
            package_hash="h",
            materialization_hash="m",
            output_path=str(tmp_path / "final.mp4"),
        )

        result = Exporter().export(spec, str(source))

        assert result.success
        assert Path(result.file_path or "").read_bytes() == source.read_bytes()

    def test_missing_run_id_fails(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="",
            package_id="pkg-1",
            package_hash="h",
            materialization_hash="m",
            output_path="/tmp/final.mp4",
        )
        result = exporter.export(spec, "/tmp/timeline.mp4")
        assert not result.success

    def test_manifest_generation(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1",
            package_id="pkg-1",
            package_hash="pkg-hash",
            materialization_hash="mat-hash",
            output_path="/tmp/final.mp4",
            backend_ids=["comfyui.h3"],
            workflow_hashes=["wf-1"],
            model_versions=["minimax_h3_v1"],
        )
        manifest = exporter.build_manifest(spec)
        assert manifest.run_id == "run-1"
        assert "comfyui.h3" in manifest.backends

    def test_manifest_json_serializable(self) -> None:
        manifest = ExportManifest(
            run_id="r",
            package_id="p",
            package_hash="h",
            materialization_hash="m",
        )
        json_str = manifest.to_json()
        assert '"run_id": "r"' in json_str
