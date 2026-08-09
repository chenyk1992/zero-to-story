"""Materializer — convert an approved Package into an immutable Run Snapshot.

Materialization is deterministic: the same inputs always produce the same
snapshot hash. Any change that affects output changes the hash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.backends.selector import select_backend, SelectionFailure
from lfo.contracts.clips import ClipSpec
from lfo.contracts.package import VideoExecutionPackage


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
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    native_audio: str | None = None
    # Dependencies on other clip_ids
    dependencies: list[str] = field(default_factory=list)
    # Media types consumed
    input_media_types: list[str] = field(default_factory=list)
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
    # Asset key -> asset revision id mapping
    asset_resolutions: dict[str, str] = field(default_factory=dict)
    output_policy: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterializationError(Exception):
    """Raised when materialization fails."""

    message: str
    details: list[str] = field(default_factory=list)


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


def materialize(
    run_id: str,
    package: VideoExecutionPackage,
    package_hash: str,
    registry: BackendRegistry,
    asset_resolutions: dict[str, str] | None = None,
    preferred_backends: list[tuple[str, str]] | None = None,
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
    clips_materialized: list[MaterializedClip] = []
    all_warnings: list[str] = []
    all_rejections: list[str] = []

    for clip in package.clips:
        # Collect media types from references
        ref_media_types: list[str] = []
        for ref in clip.generation.references:
            mt = _asset_media_type(ref.asset_key, package)
            if mt:
                ref_media_types.append(mt)

        # Build requirements dict
        req = clip.generation.requirements
        requirements: dict[str, Any] = {}
        requirements["duration_ms"] = clip.duration_ms
        if req.width is not None:
            requirements["width"] = req.width
        if req.height is not None:
            requirements["height"] = req.height
        if req.fps is not None:
            requirements["fps"] = req.fps
        if req.native_audio is not None:
            requirements["native_audio"] = req.native_audio

        # Select backend
        try:
            sel = select_backend(
                operation=clip.generation.operation,
                requirements=requirements,
                registry=registry,
                media_types=ref_media_types if ref_media_types else None,
                reference_count=len(clip.generation.references),
                preferred_backends=preferred_backends,
            )
        except SelectionFailure as e:
            all_rejections.extend(e.reasons_formatted())
            raise MaterializationError(
                message=f"Cannot materialize clip {clip.clip_id}: no suitable backend",
                details=e.reasons_formatted(),
            )

        if sel.dropped_references:
            all_warnings.append(
                f"Clip {clip.clip_id}: dropped {len(sel.dropped_references)} optional references"
            )

        if sel.rejections:
            for r in sel.rejections:
                all_warnings.append(
                    f"Clip {clip.clip_id}: rejected {r.backend_id}@{r.revision}: {r.reason}"
                )

        # Resolve references to asset revisions
        resolved_refs: list[dict[str, Any]] = []
        dropped_refs: list[dict[str, Any]] = []
        for i, ref in enumerate(clip.generation.references):
            if i >= sel.dropped_references.__len__() + len([
                r for r in clip.generation.references
                if r.binding.required
            ]):
                # This reference was dropped during selection
                pass
            asset_rev = asset_resolutions.get(ref.asset_key)
            resolved_refs.append({
                "reference_id": ref.reference_id,
                "asset_key": ref.asset_key,
                "asset_revision_id": asset_rev,
                "semantic_usage": ref.semantic_usage,
                "slot": ref.binding.slot,
                "required": ref.binding.required,
                "placement": ref.binding.placement,
            })

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
            width=req.width,
            height=req.height,
            fps=req.fps,
            native_audio=req.native_audio,
            dependencies=list(clip.dependencies),
            input_media_types=ref_media_types,
            extensions=dict(clip.extensions),
        )
        clips_materialized.append(mat_clip)

    # Build the snapshot for hashing
    snapshot_data = {
        "package_id": package.package_id,
        "package_revision": package.revision,
        "package_hash": package_hash,
        "clips": [_clip_to_dict(c) for c in clips_materialized],
        "asset_resolutions": dict(asset_resolutions),
        "output_policy": package.output.to_dict(),
    }
    mat_hash = _compute_hash(snapshot_data)

    return MaterializedRun(
        run_id=run_id,
        package_id=package.package_id,
        package_revision=package.revision,
        package_hash=package_hash,
        materialization_hash=mat_hash,
        clips=clips_materialized,
        asset_resolutions=dict(asset_resolutions),
        output_policy=package.output.to_dict(),
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
        "width": clip.width,
        "height": clip.height,
        "fps": clip.fps,
        "native_audio": clip.native_audio,
        "dependencies": clip.dependencies,
        "input_media_types": clip.input_media_types,
        "extensions": clip.extensions,
    }
