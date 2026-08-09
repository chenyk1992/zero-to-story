"""Runtime task handlers backed by the real local media pipeline."""
from __future__ import annotations

import hashlib
import pathlib
import shutil
from typing import Any

from lfo.execution.handlers import HandlerRegistry, HandlerResult, TaskHandler
from lfo.media._ffmpeg import probe
from lfo.media.audio import AudioMixer, AudioMixRequest, AudioTrack
from lfo.media.export import Exporter, ExportSpec
from lfo.media.normalize import Normalizer, NormalizeTarget
from lfo.media.qc import QCContract, TechnicalQC
from lfo.media.subtitles import SubtitleCue, SubtitleRenderer
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec


def build_media_handler_registry(workspace_root: pathlib.Path | str) -> HandlerRegistry:
    """Create production handlers sharing one managed workspace root."""

    root = pathlib.Path(workspace_root).resolve()
    registry = HandlerRegistry()
    registry.register("media.normalize", NormalizeHandler(root))
    registry.register("media.qc", QCHandler())
    registry.register("audio.mix", AudioHandler(root))
    registry.register("subtitle.render", SubtitleHandler(root))
    registry.register("timeline.assemble", TimelineHandler(root))
    registry.register("export.finalize", ExportHandler(root))
    return registry


class NormalizeHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        source = _single_input_path(metadata)
        if source is None:
            return _terminal("Normalization input artifact has no file_path")
        policy = _policy(metadata)
        output = _work_path(self.root, metadata, "normalized", ".mp4")
        result = Normalizer().normalize(
            source,
            output,
            NormalizeTarget(
                width=_optional_int(policy.get("width")),
                height=_optional_int(policy.get("height")),
                fps=_optional_float(policy.get("fps")),
                sample_rate=_optional_int(policy.get("sample_rate")),
                loudness_db=_optional_float(policy.get("loudness_db")),
                codec=_ffmpeg_video_encoder(policy.get("video_encoder")),
                container=str(policy.get("container", "mp4")),
            ),
        )
        if not result.success or not result.output_path:
            return HandlerResult(False, error=result.error or "Normalization failed", retryable=True)
        return _file_result("normalized_video", pathlib.Path(result.output_path), result.output_metadata)


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
            expected_width=_optional_int(policy.get("width")),
            expected_height=_optional_int(policy.get("height")),
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
        output = _work_path(self.root, metadata, "audio", ".mp4")
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
                output = _work_path(self.root, metadata, "subtitles", source.suffix.lower() or ".srt")
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
            elif cues:
                output = _work_path(self.root, metadata, "subtitles", ".srt")
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


class TimelineHandler(TaskHandler):
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def execute(self, task_id: str, task_type: str, logical_key: str,
                metadata: dict[str, Any], attempt_id: str) -> HandlerResult:
        artifacts = _input_artifacts(metadata)
        segments_data = metadata.get("segments", [])
        if not isinstance(segments_data, list):
            return _terminal("timeline segments must be a list")
        segments: list[ClipSegment] = []
        for item in segments_data:
            if not isinstance(item, dict):
                return _terminal("timeline segment must be an object")
            artifact = artifacts.get(str(item.get("input_task_id")), {})
            path = artifact.get("file_path") if isinstance(artifact, dict) else None
            if not isinstance(path, str):
                return _terminal(f"Timeline input missing for clip {item.get('clip_id')}")
            segments.append(
                ClipSegment(
                    clip_id=str(item.get("clip_id")),
                    file_path=path,
                    duration_ms=int(item.get("duration_ms", 0)),
                )
            )
        policy = _policy(metadata)
        output = _work_path(self.root, metadata, "timeline", ".mp4")
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
            return HandlerResult(False, error=result.error or "Timeline assembly failed", retryable=True)
        return _file_result(
            "timeline_video",
            pathlib.Path(result.output_path),
            {
                "duration_ms": result.total_duration_ms,
                "segments": [
                    {"clip_id": item.clip_id, "start_ms": item.start_ms, "duration_ms": item.duration_ms}
                    for item in segments
                ],
            },
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
            burned = _work_path(self.root, metadata, "timeline-subtitled", ".mp4")
            try:
                SubtitleRenderer().burn_in(source_path, subtitle_path, burned)
            except Exception as exc:
                return _terminal(f"Subtitle burn-in failed: {exc}")
            source_path = burned
        package_id = str(metadata.get("package_id", "package"))
        run_id = str(metadata.get("run_id", "run"))
        directory = _safe_component(str(policy.get("directory") or package_id))
        container = str(policy.get("container", "mp4"))
        output = self.root / "exports" / directory / f"{_safe_component(package_id)}-{run_id}.{container}"
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
        offsets = {
            str(item.get("clip_id")): sum(
                int(previous.get("duration_ms", 0))
                for previous in metadata.get("segments", [])
                if isinstance(previous, dict)
                and int(previous.get("sequence", 0)) < int(item.get("sequence", 0))
            )
            for item in metadata.get("segments", [])
            if isinstance(item, dict)
        }
        cues: list[SubtitleCue] = []
        for artifact in subtitle_artifacts:
            clip_id = str(artifact.get("clip_id", ""))
            offset = offsets.get(clip_id, 0)
            for cue in artifact.get("cues", []):
                if isinstance(cue, dict):
                    cues.append(
                        SubtitleCue(
                            int(cue["start_ms"]) + offset,
                            int(cue["end_ms"]) + offset,
                            str(cue["text"]),
                        )
                    )
        if not cues:
            # External sidecars are already valid; use the first one when no
            # structured cues were available for global retiming.
            path = subtitle_artifacts[0].get("file_path")
            return pathlib.Path(path) if isinstance(path, str) else None
        output = _work_path(self.root, metadata, "subtitles-global", ".srt")
        SubtitleRenderer().render_srt(sorted(cues, key=lambda cue: cue.start_ms), output)
        return output


def _input_artifacts(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = metadata.get("input_artifacts", {})
    return value if isinstance(value, dict) else {}


def _single_input_path(metadata: dict[str, Any]) -> pathlib.Path | None:
    for artifact in _input_artifacts(metadata).values():
        if isinstance(artifact, dict) and isinstance(artifact.get("file_path"), str):
            return pathlib.Path(artifact["file_path"])
    return None


def _policy(metadata: dict[str, Any]) -> dict[str, Any]:
    value = metadata.get("output_policy", {})
    return value if isinstance(value, dict) else {}


def _work_path(root: pathlib.Path, metadata: dict[str, Any], name: str, suffix: str) -> pathlib.Path:
    run_id = _safe_component(str(metadata.get("run_id", "run")))
    clip_id = _safe_component(str(metadata.get("clip_id", "global")))
    path = root / "runs" / run_id / "work" / clip_id / f"{name}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_component(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-_." else "_" for character in value)
    return safe.strip(". ") or "item"


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
