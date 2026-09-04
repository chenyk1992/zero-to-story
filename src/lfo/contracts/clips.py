"""ClipSpec — the atomic unit of video generation and local re-do.

A ``ClipSpec`` describes exactly one video generation. It carries its own
references, audio strategy, subtitles and dependencies so that a single clip
can be re-done without touching others.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .strict import ensure_allowed_fields
from .upscale import _raise_invalid_upscale_options

# Operations are open strings; these are the well-known v1 examples.
KNOWN_OPERATIONS = frozenset({
    "video.text_to_video",
    "video.image_to_video",
    "video.reference_to_video",
    "video.first_last_frame",
    "video.virtual_presenter",
    "video.passthrough",
})

# Placement values for BindingPolicy.
PLACEMENTS = frozenset({"any", "first", "last", "fixed"})

# on_unsupported values.
ON_UNSUPPORTED = frozenset({"fail", "drop"})

# native_audio strategies (for AudioPolicy).
NATIVE_AUDIO = frozenset({"preserve", "mute", "mix", "replace"})

# native_audio preferences (for GenerationRequirements).
# Open string — backend manifests constrain actual values.
NATIVE_AUDIO_PREFS = frozenset({"allowed", "required", "none"})


@dataclass
class BindingPolicy:
    """How a reference participates in a backend input.

    LFO does not guess priority or placement from semantic tags — the Skill
    must state them explicitly.
    """

    required: bool = True
    priority: int = 0
    placement: str = "any"
    on_unsupported: str = "fail"
    slot: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> BindingPolicy:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {"required", "priority", "placement", "on_unsupported", "slot"},
        )
        required = data.get("required", True)
        if not isinstance(required, bool):
            raise TypeError(f"{path}.required: expected boolean")
        priority = data.get("priority", 0)
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise TypeError(f"{path}.priority: expected integer")
        placement = data.get("placement", "any")
        if placement not in PLACEMENTS:
            raise ValueError(f"{path}.placement: must be one of {sorted(PLACEMENTS)}")
        on_unsupported = data.get("on_unsupported", "fail")
        if on_unsupported not in ON_UNSUPPORTED:
            raise ValueError(
                f"{path}.on_unsupported: must be one of {sorted(ON_UNSUPPORTED)}"
            )
        slot = data.get("slot")
        if slot is not None and not isinstance(slot, str):
            raise TypeError(f"{path}.slot: expected string or null")
        if placement == "fixed" and not slot:
            raise ValueError(f"{path}.slot: required when placement='fixed'")
        if required and on_unsupported == "drop":
            raise ValueError(
                f"{path}.on_unsupported: required reference cannot be 'drop'"
            )
        return cls(
            required=required,
            priority=priority,
            placement=placement,
            on_unsupported=on_unsupported,
            slot=slot,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.required is not True:
            d["required"] = self.required
        if self.priority != 0:
            d["priority"] = self.priority
        if self.placement != "any":
            d["placement"] = self.placement
        if self.on_unsupported != "fail":
            d["on_unsupported"] = self.on_unsupported
        if self.slot is not None:
            d["slot"] = self.slot
        return d


@dataclass
class ReferenceSpec:
    """A reference from a Clip to an input asset."""

    reference_id: str
    asset_key: str
    semantic_usage: str
    binding: BindingPolicy
    instruction: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ReferenceSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {"reference_id", "asset_key", "semantic_usage", "instruction", "binding"},
        )
        ref_id = data.get("reference_id")
        if not isinstance(ref_id, str) or not ref_id:
            raise ValueError(f"{path}.reference_id: required string")
        asset_key = data.get("asset_key")
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"{path}.asset_key: required string")
        semantic_usage = data.get("semantic_usage")
        if not isinstance(semantic_usage, str) or not semantic_usage.strip():
            raise ValueError(f"{path}.semantic_usage: required non-empty string")
        binding_data = data.get("binding")
        if not isinstance(binding_data, dict):
            raise ValueError(f"{path}.binding: required object")
        binding = BindingPolicy.from_dict(binding_data, f"{path}.binding")
        instruction = data.get("instruction")
        if instruction is not None and not isinstance(instruction, str):
            raise TypeError(f"{path}.instruction: expected string or null")
        return cls(
            reference_id=ref_id,
            asset_key=asset_key,
            semantic_usage=semantic_usage,
            binding=binding,
            instruction=instruction,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "reference_id": self.reference_id,
            "asset_key": self.asset_key,
            "semantic_usage": self.semantic_usage,
            "binding": self.binding.to_dict(),
        }
        if self.instruction is not None:
            d["instruction"] = self.instruction
        return d


@dataclass
class GenerationRequirements:
    """Output requirements that backends must satisfy."""

    aspect_ratio: str | None = None
    megapixels: float | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    native_audio: str | None = None
    reference_image_size: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> GenerationRequirements:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {
                "aspect_ratio",
                "megapixels",
                "width",
                "height",
                "fps",
                "native_audio",
                "reference_image_size",
            },
        )
        aspect_ratio = data.get("aspect_ratio")
        if aspect_ratio is not None and not isinstance(aspect_ratio, str):
            raise TypeError(f"{path}.aspect_ratio: expected string or null")
        megapixels = data.get("megapixels")
        megapixels_value: float | None = None
        if megapixels is not None:
            if isinstance(megapixels, bool) or not isinstance(megapixels, (int, float, str)):
                raise TypeError(f"{path}.megapixels: expected positive number")
            try:
                megapixels_value = float(megapixels)
            except (TypeError, ValueError, OverflowError):
                raise TypeError(f"{path}.megapixels: expected positive number") from None
            if not math.isfinite(megapixels_value) or megapixels_value <= 0:
                raise ValueError(f"{path}.megapixels: must be positive")
        width = data.get("width")
        if width is not None:
            if not isinstance(width, int) or isinstance(width, bool):
                raise TypeError(f"{path}.width: expected integer")
            if width <= 0:
                raise ValueError(f"{path}.width: must be positive")
        height = data.get("height")
        if height is not None:
            if not isinstance(height, int) or isinstance(height, bool):
                raise TypeError(f"{path}.height: expected integer")
            if height <= 0:
                raise ValueError(f"{path}.height: must be positive")
        if megapixels is not None and (width is not None or height is not None):
            raise ValueError(f"{path}.megapixels: cannot be combined with width or height")
        fps = data.get("fps")
        if fps is not None:
            if not isinstance(fps, int) or isinstance(fps, bool):
                raise TypeError(f"{path}.fps: expected integer")
            if fps <= 0:
                raise ValueError(f"{path}.fps: must be positive")
        native_audio = data.get("native_audio")
        if native_audio is not None:
            if not isinstance(native_audio, str):
                raise TypeError(f"{path}.native_audio: expected string or null")
        reference_image_size = data.get("reference_image_size")
        if reference_image_size is not None and reference_image_size not in {"match", "max"}:
            raise ValueError(f"{path}.reference_image_size: expected 'match' or 'max'")
        return cls(
            aspect_ratio=aspect_ratio,
            megapixels=megapixels_value,
            width=width,
            height=height,
            fps=fps,
            native_audio=native_audio,
            reference_image_size=reference_image_size,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.aspect_ratio is not None:
            d["aspect_ratio"] = self.aspect_ratio
        if self.megapixels is not None:
            d["megapixels"] = format(self.megapixels, ".15g")
        if self.width is not None:
            d["width"] = self.width
        if self.height is not None:
            d["height"] = self.height
        if self.fps is not None:
            d["fps"] = self.fps
        if self.native_audio is not None:
            d["native_audio"] = self.native_audio
        if self.reference_image_size is not None:
            d["reference_image_size"] = self.reference_image_size
        return d


@dataclass
class GenerationSpec:
    """What to generate and how."""

    operation: str
    prompt: str
    references: list[ReferenceSpec] = field(default_factory=list)
    seed: int | None = None
    requirements: GenerationRequirements = field(default_factory=GenerationRequirements)

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> GenerationSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {"operation", "prompt", "seed", "requirements", "references"},
        )
        operation = data.get("operation")
        if not isinstance(operation, str) or not operation:
            raise ValueError(f"{path}.operation: required string")
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError(f"{path}.prompt: required string")
        if operation not in KNOWN_OPERATIONS:
            raise ValueError(f"{path}.operation: unsupported video operation {operation!r}")
        seed = data.get("seed")
        if seed is not None:
            if not isinstance(seed, int) or isinstance(seed, bool):
                raise TypeError(f"{path}.seed: expected integer")
        refs_data = data.get("references", [])
        if not isinstance(refs_data, list):
            raise TypeError(f"{path}.references: expected array")
        references = [
            ReferenceSpec.from_dict(r, f"{path}.references[{i}]")
            for i, r in enumerate(refs_data)
        ]
        seen_reference_ids: set[str] = set()
        for index, reference in enumerate(references):
            if reference.reference_id in seen_reference_ids:
                raise ValueError(
                    f"{path}.references[{index}].reference_id: duplicate reference_id "
                    f"{reference.reference_id!r}"
                )
            seen_reference_ids.add(reference.reference_id)
        req_data = data.get("requirements", {})
        if not isinstance(req_data, dict):
            raise TypeError(f"{path}.requirements: expected object")
        requirements = GenerationRequirements.from_dict(req_data, f"{path}.requirements")
        return cls(
            operation=operation,
            prompt=prompt,
            references=references,
            seed=seed,
            requirements=requirements,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"operation": self.operation, "prompt": self.prompt}
        if self.seed is not None:
            d["seed"] = self.seed
        d["requirements"] = self.requirements.to_dict()
        if self.references:
            d["references"] = [r.to_dict() for r in self.references]
        return d


@dataclass
class AudioTrackSpec:
    """An external audio track to be mixed."""

    asset_key: str
    role: str
    offset_ms: int = 0
    gain_db: str = "0"
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    duck_group: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> AudioTrackSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {
                "asset_key",
                "role",
                "offset_ms",
                "gain_db",
                "fade_in_ms",
                "fade_out_ms",
                "duck_group",
            },
        )
        asset_key = data.get("asset_key")
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"{path}.asset_key: required string")
        role = data.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"{path}.role: required non-empty string")
        offset_ms = data.get("offset_ms", 0)
        if not isinstance(offset_ms, int) or isinstance(offset_ms, bool):
            raise TypeError(f"{path}.offset_ms: expected integer")
        gain_db = data.get("gain_db", "0")
        if not isinstance(gain_db, str):
            raise TypeError(f"{path}.gain_db: expected string")
        try:
            gain_value = float(gain_db)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{path}.gain_db: expected a finite number") from None
        if not math.isfinite(gain_value):
            raise ValueError(f"{path}.gain_db: expected a finite number")
        fade_in_ms = data.get("fade_in_ms", 0)
        if not isinstance(fade_in_ms, int) or isinstance(fade_in_ms, bool):
            raise TypeError(f"{path}.fade_in_ms: expected integer")
        if offset_ms < 0:
            raise ValueError(f"{path}.offset_ms: must be >= 0")
        if fade_in_ms < 0:
            raise ValueError(f"{path}.fade_in_ms: must be >= 0")
        fade_out_ms = data.get("fade_out_ms", 0)
        if not isinstance(fade_out_ms, int) or isinstance(fade_out_ms, bool):
            raise TypeError(f"{path}.fade_out_ms: expected integer")
        if fade_out_ms < 0:
            raise ValueError(f"{path}.fade_out_ms: must be >= 0")
        duck_group = data.get("duck_group")
        if duck_group is not None and not isinstance(duck_group, str):
            raise TypeError(f"{path}.duck_group: expected string or null")
        return cls(
            asset_key=asset_key,
            role=role,
            offset_ms=offset_ms,
            gain_db=gain_db,
            fade_in_ms=fade_in_ms,
            fade_out_ms=fade_out_ms,
            duck_group=duck_group,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "asset_key": self.asset_key,
            "role": self.role,
            "offset_ms": self.offset_ms,
            "gain_db": self.gain_db,
            "fade_in_ms": self.fade_in_ms,
            "fade_out_ms": self.fade_out_ms,
        }
        if self.duck_group is not None:
            d["duck_group"] = self.duck_group
        return d


@dataclass
class AudioPolicy:
    """Native audio strategy + external tracks."""

    native_audio: str = "preserve"
    tracks: list[AudioTrackSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> AudioPolicy:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"native_audio", "tracks"})
        native_audio = data.get("native_audio", "preserve")
        if native_audio not in NATIVE_AUDIO:
            raise ValueError(
                f"{path}.native_audio: must be one of {sorted(NATIVE_AUDIO)}"
            )
        tracks_data = data.get("tracks", [])
        if not isinstance(tracks_data, list):
            raise TypeError(f"{path}.tracks: expected array")
        tracks = [
            AudioTrackSpec.from_dict(t, f"{path}.tracks[{i}]")
            for i, t in enumerate(tracks_data)
        ]
        return cls(native_audio=native_audio, tracks=tracks)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"native_audio": self.native_audio}
        if self.tracks:
            d["tracks"] = [t.to_dict() for t in self.tracks]
        return d


@dataclass
class SubtitleCue:
    """A single timed subtitle cue."""

    start_ms: int
    end_ms: int
    text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> SubtitleCue:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"start_ms", "end_ms", "text"})
        start_ms = data.get("start_ms")
        if not isinstance(start_ms, int) or isinstance(start_ms, bool):
            raise TypeError(f"{path}.start_ms: expected integer")
        if start_ms < 0:
            raise ValueError(f"{path}.start_ms: must be >= 0")
        end_ms = data.get("end_ms")
        if not isinstance(end_ms, int) or isinstance(end_ms, bool):
            raise TypeError(f"{path}.end_ms: expected integer")
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{path}.text: required non-empty string")
        if end_ms <= start_ms:
            raise ValueError(f"{path}.end_ms: must be greater than start_ms")
        return cls(start_ms=start_ms, end_ms=end_ms, text=text)

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms, "text": self.text}


@dataclass
class SubtitleSpec:
    """Subtitle input: timed cues, external asset, or both."""

    cues: list[SubtitleCue] = field(default_factory=list)
    asset_key: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> SubtitleSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(data, path, {"cues", "asset_key"})
        cues_data = data.get("cues", [])
        if not isinstance(cues_data, list):
            raise TypeError(f"{path}.cues: expected array")
        cues = [
            SubtitleCue.from_dict(c, f"{path}.cues[{i}]")
            for i, c in enumerate(cues_data)
        ]
        previous_end = 0
        for index, cue in enumerate(cues):
            if cue.start_ms < previous_end:
                raise ValueError(
                    f"{path}.cues[{index}].start_ms: overlaps the previous cue"
                )
            previous_end = cue.end_ms
        asset_key = data.get("asset_key")
        if asset_key is not None and not isinstance(asset_key, str):
            raise TypeError(f"{path}.asset_key: expected string or null")
        return cls(cues=cues, asset_key=asset_key)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.cues:
            d["cues"] = [c.to_dict() for c in self.cues]
        if self.asset_key is not None:
            d["asset_key"] = self.asset_key
        return d


@dataclass
class ClipSpec:
    """Atomic video generation and local re-do unit."""

    clip_id: str
    sequence: int
    duration_ms: int
    generation: GenerationSpec
    audio: AudioPolicy = field(default_factory=AudioPolicy)
    subtitles: SubtitleSpec = field(default_factory=SubtitleSpec)
    dependencies: list[str] = field(default_factory=list)
    source_context: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        path: str,
        *,
        _validate_upscale: bool = True,
    ) -> ClipSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        ensure_allowed_fields(
            data,
            path,
            {
                "clip_id",
                "sequence",
                "duration_ms",
                "generation",
                "audio",
                "subtitles",
                "dependencies",
                "source_context",
                "extensions",
            },
        )
        clip_id = data.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id:
            raise ValueError(f"{path}.clip_id: required string")
        # Keep the public contract aligned with the artifact layout: clip IDs
        # are path components, never paths.  Import lazily to avoid the
        # artifact-layout module's contract import cycle.
        from lfo.services.artifact_layout import ArtifactLayoutError, safe_component

        try:
            safe_component(clip_id, field="clip_id")
        except ArtifactLayoutError as exc:
            raise ValueError(f"{path}.clip_id: {exc}") from exc
        sequence = data.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise TypeError(f"{path}.sequence: expected integer")
        if sequence < 1:
            raise ValueError(f"{path}.sequence: must be >= 1")
        duration_ms = data.get("duration_ms")
        if not isinstance(duration_ms, int) or isinstance(duration_ms, bool):
            raise TypeError(f"{path}.duration_ms: expected integer")
        if duration_ms <= 0:
            raise ValueError(f"{path}.duration_ms: must be positive")
        gen_data = data.get("generation")
        if not isinstance(gen_data, dict):
            raise ValueError(f"{path}.generation: required object")
        generation = GenerationSpec.from_dict(gen_data, f"{path}.generation")
        audio = AudioPolicy.from_dict(
            data.get("audio", {}), f"{path}.audio"
        )
        subtitles = SubtitleSpec.from_dict(
            data.get("subtitles", {}), f"{path}.subtitles"
        )
        for index, cue in enumerate(subtitles.cues):
            if cue.end_ms > duration_ms:
                raise ValueError(
                    f"{path}.subtitles.cues[{index}].end_ms: exceeds clip duration"
                )
        deps = data.get("dependencies", [])
        if not isinstance(deps, list):
            raise TypeError(f"{path}.dependencies: expected array")
        for i, d_item in enumerate(deps):
            if not isinstance(d_item, str):
                raise TypeError(f"{path}.dependencies[{i}]: expected string")
        source_context = data.get("source_context", {})
        if not isinstance(source_context, dict):
            raise TypeError(f"{path}.source_context: expected object")
        extensions = data.get("extensions", {})
        if not isinstance(extensions, dict):
            raise TypeError(f"{path}.extensions: expected object")
        if _validate_upscale and "upscale" in extensions:
            _raise_invalid_upscale_options(
                extensions["upscale"],
                f"{path}.extensions.upscale",
            )
        return cls(
            clip_id=clip_id,
            sequence=sequence,
            duration_ms=duration_ms,
            generation=generation,
            audio=audio,
            subtitles=subtitles,
            dependencies=deps,
            source_context=source_context,
            extensions=extensions,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "clip_id": self.clip_id,
            "sequence": self.sequence,
            "duration_ms": self.duration_ms,
            "generation": self.generation.to_dict(),
        }
        audio_dict = self.audio.to_dict()
        if audio_dict:
            d["audio"] = audio_dict
        subtitles_dict = self.subtitles.to_dict()
        if subtitles_dict:
            d["subtitles"] = subtitles_dict
        if self.dependencies:
            d["dependencies"] = list(self.dependencies)
        if self.source_context:
            d["source_context"] = dict(self.source_context)
        if self.extensions:
            d["extensions"] = dict(self.extensions)
        return d
