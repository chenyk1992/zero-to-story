"""Zero-to-Story adapter — convert a legacy storyboard dict to VideoExecutionPackage.

Pure transformation function. No I/O, no validation beyond structural mapping.
The output is guaranteed to be a structurally valid VideoExecutionPackage.
"""
from __future__ import annotations

from typing import Any

from lfo.contracts.assets import AssetSpec, AssetSource, ProvenanceSpec, ReviewDeclaration
from lfo.contracts.clips import (
    AudioPolicy,
    AudioTrackSpec,
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    ReferenceSpec,
    SubtitleCue,
    SubtitleSpec,
)
from lfo.contracts.package import ApprovalDeclaration, OutputPolicy, ProjectInfo, VideoExecutionPackage


def _shot_to_clip(shot: dict[str, Any], sequence: int) -> ClipSpec:
    """Convert a storyboard shot to a ClipSpec."""
    shot_id = shot.get("shot_id", f"shot-{sequence:03d}")
    clip_id = f"clip-{sequence:03d}"
    duration_ms = shot.get("duration_ms", 5000)

    # Build generation spec
    generation_data = shot.get("generation", {})
    operation = generation_data.get("operation", "video.reference_to_video")
    prompt = generation_data.get("prompt", "")

    # Requirements
    req_data = generation_data.get("requirements", {})
    requirements = GenerationRequirements(
        aspect_ratio=req_data.get("aspect_ratio"),
        width=req_data.get("width"),
        height=req_data.get("height"),
        fps=req_data.get("fps"),
        native_audio=req_data.get("native_audio"),
    )

    # References
    references: list[ReferenceSpec] = []
    for i, ref_data in enumerate(generation_data.get("references", [])):
        binding_data = ref_data.get("binding", {})
        binding = BindingPolicy(
            required=binding_data.get("required", True),
            priority=binding_data.get("priority", 0),
            placement=binding_data.get("placement", "any"),
            on_unsupported=binding_data.get("on_unsupported", "fail"),
        )
        references.append(ReferenceSpec(
            reference_id=ref_data.get("reference_id", f"ref-{i + 1:03d}"),
            asset_key=ref_data.get("asset_key", ""),
            semantic_usage=ref_data.get("semantic_usage"),
            instruction=ref_data.get("instruction"),
            binding=binding,
        ))

    generation = GenerationSpec(
        operation=operation,
        prompt=prompt,
        negative_prompt=generation_data.get("negative_prompt"),
        seed=generation_data.get("seed"),
        requirements=requirements,
        references=references,
    )

    # Audio
    audio_data = shot.get("audio", {})
    audio_tracks: list[AudioTrackSpec] = []
    for t in audio_data.get("tracks", []):
        audio_tracks.append(AudioTrackSpec(
            asset_key=t.get("asset_key", ""),
            role=t.get("role"),
            offset_ms=t.get("offset_ms", 0),
            gain_db=t.get("gain_db"),
            fade_in_ms=t.get("fade_in_ms"),
            fade_out_ms=t.get("fade_out_ms"),
            duck_group=t.get("duck_group"),
        ))
    audio = AudioPolicy(
        native_audio=audio_data.get("native_audio"),
        tracks=audio_tracks,
    )

    # Subtitles
    sub_data = shot.get("subtitles", {})
    cues: list[SubtitleCue] = []
    for c in sub_data.get("cues", []):
        cues.append(SubtitleCue(
            start_ms=c.get("start_ms", 0),
            end_ms=c.get("end_ms", 0),
            text=c.get("text", ""),
        ))
    subtitles = SubtitleSpec(
        asset_key=sub_data.get("asset_key"),
        cues=cues,
    )

    return ClipSpec(
        clip_id=clip_id,
        sequence=sequence,
        duration_ms=duration_ms,
        generation=generation,
        audio=audio,
        subtitles=subtitles,
        dependencies=list(shot.get("dependencies", [])),
    )


def _collect_assets_from_storyboard(storyboard: dict[str, Any]) -> list[AssetSpec]:
    """Extract unique assets from a storyboard dict."""
    assets: dict[str, AssetSpec] = {}

    # Direct assets list
    for a in storyboard.get("assets", []):
        key = a.get("asset_key", "")
        if key and key not in assets:
            source_data = a.get("source", {})
            prov_data = a.get("provenance", {})
            review_data = a.get("review", {})
            assets[key] = AssetSpec(
                asset_key=key,
                media_type=a.get("media_type", "image"),
                source=AssetSource(
                    uri=source_data.get("uri", ""),
                    sha256=source_data.get("sha256"),
                ),
                provenance=ProvenanceSpec(
                    source_type=prov_data.get("source_type"),
                    producer=prov_data.get("producer"),
                    producer_version=prov_data.get("producer_version"),
                    operation=prov_data.get("operation"),
                    source_asset_keys=prov_data.get("source_asset_keys"),
                    prompt_hash=prov_data.get("prompt_hash"),
                ),
                review=ReviewDeclaration(
                    required=review_data.get("required", True),
                ),
            )

    # Collect references from shots
    for shot in storyboard.get("shots", []):
        for ref in shot.get("generation", {}).get("references", []):
            asset_key = ref.get("asset_key", "")
            if asset_key and asset_key not in assets:
                # Create a placeholder asset (must be provided by the skill)
                assets[asset_key] = AssetSpec(
                    asset_key=asset_key,
                    media_type="image",
                    source=AssetSource(uri=f"assets/{asset_key.replace('.', '_')}.png"),
                )

    return list(assets.values())


def adapt(storyboard: dict[str, Any]) -> VideoExecutionPackage:
    """Convert a legacy storyboard dict to a VideoExecutionPackage.

    Args:
        storyboard: Parsed storyboard JSON (the ``lfo.storyboard.v1`` format).

    Returns:
        A valid VideoExecutionPackage ready for ``VideoRuntime.execute()``.
    """
    project_data = storyboard.get("project", {})
    package_id = project_data.get("package_id") or storyboard.get("project_id", "unknown")
    revision = project_data.get("revision", 1)

    project = ProjectInfo(
        title=project_data.get("title", "Untitled"),
        locale=project_data.get("locale"),
    )

    assets = _collect_assets_from_storyboard(storyboard)

    clips: list[ClipSpec] = []
    for i, shot in enumerate(storyboard.get("shots", [])):
        clips.append(_shot_to_clip(shot, sequence=i + 1))

    # Output policy from storyboard (use from_dict for safe defaults)
    output_data = dict(storyboard.get("output", {}))
    # Remove keys that OutputPolicy doesn't understand
    for key in list(output_data.keys()):
        if key not in {"container", "video_encoder", "audio_encoder", "width",
                       "height", "fps", "sample_rate", "loudness_db",
                       "transitions", "subtitles_mode", "directory"}:
            del output_data[key]
    output = OutputPolicy.from_dict(output_data, "$.output")

    # Approval
    approval_data = storyboard.get("approval", {})
    approval = ApprovalDeclaration(
        approved_by=approval_data.get("approved_by"),
        approved_at=approval_data.get("approved_at"),
        notes=approval_data.get("notes"),
    )

    return VideoExecutionPackage(
        package_id=package_id,
        revision=revision,
        project=project,
        assets=assets,
        clips=clips,
        output=output,
        approval=approval,
    )
