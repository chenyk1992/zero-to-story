"""LFO Storyboard Schema — the central creative document.

A Storyboard is the single source of truth for creative intent.
It is generated from an Intake, reviewed by the user, and consumed by
the Task Segmenter and Prompt Compilers.

Every entity uses a stable ID (not display index). Display indices are
computed at render time and never stored as identity.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Review status constants
# ---------------------------------------------------------------------------

REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

@dataclass
class ProjectInfo:
    """Top-level project metadata.

    On-disk layout is novel-centric: ``<workspace>/<novel_id>/<chapter_id>/``.
    The explicit ``novel_id`` and ``chapter_id`` fields are the authoritative
    source for path resolution. If either is missing, the code falls back
    to deriving it from ``project_id`` by splitting on the first ``-`` —
    so a storyboard that only sets ``project_id="我今天不上班-chapter_01"``
    still works, but a novel name that happens to contain ``-`` should
    set ``novel_id`` explicitly to avoid the ambiguity.
    """
    project_id: str = ""
    title: str = ""
    created_at: str = ""           # ISO 8601
    schema_version: str = "lfo.storyboard.v1"
    intake_ref: str = ""           # source intake project_id
    revision: int = 1              # incremented on each content change
    content_hash: str = ""         # LFO-CJ1 hash of the storyboard (computed)
    reference_character_order: list[str] = field(default_factory=list)  # stable char order for R2V
    # Novel-centric routing — optional. If set, used directly. If either is
    # empty, callers fall back to splitting project_id on the first '-'.
    # Unicode (e.g. Chinese) novel names work fine; the only ambiguity is
    # when the novel name itself contains '-'.
    novel_id: str = ""
    chapter_id: str = ""

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "intake_ref": self.intake_ref,
            "revision": self.revision,
            "content_hash": self.content_hash,
            "reference_character_order": self.reference_character_order,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectInfo:
        return cls(**data)


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------

@dataclass
class Story:
    """Narrative summary derived from intake."""
    logline: str = ""              # one-sentence summary
    synopsis: str = ""             # paragraph summary
    theme: str = ""                # central theme
    emotional_arc: str = ""        # how emotion changes across the film
    origin_source_ids: list[str] = field(default_factory=list)  # which intake sources

    def to_dict(self) -> dict:
        return {
            "logline": self.logline,
            "synopsis": self.synopsis,
            "theme": self.theme,
            "emotional_arc": self.emotional_arc,
            "origin_source_ids": self.origin_source_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Story:
        return cls(**data)


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

@dataclass
class StyleGuide:
    """Visual and tonal style specification."""
    visual_style: str = ""         # e.g. "cyberpunk realistic", "ghibli anime"
    color_palette: str = ""        # dominant colors
    lighting: str = ""             # lighting style
    mood: str = ""                 # overall mood
    reference_films: list[str] = field(default_factory=list)
    reference_artists: list[str] = field(default_factory=list)
    custom: dict = field(default_factory=dict)
    medium_lock: str = ""          # "Medium: ... NOT X, NOT Y."
    style_keywords: list[str] = field(default_factory=list)  # ["cinematic", "neon-lit"]

    def to_dict(self) -> dict:
        return {
            "visual_style": self.visual_style,
            "color_palette": self.color_palette,
            "lighting": self.lighting,
            "mood": self.mood,
            "reference_films": self.reference_films,
            "reference_artists": self.reference_artists,
            "custom": self.custom,
            "medium_lock": self.medium_lock,
            "style_keywords": self.style_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StyleGuide:
        return cls(**data)


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

@dataclass
class Character:
    """A character appearing in the story."""
    character_id: str = field(default_factory=lambda: f"char_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""          # physical appearance, personality
    role: str = ""                 # 'protagonist' | 'antagonist' | 'supporting' | 'extra'
    age: str = ""
    gender: str = ""
    distinguishing_features: str = ""  # key visual identifiers
    origin: str = ""               # origin tracking
    signature_action: str = ""     # 标志性动作/姿态
    key_prop: str = ""             # 关键道具（无则空）
    ref_asset_id: str = ""         # 生成的设定图 asset_id（回填）
    ref_image_path: str = ""       # agent 生图后的文件路径（回填）

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "age": self.age,
            "gender": self.gender,
            "distinguishing_features": self.distinguishing_features,
            "origin": self.origin,
            "signature_action": self.signature_action,
            "key_prop": self.key_prop,
            "ref_asset_id": self.ref_asset_id,
            "ref_image_path": self.ref_image_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Character:
        return cls(**data)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

@dataclass
class Scene:
    """A physical location where action takes place."""
    scene_id: str = field(default_factory=lambda: f"scene_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""          # location description
    time_of_day: str = ""          # 'day' | 'night' | 'dawn' | 'dusk'
    lighting: str = ""             # scene-specific lighting
    mood: str = ""
    environment: str = ""          # 'interior' | 'exterior'

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "time_of_day": self.time_of_day,
            "lighting": self.lighting,
            "mood": self.mood,
            "environment": self.environment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        return cls(**data)


# ---------------------------------------------------------------------------
# Prop
# ---------------------------------------------------------------------------

@dataclass
class Prop:
    """A significant object appearing in scenes."""
    prop_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    significance: str = ""         # why this prop matters

    def to_dict(self) -> dict:
        return {
            "prop_id": self.prop_id,
            "name": self.name,
            "description": self.description,
            "significance": self.significance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Prop:
        return cls(**data)


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

@dataclass
class Camera:
    """Camera specification for a shot."""
    shot_size: str = "medium"      # 'extreme_close_up' | 'close_up' | 'medium' | 'wide' | 'extreme_wide'
    angle: str = "eye_level"       # 'eye_level' | 'low' | 'high' | 'birds_eye' | 'worms_eye'
    movement: str = "static"       # 'static' | 'pan' | 'tilt' | 'dolly' | 'tracking' | 'crane' | 'handheld' | 'slow_push_in'
    focus: str = ""                # focus description

    def to_dict(self) -> dict:
        return {
            "shot_size": self.shot_size,
            "angle": self.angle,
            "movement": self.movement,
            "focus": self.focus,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Camera:
        return cls(**data)


# ---------------------------------------------------------------------------
# CharacterAppearance (character in a specific shot)
# ---------------------------------------------------------------------------

@dataclass
class CharacterAppearance:
    """A character's appearance and action within a specific shot."""
    character_id: str = ""
    screen_position: str = "center"  # 'left' | 'center' | 'right' | 'left_foreground' | 'right_midground' etc.
    orientation: str = "facing_camera"  # 'facing_camera' | 'facing_left' | 'facing_right' | 'back'
    action: str = ""               # what the character is doing
    expression: str = ""           # facial expression

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "screen_position": self.screen_position,
            "orientation": self.orientation,
            "action": self.action,
            "expression": self.expression,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CharacterAppearance:
        return cls(**data)


# ---------------------------------------------------------------------------
# ActionBeat
# ---------------------------------------------------------------------------

@dataclass
class ActionBeat:
    """A discrete action moment within a shot."""
    sequence: int = 0              # order within the shot
    description: str = ""          # what happens
    duration_ms: int = 0           # estimated duration

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "description": self.description,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ActionBeat:
        return cls(**data)


# ---------------------------------------------------------------------------
# ContinuityInfo
# ---------------------------------------------------------------------------

@dataclass
class ContinuityInfo:
    """Continuity tracking between shots."""
    start_state: str = ""          # state at the beginning of this shot
    end_state: str = ""            # state at the end of this shot
    previous_shot_id: str | None = None
    next_shot_id: str | None = None
    priority: str = "medium"       # 'high' | 'medium' | 'low'
    continuity_elements: list[str] = field(default_factory=list)  # e.g. ["costume:blue_jacket", "prop:umbrella"]
    start_frame_needed: bool = False  # True if first frame comes from previous shot's last frame

    def to_dict(self) -> dict:
        return {
            "start_state": self.start_state,
            "end_state": self.end_state,
            "previous_shot_id": self.previous_shot_id,
            "next_shot_id": self.next_shot_id,
            "priority": self.priority,
            "continuity_elements": self.continuity_elements,
            "start_frame_needed": self.start_frame_needed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContinuityInfo:
        return cls(**data)


# ---------------------------------------------------------------------------
# GenerationHint
# ---------------------------------------------------------------------------

@dataclass
class GenerationHint:
    """Hint for which generation mode to use (planning suggestion only)."""
    preferred_family: str = ""     # 'h3_fl2va' | 'h3_ref2va'
    preferred_mode: str = ""       # 't2va' | 'i2v' | 'first_last' | 'r2v'
    notes: str = ""                # why this hint

    def to_dict(self) -> dict:
        return {
            "preferred_family": self.preferred_family,
            "preferred_mode": self.preferred_mode,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GenerationHint:
        return cls(**data)


# ---------------------------------------------------------------------------
# Shot
# ---------------------------------------------------------------------------

@dataclass
class Shot:
    """A single shot in the storyboard."""
    shot_id: str = field(default_factory=lambda: f"shot_{uuid.uuid4().hex[:8]}")
    display_index: int = 0         # 1-based, for display only — NOT identity
    scene_id: str = ""
    desired_duration_ms: int = 5000
    camera: Camera = field(default_factory=Camera)
    characters: list[CharacterAppearance] = field(default_factory=list)
    action_beats: list[ActionBeat] = field(default_factory=list)
    narration: str = ""            # voiceover or dialogue text
    continuity: ContinuityInfo = field(default_factory=ContinuityInfo)
    generation_hint: GenerationHint = field(default_factory=GenerationHint)
    description: str = ""          # human-readable shot description

    def to_dict(self) -> dict:
        return {
            "shot_id": self.shot_id,
            "display_index": self.display_index,
            "scene_id": self.scene_id,
            "desired_duration_ms": self.desired_duration_ms,
            "camera": self.camera.to_dict(),
            "characters": [c.to_dict() for c in self.characters],
            "action_beats": [b.to_dict() for b in self.action_beats],
            "narration": self.narration,
            "continuity": self.continuity.to_dict(),
            "generation_hint": self.generation_hint.to_dict(),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Shot:
        camera = Camera.from_dict(data.pop("camera", {}))
        characters = [CharacterAppearance.from_dict(c) for c in data.pop("characters", [])]
        beats = [ActionBeat.from_dict(b) for b in data.pop("action_beats", [])]
        continuity = ContinuityInfo.from_dict(data.pop("continuity", {}))
        hint = GenerationHint.from_dict(data.pop("generation_hint", {}))
        return cls(
            camera=camera,
            characters=characters,
            action_beats=beats,
            continuity=continuity,
            generation_hint=hint,
            **data,
        )


# ---------------------------------------------------------------------------
# ContinuityChain
# ---------------------------------------------------------------------------

@dataclass
class ContinuityChain:
    """A chain of shots that share continuity."""
    chain_id: str = field(default_factory=lambda: f"chain_{uuid.uuid4().hex[:8]}")
    shot_ids: list[str] = field(default_factory=list)
    shared_elements: list[str] = field(default_factory=list)
    reference_character_order: list[str] = field(default_factory=list)  # char order for R2V in this chain

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "shot_ids": self.shot_ids,
            "shared_elements": self.shared_elements,
            "reference_character_order": self.reference_character_order,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContinuityChain:
        return cls(**data)


# ---------------------------------------------------------------------------
# AudioPolicy
# ---------------------------------------------------------------------------

@dataclass
class AudioPolicy:
    """Audio generation and assembly policy."""
    mode: str = "effects_only"     # 'effects_only' | 'full' | 'none'
    music: str = "none"            # 'none' | 'generated' | 'user_provided'
    sound_effects: str = "auto"    # 'none' | 'auto' | 'manual'
    dialogue: str = "none"         # 'none' | 'tts' | 'user_proferred'
    ambient: str = "auto"          # 'none' | 'auto'

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "music": self.music,
            "sound_effects": self.sound_effects,
            "dialogue": self.dialogue,
            "ambient": self.ambient,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AudioPolicy:
        return cls(**data)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@dataclass
class ReviewStatus:
    """Approval state of the storyboard."""
    status: str = REVIEW_PENDING   # 'pending' | 'approved' | 'rejected'
    approved_hash: str = ""        # content_hash at time of approval
    approved_revision: int = 0     # revision at time of approval
    approved_at: str = ""          # ISO 8601
    reviewer: str = ""             # who approved
    notes: str = ""                # reviewer notes

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "approved_hash": self.approved_hash,
            "approved_revision": self.approved_revision,
            "approved_at": self.approved_at,
            "reviewer": self.reviewer,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ReviewStatus:
        return cls(**data)


# ---------------------------------------------------------------------------
# Storyboard (top-level)
# ---------------------------------------------------------------------------

@dataclass
class Storyboard:
    """Complete storyboard document — single source of truth for creative intent.

    Attributes:
        project: top-level project info
        story: narrative summary
        style: visual style guide
        characters: list of characters
        scenes: list of scenes
        props: list of significant props
        shots: ordered list of shots
        continuity_chains: chains of shots sharing continuity
        audio_policy: audio generation policy
        review: approval status
        user_constraints: free-form user constraints
    """
    project: ProjectInfo = field(default_factory=lambda: ProjectInfo(project_id=""))
    story: Story = field(default_factory=Story)
    style: StyleGuide = field(default_factory=StyleGuide)
    characters: list[Character] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    continuity_chains: list[ContinuityChain] = field(default_factory=list)
    audio_policy: AudioPolicy = field(default_factory=AudioPolicy)
    review: ReviewStatus = field(default_factory=ReviewStatus)
    user_constraints: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project": self.project.to_dict(),
            "story": self.story.to_dict(),
            "style": self.style.to_dict(),
            "characters": [c.to_dict() for c in self.characters],
            "scenes": [s.to_dict() for s in self.scenes],
            "props": [p.to_dict() for p in self.props],
            "shots": [s.to_dict() for s in self.shots],
            "continuity_chains": [c.to_dict() for c in self.continuity_chains],
            "audio_policy": self.audio_policy.to_dict(),
            "review": self.review.to_dict(),
            "user_constraints": self.user_constraints,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Storyboard:
        # Top-level metadata keys that aren't dataclass fields. Pop them
        # first so the **data splat at the end doesn't blow up with
        # "unexpected keyword argument".
        data.pop("schema_version", None)
        data.pop("created_at", None)
        project = ProjectInfo.from_dict(data.pop("project", {}))
        story = Story.from_dict(data.pop("story", {}))
        style = StyleGuide.from_dict(data.pop("style", {}))
        characters = [Character.from_dict(c) for c in data.pop("characters", [])]
        scenes = [Scene.from_dict(s) for s in data.pop("scenes", [])]
        props = [Prop.from_dict(p) for p in data.pop("props", [])]
        shots = [Shot.from_dict(s) for s in data.pop("shots", [])]
        chains = [ContinuityChain.from_dict(c) for c in data.pop("continuity_chains", [])]
        audio = AudioPolicy.from_dict(data.pop("audio_policy", {}))
        review = ReviewStatus.from_dict(data.pop("review", {}))
        return cls(
            project=project, story=story, style=style,
            characters=characters, scenes=scenes, props=props,
            shots=shots, continuity_chains=chains,
            audio_policy=audio, review=review, **data,
        )

    def shot_by_id(self, shot_id: str) -> Shot | None:
        """Look up a shot by its stable ID."""
        for s in self.shots:
            if s.shot_id == shot_id:
                return s
        return None

    def character_by_id(self, character_id: str) -> Character | None:
        for c in self.characters:
            if c.character_id == character_id:
                return c
        return None

    def scene_by_id(self, scene_id: str) -> Scene | None:
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        return None

    def total_duration_ms(self) -> int:
        """Sum of all shot durations."""
        return sum(s.desired_duration_ms for s in self.shots)

    def display_index_for(self, shot_id: str) -> int:
        """Return the 1-based display index for a shot ID."""
        for i, s in enumerate(self.shots):
            if s.shot_id == shot_id:
                return i + 1
        return 0
