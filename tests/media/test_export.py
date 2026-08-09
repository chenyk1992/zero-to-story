"""Tests for exporter."""
from __future__ import annotations

from lfo.media.export import ExportManifest, ExportSpec, Exporter


class TestExporter:
    def test_successful_export(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1",
            package_id="pkg-1",
            package_hash="pkg-hash",
            materialization_hash="mat-hash",
            output_path="/tmp/final.mp4",
        )
        result = exporter.export(spec, "/tmp/timeline.mp4", qc_passed=True)
        assert result.success
        assert result.file_path == "/tmp/final.mp4"

    def test_qc_gate_fails(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1", package_id="pkg-1",
            package_hash="h", materialization_hash="m",
            output_path="/tmp/final.mp4",
        )
        result = exporter.export(spec, "/tmp/timeline.mp4", qc_passed=False)
        assert not result.success
        assert "QC" in result.error

    def test_missing_run_id_fails(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="", package_id="pkg-1",
            package_hash="h", materialization_hash="m",
            output_path="/tmp/final.mp4",
        )
        result = exporter.export(spec, "/tmp/timeline.mp4")
        assert not result.success

    def test_manifest_generation(self) -> None:
        exporter = Exporter()
        spec = ExportSpec(
            run_id="run-1", package_id="pkg-1",
            package_hash="pkg-hash", materialization_hash="mat-hash",
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
            run_id="r", package_id="p", package_hash="h", materialization_hash="m",
        )
        json_str = manifest.to_json()
        assert '"run_id": "r"' in json_str
