"""Output schema for StoryboardDecomposer.

The decomposer calls an LLM and expects a JSON object describing only the
``shots[]`` array (and the new ``scenes[]``/``props[]`` it discovered
during decomposition). The rest of the Storyboard (project, story, style,
characters, audio_policy, review) is supplied by the caller and merged in
after validation.

This module:
- Defines the expected JSON shape the LLM must produce
- Validates the LLM output against that shape
- Validates internal cross-references (shot n+1 must reference shot n if
  start_frame_needed=true, etc.)

Validation is strict: any structural problem raises ``DecomposeSchemaError``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class DecomposeSchemaError(ValueError):
    """Raised when LLM output does not conform to the decompose schema."""


# ---------------------------------------------------------------------------
# Allowed enum values (must match the Storyboard dataclass field choices)
# ---------------------------------------------------------------------------

CAMERA_SHOT_SIZES = {
    "extreme_close_up", "close_up", "medium", "wide", "extreme_wide",
}
CAMERA_ANGLES = {"eye_level", "low", "high", "birds_eye", "worms_eye"}
CAMERA_MOVEMENTS = {
    "static", "pan", "tilt", "dolly", "tracking", "crane", "handheld", "slow_push_in", "slow_pull_out",
}
SCREEN_POSITIONS = {
    "left", "center", "right", "left_foreground", "right_foreground",
    "left_midground", "right_midground", "left_background", "right_background",
    "lower_left", "lower_right", "lower_center",
    "upper_left", "upper_right", "upper_center",
}
ORIENTATIONS = {"facing_camera", "facing_left", "facing_right", "back", "profile"}
GENERATION_FAMILIES = {"h3_fl2va", "h3_ref2va"}
GENERATION_MODES = {"t2va", "i2v", "first_last", "r2v"}

# shot_id format: we let the LLM propose IDs but they must be unique within
# the response. We accept any non-empty identifier matching the loose pattern.
_SHOT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SCENE_ID_RE = re.compile(r"^scene_[A-Za-z0-9_-]{1,63}$")
_CHAR_ID_RE = re.compile(r"^char_[A-Za-z0-9_-]{1,63}$")

# Spatial keywords for soft validation — warn (not reject) if absent.
SPATIAL_KEYWORDS = {
    "foreground", "midground", "background",
    "前景", "中景", "远景",
    "left", "right", "center",
    "左", "右", "中央", "旁", "远", "近",
}


# ---------------------------------------------------------------------------
# Validation result (we don't need full ValidationResult from .validate
# since this is internal to the decomposer and the API is raise-on-error)
# ---------------------------------------------------------------------------


@dataclass
class DecomposePayload:
    """Validated payload from the LLM.

    Attributes:
        new_scenes: scenes the LLM discovered (or matched to existing ones
            by name — see ``match_existing`` in :mod:`lfo.storyboard.decompose`).
        new_props:  props the LLM discovered.
        new_shots:  ordered list of shot dicts.
    """
    new_scenes: list[dict] = field(default_factory=list)
    new_props: list[dict] = field(default_factory=list)
    new_shots: list[dict] = field(default_factory=list)


def _expect_type(value, expected_type: type, path: str) -> None:
    if not isinstance(value, expected_type):
        raise DecomposeSchemaError(
            f"{path}: expected {expected_type.__name__}, got {type(value).__name__}"
        )


def _expect_in(value, allowed: set, path: str) -> None:
    if value not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        raise DecomposeSchemaError(
            f"{path}: '{value}' not in {{{allowed_str}}}"
        )


def _expect_str(value, path: str, *, max_len: int = 2000) -> str:
    _expect_type(value, str, path)
    if not value:
        raise DecomposeSchemaError(f"{path}: must be a non-empty string")
    if len(value) > max_len:
        raise DecomposeSchemaError(
            f"{path}: string too long ({len(value)} > {max_len})"
        )
    return value


# ---------------------------------------------------------------------------
# Per-entity validators
# ---------------------------------------------------------------------------


def _validate_scene(scene: dict, path: str) -> None:
    if not isinstance(scene, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    scene_id = scene.get("scene_id", "")
    _expect_str(scene_id, f"{path}/scene_id", max_len=64)
    if not _SCENE_ID_RE.match(scene_id):
        raise DecomposeSchemaError(
            f"{path}/scene_id: must match {_SCENE_ID_RE.pattern}"
        )
    _expect_str(scene.get("name", ""), f"{path}/name", max_len=200)
    _expect_str(scene.get("description", ""), f"{path}/description", max_len=2000)
    if scene.get("time_of_day") and scene["time_of_day"] not in {
        "day", "night", "dawn", "dusk",
    }:
        raise DecomposeSchemaError(
            f"{path}/time_of_day: '{scene['time_of_day']}' invalid"
        )
    if scene.get("environment") and scene["environment"] not in {
        "interior", "exterior",
    }:
        raise DecomposeSchemaError(
            f"{path}/environment: '{scene['environment']}' invalid"
        )


def _validate_prop(prop: dict, path: str) -> None:
    if not isinstance(prop, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    prop_id = prop.get("prop_id", "")
    _expect_str(prop_id, f"{path}/prop_id", max_len=64)
    if not prop_id.startswith("prop_"):
        raise DecomposeSchemaError(f"{path}/prop_id: must start with 'prop_'")
    _expect_str(prop.get("name", ""), f"{path}/name", max_len=200)
    _expect_str(prop.get("description", ""), f"{path}/description", max_len=2000)


def _validate_camera(cam: dict, path: str) -> None:
    if not isinstance(cam, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    if cam.get("shot_size"):
        _expect_in(cam["shot_size"], CAMERA_SHOT_SIZES, f"{path}/shot_size")
    if cam.get("angle"):
        _expect_in(cam["angle"], CAMERA_ANGLES, f"{path}/angle")
    if cam.get("movement"):
        _expect_in(cam["movement"], CAMERA_MOVEMENTS, f"{path}/movement")
    if cam.get("focus") is not None:
        _expect_type(cam["focus"], str, f"{path}/focus")


def _validate_char_appearance(app: dict, path: str) -> None:
    if not isinstance(app, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    _expect_str(app.get("character_id", ""), f"{path}/character_id", max_len=64)
    if not _CHAR_ID_RE.match(app["character_id"]):
        raise DecomposeSchemaError(
            f"{path}/character_id: must match {_CHAR_ID_RE.pattern}"
        )
    if app.get("screen_position"):
        _expect_in(app["screen_position"], SCREEN_POSITIONS, f"{path}/screen_position")
    if app.get("orientation"):
        _expect_in(app["orientation"], ORIENTATIONS, f"{path}/orientation")
    if app.get("action") is not None:
        _expect_type(app["action"], str, f"{path}/action")
    if app.get("expression") is not None:
        _expect_type(app["expression"], str, f"{path}/expression")


def _validate_continuity(cont: dict, path: str) -> None:
    if not isinstance(cont, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    if cont.get("priority") and cont["priority"] not in {"high", "medium", "low"}:
        raise DecomposeSchemaError(f"{path}/priority: '{cont['priority']}' invalid")
    if cont.get("previous_shot_id") is not None:
        _expect_type(cont["previous_shot_id"], str, f"{path}/previous_shot_id")
    if cont.get("next_shot_id") is not None:
        _expect_type(cont["next_shot_id"], str, f"{path}/next_shot_id")
    if cont.get("start_frame_needed") is not None:
        _expect_type(cont["start_frame_needed"], bool, f"{path}/start_frame_needed")
    if cont.get("continuity_elements") is not None:
        _expect_type(cont["continuity_elements"], list, f"{path}/continuity_elements")
    if cont.get("start_state") is not None:
        _expect_type(cont["start_state"], str, f"{path}/start_state")
    if cont.get("end_state") is not None:
        _expect_type(cont["end_state"], str, f"{path}/end_state")


def _validate_hint(hint: dict, path: str) -> None:
    if not isinstance(hint, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    if hint.get("preferred_family"):
        _expect_in(hint["preferred_family"], GENERATION_FAMILIES, f"{path}/preferred_family")
    if hint.get("preferred_mode"):
        _expect_in(hint["preferred_mode"], GENERATION_MODES, f"{path}/preferred_mode")
    if hint.get("notes") is not None:
        _expect_type(hint["notes"], str, f"{path}/notes")


def _validate_action_beat(beat: dict, path: str) -> None:
    if not isinstance(beat, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    if "sequence" in beat and not isinstance(beat["sequence"], int):
        raise DecomposeSchemaError(f"{path}/sequence: must be int")
    _expect_str(beat.get("description", ""), f"{path}/description", max_len=1000)
    if "duration_ms" in beat and (
        not isinstance(beat["duration_ms"], int) or beat["duration_ms"] < 0
    ):
        raise DecomposeSchemaError(f"{path}/duration_ms: must be non-negative int")


def _validate_shot(shot: dict, path: str) -> None:
    if not isinstance(shot, dict):
        raise DecomposeSchemaError(f"{path}: must be an object")
    shot_id = shot.get("shot_id", "")
    _expect_str(shot_id, f"{path}/shot_id", max_len=64)
    if not _SHOT_ID_RE.match(shot_id):
        raise DecomposeSchemaError(
            f"{path}/shot_id: '{shot_id}' must match {_SHOT_ID_RE.pattern}"
        )
    _expect_str(shot.get("scene_id", ""), f"{path}/scene_id", max_len=64)
    if not shot.get("description"):
        raise DecomposeSchemaError(f"{path}/description: required (non-empty)")
    if "desired_duration_ms" in shot:
        if not isinstance(shot["desired_duration_ms"], int) or shot["desired_duration_ms"] <= 0:
            raise DecomposeSchemaError(
                f"{path}/desired_duration_ms: must be a positive int"
            )
    else:
        raise DecomposeSchemaError(f"{path}/desired_duration_ms: required")

    if "camera" in shot:
        _validate_camera(shot["camera"], f"{path}/camera")
    if "characters" in shot:
        for j, app in enumerate(shot["characters"]):
            _validate_char_appearance(app, f"{path}/characters/{j}")
    if "action_beats" in shot:
        for j, beat in enumerate(shot["action_beats"]):
            _validate_action_beat(beat, f"{path}/action_beats/{j}")
    if "continuity" in shot:
        _validate_continuity(shot["continuity"], f"{path}/continuity")
    if "generation_hint" in shot:
        _validate_hint(shot["generation_hint"], f"{path}/generation_hint")
    if "narration" in shot and shot["narration"] is not None:
        _expect_type(shot["narration"], str, f"{path}/narration")


# ---------------------------------------------------------------------------
# Top-level validation
# ---------------------------------------------------------------------------


def _expect_list(value, path: str) -> list:
    _expect_type(value, list, path)
    return value


def parse_llm_output(raw: str) -> dict:
    """Parse the raw LLM text into a JSON object.

    Tolerates ```` ```json ... ```` fences and a leading prose preamble.
    Raises :class:`DecomposeSchemaError` if no JSON object is found.
    """
    import json

    text = raw.strip()
    # Strip a single leading ```json ... ``` block if present
    if text.startswith("```"):
        # Find first '{' and last '}'
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1]

    # Try the whole text first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object in the text
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace <= first_brace:
        raise DecomposeSchemaError("LLM output contained no JSON object")
    candidate = text[first_brace : last_brace + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise DecomposeSchemaError(
            f"LLM output is not valid JSON: {exc.msg} at pos {exc.pos}"
        ) from exc
    except ValueError as exc:
        # json.JSONDecodeError is a subclass of ValueError, but on the off
        # chance a different ValueError is raised by a custom decoder.
        raise DecomposeSchemaError(f"LLM output is not valid JSON: {exc}") from exc


def collect_warnings(data: dict) -> list[str]:
    """Collect soft validation warnings for an LLM payload.

    Unlike ``validate_llm_payload`` (which raises on errors), this function
    returns a list of human-readable warnings. Callers may surface these
    to the user without blocking the pipeline.

    Current checks:
    - Shot ``description`` missing spatial relationship keywords.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings

    shots = data.get("shots", [])
    if isinstance(shots, list):
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):
                continue
            desc = shot.get("description", "")
            if desc and not any(kw in desc.lower() for kw in SPATIAL_KEYWORDS):
                warnings.append(
                    f"/shots/{i}/description: no spatial relationship keywords found"
                )
    return warnings


def validate_llm_payload(data: dict) -> DecomposePayload:
    """Validate the parsed LLM JSON against the decompose schema.

    Required top-level keys (all optional except ``shots``):
    - ``scenes`` (optional): array of scene objects — LLM-discovered locations
    - ``props``  (optional): array of prop objects
    - ``shots``  (required): ordered array of shot objects

    Returns a :class:`DecomposePayload` on success.
    """
    if not isinstance(data, dict):
        raise DecomposeSchemaError("LLM output must be a JSON object")

    payload = DecomposePayload()

    if "scenes" in data and data["scenes"] is not None:
        for i, scene in enumerate(_expect_list(data["scenes"], "/scenes")):
            _validate_scene(scene, f"/scenes/{i}")
            payload.new_scenes.append(scene)

    if "props" in data and data["props"] is not None:
        for i, prop in enumerate(_expect_list(data["props"], "/props")):
            _validate_prop(prop, f"/props/{i}")
            payload.new_props.append(prop)

    if "shots" not in data:
        raise DecomposeSchemaError("LLM output missing required field: shots")
    shots = _expect_list(data["shots"], "/shots")
    if not shots:
        raise DecomposeSchemaError("LLM output has empty shots array")

    for i, shot in enumerate(shots):
        _validate_shot(shot, f"/shots/{i}")
        payload.new_shots.append(shot)

    # Cross-shot integrity checks
    _validate_shot_sequence(payload)

    return payload


# ---------------------------------------------------------------------------
# Cross-shot checks
# ---------------------------------------------------------------------------


def _validate_shot_sequence(payload: DecomposePayload) -> None:
    """Check that continuity references resolve and IDs are unique."""
    shot_ids = [s["shot_id"] for s in payload.new_shots]

    # Uniqueness
    if len(shot_ids) != len(set(shot_ids)):
        from collections import Counter
        dupes = [sid for sid, n in Counter(shot_ids).items() if n > 1]
        raise DecomposeSchemaError(f"duplicate shot_ids: {dupes}")

    # scene_id references in shots must point to either:
    # - an LLM-discovered scene in payload.new_scenes
    # - or simply be present (the caller will resolve to existing storyboard
    #   scenes by name in a post-process step). For now we just ensure it's
    #   not empty.
    discovered_scene_ids = {s["scene_id"] for s in payload.new_scenes}
    for i, shot in enumerate(payload.new_shots):
        scene_id = shot.get("scene_id", "")
        if scene_id in discovered_scene_ids:
            continue
        # Otherwise just ensure it looks reasonable
        if not scene_id.startswith("scene_") and not scene_id.startswith("ref_"):
            # We allow scene_ref to existing scenes (caller resolves)
            if "_" not in scene_id:
                raise DecomposeSchemaError(
                    f"/shots/{i}/scene_id: '{scene_id}' must start with 'scene_' or 'ref_'"
                )

    # continuity.previous_shot_id / next_shot_id must reference a shot in this
    # payload (or be null) and form a valid chain
    for i, shot in enumerate(payload.new_shots):
        cont = shot.get("continuity", {})
        prev = cont.get("previous_shot_id")
        nxt = cont.get("next_shot_id")
        sfn = cont.get("start_frame_needed", False)

        if prev and prev not in shot_ids:
            raise DecomposeSchemaError(
                f"/shots/{i}/continuity/previous_shot_id: '{prev}' not in this payload's shot_ids"
            )
        if nxt and nxt not in shot_ids:
            raise DecomposeSchemaError(
                f"/shots/{i}/continuity/next_shot_id: '{nxt}' not in this payload's shot_ids"
            )
        if sfn and not prev:
            raise DecomposeSchemaError(
                f"/shots/{i}/continuity: start_frame_needed=true requires previous_shot_id"
            )

    # If shot N declares start_frame_needed=true and references shot N-1, the
    # previous shot should be the immediately preceding one in the array.
    # This is a soft warning, not a hard error — the LLM may intentionally
    # skip a shot (e.g. cutaway). We only validate the *first* shot doesn't
    # claim start_frame_needed.
    if payload.new_shots:
        first = payload.new_shots[0]
        if first.get("continuity", {}).get("start_frame_needed", False):
            raise DecomposeSchemaError(
                "/shots/0/continuity: first shot cannot have start_frame_needed=true"
            )
