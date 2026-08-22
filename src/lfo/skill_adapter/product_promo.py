"""Product promo adapter — build a VideoExecutionPackage for product marketing.

Demonstrates that a non-story skill can produce the same contract.
Pure builder function, no I/O.
"""
from __future__ import annotations

from typing import Any

from lfo.contracts.assets import AssetSource, AssetSpec, ProvenanceSpec, ReviewDeclaration
from lfo.contracts.builder import VideoPackageBuilder
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
from lfo.contracts.package import ApprovalDeclaration, VideoExecutionPackage
from lfo.contracts.timeline import OutputPolicy


def build_package(
    package_id: str,
    title: str,
    product_images: list[dict[str, str]],
    scripts: list[dict[str, Any]],
    dialogue_audio: list[dict[str, str]] | None = None,
    locale: str = "en-US",
    project_id: str | None = None,
    aspect_ratio: str = "9:16",
    megapixels: float = 0.4,
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
) -> VideoExecutionPackage:
    """Build a product promo VideoExecutionPackage.

    Args:
        package_id: Unique package identifier.
        title: Project title.
        product_images: List of {"asset_key": ..., "uri": ..., "prompt": ...}.
        scripts: List of {"clip_id": ..., "prompt": ..., "duration_ms": ...}.
        dialogue_audio: Optional list of {"asset_key": ..., "uri": ...}.
        locale: Project locale.
        aspect_ratio: H3 generation canvas ratio, e.g. ``9:16`` or ``16:9``.
        megapixels: H3 ResolutionSelector megapixel target.
        width: Delivery width for OutputPolicy, not H3 generation.
        height: Delivery height for OutputPolicy, not H3 generation.
        fps: Target fps.

    Returns:
        A valid VideoExecutionPackage.
    """
    builder = VideoPackageBuilder(
        package_id,
        title,
        locale=locale,
        project_id=project_id or package_id,
    )

    # Build assets
    assets: list[AssetSpec] = []
    asset_keys_seen: set[str] = set()

    for img in product_images:
        key = img["asset_key"]
        if key in asset_keys_seen:
            continue
        asset_keys_seen.add(key)
        assets.append(AssetSpec(
            asset_key=key,
            media_type="image",
            source=AssetSource(uri=img["uri"]),
            provenance=ProvenanceSpec(
                source_type="external_skill",
                producer=img.get("producer", "imagegen"),
                operation="image.generate",
                prompt_hash=img.get("prompt_hash"),
            ),
            review=ReviewDeclaration(required=True),
        ))

    for audio in dialogue_audio or []:
        key = audio["asset_key"]
        if key in asset_keys_seen:
            continue
        asset_keys_seen.add(key)
        assets.append(AssetSpec(
            asset_key=key,
            media_type="audio",
            source=AssetSource(uri=audio["uri"]),
            provenance=ProvenanceSpec(
                source_type="external_skill",
                producer=audio.get("producer", "tts"),
                operation="audio.synthesize",
            ),
            review=ReviewDeclaration(required=False),
        ))

    for asset in assets:
        builder.add_asset(asset)

    # Build clips
    for i, script in enumerate(scripts):
        clip_id = script.get("clip_id", f"clip-{i + 1:03d}")
        duration_ms = script.get("duration_ms", 5000)

        # References: use all product images
        references: list[ReferenceSpec] = []
        for j, img in enumerate(product_images):
            references.append(ReferenceSpec(
                reference_id=f"ref-{i + 1:03d}-{j + 1:03d}",
                asset_key=img["asset_key"],
                semantic_usage="product.visual",
                instruction="Keep product appearance consistent",
                binding=BindingPolicy(
                    required=True,
                    priority=100 - j * 10,
                    placement="any",
                    on_unsupported="fail",
                ),
            ))

        # Audio tracks
        audio_tracks: list[AudioTrackSpec] = []
        if dialogue_audio and i < len(dialogue_audio):
            audio_tracks.append(AudioTrackSpec(
                asset_key=dialogue_audio[i]["asset_key"],
                role="dialogue",
                offset_ms=0,
                gain_db="0",
            ))

        # Subtitle cues from script
        sub_cues: list[SubtitleCue] = []
        for cue in script.get("cues", []):
            sub_cues.append(SubtitleCue(
                start_ms=cue.get("start_ms", 0),
                end_ms=cue.get("end_ms", 1000),
                text=cue.get("text", ""),
            ))

        builder.add_clip(ClipSpec(
            clip_id=clip_id,
            sequence=i + 1,
            duration_ms=duration_ms,
            generation=GenerationSpec(
                operation="video.reference_to_video",
                prompt=script.get("prompt", ""),
                requirements=GenerationRequirements(
                    aspect_ratio=aspect_ratio,
                    megapixels=megapixels,
                    fps=fps,
                    native_audio="allowed",
                ),
                references=references,
            ),
            audio=AudioPolicy(
                native_audio="preserve",
                tracks=audio_tracks,
            ),
            subtitles=SubtitleSpec(cues=sub_cues),
        ))

    output = OutputPolicy(
        width=width,
        height=height,
        fps=fps,
        sample_rate=44100,
        subtitles_mode="both",
        directory=package_id,
    )

    return (
        builder
        .output(output)
        .approval(ApprovalDeclaration(
            approved_by="skill",
            notes="Auto-generated by product_promo adapter",
        ))
        .build()
    )
