"""Materializer — convert an approved Package into an immutable Run Snapshot.

Materialization is deterministic: the same inputs always produce the same
snapshot hash. Any change that affects output changes the hash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from lfo.backends.registry import BackendRegistry
from lfo.backends.selector import SelectionFailure, select_backend
from lfo.contracts.package import VideoExecutionPackage
from lfo.contracts.timeline import TimelineSpec


@dataclass
class MaterializedClip:
    """A clip with its backend selection and resolved references."""

    clip_id: str
    sequence: int
    duration_ms: int
    operation: str
    prompt: str
    negative_prompt: str | None
    seed: int | None
    backend_id: str
    backend_revision: str
    workflow_hash: str
    # Resolved references: list of (reference_id, asset_revision_id, slot)
    resolved_references: list[dict[str, Any]] = field(default_factory=list)
    # References that were dropped (optional, beyond backend max)
    dropped_references: list[dict[str, Any]] = field(default_factory=list)
    # Requirements snapshot
    aspect_ratio: str | None = None
    megapixels: float | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    native_audio: str | None = None
    reference_image_size: str | None = None
    # Dependencies on other clip_ids
    dependencies: list[str] = field(default_factory=list)
    # Media types consumed
    input_media_types: list[str] = field(default_factory=list)
    audio_policy: dict[str, Any] = field(default_factory=dict)
    subtitles: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterializedRun:
    """Immutable snapshot of a ready-to-execute run."""

    run_id: str
    package_id: str
    package_revision: int
    package_hash: str
    materialization_hash: str
    clips: list[MaterializedClip] = field(default_factory=list)
    timeline: TimelineSpec = field(default_factory=TimelineSpec)
    # Asset key -> asset revision id mapping
    asset_resolutions: dict[str, Any] = field(default_factory=dict)
    output_policy: dict[str, Any] = field(default_factory=dict)
    artifact_layout: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterializationError(Exception):
    """Raised when materialization fails."""

    message: str
    details: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return "; ".join([self.message, *self.details])


def _compute_hash(data: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of a dict."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _asset_media_type(
    asset_key: str,
    package: VideoExecutionPackage,
) -> str | None:
    """Look up the media_type of an asset by key."""
    for a in package.assets:
        if a.asset_key == asset_key:
            return a.media_type
    return None


def _asset_revision_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("asset_revision_id") or value.get("revision_id")
        return candidate if isinstance(candidate, str) else None
    return None


def _asset_path(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("file_path", "blob_path", "local_path"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _ordered_references(clip: Any) -> list[Any]:
    """Return references in a deterministic backend binding order.

    ``first`` and ``last`` carry an observable slot constraint; otherwise
    higher-priority references win when a backend has fewer inputs available.
    Fixed slots are retained by their declared slot name and sorted with their
    placement group to avoid relying on incoming JSON array order.
    """
    placement_order = {"first": 0, "fixed": 1, "any": 2, "last": 3}
    return sorted(
        clip.generation.references,
        key=lambda ref: (
            placement_order.get(ref.binding.placement, 2),
            -ref.binding.priority,
            ref.binding.slot or "",
            ref.reference_id,
        ),
    )


def _bind_references(
    clip: Any,
    package: VideoExecutionPackage,
    asset_resolutions: dict[str, Any],
    max_references: int,
    accepted_media_types: list[str],
) -> tuple[list[Any], list[dict[str, Any]], list[str]]:
    """Resolve, validate and trim references for one specific backend.

    Required references are never silently discarded. Optional references are
    dropped only when their policy explicitly permits it; otherwise that
    backend is not eligible. The return order is the concrete slot order.
    """
    kept: list[Any] = []
    dropped: list[dict[str, Any]] = []
    failures: list[str] = []
    for ref in _ordered_references(clip):
        media_type = _asset_media_type(ref.asset_key, package)
        if media_type is None:
            failures.append(f"{ref.reference_id}: unknown asset {ref.asset_key!r}")
            continue
        if ref.binding.required and not _asset_revision_id(asset_resolutions.get(ref.asset_key)):
            failures.append(f"{ref.reference_id}: required asset {ref.asset_key!r} has no imported revision")
            continue
        if media_type not in accepted_media_types:
            if not ref.binding.required and ref.binding.on_unsupported == "drop":
                dropped.append(_dropped_ref(ref, "unsupported_media_type"))
                continue
            failures.append(f"{ref.reference_id}: backend does not accept {media_type}")
            continue
        kept.append(ref)

    required_count = sum(ref.binding.required for ref in kept)
    if required_count > max_references:
        failures.append(f"{required_count} required references exceed backend maximum {max_references}")
        return kept, dropped, failures

    if len(kept) > max_references:
        # Drop only optional references that explicitly allow it, lowest
        # priority first. Required and optional-on-fail remain binding.
        optional = sorted(
            (ref for ref in kept if not ref.binding.required),
            key=lambda ref: (ref.binding.priority, ref.reference_id),
        )
        for ref in optional:
            if len(kept) <= max_references:
                break
            if ref.binding.on_unsupported != "drop":
                continue
            kept.remove(ref)
            dropped.append(_dropped_ref(ref, "max_references"))
        if len(kept) > max_references:
            failures.append(
                f"{len(kept)} references exceed backend maximum {max_references}; remaining optional references require fail"
            )
    return kept, dropped, failures


def _dropped_ref(ref: Any, reason: str) -> dict[str, Any]:
    return {
        "reference_id": ref.reference_id,
        "asset_key": ref.asset_key,
        "semantic_usage": ref.semantic_usage,
        "reason": reason,
        "priority": ref.binding.priority,
        "placement": ref.binding.placement,
    }


def materialize(
    run_id: str,
    package: VideoExecutionPackage,
    package_hash: str,
    registry: BackendRegistry,
    asset_resolutions: dict[str, Any] | None = None,
    preferred_backends: list[tuple[str, str]] | None = None,
    artifact_layout: dict[str, Any] | None = None,
) -> MaterializedRun:
    """Materialize a Package into an immutable Run snapshot.

    Args:
        run_id: Unique identifier for this run.
        package: The validated VideoExecutionPackage.
        package_hash: Canonical hash of the package content.
        registry: Backend registry for capability selection.
        asset_resolutions: Mapping of asset_key -> internal asset_revision_id.
        preferred_backends: Ordered list of (backend_id, revision) preferences.

    Returns:
        MaterializedRun with deterministic hash.

    Raises:
        MaterializationError if any clip cannot be satisfied.
    """
    asset_resolutions = asset_resolutions or {}
    clip_durations = {clip.clip_id: clip.duration_ms for clip in package.clips}
    timeline = package.timeline
    if not timeline.segments:
        timeline = TimelineSpec.for_clips(package.clips)
    timeline.validate(clip_durations)
    clips_materialized: list[MaterializedClip] = []
    all_warnings: list[str] = []
    all_rejections: list[str] = []

    for clip in package.clips:
        for track in clip.audio.tracks:
            resolved_track = asset_resolutions.get(track.asset_key)
            if not _asset_revision_id(resolved_track) or not _asset_path(resolved_track):
                raise MaterializationError(
                    message=f"Cannot materialize clip {clip.clip_id}: unresolved audio asset",
                    details=[f"Audio asset {track.asset_key!r} has no imported revision/path"],
                )
        if clip.subtitles.asset_key is not None:
            resolved_subtitle = asset_resolutions.get(clip.subtitles.asset_key)
            if not _asset_revision_id(resolved_subtitle) or not _asset_path(resolved_subtitle):
                raise MaterializationError(
                    message=f"Cannot materialize clip {clip.clip_id}: unresolved subtitle asset",
                    details=[
                        f"Subtitle asset {clip.subtitles.asset_key!r} has no imported revision/path"
                    ],
                )
        # Build requirements dict
        req = clip.generation.requirements
        requirements: dict[str, Any] = {}
        requirements["duration_ms"] = clip.duration_ms
        if req.width is not None:
            requirements["width"] = req.width
        if req.height is not None:
            requirements["height"] = req.height
        if req.megapixels is not None:
            requirements["megapixels"] = req.megapixels
        if req.fps is not None:
            requirements["fps"] = req.fps
        if req.native_audio is not None:
            requirements["native_audio"] = req.native_audio
        if req.reference_image_size is not None:
            requirements["reference_image_size"] = req.reference_image_size
        if clip.generation.seed is not None:
            requirements["seed"] = clip.generation.seed
        if req.aspect_ratio is not None:
            requirements["aspect_ratio"] = req.aspect_ratio

        # The binding policy changes feasibility, so selection is evaluated per
        # candidate rather than selecting on a raw untrimmed reference count.
        candidates: list[tuple[int, Any, list[Any], list[dict[str, Any]]]] = []
        candidate_errors: list[str] = []
        for rank, cap in enumerate(registry.query_by_operation(clip.generation.operation)):
            kept, dropped_refs, binding_errors = _bind_references(
                clip, package, asset_resolutions, cap.max_references, cap.accepted_media_types,
            )
            if binding_errors:
                candidate_errors.extend(f"{cap.backend_id}@{cap.revision}: {error}" for error in binding_errors)
                continue
            candidate_registry = BackendRegistry()
            candidate_registry.register(cap)
            try:
                kept_media_types = [
                    media_type
                    for ref in kept
                    if isinstance((media_type := _asset_media_type(ref.asset_key, package)), str)
                ]
                selection = select_backend(
                    operation=clip.generation.operation,
                    requirements=requirements,
                    registry=candidate_registry,
                    media_types=kept_media_types,
                    reference_count=len(kept),
                    preferred_backends=preferred_backends,
                )
            except SelectionFailure as error:
                candidate_errors.extend(error.reasons_formatted())
                continue
            preferred_rank = len(preferred_backends or [])
            if preferred_backends:
                for index, preferred in enumerate(preferred_backends):
                    if preferred == (cap.backend_id, cap.revision):
                        preferred_rank = index
                        break
            candidates.append((preferred_rank * 10_000 + rank, selection, kept, dropped_refs))

        if not candidates:
            details = candidate_errors or ["No registered backend supports the requested operation"]
            all_rejections.extend(details)
            raise MaterializationError(
                message=f"Cannot materialize clip {clip.clip_id}: no suitable backend", details=details
            )
        _, sel, kept_refs, dropped_refs = min(candidates, key=lambda candidate: candidate[0])
        if dropped_refs:
            all_warnings.append(f"Clip {clip.clip_id}: dropped {len(dropped_refs)} optional references")

        resolved_refs: list[dict[str, Any]] = []
        for index, ref in enumerate(kept_refs):
            asset_value = asset_resolutions.get(ref.asset_key)
            asset_rev = _asset_revision_id(asset_value)
            resolved_refs.append({
                "reference_id": ref.reference_id,
                "asset_key": ref.asset_key,
                "asset_revision_id": asset_rev,
                "file_path": _asset_path(asset_value),
                "media_type": _asset_media_type(ref.asset_key, package),
                "semantic_usage": ref.semantic_usage,
                "slot": ref.binding.slot or str(index),
                "required": ref.binding.required,
                "placement": ref.binding.placement,
                "on_unsupported": ref.binding.on_unsupported,
            })

        audio_policy = clip.audio.to_dict()
        audio_tracks = audio_policy.get("tracks", [])
        if isinstance(audio_tracks, list):
            for track in audio_tracks:
                if isinstance(track, dict):
                    track_asset_key = track.get("asset_key")
                    track["file_path"] = _asset_path(
                        asset_resolutions.get(track_asset_key)
                        if isinstance(track_asset_key, str)
                        else None
                    )
        subtitles = clip.subtitles.to_dict()
        subtitle_asset_key = subtitles.get("asset_key")
        if isinstance(subtitle_asset_key, str):
            subtitles["file_path"] = _asset_path(asset_resolutions.get(subtitle_asset_key))

        mat_clip = MaterializedClip(
            clip_id=clip.clip_id,
            sequence=clip.sequence,
            duration_ms=clip.duration_ms,
            operation=clip.generation.operation,
            prompt=clip.generation.prompt,
            negative_prompt=clip.generation.negative_prompt,
            seed=clip.generation.seed,
            backend_id=sel.backend_id,
            backend_revision=sel.revision,
            workflow_hash=sel.workflow_hash,
            resolved_references=resolved_refs,
            dropped_references=dropped_refs,
            aspect_ratio=req.aspect_ratio,
            megapixels=req.megapixels,
            width=req.width,
            height=req.height,
            fps=req.fps,
            native_audio=req.native_audio,
            reference_image_size=req.reference_image_size,
            dependencies=list(clip.dependencies),
            input_media_types=[
                media_type
                for ref in kept_refs
                if isinstance((media_type := _asset_media_type(ref.asset_key, package)), str)
            ],
            audio_policy=audio_policy,
            subtitles=subtitles,
            source_context=dict(clip.source_context),
            extensions=dict(clip.extensions),
        )
        clips_materialized.append(mat_clip)

    # Build the snapshot for hashing
    snapshot_data = {
        "package_id": package.package_id,
        "package_revision": package.revision,
        "package_hash": package_hash,
        "clips": [_clip_to_dict(c) for c in clips_materialized],
        "timeline": timeline.to_dict(),
        "asset_resolutions": dict(asset_resolutions),
        "output_policy": package.output.to_dict(),
        # The lock and audio/prompt contracts are part of the immutable
        # execution snapshot. Prompt revisions are task-level audit events;
        # they do not mutate this snapshot or require storyboard re-layout.
        "extensions": dict(package.extensions),
        "artifact_layout": _layout_hash_payload(artifact_layout or {}),
    }
    mat_hash = _compute_hash(snapshot_data)

    return MaterializedRun(
        run_id=run_id,
        package_id=package.package_id,
        package_revision=package.revision,
        package_hash=package_hash,
        materialization_hash=mat_hash,
        clips=clips_materialized,
        timeline=timeline,
        asset_resolutions=dict(asset_resolutions),
        output_policy=package.output.to_dict(),
        artifact_layout=dict(artifact_layout or {}),
        warnings=all_warnings,
        extensions=dict(package.extensions),
    )


def _clip_to_dict(clip: MaterializedClip) -> dict[str, Any]:
    """Serialize a MaterializedClip to a dict for hashing."""
    return {
        "clip_id": clip.clip_id,
        "sequence": clip.sequence,
        "duration_ms": clip.duration_ms,
        "operation": clip.operation,
        "prompt": clip.prompt,
        "negative_prompt": clip.negative_prompt,
        "seed": clip.seed,
        "backend_id": clip.backend_id,
        "backend_revision": clip.backend_revision,
        "workflow_hash": clip.workflow_hash,
        "resolved_references": clip.resolved_references,
        "dropped_references": clip.dropped_references,
        "aspect_ratio": clip.aspect_ratio,
        "megapixels": clip.megapixels,
        "width": clip.width,
        "height": clip.height,
        "fps": clip.fps,
        "native_audio": clip.native_audio,
        "reference_image_size": clip.reference_image_size,
        "dependencies": clip.dependencies,
        "input_media_types": clip.input_media_types,
        "audio_policy": clip.audio_policy,
        "subtitles": clip.subtitles,
        "source_context": clip.source_context,
        "extensions": clip.extensions,
    }


def _layout_hash_payload(layout: dict[str, Any]) -> dict[str, Any]:
    """Keep filesystem realization out of the content-derived snapshot hash."""
    keys = (
        "layout_version",
        "project_id",
        "package_id",
        "package_revision",
        "publication_directory",
        "container",
    )
    return {key: layout[key] for key in keys if key in layout}
