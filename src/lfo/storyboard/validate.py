"""LFO Storyboard validation — structural and semantic checks.

Validates intake and storyboard documents against their schemas.
Returns structured error reports with JSON Pointer paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .storyboard import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
)


@dataclass
class ValidationError:
    """A single validation error."""
    path: str          # JSON Pointer path, e.g. "/shots/0/camera/shot_size"
    message: str       # human-readable error message
    severity: str = "error"  # 'error' | 'warning'

    def to_dict(self) -> dict:
        return {"path": self.path, "message": self.message, "severity": self.severity}


@dataclass
class ValidationResult:
    """Result of a validation pass."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(ValidationError(path=path, message=message, severity="error"))
        self.valid = False

    def add_warning(self, path: str, message: str) -> None:
        self.warnings.append(ValidationError(path=path, message=message, severity="warning"))

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def validate_intake(data: dict) -> ValidationResult:
    """Validate an intake dict against the intake schema."""
    result = ValidationResult(valid=True)

    # Required fields
    if "sources" not in data or not data["sources"]:
        result.add_error("/sources", "At least one input source is required")

    if "constraints" not in data:
        result.add_error("/constraints", "Constraints section is required")

    # Validate each source
    for i, src in enumerate(data.get("sources", [])):
        prefix = f"/sources/{i}"
        if not src.get("source_id"):
            result.add_error(f"{prefix}/source_id", "source_id is required")
        if not src.get("type"):
            result.add_error(f"{prefix}/type", "type is required")
        elif src["type"] not in ("creative_brief", "story_synopsis", "screenplay"):
            result.add_error(f"{prefix}/type", f"Invalid source type: {src['type']}")
        if not src.get("content"):
            result.add_error(f"{prefix}/content", "content is required")

    # Validate constraints
    constraints = data.get("constraints", {})
    if "target_duration_ms" in constraints:
        if constraints["target_duration_ms"] <= 0:
            result.add_error("/constraints/target_duration_ms", "Must be positive")
        if constraints["target_duration_ms"] > 600000:  # 10 minutes
            result.add_warning("/constraints/target_duration_ms",
                               "Duration exceeds 10 minutes — may be too long for MVP")

    if "aspect_ratio" in constraints:
        valid_ratios = ("9:16", "16:9", "1:1", "4:3", "21:9")
        if constraints["aspect_ratio"] not in valid_ratios:
            result.add_error("/constraints/aspect_ratio",
                             f"Invalid aspect ratio. Must be one of: {valid_ratios}")

    if "max_characters" in constraints:
        if constraints["max_characters"] < 1:
            result.add_error("/constraints/max_characters", "Must be at least 1")
        if constraints["max_characters"] > 5:
            result.add_warning("/constraints/max_characters",
                               "More than 5 characters may exceed MVP scope")

    if "max_scenes" in constraints:
        if constraints["max_scenes"] < 1:
            result.add_error("/constraints/max_scenes", "Must be at least 1")

    return result


def validate_storyboard(data: dict) -> ValidationResult:
    """Validate a storyboard dict against the storyboard schema."""
    result = ValidationResult(valid=True)

    # Required top-level sections
    for section in ("project", "story", "beats", "panels"):
        if section not in data:
            result.add_error(f"/{section}", f"Required section '{section}' is missing")

    # Project
    project = data.get("project", {})
    if not project.get("project_id"):
        result.add_error("/project/project_id", "project_id is required")

    # Beats
    beats = data.get("beats", [])
    if not beats:
        result.add_error("/beats", "At least one beat is required")

    character_ids = {c.get("character_id") for c in data.get("characters", [])}
    scene_ids = {s.get("scene_id") for s in data.get("scenes", [])}
    beat_ids = {b.get("beat_id") for b in beats}

    for i, beat in enumerate(beats):
        prefix = f"/beats/{i}"
        if not beat.get("beat_id"):
            result.add_error(f"{prefix}/beat_id", "beat_id is required")
        if not beat.get("scene_id"):
            result.add_error(f"{prefix}/scene_id", "scene_id is required")

        for j, char_app in enumerate(beat.get("characters", [])):
            cid = char_app.get("character_id")
            if cid and cid not in character_ids:
                result.add_error(
                    f"{prefix}/characters/{j}/character_id",
                    f"Character '{cid}' not found in storyboard.characters",
                )

        if beat.get("scene_id") and beat["scene_id"] not in scene_ids:
            result.add_error(
                f"{prefix}/scene_id",
                f"Scene '{beat['scene_id']}' not found in storyboard.scenes",
            )

    # Panels
    panels = data.get("panels", [])
    if not panels:
        result.add_error("/panels", "At least one panel is required")

    for i, panel in enumerate(panels):
        prefix = f"/panels/{i}"
        if not panel.get("panel_id"):
            result.add_error(f"{prefix}/panel_id", "panel_id is required")
        if panel.get("desired_duration_ms", 0) <= 0:
            result.add_error(f"{prefix}/desired_duration_ms", "Must be positive")

        for bid in panel.get("beat_ids", []):
            if bid and bid not in beat_ids:
                result.add_error(
                    f"{prefix}/beat_ids",
                    f"beat_id '{bid}' not found in storyboard.beats",
                )

    # Review status
    review = data.get("review", {})
    valid_statuses = (REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED)
    if review.get("status") and review["status"] not in valid_statuses:
        result.add_error("/review/status", f"Invalid status. Must be one of: {valid_statuses}")

    return result
