"""Backend selection — match a clip's capability requirements to a backend.

Selection never silently degrades. If no backend satisfies the requirements,
a structured rejection is returned explaining exactly why each candidate
failed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capabilities import CapabilityManifest
from .registry import BackendRegistry


@dataclass
class RejectionReason:
    """Why a candidate backend was rejected."""

    backend_id: str
    revision: str
    reason: str
    detail: str = ""


@dataclass
class SelectionResult:
    """Result of backend selection."""

    backend_id: str
    revision: str
    workflow_hash: str
    rejections: list[RejectionReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # References that were dropped (optional refs beyond max_references)
    dropped_references: list[str] = field(default_factory=list)


@dataclass
class SelectionFailure(Exception):
    """Raised when no backend satisfies the requirements."""

    operation: str
    rejections: list[RejectionReason] = field(default_factory=list)
    message: str = ""

    def __str__(self) -> str:
        parts = [f"No backend supports operation {self.operation!r}"]
        for r in self.reasons_formatted():
            parts.append(f"  - {r}")
        return "\n".join(parts)

    def reasons_formatted(self) -> list[str]:
        out = []
        for r in self.rejections:
            line = f"{r.backend_id}@{r.revision}: {r.reason}"
            if r.detail:
                line += f" ({r.detail})"
            out.append(line)
        return out


def select_backend(
    operation: str,
    requirements: dict[str, Any],
    registry: BackendRegistry,
    media_types: list[str] | None = None,
    reference_count: int = 0,
    preferred_backends: list[tuple[str, str]] | None = None,
) -> SelectionResult:
    """Select a backend that satisfies the given requirements.

    Args:
        operation: The video generation operation (e.g. "video.reference_to_video").
        requirements: Dict with optional keys: width, height, fps, duration_ms,
            native_audio, seed.
        registry: The BackendRegistry to query.
        media_types: Media types that will be used as input references.
        reference_count: Number of input references.
        preferred_backends: Ordered list of (backend_id, revision) preference.

    Returns:
        SelectionResult on success.

    Raises:
        SelectionFailure if no backend matches.
    """
    candidates = registry.query_by_operation(operation)
    rejections: list[RejectionReason] = []

    if not candidates:
        raise SelectionFailure(
            operation=operation,
            rejections=rejections,
            message=f"No backend registered for operation {operation!r}",
        )

    scored: list[tuple[int, CapabilityManifest]] = []
    for cap in candidates:
        reject = _check_candidate(cap, requirements, media_types, reference_count)
        if reject is not None:
            rejections.append(reject)
            continue
        score = _score_backend(cap, preferred_backends)
        scored.append((score, cap))

    if not scored:
        raise SelectionFailure(
            operation=operation,
            rejections=rejections,
            message=f"No backend satisfies requirements for {operation!r}",
        )

    # Sort by score descending (higher = more preferred)
    scored.sort(key=lambda x: x[0], reverse=True)
    _, best = scored[0]

    # Compute dropped references (optional refs beyond max_references)
    dropped: list[str] = []
    if reference_count > best.max_references:
        # This shouldn't happen because _check_candidate would reject,
        # but guard anyway.
        dropped = [f"ref-{i}" for i in range(best.max_references, reference_count)]

    return SelectionResult(
        backend_id=best.backend_id,
        revision=best.revision,
        workflow_hash=best.workflow_hash,
        rejections=rejections,
        dropped_references=dropped,
    )


def validate_sampling_requirements(
    operation: str,
    requirements: dict[str, Any],
    registry: BackendRegistry,
) -> None:
    """Validate an explicit sampling choice without resolving media assets.

    ``VideoRuntime.validate`` uses this small capability-only check so an
    unsupported profile or step count is reported before planning or a
    ComfyUI submission.  Legacy packages with both fields absent intentionally
    pass through to the handler's historical workflow defaults.
    """
    profile = requirements.get("sampler_profile")
    steps = requirements.get("steps")
    if profile is None and steps is None:
        return
    rejections: list[RejectionReason] = []
    for cap in registry.query_by_operation(operation):
        rejection = _check_sampling_candidate(cap, requirements)
        if rejection is None:
            return
        rejections.append(rejection)
    raise SelectionFailure(operation=operation, rejections=rejections)


def _check_candidate(
    cap: CapabilityManifest,
    requirements: dict[str, Any],
    media_types: list[str] | None,
    reference_count: int,
) -> RejectionReason | None:
    """Check if a candidate manifest satisfies requirements.

    Returns None if it passes, or a RejectionReason if it fails.
    """
    # Operation already filtered by registry query

    # Reference count
    if reference_count > cap.max_references:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="too_many_references",
            detail=f"{reference_count} > max {cap.max_references}",
        )

    # Media types
    if media_types:
        for mt in media_types:
            if not cap.accepts_media_type(mt):
                return RejectionReason(
                    backend_id=cap.backend_id,
                    revision=cap.revision,
                    reason="unsupported_media_type",
                    detail=mt,
                )

    # Duration
    req_duration = requirements.get("duration_ms")
    if req_duration is not None and cap.duration_constraints:
        dc = cap.duration_constraints
        min_d = dc.get("min_ms")
        max_d = dc.get("max_ms")
        if min_d is not None and req_duration < min_d:
            return RejectionReason(
                backend_id=cap.backend_id,
                revision=cap.revision,
                reason="duration_too_short",
                detail=f"{req_duration}ms < min {min_d}ms",
            )
        if max_d is not None and req_duration > max_d:
            return RejectionReason(
                backend_id=cap.backend_id,
                revision=cap.revision,
                reason="duration_too_long",
                detail=f"{req_duration}ms > max {max_d}ms",
            )

    # Resolution
    req_width = requirements.get("width")
    req_height = requirements.get("height")
    if (req_width is not None or req_height is not None) and cap.resolution_constraints:
        rc = cap.resolution_constraints
        if req_width is not None:
            min_w = rc.get("min_width")
            max_w = rc.get("max_width")
            if min_w is not None and req_width < min_w:
                return RejectionReason(
                    backend_id=cap.backend_id,
                    revision=cap.revision,
                    reason="width_too_small",
                    detail=f"{req_width} < min {min_w}",
                )
            if max_w is not None and req_width > max_w:
                return RejectionReason(
                    backend_id=cap.backend_id,
                    revision=cap.revision,
                    reason="width_too_large",
                    detail=f"{req_width} > max {max_w}",
                )
        if req_height is not None:
            min_h = rc.get("min_height")
            max_h = rc.get("max_height")
            if min_h is not None and req_height < min_h:
                return RejectionReason(
                    backend_id=cap.backend_id,
                    revision=cap.revision,
                    reason="height_too_small",
                    detail=f"{req_height} < min {min_h}",
                )
            if max_h is not None and req_height > max_h:
                return RejectionReason(
                    backend_id=cap.backend_id,
                    revision=cap.revision,
                    reason="height_too_large",
                    detail=f"{req_height} > max {max_h}",
                )

    # FPS
    req_fps = requirements.get("fps")
    if req_fps is not None and cap.fps_constraints:
        allowed = [float(f) for f in cap.fps_constraints]
        if float(req_fps) not in allowed:
            return RejectionReason(
                backend_id=cap.backend_id,
                revision=cap.revision,
                reason="unsupported_fps",
                detail=f"{req_fps} not in {allowed}",
            )

    # Native audio
    req_audio = requirements.get("native_audio")
    if req_audio == "required" and cap.native_audio_capability == "none":
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="native_audio_unsupported",
        )

    # Seed
    if requirements.get("seed") is not None and not cap.seed_capability:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="seed_unsupported",
        )

    sampling_rejection = _check_sampling_candidate(cap, requirements)
    if sampling_rejection is not None:
        return sampling_rejection

    return None


def _check_sampling_candidate(
    cap: CapabilityManifest,
    requirements: dict[str, Any],
) -> RejectionReason | None:
    """Check a backend's declared sampler profiles and step constraints."""
    profile = requirements.get("sampler_profile")
    steps = requirements.get("steps")
    if profile is None and steps is None:
        return None
    if profile is None or steps is None:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="sampling_fields_incomplete",
            detail="sampler_profile and steps must be provided together",
        )
    if not isinstance(profile, str) or not profile.strip():
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="unsupported_sampler_profile",
            detail="sampler_profile must be a non-empty string",
        )
    if isinstance(steps, bool) or not isinstance(steps, int):
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="invalid_sampling_steps",
            detail="steps must be an integer",
        )
    profiles = cap.extensions.get("sampling_profiles", {})
    profile_spec = profiles.get(profile) if isinstance(profiles, dict) else None
    if not isinstance(profile_spec, dict):
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="unsupported_sampler_profile",
            detail=profile,
        )
    minimum = profile_spec.get("min_steps")
    if isinstance(minimum, int) and steps < minimum:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="sampling_steps_too_small",
            detail=f"{steps} < min {minimum} for {profile}",
        )
    maximum = profile_spec.get("max_steps")
    if isinstance(maximum, int) and steps > maximum:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="sampling_steps_too_large",
            detail=f"{steps} > max {maximum} for {profile}",
        )
    allowed = profile_spec.get("allowed_steps")
    if isinstance(allowed, list) and steps not in allowed:
        return RejectionReason(
            backend_id=cap.backend_id,
            revision=cap.revision,
            reason="unsupported_sampling_steps",
            detail=f"{steps} not in {allowed} for {profile}",
        )
    return None


def _score_backend(
    cap: CapabilityManifest,
    preferred_backends: list[tuple[str, str]] | None,
) -> int:
    """Score a backend. Higher = more preferred.

    Preferred backends (explicitly listed) get a large bonus.
    Backends with exact reproducibility get a small bonus.
    """
    score = 0
    if preferred_backends:
        for i, (bid, rev) in enumerate(preferred_backends):
            if cap.backend_id == bid and cap.revision == rev:
                # Earlier in list = higher score
                score += 1000 - i * 100
                break
    if cap.reproducibility_claim == "exact":
        score += 10
    elif cap.reproducibility_claim == "best_effort":
        score += 5
    return score
