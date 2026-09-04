"""Backend-agnostic operation/reference contract rules."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .clips import KNOWN_OPERATIONS, ReferenceSpec


def validate_operation_references(
    operation: str,
    references: object,
    *,
    asset_media_types: Mapping[str, str] | None = None,
) -> None:
    """Validate the reference shape consumed by a known video operation.

    The public contract and provider handlers use the same rules.  Providers
    may keep additional capability limits.  R2V references always use an
    explicit typed slot (``ref_image_N``, ``ref_video_N`` or ``ref_audio_N``)
    so the runtime never has to infer provider input positions.
    """
    if operation not in KNOWN_OPERATIONS:
        raise ValueError(f"Unsupported video operation: {operation!r}")
    if not isinstance(references, list):
        raise TypeError("resolved_references must be a list")
    views = [_reference_view(reference, asset_media_types) for reference in references]

    if operation == "video.text_to_video":
        if views:
            raise ValueError(
                "video.text_to_video does not accept image references or other references; "
                "it requires no references"
            )
        return

    if operation in {"video.image_to_video", "video.first_last_frame"}:
        expected_count = 1 if operation == "video.image_to_video" else 2
        if len(views) != expected_count:
            expected = "one first-frame" if expected_count == 1 else "first-frame and last-frame"
            raise ValueError(
                f"{operation} requires exactly {expected_count} explicit frame reference(s) "
                f"({expected}); ordinary references cannot be consumed by this workflow"
            )
        roles = {_frame_role(view) for view in views}
        required_roles = {"first"} if expected_count == 1 else {"first", "last"}
        if roles != required_roles:
            raise ValueError(
                f"{operation} references must be explicitly bound to first_frame"
                + (" and last_frame" if expected_count == 2 else "")
            )
        if any(view.media_type != "image" for view in views):
            raise ValueError(f"{operation} frame references must use image assets")
        return

    if operation == "video.virtual_presenter":
        if not views:
            raise ValueError("video.virtual_presenter requires at least one reference")
        seen_slots: set[str] = set()
        for view in views:
            if _claims_exact_first_frame(view.semantic_usage, view.instruction):
                raise ValueError(
                    "video.virtual_presenter cannot claim exact/hard first-frame continuity"
                )
            if view.placement != "fixed":
                raise ValueError(
                    "video.virtual_presenter references require typed fixed slots "
                    "ref_image_N, ref_video_N or ref_audio_N"
                )
            match = re.fullmatch(r"ref_(image|video|audio)_(\d+)", view.slot)
            if match is None:
                raise ValueError(
                    "video.virtual_presenter references require typed fixed slots "
                    "ref_image_N, ref_video_N or ref_audio_N"
                )
            if match.group(1) != view.media_type:
                raise ValueError(
                    f"video.virtual_presenter slot {view.slot!r} does not match "
                    f"reference media type {view.media_type!r}"
                )
            if view.slot in seen_slots:
                raise ValueError(
                    f"video.virtual_presenter contains duplicate slot {view.slot!r}"
                )
            seen_slots.add(view.slot)
        return

    if operation == "video.passthrough":
        if len(views) != 1 or views[0].media_type != "video":
            raise ValueError(
                "video.passthrough requires exactly one video reference"
            )
        return

    if operation != "video.reference_to_video":
        return
    if not views:
        raise ValueError("video.reference_to_video requires at least one reference")
    seen_slots: set[str] = set()
    for view in views:
        if view.placement in {"first", "last"} or view.slot in {
            "first_frame",
            "last_frame",
            "ref_image_first",
            "ref_image_last",
        }:
            raise ValueError(
                "video.reference_to_video cannot claim first/last-frame binding; "
                "use video.image_to_video or video.first_last_frame"
            )
        if _claims_exact_first_frame(view.semantic_usage, view.instruction):
            raise ValueError(
                "video.reference_to_video cannot claim exact/hard first-frame continuity"
            )
        if view.placement != "fixed":
            raise ValueError(
                "video.reference_to_video references require typed fixed slots "
                "ref_image_N, ref_video_N or ref_audio_N"
            )
        match = re.fullmatch(r"ref_(image|video|audio)_(\d+)", view.slot)
        if match is None:
            raise ValueError(
                "video.reference_to_video references require typed fixed slots "
                "ref_image_N, ref_video_N or ref_audio_N"
            )
        if match.group(1) != view.media_type:
            raise ValueError(
                f"video.reference_to_video slot {view.slot!r} does not match "
                f"reference media type {view.media_type!r}"
            )
        if view.slot in seen_slots:
            raise ValueError(
                f"video.reference_to_video contains duplicate slot {view.slot!r}"
            )
        seen_slots.add(view.slot)


@dataclass(frozen=True, slots=True)
class _ReferenceView:
    media_type: str
    placement: str
    slot: str
    semantic_usage: str
    instruction: str


def _reference_view(
    reference: object,
    asset_media_types: Mapping[str, str] | None,
) -> _ReferenceView:
    if isinstance(reference, ReferenceSpec):
        media_type = (
            asset_media_types.get(reference.asset_key, "image")
            if asset_media_types is not None
            else "image"
        )
        return _ReferenceView(
            media_type=media_type,
            placement=reference.binding.placement,
            slot=reference.binding.slot or "",
            semantic_usage=reference.semantic_usage,
            instruction=reference.instruction or "",
        )
    if not isinstance(reference, Mapping):
        raise TypeError("Each resolved reference must be an object")
    asset_key = reference.get("asset_key")
    media_type = reference.get("media_type") or "image"
    if asset_media_types is not None and isinstance(asset_key, str):
        media_type = asset_media_types.get(asset_key, media_type)
    return _ReferenceView(
        media_type=str(media_type),
        placement=str(reference.get("placement") or "any"),
        slot=str(reference.get("slot") or ""),
        semantic_usage=str(reference.get("semantic_usage") or ""),
        instruction=str(reference.get("instruction") or ""),
    )


def _frame_role(reference: _ReferenceView) -> str | None:
    if reference.placement == "first" or reference.slot in {
        "first_frame",
        "ref_image_first",
    }:
        return "first"
    if reference.placement == "last" or reference.slot in {
        "last_frame",
        "ref_image_last",
    }:
        return "last"
    return None


def _claims_exact_first_frame(semantic_usage: str, instruction: str) -> bool:
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        f"{semantic_usage} {instruction}".lower(),
    )
    if any(
        phrase in normalized
        for phrase in (
            "exact first frame",
            "hard first frame",
            "first frame lock",
            "exact frame continuity",
            "hard frame continuity",
            "exact previous last frame",
            "hard previous last frame",
            "previous last frame lock",
        )
    ):
        return True
    tokens = set(normalized.split())
    return bool(
        {"frame"} <= tokens
        and tokens.intersection({"exact", "hard"})
        and (
            tokens.intersection({"first", "continuity"})
            or {"previous", "last"} <= tokens
        )
    )
