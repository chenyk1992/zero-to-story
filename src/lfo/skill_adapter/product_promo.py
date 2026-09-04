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
    megapixels: float | None = None,
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
    if not isinstance(scripts, list) or len(scripts) != 1:
        raise ValueError("product promo production requires exactly one script/clip")
    if not isinstance(product_images, list) or not product_images:
        raise ValueError("product promo production requires at least one product image")
    if dialogue_audio is not None and not isinstance(dialogue_audio, list):
        raise TypeError("dialogue_audio must be a list when provided")
    if dialogue_audio is not None and len(dialogue_audio) > 1:
        raise ValueError(
            "product promo production supports at most one dialogue audio track"
        )
    if not isinstance(scripts[0], dict):
        raise TypeError("scripts[0] must be an object")
    builder = VideoPackageBuilder(
        package_id,
        title,
        locale=locale,
        project_id=project_id or package_id,
    )

    # Build assets
    assets: list[AssetSpec] = []
    asset_keys_seen: set[str] = set()

    for index, img in enumerate(product_images):
        if not isinstance(img, dict):
            raise TypeError(f"product_images[{index}] must be an object")
        key = img["asset_key"]
        if key in asset_keys_seen:
            raise ValueError(f"duplicate asset_key {key!r}")
        asset_keys_seen.add(key)
        sha256 = img.get("sha256")
        if sha256 is not None and not isinstance(sha256, str):
            raise TypeError(f"product_images[{index}].sha256 must be a string when provided")
        assets.append(AssetSpec(
            asset_key=key,
            media_type="image",
            source=AssetSource(uri=img["uri"], sha256=sha256),
            provenance=ProvenanceSpec(
                source_type="external_skill",
                producer=img.get("producer", "imagegen"),
                operation="image.generate",
                prompt_hash=img.get("prompt_hash"),
            ),
            review=ReviewDeclaration(required=True),
        ))

    for index, audio in enumerate(dialogue_audio or []):
        if not isinstance(audio, dict):
            raise TypeError(f"dialogue_audio[{index}] must be an object")
        key = audio["asset_key"]
        if key in asset_keys_seen:
            raise ValueError(f"duplicate asset_key {key!r}")
        asset_keys_seen.add(key)
        sha256 = audio.get("sha256")
        if sha256 is not None and not isinstance(sha256, str):
            raise TypeError(f"dialogue_audio[{index}].sha256 must be a string when provided")
        assets.append(AssetSpec(
            asset_key=key,
            media_type="audio",
            source=AssetSource(uri=audio["uri"], sha256=sha256),
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
        if not isinstance(script, dict):
            raise TypeError(f"scripts[{i}] must be an object")
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
                    placement="fixed",
                    on_unsupported="fail",
                    slot=f"ref_image_{j}",
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
        raw_cues = script.get("cues", [])
        if not isinstance(raw_cues, list):
            raise TypeError(f"scripts[{i}].cues must be a list")
        for cue_index, cue in enumerate(raw_cues):
            if not isinstance(cue, dict):
                raise TypeError(f"scripts[{i}].cues[{cue_index}] must be an object")
            cue_data = {
                "start_ms": 0,
                "end_ms": 1000,
                "text": "",
                **cue,
            }
            sub_cues.append(
                SubtitleCue.from_dict(cue_data, f"scripts[{i}].cues[{cue_index}]")
            )

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
