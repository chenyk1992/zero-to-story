"""Exporter — final file assembly with atomic rename and provenance manifest."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportSpec:
    """Specification for final export."""

    run_id: str
    package_id: str
    package_hash: str
    materialization_hash: str
    output_path: str
    container: str = "mp4"
    video_encoder: str = "h264"
    audio_encoder: str = "aac"
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    subtitles_mode: str = "sidecar"  # sidecar | burnin | both
    subtitle_paths: list[str] = field(default_factory=list)
    clip_hashes: dict[str, str] = field(default_factory=dict)
    # Provenance
    backend_ids: list[str] = field(default_factory=list)
    workflow_hashes: list[str] = field(default_factory=list)
    model_versions: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    """Result of export."""

    success: bool
    file_path: str | None = None
    file_hash: str | None = None
    file_size: int | None = None
    manifest_path: str | None = None
    subtitles_path: str | None = None
    duration_ms: int | None = None
    error: str | None = None


@dataclass
class ExportManifest:
    """Provenance manifest written alongside the export."""

    run_id: str
    package_id: str
    package_hash: str
    materialization_hash: str
    clips: list[dict[str, Any]] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    export_timestamp: str = ""
    output: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)


class Exporter:
    """Final export with atomic rename and manifest generation."""

    def export(
        self,
        spec: ExportSpec,
        source_timeline_path: str,
        qc_passed: bool = True,
    ) -> ExportResult:
        """Execute the final export.

        In production this would:
        1. Copy source to a temp file next to the final destination
        2. Run final QC gate
        3. Atomically rename temp to final path
        4. Write manifest.json sidecar
        5. Write subtitle sidecars

        Here we validate and compute the result without actual file I/O.
        """
        if not qc_passed:
            return ExportResult(success=False, error="QC gate failed")

        if not spec.run_id:
            return ExportResult(success=False, error="Missing run_id")

        # Compute manifest
        manifest = ExportManifest(
            run_id=spec.run_id,
            package_id=spec.package_id,
            package_hash=spec.package_hash,
            materialization_hash=spec.materialization_hash,
            backends=spec.backend_ids,
            workflows=spec.workflow_hashes,
            models=spec.model_versions,
            output={
                "container": spec.container,
                "video_encoder": spec.video_encoder,
                "audio_encoder": spec.audio_encoder,
                "width": spec.width,
                "height": spec.height,
                "fps": spec.fps,
            },
        )

        return ExportResult(
            success=True,
            file_path=spec.output_path,
            manifest_path=spec.output_path + ".manifest.json",
        )

    def build_manifest(self, spec: ExportSpec) -> ExportManifest:
        """Build the provenance manifest."""
        return ExportManifest(
            run_id=spec.run_id,
            package_id=spec.package_id,
            package_hash=spec.package_hash,
            materialization_hash=spec.materialization_hash,
            backends=list(spec.backend_ids),
            workflows=list(spec.workflow_hashes),
            models=list(spec.model_versions),
            output={
                "container": spec.container,
                "video_encoder": spec.video_encoder,
                "audio_encoder": spec.audio_encoder,
                "width": spec.width,
                "height": spec.height,
                "fps": spec.fps,
            },
        )
