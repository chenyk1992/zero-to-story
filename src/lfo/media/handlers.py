"""Runtime task handlers backed by the real local media pipeline."""
from __future__ import annotations

import hashlib
import pathlib
from typing import Any

from lfo.execution.handlers import HandlerRegistry, HandlerResult, TaskHandler
from lfo.media._ffmpeg import MediaCommandError, probe
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.boundary import BoundaryEvidenceBuilder, BoundaryEvidenceSpec, evidence_to_dict
from lfo.media.export import Exporter, ExportSpec
from lfo.media.qc import QCContract, TechnicalQC
from lfo.media.subtitles import (
    SubtitleCue,
    SubtitleRenderer,
    parse_srt,
    parse_vtt,
    trim_cues,
)
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec
from lfo.services.artifact_layout import ArtifactLayoutError, managed_path


def build_media_handler_registry(workspace_root: pathlib.Path | str) -> HandlerRegistry:
    """Create production handlers sharing one managed workspace root."""

    root = pathlib.Path(workspace_root).resolve()
    registry = HandlerRegistry()
    registry.register("media.qc", QCHandler())
    registry.register("audio.mix", AudioHandler(root))
    registry.register("subtitle.render", SubtitleHandler(root))
    registry.register("media.boundary_evidence", BoundaryEvidenceHandler(root))
    registry.register("timeline.assemble", TimelineHandler(root))
    registry.register("export.finalize", ExportHandler(root))
    return registry


class QCHandler(TaskHandler):
    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        source = _single_input_path(metadata)
        if source is None:
            return _terminal("QC input artifact has no file_path", qc_passed=False)
        try:
            actual = probe(source)
        except Exception as exc:
            return _terminal(f"Media probe failed: {exc}", qc_passed=False)
        policy = _policy(metadata)
        duration = _optional_int(metadata.get("duration_ms"))
        contract = QCContract(
            min_duration_ms=max(1, duration - 1_000) if duration else None,
            max_duration_ms=duration + 2_000 if duration else None,
            # Resolution is owned by the provider/source clip. LFO no longer
            # performs an implicit resize before QC.
            expected_width=None,
            expected_height=None,
            expected_fps=_optional_float(policy.get("fps")),
            expected_codec="h264" if policy.get("video_encoder", "h264") == "h264" else None,
        )
        report = TechnicalQC().check(actual, contract)
        failures = [item.message or item.rule for item in report.failures]
        return HandlerResult(
            success=report.passed,
            artifact_type="qc_video" if report.passed else None,
            artifact_metadata={
                "file_path": str(source),
                "file_hash": _sha256(source),
                "media_type": "video",
                "qc_passed": report.passed,
                "qc_results": [item.__dict__ for item in report.results],
                **actual,
            },
            error="; ".join(failures) if failures else None,
            retryable=False,
            qc_passed=report.passed,
        )


class AudioHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        source = _single_input_path(metadata)
        if source is None:
            return _terminal("Audio input artifact has no file_path")
        policy = metadata.get("audio_policy", {})
        if not isinstance(policy, dict):
            return _terminal("audio_policy must be an object")
        tracks: list[AudioTrack] = []
        for item in policy.get("tracks", []):
            if not isinstance(item, dict) or not item.get("file_path"):
                return _terminal("External audio track has no imported file_path")
            tracks.append(
                AudioTrack(
                    asset_key=str(item["file_path"]),
                    role=str(item.get("role", "effect")),
                    offset_ms=int(item.get("offset_ms", 0)),
                    gain_db=float(item.get("gain_db", 0)),
                    fade_in_ms=int(item.get("fade_in_ms", 0)),
                    fade_out_ms=int(item.get("fade_out_ms", 0)),
                    duck_group=item.get("duck_group") if isinstance(item.get("duck_group"), str) else None,
                    duration_ms=_optional_int(item.get("duration_ms")),
                )
            )
        output = _managed_output(self.root, metadata)
        # Reuse probe metadata threaded from upstream media.qc when available;
        # otherwise probe the source file directly.
        source_metadata = _input_probe(metadata)
        if source_metadata is None:
            try:
                source_metadata = probe(source)
            except Exception as exc:
                return _terminal(f"Audio source probe failed: {exc}")
        output_policy = _policy(metadata)
        result = AudioMixer().mix(
            AudioMixRequest(
                native_audio_present=bool(source_metadata.get("has_audio")),
                native_audio_strategy=str(policy.get("native_audio", "preserve")),
                tracks=tracks,
                target_loudness_db=_optional_float(output_policy.get("loudness_db")),
                target_sample_rate=_optional_int(output_policy.get("sample_rate")) or 48_000,
                clip_duration_ms=_optional_int(metadata.get("duration_ms")) or 0,
                source_video_path=str(source),
                output_path=str(output),
            )
        )
        if not result.success or not result.output_path:
            return HandlerResult(False, error=result.error or "Audio mix failed", retryable=True)
        return _file_result("mixed_video", pathlib.Path(result.output_path), {"has_audio": result.has_audio})


class SubtitleHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        subtitles = metadata.get("subtitles", {})
        if not isinstance(subtitles, dict):
            return _terminal("subtitles must be an object")
        duration = _optional_int(metadata.get("duration_ms"))
        cues: list[SubtitleCue] = []
        try:
            for cue in subtitles.get("cues", []):
                if not isinstance(cue, dict):
                    raise TypeError("Subtitle cue must be an object")
                cues.append(SubtitleCue(int(cue["start_ms"]), int(cue["end_ms"]), str(cue["text"])))
            external = subtitles.get("file_path")
            if external:
                source = pathlib.Path(str(external))
                if not source.is_file():
                    return _terminal(f"Subtitle file does not exist: {source}")
                output = _managed_output(self.root, metadata)
                content = source.read_text(encoding="utf-8-sig")
                cues = parse_vtt(content) if source.suffix.lower() == ".vtt" else parse_srt(content)
                SubtitleRenderer().render_srt(cues, output, duration_ms=duration)
            elif cues:
                output = _managed_output(self.root, metadata)
                SubtitleRenderer().render_srt(cues, output, duration_ms=duration)
            else:
                return HandlerResult(
                    True,
                    artifact_type="subtitle_none",
                    artifact_metadata={"cues": [], "sequence": metadata.get("sequence")},
                )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            return _terminal(f"Subtitle rendering failed: {exc}")
        return _file_result(
            "subtitle",
            output,
            {
                "cues": [cue.__dict__ for cue in cues],
                "sequence": metadata.get("sequence"),
                "clip_id": metadata.get("clip_id"),
                "duration_ms": duration,
            },
            media_type="subtitle",
        )


class BoundaryEvidenceHandler(TaskHandler):
    """Materialize objective evidence for one adjacent timeline boundary."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        artifacts = _input_artifacts(metadata)
        previous_task_id = str(metadata.get("previous_input_task_id", ""))
        next_task_id = str(metadata.get("next_input_task_id", ""))
        previous_path = _artifact_path(artifacts.get(previous_task_id))
        next_path = _artifact_path(artifacts.get(next_task_id))
        if previous_path is None or next_path is None:
            return _terminal("Boundary evidence requires both adjacent clip artifacts")
        try:
            evidence = BoundaryEvidenceBuilder().build(
                BoundaryEvidenceSpec(
                    boundary_id=str(metadata.get("boundary_id", "")),
                    previous_path=str(previous_path),
                    next_path=str(next_path),
                    output_directory=str(_managed_output(self.root, metadata)),
                    previous_source_in_ms=_optional_int(
                        metadata.get("previous_source_in_ms")
                    )
                    or 0,
                    previous_source_out_ms=_optional_int(
                        metadata.get("previous_source_out_ms")
                    ),
                    next_source_in_ms=_optional_int(metadata.get("next_source_in_ms")) or 0,
                    next_source_out_ms=_optional_int(metadata.get("next_source_out_ms")),
                )
            )
            details = evidence_to_dict(evidence)
            preview = pathlib.Path(evidence.preview)
            details.update(
                {
                    "file_path": evidence.preview,
                    "file_hash": _sha256(preview),
                    "file_size": preview.stat().st_size,
                    "media_type": "video",
                    "review_required": True,
                }
            )
        except (ArtifactLayoutError, MediaCommandError, OSError, TypeError, ValueError) as exc:
            return _terminal(f"Boundary evidence failed: {exc}")
        return HandlerResult(
            True,
            artifact_type="boundary_evidence",
            artifact_metadata=details,
        )


class TimelineHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        artifacts = _input_artifacts(metadata)
        segments_data = metadata.get("segments", [])
        if not isinstance(segments_data, list):
            return _terminal("timeline segments must be a list")
        try:
            segments: list[ClipSegment] = []
            for item in segments_data:
                if not isinstance(item, dict):
                    raise TypeError("timeline segment must be an object")
                artifact = artifacts.get(str(item.get("input_task_id")), {})
                path = artifact.get("file_path") if isinstance(artifact, dict) else None
                if not isinstance(path, str):
                    raise ValueError(f"Timeline input missing for clip {item.get('clip_id')}")
                segments.append(
                    ClipSegment(
                        clip_id=str(item.get("clip_id")),
                        file_path=path,
                        duration_ms=int(item.get("duration_ms", 0)),
                        source_in_ms=int(item.get("source_in_ms", 0)),
                        source_out_ms=(
                            int(item["source_out_ms"])
                            if item.get("source_out_ms") is not None
                            else None
                        ),
                    )
                )
            policy = _policy(metadata)
            output = _managed_output(self.root, metadata)
            result = TimelineAssembler().assemble(
                TimelineSpec(
                    segments=segments,
                    transitions=str(policy.get("transitions", "cut")),
                    output_width=_optional_int(policy.get("width")) or 0,
                    output_height=_optional_int(policy.get("height")) or 0,
                    output_fps=_optional_float(policy.get("fps")) or 24.0,
                    output_codec=_ffmpeg_video_encoder(policy.get("video_encoder")) or "libx264",
                    audio_codec=str(policy.get("audio_encoder", "aac")),
                    output_container=str(policy.get("container", "mp4")),
                    output_path=str(output),
                )
            )
            if not result.success or not result.output_path:
                return HandlerResult(
                    False,
                    error=result.error or "Timeline assembly failed",
                    retryable=True,
                )
            return _file_result(
                "timeline_video",
                pathlib.Path(result.output_path),
                {
                    "duration_ms": result.total_duration_ms,
                    "segments": [
                        {
                            "clip_id": item.clip_id,
                            "start_ms": item.start_ms,
                            "duration_ms": item.edited_duration_ms(),
                            "source_in_ms": item.source_in_ms,
                            "source_out_ms": item.source_out_ms,
                        }
                        for item in segments
                    ],
                },
            )
        except (MediaCommandError, OSError, TypeError, ValueError, KeyError) as exc:
            return HandlerResult(
                False,
                error=f"Timeline assembly failed: {exc}",
                retryable=True,
            )


class ExportHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        artifacts = _input_artifacts(metadata)
        timeline = next(
            (value for key, value in artifacts.items() if key.endswith(".timeline.assemble")),
            None,
        )
        if not isinstance(timeline, dict) or not isinstance(timeline.get("file_path"), str):
            return _terminal("Export timeline artifact is missing")
        policy = _policy(metadata)
        subtitle_path = self._global_subtitle(metadata, artifacts)
        mode = str(policy.get("subtitles_mode", "sidecar"))
        source_path = pathlib.Path(str(timeline["file_path"]))
        if subtitle_path is not None and mode in {"burnin", "both"}:
            burned = _global_output(
                self.root,
                metadata,
                "timeline-subtitled",
                f".{policy.get('container', 'mp4')!s}",
            )
            try:
                SubtitleRenderer().burn_in(source_path, subtitle_path, burned)
            except Exception as exc:
                return _terminal(f"Subtitle burn-in failed: {exc}")
            source_path = burned
        output = _managed_output(self.root, metadata)
        package_id = str(metadata.get("package_id", "package"))
        run_id = str(metadata.get("run_id", "run"))
        container = str(policy.get("container", "mp4"))
        result = Exporter().export(
            ExportSpec(
                run_id=run_id,
                package_id=package_id,
                package_hash=str(metadata.get("package_hash", "")),
                materialization_hash=str(metadata.get("materialization_hash", "")),
                output_path=str(output),
                container=container,
                video_encoder=str(policy.get("video_encoder", "h264")),
                audio_encoder=str(policy.get("audio_encoder", "aac")),
                width=_optional_int(policy.get("width")),
                height=_optional_int(policy.get("height")),
                fps=_optional_int(policy.get("fps")),
                subtitles_mode="sidecar" if subtitle_path is not None and mode in {"sidecar", "both"} else "none",
                subtitle_paths=[str(subtitle_path)] if subtitle_path is not None else [],
                backend_ids=[str(value) for value in metadata.get("backend_ids", [])],
                workflow_hashes=[str(value) for value in metadata.get("workflow_hashes", [])],
            ),
            str(source_path),
            qc_passed=True,
        )
        if not result.success or not result.file_path:
            return _terminal(result.error or "Export failed")
        return HandlerResult(
            True,
            artifact_type="final_video",
            artifact_metadata={
                "file_path": result.file_path,
                "file_hash": result.file_hash,
                "media_type": "video",
                "manifest_path": result.manifest_path,
                "subtitles_path": result.subtitles_path,
                "duration_ms": result.duration_ms,
                "file_size": result.file_size,
            },
        )

    def _global_subtitle(
        self, metadata: dict[str, Any], artifacts: dict[str, dict[str, Any]]
    ) -> pathlib.Path | None:
        subtitle_artifacts = [
            value for key, value in artifacts.items() if key.endswith(".subtitle.render")
        ]
        if not subtitle_artifacts:
            return None
        segments = [item for item in metadata.get("segments", []) if isinstance(item, dict)]
        offsets: dict[str, int] = {}
        current = 0
        for item in segments:
            clip_id = str(item.get("clip_id", ""))
            offsets[clip_id] = current
            current += int(item.get("edited_duration_ms", item.get("duration_ms", 0)))
        cues: list[SubtitleCue] = []
        for artifact in subtitle_artifacts:
            clip_id = str(artifact.get("clip_id", ""))
            if clip_id not in offsets:
                continue
            offset = offsets[clip_id]
            segment = next((item for item in segments if str(item.get("clip_id")) == clip_id), {})
            source_in_ms = int(segment.get("source_in_ms", 0))
            source_out_value = segment.get("source_out_ms")
            source_out_ms = int(source_out_value) if source_out_value is not None else None
            local_cues = [
                SubtitleCue(int(cue["start_ms"]), int(cue["end_ms"]), str(cue["text"]))
                for cue in artifact.get("cues", [])
                if isinstance(cue, dict)
            ]
            for cue in trim_cues(local_cues, source_in_ms, source_out_ms):
                cues.append(SubtitleCue(cue.start_ms + offset, cue.end_ms + offset, cue.text))
        if not cues:
            # External sidecars are already valid; use the first one when no
            # structured cues were available for global retiming.
            path = subtitle_artifacts[0].get("file_path")
            return pathlib.Path(path) if isinstance(path, str) else None
        output = _global_output(self.root, metadata, "subtitles-global", ".srt")
        SubtitleRenderer().render_srt(sorted(cues, key=lambda cue: cue.start_ms), output)
        return output


def _input_artifacts(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = metadata.get("input_artifacts", {})
    return value if isinstance(value, dict) else {}


def _artifact_path(artifact: object) -> pathlib.Path | None:
    if isinstance(artifact, dict) and isinstance(artifact.get("file_path"), str):
        return pathlib.Path(artifact["file_path"])
    return None


def _input_probe(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Return probe metadata from the immediate upstream artifact, if present.

    Used by downstream handlers (media.qc → audio.mix → timeline.assemble) to
    avoid re-probing the same file.  Returns None when no usable probe data is
    available, in which case the caller should probe the file directly.
    """
    for artifact in _input_artifacts(metadata).values():
        if not isinstance(artifact, dict):
            continue
        if "has_audio" in artifact and "codec" in artifact:
            return artifact
    return None


def _single_input_path(metadata: dict[str, Any]) -> pathlib.Path | None:
    for artifact in _input_artifacts(metadata).values():
        if isinstance(artifact, dict) and isinstance(artifact.get("file_path"), str):
            return pathlib.Path(artifact["file_path"])
    return None


def _policy(metadata: dict[str, Any]) -> dict[str, Any]:
    value = metadata.get("output_policy", {})
    return value if isinstance(value, dict) else {}


def _managed_output(
    root: pathlib.Path,
    metadata: dict[str, Any],
) -> pathlib.Path:
    """Return the task path supplied by the immutable project layout."""
    path = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
    projects_root = (root / "projects").resolve(strict=False)
    try:
        path.relative_to(projects_root)
    except ValueError as exc:
        raise ArtifactLayoutError(f"Managed output escapes projects root: {path}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _global_output(
    root: pathlib.Path,
    metadata: dict[str, Any],
    name: str,
    suffix: str,
) -> pathlib.Path:
    layout = metadata.get("artifact_layout")
    if not isinstance(layout, dict) or not isinstance(layout.get("global_root"), str):
        raise ArtifactLayoutError("Task is missing its project artifact_layout")
    path = managed_path(
        str(pathlib.Path(str(layout["global_root"])) / f"{name}{suffix}"),
        layout,
    )
    projects_root = (root / "projects").resolve(strict=False)
    try:
        path.relative_to(projects_root)
    except ValueError as exc:
        raise ArtifactLayoutError(f"Managed global output escapes projects root: {path}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _terminal(error: str, *, qc_passed: bool | None = None) -> HandlerResult:
    return HandlerResult(False, error=error, retryable=False, qc_passed=qc_passed)


def _file_result(
    artifact_type: str,
    path: pathlib.Path,
    metadata: dict[str, Any] | None = None,
    *,
    media_type: str = "video",
) -> HandlerResult:
    details = dict(metadata or {})
    details.update(
        {
            "file_path": str(path.resolve()),
            "file_hash": _sha256(path),
            "media_type": media_type,
            "file_size": path.stat().st_size,
        }
    )
    return HandlerResult(True, artifact_type=artifact_type, artifact_metadata=details)


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TypeError(f"Expected integer-compatible value, got {type(value).__name__}")
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TypeError(f"Expected numeric value, got {type(value).__name__}")
    return float(value)


def _ffmpeg_video_encoder(value: object) -> str | None:
    return {"h264": "libx264", "h265": "libx265", "av1": "libaom-av1", "vp9": "libvpx-vp9"}.get(
        str(value) if value is not None else "h264"
    )
