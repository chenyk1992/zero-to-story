"""LFO Intake Schema — user input for storyboard generation.

Three entry modes:
- creative_brief: short description of the desired film
- story_synopsis: longer narrative summary
- screenplay: structured script with scenes and dialogue

Every piece of content tracks its origin:
- ORIGIN_USER: explicitly provided by the user
- ORIGIN_AGENT_INFERRED: logically derived from user input
- ORIGIN_AGENT_HYPOTHESIS: assumed by agent to fill gaps
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from lfo.planning.panel_density import beat_count_for_duration_ms

# ---------------------------------------------------------------------------
# Origin constants
# ---------------------------------------------------------------------------

ORIGIN_USER = "user"
ORIGIN_AGENT_INFERRED = "agent_inferred"
ORIGIN_AGENT_HYPOTHESIS = "agent_hypothesis"


# ---------------------------------------------------------------------------
# Input source types
# ---------------------------------------------------------------------------

class InputSourceType:
    CREATIVE_BRIEF = "creative_brief"
    STORY_SYNOPSIS = "story_synopsis"
    SCREENPLAY = "screenplay"


# ---------------------------------------------------------------------------
# Origin tracking
# ---------------------------------------------------------------------------

@dataclass
class Origin:
    """Tracks where a piece of content came from."""
    source: str = ORIGIN_USER  # ORIGIN_USER | ORIGIN_AGENT_INFERRED | ORIGIN_AGENT_HYPOTHESIS
    confidence: str = "high"   # 'high' | 'medium' | 'low'
    derived_from: list[str] = field(default_factory=list)  # source_ids this was derived from
    reason: str = ""           # why the agent inferred/hypothesized this

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "derived_from": self.derived_from,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Origin:
        return cls(**data)


# ---------------------------------------------------------------------------
# Intake source (one input)
# ---------------------------------------------------------------------------

@dataclass
class IntakeSource:
    """A single user-provided input."""
    source_id: str = ""
    type: str = ""     # creative_brief | story_synopsis | screenplay
    content: str = ""  # the actual text
    origin: str = ORIGIN_USER
    metadata: dict = field(default_factory=dict)  # extra info (filename, URL, etc.)

    def __post_init__(self):
        if not self.source_id:
            self.source_id = f"source_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "type": self.type,
            "content": self.content,
            "origin": self.origin,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntakeSource:
        return cls(**data)


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

@dataclass
class IntakeConstraints:
    """User-specified constraints for the film."""
    target_duration_ms: int = 30000       # total duration in milliseconds
    aspect_ratio: str = "9:16"            # "9:16" | "16:9" | "1:1" | "4:3"
    delivery_width: int = 1080            # output width in pixels
    delivery_height: int = 1920           # output height in pixels
    language: str = "zh-CN"               # primary language
    visual_style: str = ""                # e.g. "cyberpunk realistic", "anime"
    medium_lock: str = ""                 # 硬风格约束（可选，有明确偏好时指定）
    max_characters: int = 2               # max unique characters
    max_scenes: int = 1                   # max unique scenes
    pacing: str = "medium"                # 'slow' | 'medium' | 'fast'
    mood: str = ""                        # e.g. "tense", "melancholic", "hopeful"
    audio_policy: str = "effects_only"    # 'effects_only' | 'full' | 'none'
    custom: dict = field(default_factory=dict)  # user-defined extra constraints

    def beat_count_target(self) -> int:
        """Target narrative beat count for decompose (Hub density).

        ``custom.shot_count_target`` is the handoff alias; ``beat_count_target``
        is accepted as an explicit override. Otherwise derive from duration.
        """
        custom = self.custom or {}
        if "shot_count_target" in custom:
            return int(custom["shot_count_target"])
        if "beat_count_target" in custom:
            return int(custom["beat_count_target"])
        return beat_count_for_duration_ms(self.target_duration_ms)

    def to_dict(self) -> dict:
        return {
            "target_duration_ms": self.target_duration_ms,
            "aspect_ratio": self.aspect_ratio,
            "delivery_width": self.delivery_width,
            "delivery_height": self.delivery_height,
            "language": self.language,
            "visual_style": self.visual_style,
            "medium_lock": self.medium_lock,
            "max_characters": self.max_characters,
            "max_scenes": self.max_scenes,
            "pacing": self.pacing,
            "mood": self.mood,
            "audio_policy": self.audio_policy,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntakeConstraints:
        return cls(**data)


# ---------------------------------------------------------------------------
# Intake (top-level)
# ---------------------------------------------------------------------------

@dataclass
class Intake:
    """Complete user input for storyboard generation.

    Attributes:
        schema_version: schema version for forward compatibility
        project_id: stable project identifier
        sources: list of input sources (at least one)
        constraints: user-specified constraints
        origin: where this intake came from
    """
    schema_version: str = "lfo.intake.v1"
    project_id: str = field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:12]}")
    sources: list[IntakeSource] = field(default_factory=list)
    constraints: IntakeConstraints = field(default_factory=IntakeConstraints)
    origin: Origin = field(default_factory=Origin)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "sources": [s.to_dict() for s in self.sources],
            "constraints": self.constraints.to_dict(),
            "origin": self.origin.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Intake:
        sources = [IntakeSource.from_dict(s) for s in data.pop("sources", [])]
        constraints = IntakeConstraints.from_dict(data.pop("constraints", {}))
        origin = Origin.from_dict(data.pop("origin", {}))
        return cls(sources=sources, constraints=constraints, origin=origin, **data)

    def add_source(self, source_type: str, content: str, source_id: str = "",
                   origin: str = ORIGIN_USER, metadata: dict = None) -> IntakeSource:
        """Convenience: add an input source and return it."""
        src = IntakeSource(
            source_id=source_id,
            type=source_type,
            content=content,
            origin=origin,
            metadata=metadata or {},
        )
        self.sources.append(src)
        return src

    def primary_text(self) -> str:
        """Return the primary text content (first source)."""
        return self.sources[0].content if self.sources else ""
