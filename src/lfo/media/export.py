"""Atomic final export, sidecars, and provenance manifest publication."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from lfo.media._ffmpeg import MediaCommandError


@dataclass
class ExportSpec:
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
    subtitles_mode: str = "sidecar"
    subtitle_paths: list[str] = field(default_factory=list)
    clip_hashes: dict[str, str] = field(default_factory=dict)
    backend_ids: list[str] = field(default_factory=list)
    workflow_hashes: list[str] = field(default_factory=list)
    model_versions: list[str] = field(default_factory=list)
    # Supplied by the assembled timeline artifact when available.  It is
    # descriptive metadata, not a duration QC constraint.
    duration_ms: int | None = None


@dataclass
class ExportResult:
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
    run_id: str
    package_id: str
    package_hash: str
    materialization_hash: str
    clips: list[dict[str, object]] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    export_timestamp: str = ""
    output: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False, sort_keys=True)


class Exporter:
    """Publish an already assembled timeline after upstream gates pass."""

    def export(
        self, spec: ExportSpec, source_timeline_path: str, qc_passed: bool = True
    ) -> ExportResult:
        if not qc_passed:
            return ExportResult(False, error="QC gate failed")
        if not spec.run_id:
            return ExportResult(False, error="Missing run_id")
        source, output = Path(source_timeline_path), Path(spec.output_path)
        if not source.is_file():
            return ExportResult(False, error=f"Timeline source does not exist: {source}")
        if spec.subtitles_mode not in {"sidecar", "burnin", "both", "none"}:
            return ExportResult(False, error=f"Unsupported subtitles mode: {spec.subtitles_mode}")
        if any(not Path(path).is_file() for path in spec.subtitle_paths):
            return ExportResult(False, error="Subtitle sidecar does not exist")
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix}")
        try:
            shutil.copy2(source, temp)
            if not temp.is_file() or temp.stat().st_size == 0:
                raise MediaCommandError("Export copy produced no file")
            temp.replace(output)
            subtitle_path = self._publish_sidecars(spec, output)
            manifest = self.build_manifest(spec)
            manifest.clips = [
                {"clip_id": key, "hash": value} for key, value in sorted(spec.clip_hashes.items())
            ]
            manifest.export_timestamp = datetime.now(UTC).isoformat()
            manifest.output.update(
                {
                    "path": str(output),
                    "sha256": self._sha256(output),
                    "size": output.stat().st_size,
                    "duration_ms": spec.duration_ms,
                }
            )
            manifest_path = Path(f"{output}.manifest.json")
            self._atomic_text(manifest_path, manifest.to_json())
            return ExportResult(
                True,
                str(output),
                self._sha256(output),
                output.stat().st_size,
                str(manifest_path),
                subtitle_path,
                spec.duration_ms,
            )
        except (OSError, MediaCommandError) as exc:
            temp.unlink(missing_ok=True)
            return ExportResult(False, error=str(exc))

    def _publish_sidecars(self, spec: ExportSpec, output: Path) -> str | None:
        if spec.subtitles_mode not in {"sidecar", "both"} or not spec.subtitle_paths:
            return None
        source = Path(spec.subtitle_paths[0])
        destination = output.with_suffix(source.suffix)
        temp = destination.with_name(f".{destination.stem}.{uuid4().hex}.tmp{destination.suffix}")
        shutil.copy2(source, temp)
        temp.replace(destination)
        return str(destination)

    def _atomic_text(self, path: Path, text: str) -> None:
        temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def build_manifest(self, spec: ExportSpec) -> ExportManifest:
        return ExportManifest(
            spec.run_id,
            spec.package_id,
            spec.package_hash,
            spec.materialization_hash,
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
