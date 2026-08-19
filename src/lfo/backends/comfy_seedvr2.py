"""SeedVR2 video-upscale handler for local ComfyUI."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lfo.comfy.bindings import Binding, BindingResolver
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import ComfyUnreachableError, LfoComfyError
from lfo.comfy.monitor import ComfyMonitor
from lfo.comfy.workflow import WorkflowLoader
from lfo.contracts.upscale import resolve_upscale_options
from lfo.core.workflow_registry import KNOWN_WORKFLOWS, WorkflowManifest
from lfo.execution.handlers import HandlerResult, TaskHandler
from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec
from lfo.services.artifact_layout import atomic_copy_verified, managed_path

SEEDVR2_UPSCALE_WORKFLOW_ID = "seedvr2_upscale"
DEFAULT_SEGMENT_SECONDS = 8.0
logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ComfyUpscaleConfig:
    """Local paths and wait policy for the bundled SeedVR2 workflow."""

    base_url: str = "http://127.0.0.1:8188"
    workflow_dir: pathlib.Path = pathlib.Path(__file__).resolve().parents[1] / "registry"
    output_root: pathlib.Path = pathlib.Path(
        os.environ.get(
            "LFO_COMFY_OUTPUT_ROOT",
            "D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output",
        )
    )
    poll_interval_seconds: float = 3.0
    timeout_seconds: float = 1_200.0


class ComfyUpscaleVideoHandler(TaskHandler):
    """Execute one ``video.upscale`` task with the SeedVR2 ComfyUI workflow."""

    def __init__(
        self,
        config: ComfyUpscaleConfig | None = None,
        *,
        client: ComfyApiClient | None = None,
        monitor: ComfyMonitor | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.config = config or ComfyUpscaleConfig()
        self.client = client or ComfyApiClient(self.config.base_url)
        self.monitor = monitor or ComfyMonitor(self.client)
        self.progress_callback = progress_callback

    def execute(
        self,
        task_id: str,
        task_type: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
    ) -> HandlerResult:
        if task_type != "video.upscale":
            return HandlerResult(
                success=False,
                error=f"Unsupported task type: {task_type}",
                retryable=False,
            )

        try:
            source_video = self._source_video_path(metadata)
            segment_seconds = self._segment_seconds(metadata)
            if segment_seconds is not None:
                return self._execute_segmented(
                    task_id,
                    logical_key,
                    metadata,
                    attempt_id,
                    source_video,
                    segment_seconds,
                )
            return self._execute_single(
                task_id,
                logical_key,
                metadata,
                attempt_id,
                source_video,
            )
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            return HandlerResult(success=False, error=str(exc), retryable=False)
        except ComfyUnreachableError as exc:
            return HandlerResult(success=False, error=str(exc), retryable=True)
        except Exception as exc:  # provider extensions may raise their own exception types
            return HandlerResult(
                success=False,
                error=f"ComfyUI execution error: {exc}",
                retryable=True,
            )

    def _execute_single(
        self,
        task_id: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
        source_video: pathlib.Path,
    ) -> HandlerResult:
        """Upscale one video file through one ComfyUI prompt."""
        # H3 and SeedVR2 are both large GPU models.  Release H3's cached
        # weights before loading SeedVR2 on single-GPU workstations.
        self.client.free_memory()
        upload = self.client.upload_file(source_video, subfolder="lfo-input")
        uploaded_name = self._uploaded_name(upload)
        workflow, scale_multiplier = self._prepare_workflow(
            metadata,
            uploaded_name,
            output_prefix=f"lfo/{metadata.get('run_id', 'run')}/{task_id}/{attempt_id}/upscaled",
        )
        client_id = f"lfo-{uuid.uuid4().hex}"
        submitted = self.client.submit_prompt(workflow, client_id=client_id)
        prompt_id = submitted.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise LfoComfyError("ComfyUI response did not include prompt_id")

        status = self.monitor.poll_until_done(
            prompt_id,
            interval=self.config.poll_interval_seconds,
            timeout=self.config.timeout_seconds,
        )
        if status.get("status") == "timeout":
            return HandlerResult(
                success=False,
                error=f"ComfyUI prompt {prompt_id} timed out",
                retryable=True,
                artifact_metadata={"provider_job_id": prompt_id},
            )
        if not status.get("completed"):
            return HandlerResult(
                success=False,
                error=(
                    f"ComfyUI prompt {prompt_id} failed: "
                    f"{status.get('error') or status.get('status')}"
                ),
                retryable=False,
                artifact_metadata={"provider_job_id": prompt_id},
            )

        output = self._find_output(prompt_id, status)
        managed = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
        managed_hash, managed_size = atomic_copy_verified(output, managed)
        return HandlerResult(
            success=True,
            artifact_type="video",
            artifact_metadata={
                "file_path": str(managed.resolve()),
                "file_hash": managed_hash,
                "media_type": "video",
                "provider_job_id": prompt_id,
                "workflow_id": SEEDVR2_UPSCALE_WORKFLOW_ID,
                "source_video_path": str(source_video),
                "uploaded_source": uploaded_name,
                "scale_multiplier": scale_multiplier,
                "size": managed_size,
                "provider_source_path": str(output),
                "provider_file_hash": _sha256_file(output),
            },
        )

    def _execute_segmented(
        self,
        task_id: str,
        logical_key: str,
        metadata: dict[str, Any],
        attempt_id: str,
        source_video: pathlib.Path,
        segment_seconds: float,
    ) -> HandlerResult:
        """Upscale short sequential segments and concatenate them for the clip."""
        final_path = managed_path(metadata.get("output_path"), metadata.get("artifact_layout"))
        duration_ms = int(probe(source_video)["duration_ms"] or 0)
        ranges = self._segment_ranges(duration_ms, segment_seconds)
        if len(ranges) <= 1:
            return self._execute_single(task_id, logical_key, metadata, attempt_id, source_video)

        segment_root = final_path.parent / f".{final_path.stem}.segments-{attempt_id}"
        segment_root.mkdir(parents=True, exist_ok=True)
        source_hash = _sha256_file(source_video)
        manifest_path = segment_root / "segments.json"
        manifest = {
            "source_hash": source_hash,
            "duration_ms": duration_ms,
            "segment_seconds": segment_seconds,
            "ranges": [[start, end] for start, end in ranges],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        upscaled_segments: list[ClipSegment] = []
        provider_jobs: list[str] = []
        segment_reports: list[dict[str, Any]] = []
        scale_multiplier: float | None = None
        configured_scale = metadata.get("upscale", {})
        if isinstance(configured_scale, dict):
            configured_multiplier = configured_scale.get("scale_multiplier")
            if isinstance(configured_multiplier, (int, float)):
                scale_multiplier = float(configured_multiplier)

        self._report_progress(
            task_id,
            logical_key,
            status="running",
            segment_index=0,
            segment_count=len(ranges),
            completed_segments=0,
        )

        for index, (start_ms, end_ms) in enumerate(ranges, start=1):
            segment_source = segment_root / f"segment-{index:03d}.mp4"
            segment_output = segment_root / f"segment-{index:03d}.upscaled.mp4"
            expected_duration_ms = end_ms - start_ms
            reused = self._reuse_segment_if_valid(
                segment_root,
                segment_output,
                source_hash,
                duration_ms,
                segment_seconds,
                ranges,
                index,
                expected_duration_ms,
            )
            if reused:
                segment_probe = reused
                provider_jobs.append("reused")
                self._report_progress(
                    task_id,
                    logical_key,
                    status="reused",
                    segment_index=index,
                    segment_count=len(ranges),
                    completed_segments=index,
                )
            else:
                self._report_progress(
                    task_id,
                    logical_key,
                    status="processing",
                    segment_index=index,
                    segment_count=len(ranges),
                    completed_segments=index - 1,
                )
                if not self._is_valid_media(segment_source, expected_duration_ms):
                    self._extract_segment(
                        source_video,
                        segment_source,
                        start_ms / 1000.0,
                        (end_ms - start_ms) / 1000.0,
                    )
                self._require_valid_media(segment_source, expected_duration_ms, "source segment")
                segment_metadata = dict(metadata)
                segment_metadata["input_task_ids"] = ["segment-source"]
                segment_metadata["input_artifacts"] = {
                    "segment-source": {"file_path": str(segment_source.resolve())}
                }
                segment_metadata["output_path"] = str(segment_output)
                result = self._execute_single(
                    f"{task_id}.segment-{index:03d}",
                    f"{logical_key}:segment-{index:03d}",
                    segment_metadata,
                    f"{attempt_id}-segment-{index:03d}",
                    segment_source,
                )
                if not result.success:
                    return result
                provider_job = result.artifact_metadata.get("provider_job_id")
                if isinstance(provider_job, str):
                    provider_jobs.append(provider_job)
                multiplier = result.artifact_metadata.get("scale_multiplier")
                if isinstance(multiplier, (int, float)):
                    scale_multiplier = float(multiplier)
                segment_probe = self._require_valid_media(
                    segment_output, expected_duration_ms, "upscaled segment"
                )
                self._report_progress(
                    task_id,
                    logical_key,
                    status="completed",
                    segment_index=index,
                    segment_count=len(ranges),
                    completed_segments=index,
                )
            upscaled_segments.append(
                ClipSegment(
                    clip_id=f"{task_id}.segment-{index:03d}",
                    file_path=str(segment_output),
                    duration_ms=int(segment_probe["duration_ms"] or expected_duration_ms),
                )
            )
            segment_reports.append(
                {
                    "index": index,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reused": reused is not None,
                    "file_path": str(segment_output),
                    "probe": segment_probe,
                }
            )

        self._report_progress(
            task_id,
            logical_key,
            status="assembling",
            segment_index=len(ranges),
            segment_count=len(ranges),
            completed_segments=len(ranges),
        )
        assembled_temp = final_path.with_name(
            f".{final_path.stem}.{uuid.uuid4().hex}.tmp{final_path.suffix}"
        )
        timeline = TimelineAssembler().assemble(
            TimelineSpec(segments=upscaled_segments, transitions="cut", output_path=str(assembled_temp)),
            timeout_s=self.config.timeout_seconds,
        )
        if not timeline.success or not assembled_temp.is_file():
            assembled_temp.unlink(missing_ok=True)
            raise MediaCommandError(timeline.error or "Segmented upscale concatenation failed")
        atomic_replace(assembled_temp, final_path)
        final_probe = self._require_valid_media(final_path, duration_ms, "assembled upscale")
        final_hash = _sha256_file(final_path)
        self._report_progress(
            task_id,
            logical_key,
            status="completed",
            segment_index=len(ranges),
            segment_count=len(ranges),
            completed_segments=len(ranges),
        )
        return HandlerResult(
            success=True,
            artifact_type="video",
            artifact_metadata={
                "file_path": str(final_path.resolve()),
                "file_hash": final_hash,
                "media_type": "video",
                "provider_job_id": "segmented:" + ",".join(provider_jobs),
                "workflow_id": SEEDVR2_UPSCALE_WORKFLOW_ID,
                "source_video_path": str(source_video),
                "scale_multiplier": scale_multiplier,
                "size": final_path.stat().st_size,
                "segmented": True,
                "segment_seconds": segment_seconds,
                "segment_count": len(upscaled_segments),
                "segment_root": str(segment_root),
                "segments": segment_reports,
                "probe": final_probe,
            },
        )

    @staticmethod
    def _segment_seconds(metadata: dict[str, Any]) -> float | None:
        config = metadata.get("upscale")
        if not isinstance(config, dict):
            return DEFAULT_SEGMENT_SECONDS
        if "segment_seconds" not in config:
            return DEFAULT_SEGMENT_SECONDS
        value = config["segment_seconds"]
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("video.upscale metadata.upscale.segment_seconds must be positive")
        return float(value)

    def _reuse_segment_if_valid(
        self,
        current_root: pathlib.Path,
        current_output: pathlib.Path,
        source_hash: str,
        duration_ms: int,
        segment_seconds: float,
        ranges: list[tuple[int, int]],
        index: int,
        expected_duration_ms: int,
    ) -> dict[str, Any] | None:
        roots = [current_root]
        prefix = current_root.name.rsplit("segments-", 1)[0] + "segments-"
        roots.extend(
            sorted(
                (
                    path
                    for path in current_root.parent.glob(f"{prefix}*")
                    if path.is_dir() and path != current_root
                ),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
        for root in roots:
            manifest_path = root / "segments.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            try:
                manifest_segment_seconds = float(manifest.get("segment_seconds", 0))
            except (TypeError, ValueError):
                continue
            if (
                manifest.get("source_hash") != source_hash
                or manifest.get("duration_ms") != duration_ms
                or manifest_segment_seconds != segment_seconds
                or manifest.get("ranges") != [[start, end] for start, end in ranges]
            ):
                continue
            candidate = root / f"segment-{index:03d}.upscaled.mp4"
            if not self._is_valid_media(candidate, expected_duration_ms):
                continue
            if candidate != current_output:
                atomic_copy_verified(candidate, current_output)
            return probe(current_output)
        return None

    @staticmethod
    def _is_valid_media(path: pathlib.Path, expected_duration_ms: int | None = None) -> bool:
        try:
            details = probe(path)
        except (MediaCommandError, OSError, ValueError, TypeError):
            return False
        duration_ms = int(details.get("duration_ms") or 0)
        if not details.get("width") or not details.get("height") or not details.get("codec"):
            return False
        if expected_duration_ms is not None:
            tolerance = max(250, round(expected_duration_ms * 0.08))
            if abs(duration_ms - expected_duration_ms) > tolerance:
                return False
        return duration_ms > 0

    @classmethod
    def _require_valid_media(
        cls,
        path: pathlib.Path,
        expected_duration_ms: int | None,
        label: str,
    ) -> dict[str, Any]:
        if not cls._is_valid_media(path, expected_duration_ms):
            raise MediaCommandError(f"{label} failed media validation: {path}")
        return probe(path)

    def _report_progress(
        self,
        task_id: str,
        logical_key: str,
        **progress: Any,
    ) -> None:
        if self.progress_callback is None:
            return
        event = {"task_id": task_id, "logical_key": logical_key, **progress}
        try:
            self.progress_callback(event)
        except Exception as exc:  # progress must never fail media execution
            logger.warning("Unable to persist upscale progress: %s", exc)

    @staticmethod
    def _segment_ranges(duration_ms: int, segment_seconds: float) -> list[tuple[int, int]]:
        if duration_ms <= 0:
            raise ValueError("video.upscale segmented source has no duration")
        step_ms = max(1, round(segment_seconds * 1000))
        ranges = [
            (start, min(start + step_ms, duration_ms))
            for start in range(0, duration_ms, step_ms)
        ]
        if len(ranges) > 1 and ranges[-1][1] - ranges[-1][0] < 250:
            ranges[-2] = (ranges[-2][0], ranges[-1][1])
            ranges.pop()
        return ranges

    @staticmethod
    def _extract_segment(
        source: pathlib.Path,
        destination: pathlib.Path,
        start_seconds: float,
        duration_seconds: float,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                "ffmpeg", "-y", "-ss", f"{start_seconds:.3f}", "-i", str(source),
                "-t", f"{duration_seconds:.3f}", "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100",
                "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
                str(destination),
            ],
            timeout_s=300.0,
        )

    def _prepare_workflow(
        self,
        metadata: dict[str, Any],
        uploaded_name: str,
        *,
        output_prefix: str,
    ) -> tuple[dict[str, Any], float]:
        config = metadata.get("upscale", {})
        options = resolve_upscale_options({"upscale": config}, {})
        if not options.enabled:
            raise ValueError("video.upscale metadata.upscale.enabled must be true")

        manifest = KNOWN_WORKFLOWS[SEEDVR2_UPSCALE_WORKFLOW_ID]
        workflow = WorkflowLoader.load(self.config.workflow_dir / manifest.source_file)
        bindings = self._resolve_bindings(workflow, manifest)
        values: dict[str, Any] = {
            "input_video": uploaded_name,
            "scale_multiplier": options.scale_multiplier,
            "filename_prefix": output_prefix.replace("\\", "/"),
        }
        if options.seed is not None:
            values["seed"] = options.seed
        resolved_values = [
            (bindings[key], value) for key, value in values.items() if key in bindings
        ]
        return BindingResolver(workflow).apply_values(resolved_values), options.scale_multiplier

    @staticmethod
    def _resolve_bindings(
        workflow: dict[str, Any],
        manifest: WorkflowManifest,
    ) -> dict[str, Binding]:
        resolver = BindingResolver(workflow)
        resolved: dict[str, Binding] = {}
        for slot in manifest.input_slots:
            binding = Binding(
                binding_id=slot.binding_id,
                selector_title=slot.selector_title,
                selector_class_type=slot.selector_class_type,
                input_name=slot.input_name,
            )
            resolved[slot.binding_id] = resolver.resolve_binding(binding, mode="strict")
        return resolved

    @staticmethod
    def _source_video_path(metadata: dict[str, Any]) -> pathlib.Path:
        input_artifacts = metadata.get("input_artifacts")
        if not isinstance(input_artifacts, dict) or not input_artifacts:
            raise ValueError("video.upscale requires one upstream video artifact")
        input_task_ids = metadata.get("input_task_ids")
        artifact_ids = input_task_ids if isinstance(input_task_ids, list) else list(input_artifacts)
        candidates: list[pathlib.Path] = []
        for source_task_id in artifact_ids:
            artifact = input_artifacts.get(source_task_id)
            if not isinstance(artifact, dict):
                continue
            file_path = artifact.get("file_path")
            if isinstance(file_path, str) and file_path:
                candidates.append(pathlib.Path(file_path).resolve())
        if len(candidates) != 1:
            raise ValueError("video.upscale requires exactly one upstream video artifact")
        source = candidates[0]
        if not source.is_file():
            raise FileNotFoundError(f"Upstream video artifact not found: {source}")
        return source

    @staticmethod
    def _uploaded_name(upload: object) -> str:
        if not isinstance(upload, dict):
            raise TypeError("ComfyUI upload response must be an object")
        name = upload.get("name")
        subfolder = upload.get("subfolder", "")
        if not isinstance(name, str) or not name:
            raise ValueError("ComfyUI upload response did not include a file name")
        if not isinstance(subfolder, str):
            raise TypeError("ComfyUI upload response subfolder must be a string")
        return f"{subfolder.rstrip('/')}/{name}" if subfolder else name

    def _find_output(self, prompt_id: str, status: dict[str, Any]) -> pathlib.Path:
        outputs = status.get("outputs")
        if not isinstance(outputs, dict) or not outputs:
            history = self.client.get_history(prompt_id)
            entry = history.get(prompt_id, {})
            outputs = entry.get("outputs", {}) if isinstance(entry, dict) else {}

        candidates: list[pathlib.Path] = []
        for node_output in outputs.values() if isinstance(outputs, dict) else []:
            if not isinstance(node_output, dict):
                continue
            for collection in ("video", "videos", "images", "gifs"):
                items = node_output.get(collection, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not isinstance(filename, str) or not filename:
                        continue
                    subfolder = item.get("subfolder", "")
                    path = self.config.output_root / str(subfolder) / filename
                    if path.is_file():
                        candidates.append(path.resolve())
        if not candidates:
            raise FileNotFoundError(f"No local output found for ComfyUI prompt {prompt_id}")
        videos = [
            path for path in candidates
            if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
        ]
        return max(videos or candidates, key=lambda path: path.stat().st_mtime_ns)


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
