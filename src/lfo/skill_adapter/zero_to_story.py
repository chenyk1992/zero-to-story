"""Adapt approved zero-to-story creative output to ``VideoExecutionPackage``.

The only accepted input is a Panel-first creative document.  A production
package contains one approved Panel/Clip; multi-clip packages are reserved for
the separate passthrough assembly adapter.
"""
from __future__ import annotations

import math
from typing import Any

from lfo.contracts.assets import AssetSource, AssetSpec, ProvenanceSpec, ReviewDeclaration
from lfo.contracts.builder import VideoPackageBuilder
from lfo.contracts.clips import (
    AudioPolicy,
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    ReferenceSpec,
    SubtitleSpec,
)
from lfo.contracts.operations import validate_operation_references
from lfo.contracts.package import ApprovalDeclaration, VideoExecutionPackage
from lfo.contracts.timeline import OutputPolicy


def _aspect_from_pixels(width: object, height: object) -> str | None:
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        return None
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        return None
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _canvas_requirements(data: dict[str, Any], path: str) -> GenerationRequirements:
    """H3 generation uses aspect_ratio + megapixels, never pixel width/height."""
    payload = dict(data)
    width = payload.pop("width", None)
    height = payload.pop("height", None)
    aspect = payload.get("aspect_ratio")
    if not isinstance(aspect, str) or not aspect.strip():
        payload["aspect_ratio"] = _aspect_from_pixels(width, height) or "16:9"
    return GenerationRequirements.from_dict(payload, path)


def _asset_spec(data: dict[str, Any]) -> AssetSpec:
    """Accept a public AssetSpec dict or concise Skill asset declaration."""
    if not isinstance(data, dict):
        raise ValueError("assets[] must be an object")
    # ``asset_id``/``external_asset_id`` belong to the creative handoff.  They
    # are useful for resolving Panel references but are deliberately not part
    # of the public AssetSpec object.
    public_data = dict(data)
    public_data.pop("asset_id", None)
    public_data.pop("external_asset_id", None)
    if "source" in public_data and "provenance" in public_data:
        return AssetSpec.from_dict(public_data, "$.assets[]")
    asset_key = data.get("asset_key")
    if not isinstance(asset_key, str) or not asset_key:
        raise ValueError("assets[].asset_key must be a non-empty string")
    uri = data.get("uri", data.get("path", ""))
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError(f"assets[{asset_key!r}].uri must be a non-empty string")
    sha256 = data.get("sha256")
    if sha256 is not None and not isinstance(sha256, str):
        raise TypeError(f"assets[{asset_key!r}].sha256 must be a string when provided")
    review_required = data.get("review_required", True)
    if not isinstance(review_required, bool):
        raise TypeError(f"assets[{asset_key!r}].review_required must be a boolean")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TypeError(f"assets[{asset_key!r}].metadata must be an object")
    return AssetSpec(
        asset_key=asset_key,
        media_type=data.get("media_type", "image"),
        source=AssetSource(uri=uri, sha256=sha256),
        provenance=ProvenanceSpec(
            source_type=data.get("source_type", "external_skill"),
            producer=data.get("producer", "zero-to-story"),
            operation=data.get("operation", "image.generate"),
            producer_version=data.get("producer_version"),
            source_asset_keys=list(data.get("source_asset_keys", [])),
            prompt_hash=data.get("prompt_hash"),
        ),
        review=ReviewDeclaration(required=review_required),
        metadata=dict(metadata),
    )


def _asset_id_index(assets: list[dict[str, Any]]) -> dict[str, str]:
    """Resolve creator-facing asset IDs without leaking them to LFO."""
    index: dict[str, str] = {}
    seen_keys: set[str] = set()
    for position, asset in enumerate(assets):
        if not isinstance(asset, dict):
            raise ValueError(f"assets[{position}] must be an object")
        key = asset.get("asset_key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"assets[{position}].asset_key must be a non-empty string")
        if key in seen_keys or key in index:
            raise ValueError(f"duplicate asset identifier {key!r}")
        index[key] = key
        seen_keys.add(key)
        for field in ("asset_id", "external_asset_id"):
            external_id = asset.get(field)
            if external_id is None:
                continue
            if not isinstance(external_id, str) or not external_id:
                raise ValueError(f"assets[{position}].{field} must be a non-empty string")
            existing = index.get(external_id)
            if existing is not None and existing != key:
                raise ValueError(f"duplicate asset identifier {external_id!r}")
            index[external_id] = key
    return index


def _resolve_audio_asset_keys(
    data: dict[str, Any],
    asset_keys: dict[str, str],
    path: str,
) -> dict[str, Any]:
    """Map creator-facing audio asset IDs to public ``asset_key`` values."""
    resolved = dict(data)
    tracks = resolved.get("tracks", [])
    if not isinstance(tracks, list):
        return resolved
    resolved_tracks: list[Any] = []
    for index, raw_track in enumerate(tracks):
        if not isinstance(raw_track, dict):
            raise ValueError(f"{path}.tracks[{index}] must be an object")
        track = dict(raw_track)
        source_key = track.get("asset_key") or track.get("asset_id")
        track.pop("asset_id", None)
        if isinstance(source_key, str):
            track["asset_key"] = asset_keys.get(source_key, source_key)
        resolved_tracks.append(track)
    resolved["tracks"] = resolved_tracks
    return resolved


def _resolve_subtitle_asset_key(
    data: dict[str, Any],
    asset_keys: dict[str, str],
) -> dict[str, Any]:
    """Map a creator-facing subtitle asset ID to a public ``asset_key``."""
    resolved = dict(data)
    source_key = resolved.get("asset_key") or resolved.get("asset_id")
    resolved.pop("asset_id", None)
    if isinstance(source_key, str):
        resolved["asset_key"] = asset_keys.get(source_key, source_key)
    return resolved


def _semantic_usage(role: str | None) -> str:
    """Keep creator vocabulary at the adapter boundary, not in the runtime."""
    return {
        "character": "subject.identity",
        "composition": "composition.motion",
        "style": "style.visual",
    }.get(role or "", f"reference.{role or 'visual'}")


def _panel_references(
    panel: dict[str, Any],
    asset_keys: dict[str, str],
) -> list[ReferenceSpec]:
    if "references" in panel:
        raw_refs = panel["references"]
    else:
        pack = panel.get("pack", {})
        if not isinstance(pack, dict):
            raise ValueError("panel.pack must be an object")
        raw_refs = pack.get("refs", [])
    if not isinstance(raw_refs, list):
        raise ValueError("panel references must be a list")
    refs: list[ReferenceSpec] = []
    seen_reference_ids: set[str] = set()
    for index, raw in enumerate(raw_refs):
        if not isinstance(raw, dict):
            raise ValueError(f"panel references[{index}] must be an object")
        source_key = raw.get("asset_key") or raw.get("asset_id")
        asset_key = asset_keys.get(source_key, source_key) if isinstance(source_key, str) else None
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"panel reference {index + 1} has no resolvable asset_key")
        binding_data = raw.get("binding", {})
        if not isinstance(binding_data, dict):
            raise ValueError(f"panel references[{index}].binding must be an object")
        reference_id = raw.get("reference_id", f"ref-{index + 1:03d}")
        if not isinstance(reference_id, str) or not reference_id:
            raise ValueError(f"panel references[{index}].reference_id must be a non-empty string")
        if reference_id in seen_reference_ids:
            raise ValueError(
                f"panel references[{index}].reference_id duplicates {reference_id!r}"
            )
        seen_reference_ids.add(reference_id)
        semantic_usage = raw.get("semantic_usage", _semantic_usage(raw.get("role")))
        if not isinstance(semantic_usage, str) or not semantic_usage:
            raise ValueError(f"panel references[{index}].semantic_usage must be a non-empty string")
        refs.append(ReferenceSpec(
            reference_id=reference_id,
            asset_key=asset_key,
            semantic_usage=semantic_usage,
            instruction=raw.get("instruction", raw.get("purpose")),
            binding=BindingPolicy.from_dict(
                binding_data,
                f"$.references[{index}].binding",
            ),
        ))
    return refs


def _validate_operation_references(
    operation: str,
    references: list[ReferenceSpec],
    asset_media_types: dict[str, str],
) -> None:
    """Validate creator references with explicit typed R2V slots."""
    validate_operation_references(
        operation,
        references,
        asset_media_types=asset_media_types,
    )


def _panel_to_clip(
    panel: dict[str, Any],
    sequence: int,
    asset_keys: dict[str, str],
    asset_media_types: dict[str, str],
    requirements: GenerationRequirements,
) -> ClipSpec:
    panel_id = panel.get("panel_id", f"panel-{sequence:03d}")
    prompt = panel.get("prompt", panel.get("prompt_text", ""))
    generation_data = panel.get("generation", {})
    if not isinstance(generation_data, dict):
        raise ValueError(f"panel {panel_id!r}.generation must be an object")
    if "negative_prompt" in generation_data:
        raise ValueError(
            f"panel {panel_id!r}.generation.negative_prompt is not part of the "
            "approved single-prompt handoff"
        )
    operation = generation_data.get("operation")
    if not isinstance(operation, str) or not operation:
        raise ValueError(f"panel {panel_id!r}.generation.operation is required")
    if operation == "video.passthrough":
        raise ValueError(
            "zero-to-story production packages require one generated Clip; "
            "use an assembly adapter for video.passthrough"
        )
    if generation_data:
        prompt = generation_data.get("prompt", prompt)
    if not isinstance(prompt, str) or not prompt:
        raise ValueError(f"panel {panel_id!r} requires approved prompt_text")
    audio_policy = panel.get("audio", {})
    if not isinstance(audio_policy, dict):
        raise ValueError(f"panel {panel_id!r}.audio must be an object")
    subtitle_data = panel.get("subtitles", {})
    if not isinstance(subtitle_data, dict):
        raise ValueError(f"panel {panel_id!r}.subtitles must be an object")
    audio_policy = _resolve_audio_asset_keys(
        audio_policy,
        asset_keys,
        f"$.panels[{sequence - 1}].audio",
    )
    subtitle_data = _resolve_subtitle_asset_key(subtitle_data, asset_keys)
    extension_data = panel.get("extensions", {})
    if not isinstance(extension_data, dict):
        raise ValueError(f"panel {panel_id!r}.extensions must be an object")
    source_context_data = panel.get("source_context", {})
    if not isinstance(source_context_data, dict):
        raise ValueError(f"panel {panel_id!r}.source_context must be an object")
    requirement_data = generation_data.get("requirements", {})
    if not isinstance(requirement_data, dict):
        raise ValueError(f"panel {panel_id!r}.generation.requirements must be an object")
    # A project-level sampling choice is inherited by every Panel.  A Panel
    # may repeat the same pair for readability, but it cannot silently select
    # a different profile or step count.
    for sampling_key in ("sampler_profile", "steps"):
        project_value = getattr(requirements, sampling_key)
        if sampling_key in requirement_data and project_value is not None:
            panel_value = requirement_data[sampling_key]
            if panel_value != project_value:
                raise ValueError(
                    f"panel {panel_id!r}.generation.requirements.{sampling_key} "
                    f"conflicts with project user_constraints.{sampling_key}"
                )
    resolved_requirements = _canvas_requirements(
        requirements.to_dict() | requirement_data,
        f"$.panels[{sequence - 1}].generation.requirements",
    )
    references = _panel_references(panel, asset_keys)
    _validate_operation_references(operation, references, asset_media_types)
    return ClipSpec(
        clip_id=panel.get("clip_id", panel_id),
        sequence=panel.get("sequence", sequence),
        duration_ms=panel.get("duration_ms", panel.get("desired_duration_ms", 15_000)),
        generation=GenerationSpec(
            operation=operation,
            prompt=prompt,
            seed=generation_data.get("seed"),
            requirements=resolved_requirements,
            references=references,
        ),
        audio=AudioPolicy.from_dict(audio_policy, f"$.panels[{sequence - 1}].audio"),
        subtitles=SubtitleSpec.from_dict(subtitle_data, f"$.panels[{sequence - 1}].subtitles"),
        # Cross-Panel order is owned by the caller.  A one-Panel package must
        # not carry references to Clip IDs that do not exist inside the package.
        dependencies=[],
        source_context={
            "creative_unit": "panel",
            "beat_range": list(panel.get("beat_range", [])),
            "setup_range": list(panel.get("setup_range", [])),
            **source_context_data,
        },
        extensions=dict(extension_data),
    )


def _adapt_panels(creative: dict[str, Any]) -> VideoExecutionPackage:
    project_data = creative.get("project", {})
    if not isinstance(project_data, dict):
        raise ValueError("project must be an object")
    project_id = project_data.get("project_id") or creative.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("Panel-first input requires a stable project_id for workspace routing")
    panels = creative.get("panels", [])
    if not isinstance(panels, list) or len(panels) != 1:
        raise ValueError("Production execution requires exactly one approved panel")
    panel = panels[0]
    if not isinstance(panel, dict):
        raise ValueError("panels[0] must be an object")
    panel_id = panel.get("panel_id", "panel-001")
    if not isinstance(panel_id, str) or not panel_id:
        raise ValueError("panels[0].panel_id must be a non-empty string")
    package_id = project_data.get("package_id") or f"{project_id}-{panel_id}"
    if not isinstance(package_id, str) or not package_id:
        raise ValueError("Panel-first input requires a non-empty package_id")
    raw_assets = creative.get("assets", [])
    if not isinstance(raw_assets, list):
        raise ValueError("assets must be a list")
    asset_keys = _asset_id_index(raw_assets)
    asset_records = {
        asset["asset_key"]: asset
        for asset in raw_assets
        if isinstance(asset, dict) and isinstance(asset.get("asset_key"), str)
    }
    asset_media_types = {
        asset_key: str(asset.get("media_type") or "image")
        for asset_key, asset in asset_records.items()
    }
    builder = VideoPackageBuilder(
        package_id,
        project_data.get("title", "Untitled"),
        revision=project_data.get("revision", 1),
        locale=project_data.get("locale"),
        project_id=project_id,
    )
    custom = creative.get("user_constraints")
    if custom is None:
        style = creative.get("style", {})
        custom = style.get("custom", {}) if isinstance(style, dict) else {}
    if not isinstance(custom, dict):
        custom = {}
    resolution = custom.get("delivery_resolution")
    resolution_width: int | None = None
    resolution_height: int | None = None
    if isinstance(resolution, str) and "x" in resolution:
        width_text, height_text = resolution.lower().split("x", maxsplit=1)
        if width_text.isdigit() and height_text.isdigit():
            resolution_width, resolution_height = int(width_text), int(height_text)
    output = OutputPolicy(
        width=custom.get("delivery_width", custom.get("delivery_resolution_width")),
        height=custom.get("delivery_height", custom.get("delivery_resolution_height")),
        fps=custom.get("frame_rate"),
        directory=package_id,
    )
    if output.width is None:
        output.width = resolution_width
    if output.height is None:
        output.height = resolution_height
    requirements = _canvas_requirements(
        {
            "aspect_ratio": custom.get("aspect_ratio")
            or _aspect_from_pixels(output.width, output.height),
            "megapixels": custom.get("megapixels", custom.get("pixel_ratio")),
            "fps": output.fps,
            "native_audio": "allowed",
            "sampler_profile": custom.get("sampler_profile"),
            "steps": custom.get("steps"),
        },
        "$.generation.requirements",
    )
    for sequence, panel in enumerate(panels, start=1):
        clip = _panel_to_clip(
            panel,
            sequence,
            asset_keys,
            asset_media_types,
            requirements,
        )
        # A generation package contains only the assets that this Panel's
        # references/audio/subtitles actually consume.  Unrelated storyboard
        # assets would otherwise be imported and could fail source validation.
        builder.add_clip(clip)
        required_asset_keys = {
            reference.asset_key for reference in clip.generation.references
        }
        required_asset_keys.update(track.asset_key for track in clip.audio.tracks)
        if clip.subtitles.asset_key is not None:
            required_asset_keys.add(clip.subtitles.asset_key)
        for asset_key in sorted(required_asset_keys):
            raw_asset = asset_records.get(asset_key)
            if raw_asset is not None:
                builder.add_asset(_asset_spec(raw_asset))
    package_extensions = creative.get("extensions", {})
    if not isinstance(package_extensions, dict):
        raise ValueError("extensions must be an object")
    review = creative.get("review", {})
    if not isinstance(review, dict):
        raise ValueError("review must be an object")
    approval = ApprovalDeclaration(
        approved_by=review.get("reviewer") if review.get("status") == "approved" else None,
        approved_at=review.get("approved_at") if review.get("status") == "approved" else None,
        notes=review.get("notes"),
    )
    return builder.output(output).approval(approval).extensions(**package_extensions).build()


def adapt(creative: dict[str, Any]) -> VideoExecutionPackage:
    """Convert one approved Panel into one production Clip package."""
    if not isinstance(creative, dict):
        raise TypeError("zero-to-story input must be an object")
    if "shots" in creative:
        raise ValueError("zero-to-story input must use panels; legacy shots are not supported")
    if not creative.get("panels"):
        raise ValueError("zero-to-story input requires one approved panel")
    return _adapt_panels(creative)
