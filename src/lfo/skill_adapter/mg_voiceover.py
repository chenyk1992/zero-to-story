"""Pure adapter for the MG voiceover animation Skill.

The Skill owns prompt authoring, reference generation and user approval. This
module only maps approved inputs to the public ``VideoExecutionPackage``
contract; it performs no I/O and knows nothing about LFO runtime internals.
"""

from __future__ import annotations

import math
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
    SubtitleSpec,
)
from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.contracts.timeline import ApprovalDeclaration, OutputPolicy

_SKILL_NAME = "mg-voiceover-animation-generator"
_VISUAL_MEDIA_TYPES = frozenset({"image", "video"})


def _required_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _positive_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{path} must be an integer")
    if value <= 0:
        raise ValueError(f"{path} must be positive")
    return value


def _megapixels(value: float | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("pixel_ratio must be a positive number")
    try:
        parsed = float(value)
    except ValueError:
        raise TypeError("pixel_ratio must be a positive number") from None
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError("pixel_ratio must be positive")
    return parsed


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{path} must be an object")
    return value


def _optional_string(data: dict[str, Any], key: str, default: str, path: str) -> str:
    return _required_string(data.get(key, default), f"{path}.{key}")


def _asset(
    data: dict[str, Any],
    *,
    path: str,
    media_type: str,
    default_operation: str,
) -> AssetSpec:
    asset_key = _required_string(data.get("asset_key"), f"{path}.asset_key")
    uri = _required_string(data.get("uri"), f"{path}.uri")
    review_required = data.get("review_required", True)
    if not isinstance(review_required, bool):
        raise TypeError(f"{path}.review_required must be a boolean")
    sha256 = data.get("sha256")
    if sha256 is not None and not isinstance(sha256, str):
        raise TypeError(f"{path}.sha256 must be a string when provided")
    prompt_hash = data.get("prompt_hash")
    if prompt_hash is not None and not isinstance(prompt_hash, str):
        raise TypeError(f"{path}.prompt_hash must be a string when provided")
    return AssetSpec(
        asset_key=asset_key,
        media_type=media_type,
        source=AssetSource(uri=uri, sha256=sha256),
        provenance=ProvenanceSpec(
            source_type=_optional_string(data, "source_type", "external_skill", path),
            producer=_optional_string(data, "producer", _SKILL_NAME, path),
            operation=_optional_string(data, "operation", default_operation, path),
            prompt_hash=prompt_hash,
        ),
        review=ReviewDeclaration(required=review_required),
    )


def _visual_references(
    values: list[dict[str, Any]],
) -> tuple[list[AssetSpec], list[ReferenceSpec], str]:
    single_media_type: Any = None
    if len(values) == 1:
        single = _mapping(values[0], "reference_assets[0]")
        single_media_type = single.get("media_type", "image")
    operation = (
        "video.text_to_video"
        if not values
        else "video.image_to_video"
        if single_media_type == "image"
        else "video.reference_to_video"
    )
    assets: list[AssetSpec] = []
    references: list[ReferenceSpec] = []
    seen_keys: set[str] = set()
    seen_reference_ids: set[str] = set()
    for index, raw in enumerate(values):
        path = f"reference_assets[{index}]"
        data = _mapping(raw, path)
        media_type = data.get("media_type", "image")
        if media_type not in _VISUAL_MEDIA_TYPES:
            raise ValueError(f"{path}.media_type must be 'image' or 'video'")
        asset = _asset(
            data,
            path=path,
            media_type=media_type,
            default_operation="media.reference",
        )
        if asset.asset_key in seen_keys:
            raise ValueError(f"duplicate asset_key {asset.asset_key!r}")
        seen_keys.add(asset.asset_key)

        reference_id = _required_string(
            data.get("reference_id", f"ref-{index + 1:03d}"),
            f"{path}.reference_id",
        )
        if reference_id in seen_reference_ids:
            raise ValueError(f"duplicate reference_id {reference_id!r}")
        seen_reference_ids.add(reference_id)
        semantic_usage = _required_string(data.get("semantic_usage"), f"{path}.semantic_usage")
        instruction = _required_string(data.get("instruction"), f"{path}.instruction")
        required = data.get("required")
        if not isinstance(required, bool):
            raise TypeError(f"{path}.required must be a boolean")
        priority = data.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise TypeError(f"{path}.priority must be an integer")
        placement = data.get("placement")
        _required_string(placement, f"{path}.placement")
        on_unsupported = data.get("on_unsupported")
        _required_string(on_unsupported, f"{path}.on_unsupported")
        if operation == "video.image_to_video":
            placement = "first"
        slot = data.get("slot")
        if slot is not None and not isinstance(slot, str):
            raise TypeError(f"{path}.slot must be a string when provided")
        references.append(
            ReferenceSpec(
                reference_id=reference_id,
                asset_key=asset.asset_key,
                semantic_usage=semantic_usage,
                instruction=instruction,
                binding=BindingPolicy.from_dict(
                    {
                        "required": required,
                        "priority": priority,
                        "placement": placement,
                        "on_unsupported": on_unsupported,
                        **({"slot": slot} if slot is not None else {}),
                    },
                    f"{path}.binding",
                ),
            )
        )
        assets.append(asset)
    return assets, references, operation


def build_package(
    package_id: str,
    title: str,
    prompt: str,
    duration_ms: int,
    approved_by: str,
    reference_assets: list[dict[str, Any]] | None = None,
    voiceover_audio: dict[str, Any] | None = None,
    *,
    project_id: str | None = None,
    locale: str = "zh-CN",
    aspect_ratio: str = "9:16",
    pixel_ratio: float | str | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
    output_directory: str | None = None,
    approved_at: str | None = None,
    approval_notes: str | None = None,
) -> VideoExecutionPackage:
    """Map one approved continuous MG animation to an execution package."""

    package_id = _required_string(package_id, "package_id")
    title = _required_string(title, "title")
    prompt = _required_string(prompt, "prompt")
    approved_by = _required_string(approved_by, "approved_by")
    _required_string(aspect_ratio, "aspect_ratio")
    _positive_int(duration_ms, "duration_ms")
    _positive_int(width, "width")
    _positive_int(height, "height")
    _positive_int(fps, "fps")
    if reference_assets is not None and not isinstance(reference_assets, list):
        raise TypeError("reference_assets must be an array")
    visual_assets, references, operation = _visual_references(reference_assets or [])
    megapixels = _megapixels(pixel_ratio)
    effective_project_id = (
        package_id if project_id is None else _required_string(project_id, "project_id")
    )
    requirements = GenerationRequirements(
        aspect_ratio=aspect_ratio,
        megapixels=megapixels,
        width=None if megapixels is not None else width,
        height=None if megapixels is not None else height,
        fps=fps,
        native_audio="none" if voiceover_audio is not None else "allowed",
        reference_image_size="match" if visual_assets else None,
    )

    builder = VideoPackageBuilder(
        package_id,
        title,
        locale=locale,
        project_id=effective_project_id,
    )
    seen_asset_keys = {asset.asset_key for asset in visual_assets}
    for asset in visual_assets:
        builder.add_asset(asset)

    audio_policy = AudioPolicy(native_audio="preserve")
    if voiceover_audio is not None:
        data = _mapping(voiceover_audio, "voiceover_audio")
        audio_asset = _asset(
            data,
            path="voiceover_audio",
            media_type="audio",
            default_operation="audio.synthesize",
        )
        if audio_asset.asset_key in seen_asset_keys:
            raise ValueError(f"duplicate asset_key {audio_asset.asset_key!r}")
        builder.add_asset(audio_asset)
        audio_policy = AudioPolicy(
            native_audio="replace",
            tracks=[AudioTrackSpec(asset_key=audio_asset.asset_key, role="narration")],
        )

    builder.add_clip(
        ClipSpec(
            clip_id="clip-001",
            sequence=1,
            duration_ms=duration_ms,
            generation=GenerationSpec(
                operation=operation,
                prompt=prompt,
                references=references,
                requirements=requirements,
            ),
            audio=audio_policy,
            subtitles=SubtitleSpec(),
            source_context={
                "skill": _SKILL_NAME,
                "workflow": "approved-h3-mg-voiceover",
                "continuous_clip": True,
            },
        )
    )
    package = (
        builder.output(
            OutputPolicy(
                width=width,
                height=height,
                fps=fps,
                sample_rate=44100,
                subtitles_mode="none",
                directory=output_directory or package_id,
            )
        )
        .approval(
            ApprovalDeclaration(
                approved_by=approved_by,
                approved_at=approved_at,
                notes=approval_notes,
            )
        )
        .build()
    )
    result = validate_package(package.to_dict())
    if not result.ok:
        raise ValueError(f"invalid VideoExecutionPackage: {result.to_dict()}")
    return package
