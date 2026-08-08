"""StoryboardDecomposer — turn an Intake into a Storyboard via LLM.

This module is the bridge between narrative intent (Intake) and structured
production data (Storyboard.beats + Storyboard.panels). The decomposer:

1. Builds a prompt from the Intake, Characters, Scenes, and Style.
2. Calls the LLM via the ``LLMClient`` protocol (default: ``MmxLLMClient``).
3. Parses the LLM output and validates it against the decompose schema.
4. Merges the new scenes/props/beats with the existing Storyboard (project,
   story, style, characters, audio_policy, review) and resolves scene
   references: beats may reference existing scenes (by id) or new scenes
   (declared in the LLM payload).
5. Returns a :class:`Storyboard` with beats, derived panels, scenes, and props set.

Failures are loud: the decomposer raises
:class:`lfo.storyboard.decompose_schema.DecomposeSchemaError` (or its own
:class:`DecomposeError`) and does NOT silently fall back to a stub storyboard.

The LLM client is injectable for testing — tests use a ``FakeLLMClient``
that returns canned responses.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .decompose_schema import (
    DecomposePayload,
    DecomposeSchemaError,
    parse_llm_output,
    validate_llm_payload,
)
from .intake import Intake
from .panel_plan import derive_panels_from_beats
from .storyboard import (
    ActionBeat,
    AudioPolicy,
    Beat,
    Camera,
    Character,
    CharacterAppearance,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Scene,
    Shot,
    Story,
    Storyboard,
    StyleGuide,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DecomposeError(RuntimeError):
    """Top-level error for decomposition failures."""


# ---------------------------------------------------------------------------
# LLM client protocol
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    """Anything that can take a prompt and return a string.

    Implementations include :class:`MmxLLMClient` (production) and
    ``FakeLLMClient`` (tests).
    """

    def complete(self, system: str, user: str) -> str: ...


# ---------------------------------------------------------------------------
# mmx-backed LLM client
# ---------------------------------------------------------------------------


@dataclass
class MmxLLMClient:
    """Calls the local ``mmx`` CLI (MiniMax Messages API)."""

    model: str = "MiniMax-M3"
    max_tokens: int = 4096
    temperature: float = 0.4
    timeout_sec: int = 300
    mmx_path: str = "mmx"  # allow override for tests

    def complete(self, system: str, user: str) -> str:
        mmx = shutil.which(self.mmx_path) or self.mmx_path

        # Build messages JSON. The user content can be large, so we use
        # --messages-file (- for stdin) to avoid Windows ARG_MAX and any
        # quoting surprises with embedded newlines / quotes.
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as fh:
            json.dump(messages, fh, ensure_ascii=False)
            messages_path = fh.name

        try:
            cmd = [
                mmx, "text", "chat",
                "--model", self.model,
                "--messages-file", messages_path,
                "--max-tokens", str(self.max_tokens),
                "--temperature", str(self.temperature),
                "--no-color",
                "--non-interactive",
                "--quiet",
                "--output", "text",
            ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
            except FileNotFoundError as exc:
                raise DecomposeError(
                    f"mmx CLI not found at {mmx!r}. "
                    f"Install with: npm install -g @MiniMax/mmx-cli"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise DecomposeError(
                    f"mmx call timed out after {self.timeout_sec}s"
                ) from exc
        finally:
            try:
                Path(messages_path).unlink()
            except OSError:
                pass

        if result.returncode != 0:
            raise DecomposeError(
                f"mmx failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
            )

        return self._extract_text(result.stdout)

    @staticmethod
    def _extract_text(raw: str) -> str:
        """Extract the assistant text from the mmx response.

        With --output text, mmx returns the assistant text directly. But
        depending on the version it may wrap it in ``{"response": "..."}`` or
        even the full JSON envelope. We try to peel the envelope; if that
        fails, return the raw stripped text.
        """
        text = raw.strip()
        if not text:
            return text

        # If it looks like JSON, try to extract the assistant content
        if text.startswith("{"):
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                return text

            # {"response": "..."} wrapper
            if isinstance(obj, dict) and isinstance(obj.get("response"), str):
                return obj["response"]

            # Full message envelope: {content: [{type: "text", text: "..."}]}
            content = obj.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]

        return text


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


_PROMPT_PATH = Path(__file__).parent / "prompts" / "decompose_v1.j2"


def _format_characters(characters: list[Character]) -> str:
    if not characters:
        return "(none — invent characters if the story requires them; the pipeline will require a character_id and you can pick any char_<id> — but note that downstream rendering cannot match an undeclared character)"
    lines = []
    for c in characters:
        lines.append(
            f"- {c.character_id} | name={c.name!r} | role={c.role!r} | "
            f"age={c.age!r} | gender={c.gender!r} | "
            f"distinguishing_features={c.distinguishing_features!r} | "
            f"description={c.description!r}"
        )
    return "\n".join(lines)


def _format_scenes(scenes: list[Scene]) -> str:
    if not scenes:
        return "(none — invent all scenes yourself; declare each new one in `scenes[]`)"
    lines = []
    for s in scenes:
        lines.append(
            f"- {s.scene_id} | name={s.name!r} | time_of_day={s.time_of_day!r} | "
            f"environment={s.environment!r} | lighting={s.lighting!r} | mood={s.mood!r}"
        )
    return "\n".join(lines)


def _format_style(style: StyleGuide) -> str:
    return (
        f"visual_style={style.visual_style!r}\n"
        f"color_palette={style.color_palette!r}\n"
        f"lighting={style.lighting!r}\n"
        f"mood={style.mood!r}\n"
        f"reference_films={style.reference_films}\n"
        f"reference_artists={style.reference_artists}"
    )


def _read_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_prompt(
    intake: Intake,
    project: ProjectInfo,
    story: Story,
    style: StyleGuide,
    characters: list[Character],
    scenes: list[Scene],
    logline: str,
) -> tuple[str, str]:
    """Build the (system, user) prompt pair for the LLM."""
    constraints = intake.constraints
    primary = intake.primary_text() or story.synopsis
    template = _read_prompt_template()

    user = template
    replacements = {
        "{{ project_title }}": project.title or "(untitled)",
        "{{ style_block }}": _format_style(style),
        "{{ medium_lock }}": style.medium_lock or "(none — infer from style)",
        "{{ style_keywords }}": ", ".join(style.style_keywords) if style.style_keywords else "(none)",
        "{{ characters_block }}": _format_characters(characters),
        "{{ scenes_block }}": _format_scenes(scenes),
        "{{ synopsis }}": primary,
        "{{ logline }}": logline or story.logline or "(none)",
        "{{ emotional_arc }}": story.emotional_arc or constraints.mood or "(none)",
        "{{ target_duration_ms }}": str(constraints.target_duration_ms),
        "{{ aspect_ratio }}": constraints.aspect_ratio,
        "{{ language }}": constraints.language,
        "{{ pacing }}": constraints.pacing,
        "{{ mood }}": constraints.mood,
        "{{ audio_policy }}": constraints.audio_policy,
    }
    for placeholder, value in replacements.items():
        user = user.replace(placeholder, value)

    system = (
        "You are a cinematographer producing JSON for a video generation "
        "pipeline. You ALWAYS respond with one valid JSON object. No prose, "
        "no markdown fences, no explanations. Your first character is `{` "
        "and your last character is `}`."
    )
    return system, user


# ---------------------------------------------------------------------------
# Scene resolution
# ---------------------------------------------------------------------------


def _resolve_scene_refs(
    payload: DecomposePayload, existing_scenes: list[Scene]
) -> tuple[list[Scene], dict[str, str]]:
    """Reconcile payload.new_scenes with existing_scenes.

    Returns the merged scene list and a map from LLM-declared scene_ids
    to the final scene_ids in the merged list. If a payload shot referenced
    a scene by ID that already exists, the mapping is identity.
    """
    existing_by_id = {s.scene_id: s for s in existing_scenes}
    merged: list[Scene] = list(existing_scenes)
    remap: dict[str, str] = {}

    for new_scene in payload.new_scenes:
        declared_id = new_scene["scene_id"]
        if declared_id in existing_by_id:
            # LLM reused an existing id; keep it
            remap[declared_id] = declared_id
            continue
        # New scene — create it
        scene = Scene.from_dict(new_scene)
        # Guard against collisions with a different scene already in the merged list
        if any(s.scene_id == scene.scene_id for s in merged):
            scene.scene_id = f"scene_{uuid.uuid4().hex[:8]}"
        merged.append(scene)
        remap[declared_id] = scene.scene_id

    return merged, remap


# ---------------------------------------------------------------------------
# Shot conversion
# ---------------------------------------------------------------------------


def _convert_shot_to_beat(shot_dict: dict, scene_id_remap: dict[str, str], sequence: int) -> Beat:
    """Convert a validated LLM shot dict into a Beat."""
    shot_dict = dict(shot_dict)
    scene_id = shot_dict.get("scene_id", "")
    scene_id = scene_id_remap.get(scene_id, scene_id)
    camera = shot_dict.get("camera", {})
    framing = camera.get("shot_size", "medium")
    characters = [CharacterAppearance.from_dict(c) for c in shot_dict.get("characters", [])]
    sounds = [
        b.get("description", "")
        for b in shot_dict.get("action_beats", [])
        if b.get("description")
    ]
    return Beat(
        beat_id=shot_dict.get("shot_id", f"beat_{uuid.uuid4().hex[:8]}"),
        sequence=sequence,
        scene_id=scene_id,
        description=shot_dict.get("description", ""),
        dialogue=shot_dict.get("narration", ""),
        sound="; ".join(sounds),
        characters=characters,
        framing=framing,
    )


def _convert_shot(shot_dict: dict, scene_id_remap: dict[str, str]) -> Shot:
    """Convert a validated shot dict into a Shot dataclass."""
    scene_id = shot_dict.get("scene_id", "")
    shot_dict = dict(shot_dict)  # shallow copy so we can pop nested fields
    shot_dict["scene_id"] = scene_id_remap.get(scene_id, scene_id)

    # Default fields the LLM may have omitted
    shot_dict.setdefault("camera", {"shot_size": "medium", "angle": "eye_level", "movement": "static"})
    shot_dict.setdefault("characters", [])
    shot_dict.setdefault("action_beats", [])
    shot_dict.setdefault("narration", "")
    shot_dict.setdefault("continuity", {})
    shot_dict.setdefault("generation_hint", {"preferred_family": "h3_fl2va", "preferred_mode": "t2va"})
    shot_dict.setdefault("description", "")

    return Shot.from_dict(shot_dict)


# ---------------------------------------------------------------------------
# Storyboard merging
# ---------------------------------------------------------------------------


def _merge_props(existing: list, new: list[dict]) -> list:
    """Merge new props into existing, dedup by prop_id."""
    by_id = {p.prop_id: p for p in existing}
    for p in new:
        prop = _prop_from_dict(p)
        by_id[prop.prop_id] = prop
    return list(by_id.values())


def _prop_from_dict(d: dict):
    # Lazy import to avoid circular reference; the local Prop is from storyboard
    from .storyboard import Prop
    return Prop.from_dict(d)


# ---------------------------------------------------------------------------
# Display index assignment
# ---------------------------------------------------------------------------


def _assign_beat_sequences(beats: list[Beat]) -> None:
    for i, beat in enumerate(beats):
        beat.sequence = i + 1


# ---------------------------------------------------------------------------
# Main decomposer
# ---------------------------------------------------------------------------


class StoryboardDecomposer:
    """Decompose an Intake into a Storyboard via LLM.

    Args:
        llm: LLM client (defaults to :class:`MmxLLMClient`).
        project: project metadata to use in the resulting storyboard.
        story: narrative summary to use.
        style: visual style guide to use.
        characters: pre-declared characters (LLM may reference them).
        scenes: pre-declared scenes (LLM may reuse them or add new ones).
        audio_policy: audio policy to attach.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        project: ProjectInfo | None = None,
        story: Story | None = None,
        style: StyleGuide | None = None,
        characters: list[Character] | None = None,
        scenes: list[Scene] | None = None,
        audio_policy: AudioPolicy | None = None,
    ):
        self.llm = llm or MmxLLMClient()
        self.project = project or ProjectInfo(project_id="")
        self.story = story or Story()
        self.style = style or StyleGuide()
        self.characters = characters or []
        self.scenes = scenes or []
        self.audio_policy = audio_policy or AudioPolicy()

    def decompose(
        self,
        intake: Intake,
        *,
        logline: str = "",
    ) -> Storyboard:
        """Run the LLM and return a :class:`Storyboard`.

        Raises:
            DecomposeError: on LLM call failure.
            DecomposeSchemaError: on invalid LLM output.
        """
        system, user = _render_prompt(
            intake=intake,
            project=self.project,
            story=self.story,
            style=self.style,
            characters=self.characters,
            scenes=self.scenes,
            logline=logline,
        )

        try:
            raw = self.llm.complete(system, user)
        except DecomposeError:
            raise
        except Exception as exc:
            raise DecomposeError(f"LLM call failed: {exc}") from exc

        if not raw or not raw.strip():
            raise DecomposeError("LLM returned empty output")

        try:
            data = parse_llm_output(raw)
            payload = validate_llm_payload(data)
        except DecomposeSchemaError as exc:
            raise DecomposeError(f"Invalid LLM output: {exc}") from exc

        # Reconcile scenes
        merged_scenes, scene_remap = _resolve_scene_refs(payload, self.scenes)

        # Convert LLM shots → beats, then derive panels
        beats = [
            _convert_shot_to_beat(s, scene_remap, sequence=i + 1)
            for i, s in enumerate(payload.new_shots)
        ]
        _assign_beat_sequences(beats)

        total_ms = sum(s.get("desired_duration_ms", 0) for s in payload.new_shots)
        if total_ms <= 0:
            total_ms = intake.constraints.target_duration_ms
        panels = derive_panels_from_beats(beats, total_ms)

        # Merge props
        merged_props = _merge_props([], payload.new_props)

        # Build the final storyboard
        sb = Storyboard(
            project=self.project,
            story=self.story,
            style=self.style,
            characters=list(self.characters),
            scenes=merged_scenes,
            props=merged_props,
            beats=beats,
            panels=panels,
            audio_policy=self.audio_policy,
        )

        # Set intake_ref so downstream knows where this came from
        sb.project.intake_ref = intake.project_id

        return sb
