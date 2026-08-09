"""Adapt approved zero-to-story creative output to ``VideoExecutionPackage``.

The normal input is a Panel-first creative document: generated character and
storyboard images are listed in ``assets`` and every approved panel becomes one
independent Clip.  This module is deliberately the only place that understands
the legacy ``shots`` shape; the LFO execution contract never does.
"""
from __future__ import annotations

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
from lfo.contracts.package import ApprovalDeclaration, VideoExecutionPackage
from lfo.contracts.timeline import OutputPolicy


def _asset_spec(data: dict[str, Any]) -> AssetSpec:
    """Accept a public AssetSpec dict or concise Skill asset declaration."""
    if "source" in data and "provenance" in data:
        return AssetSpec.from_dict(data, "$.assets[]")
    return AssetSpec(
        asset_key=data["asset_key"],
        media_type=data.get("media_type", "image"),
        source=AssetSource(uri=data.get("uri", data.get("path", ""))),
        provenance=ProvenanceSpec(
            source_type=data.get("source_type", "external_skill"),
            producer=data.get("producer", "zero-to-story"),
            operation=data.get("operation", "image.generate"),
            producer_version=data.get("producer_version"),
            source_asset_keys=list(data.get("source_asset_keys", [])),
            prompt_hash=data.get("prompt_hash"),
        ),
        review=ReviewDeclaration(required=data.get("review_required", True)),
        metadata=dict(data.get("metadata", {})),
    )


def _asset_id_index(assets: list[dict[str, Any]]) -> dict[str, str]:
    """Resolve creator-facing asset IDs without leaking them to LFO."""
    index: dict[str, str] = {}
    for asset in assets:
        key = asset.get("asset_key")
        if not isinstance(key, str) or not key:
            continue
        index[key] = key
        external_id = asset.get("asset_id") or asset.get("external_asset_id")
        if isinstance(external_id, str) and external_id:
            index[external_id] = key
    return index


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
    raw_refs = panel.get("references")
    if not isinstance(raw_refs, list):
        raw_refs = panel.get("pack", {}).get("refs", [])
    refs: list[ReferenceSpec] = []
    for index, raw in enumerate(raw_refs):
        if not isinstance(raw, dict):
            raise ValueError(f"panel references[{index}] must be an object")
        source_key = raw.get("asset_key") or raw.get("asset_id")
        asset_key = asset_keys.get(source_key, source_key) if isinstance(source_key, str) else None
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"panel reference {index + 1} has no resolvable asset_key")
        binding_data = raw.get("binding", {})
        role = raw.get("role")
        placement = binding_data.get(
            "placement",
            "last" if role == "composition" else "any",
        )
        refs.append(ReferenceSpec(
            reference_id=raw.get("reference_id", f"ref-{index + 1:03d}"),
            asset_key=asset_key,
            semantic_usage=raw.get("semantic_usage", _semantic_usage(role)),
            instruction=raw.get("instruction", raw.get("purpose")),
            binding=BindingPolicy(
                required=binding_data.get("required", True),
                priority=binding_data.get("priority", 100 - index),
                placement=placement,
                on_unsupported=binding_data.get("on_unsupported", "fail"),
                slot=binding_data.get("slot"),
            ),
        ))
    return refs


def _panel_to_clip(
    panel: dict[str, Any],
    sequence: int,
    asset_keys: dict[str, str],
    requirements: GenerationRequirements,
) -> ClipSpec:
    panel_id = panel.get("panel_id", f"panel-{sequence:03d}")
    prompt = panel.get("prompt", panel.get("prompt_text", ""))
    generation_data = panel.get("generation", {})
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
    requirement_data = generation_data.get("requirements", {})
    if not isinstance(requirement_data, dict):
        raise ValueError(f"panel {panel_id!r}.generation.requirements must be an object")
    resolved_requirements = GenerationRequirements.from_dict(
        requirements.to_dict() | requirement_data,
        f"$.panels[{sequence - 1}].generation.requirements",
    )
    return ClipSpec(
        clip_id=panel.get("clip_id", panel_id),
        sequence=panel.get("sequence", sequence),
        duration_ms=panel.get("duration_ms", panel.get("desired_duration_ms", 15_000)),
        generation=GenerationSpec(
            operation=generation_data.get("operation", "video.reference_to_video"),
            prompt=prompt,
            negative_prompt=generation_data.get("negative_prompt"),
            seed=generation_data.get("seed"),
            requirements=resolved_requirements,
            references=_panel_references(panel, asset_keys),
        ),
        audio=AudioPolicy.from_dict(audio_policy, f"$.panels[{sequence - 1}].audio"),
        subtitles=SubtitleSpec.from_dict(subtitle_data, f"$.panels[{sequence - 1}].subtitles"),
        dependencies=list(panel.get("dependencies", [])),
        source_context={
            "creative_unit": "panel",
            "beat_range": list(panel.get("beat_range", [])),
        },
    )


def _adapt_panels(creative: dict[str, Any]) -> VideoExecutionPackage:
    project_data = creative.get("project", {})
    package_id = project_data.get("package_id") or project_data.get("project_id")
    if not isinstance(package_id, str) or not package_id:
        raise ValueError("Panel-first input requires project.project_id or project.package_id")
    raw_assets = creative.get("assets", [])
    if not isinstance(raw_assets, list):
        raise ValueError("assets must be a list")
    builder = VideoPackageBuilder(
        package_id,
        project_data.get("title", "Untitled"),
        revision=project_data.get("revision", 1),
        locale=project_data.get("locale"),
    )
    for asset in raw_assets:
        builder.add_asset(_asset_spec(asset))
    custom = creative.get("user_constraints", creative.get("style", {}).get("custom", {}))
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
    requirements = GenerationRequirements(
        aspect_ratio=custom.get("aspect_ratio"),
        width=output.width,
        height=output.height,
        fps=output.fps,
        native_audio="allowed",
    )
    asset_keys = _asset_id_index(raw_assets)
    panels = creative.get("panels", [])
    if not isinstance(panels, list) or not panels:
        raise ValueError("Panel-first input requires at least one panel")
    for sequence, panel in enumerate(panels, start=1):
        builder.add_clip(_panel_to_clip(panel, sequence, asset_keys, requirements))
    review = creative.get("review", {})
    approval = ApprovalDeclaration(
        approved_by=review.get("reviewer") if review.get("status") == "approved" else None,
        approved_at=review.get("approved_at") if review.get("status") == "approved" else None,
        notes=review.get("notes"),
    )
    return builder.output(output).approval(approval).build()


def _adapt_legacy_storyboard(storyboard: dict[str, Any]) -> VideoExecutionPackage:
    """Explicit compatibility conversion kept inside the zero-to-story Skill."""
    project_data = storyboard.get("project", {})
    builder = VideoPackageBuilder(
        project_data.get("package_id") or storyboard.get("project_id", "unknown"),
        project_data.get("title", "Untitled"),
        revision=project_data.get("revision", 1),
        locale=project_data.get("locale"),
    )
    assets = storyboard.get("assets", [])
    for raw_asset in assets:
        builder.add_asset(_asset_spec(raw_asset))
    asset_keys = _asset_id_index(assets)
    shots = storyboard.get("shots", [])
    shot_id_to_clip_id = {
        shot.get("shot_id", f"shot-{sequence:03d}"): shot.get("clip_id", f"clip-{sequence:03d}")
        for sequence, shot in enumerate(shots, start=1)
    }
    for sequence, shot in enumerate(shots, start=1):
        generation = shot.get("generation", {})
        refs = _panel_references({"references": generation.get("references", [])}, asset_keys)
        requirements = GenerationRequirements(**generation.get("requirements", {}))
        builder.add_clip(ClipSpec(
            clip_id=shot.get("clip_id", f"clip-{sequence:03d}"),
            sequence=sequence,
            duration_ms=shot.get("duration_ms", 5_000),
            generation=GenerationSpec(
                operation=generation.get("operation", "video.text_to_video"),
                prompt=generation.get("prompt", ""),
                negative_prompt=generation.get("negative_prompt"),
                seed=generation.get("seed"),
                requirements=requirements,
                references=refs,
            ),
            audio=AudioPolicy.from_dict(shot.get("audio", {}), "$.shots[].audio"),
            subtitles=SubtitleSpec.from_dict(shot.get("subtitles", {}), "$.shots[].subtitles"),
            dependencies=[
                shot_id_to_clip_id.get(dependency, dependency)
                for dependency in shot.get("dependencies", [])
            ],
            source_context={"creative_unit": "legacy_shot"},
        ))
    return (
        builder
        .output(OutputPolicy.from_dict(storyboard.get("output", {}), "$.output"))
        .approval(ApprovalDeclaration.from_dict(storyboard.get("approval", {}), "$.approval"))
        .build()
    )


def adapt(creative: dict[str, Any]) -> VideoExecutionPackage:
    """Convert approved Panel-first output; convert legacy shots only explicitly."""
    if creative.get("panels"):
        return _adapt_panels(creative)
    if creative.get("shots"):
        return _adapt_legacy_storyboard(creative)
    raise ValueError("zero-to-story input requires panels; legacy shots are supported only for conversion")
