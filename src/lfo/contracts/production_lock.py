"""Production-readiness and prompt-revision contracts.

The creative skills perform story, timing and prompt compilation before an
execution package reaches LFO.  LFO only needs to verify the immutable plan
hash and keep a small, backend-agnostic audio acceptance contract.  The
extensions in this module are intentionally additive so historical v1
packages remain readable during migration.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from lfo.contracts.errors import ValidationResult
from lfo.core.canonical import hash_value

PRODUCTION_LOCK_EXTENSION = "lfo.production_lock.v1"
AUDIO_ACCEPTANCE_EXTENSION = "lfo.audio_acceptance.v1"
PROMPT_MANIFEST_EXTENSION = "lfo.prompt_manifest.v1"

LOCK_SCHEMA = "lfo.production-lock.v1"
LOCKED_STATUS = "LOCKED"

# Fields that may change when a creative skill submits a prompt revision.  The
# plan hash deliberately excludes these fields; changing anything else makes a
# new production plan and must be rejected after the lock.
PROMPT_MUTABLE_FIELDS = frozenset({"prompt", "negative_prompt", "seed"})
# A prompt manifest is an evidence sidecar for the locked timing/reference
# plan.  Its prompt bytes and hashes are expected to change when the creative
# layer submits the one allowed wording revision; the timing, dialogue and
# reference records remain part of the immutable plan.  Excluding ``plan_hash``
# also avoids a circular dependency: the manifest records the Clip hash that
# is computed from the manifest's immutable fields.
PROMPT_MANIFEST_MUTABLE_FIELDS = frozenset(
    {"prompt", "prompt_path", "prompt_hash", "plan_hash"}
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
PLAN_FIELDS = (
    "clip_id",
    "sequence",
    "duration_ms",
    "generation.operation",
    "generation.requirements",
    "generation.references",
    "audio",
    "subtitles",
    "dependencies",
    "source_context",
    "extensions",
)


def clip_plan_payload(clip: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable subset of one raw ClipSpec.

    Prompt text, its negative prompt and seed are intentionally omitted.  A
    prompt revision can therefore preserve the story/shot/audio plan while
    changing only model-facing wording.
    """

    generation = clip.get("generation")
    if not isinstance(generation, Mapping):
        generation = {}
    payload = {
        "clip_id": clip.get("clip_id"),
        "sequence": clip.get("sequence"),
        "duration_ms": clip.get("duration_ms"),
        "generation": {
            "operation": generation.get("operation"),
            "requirements": generation.get("requirements", {}),
            "references": generation.get("references", []),
        },
        "audio": clip.get("audio", {}),
        "subtitles": clip.get("subtitles", {}),
        "dependencies": clip.get("dependencies", []),
        "source_context": clip.get("source_context", {}),
        # Per-Clip execution extensions (audio acceptance, upscale policy,
        # prompt-manifest bindings, etc.) are part of the locked plan.  The
        # runtime prompt revision mutates task metadata only and never edits
        # this package field.
        "extensions": _plan_extensions(clip.get("extensions", {})),
    }
    return _normalize_plan_value(payload)


def _normalize_plan_value(value: Any) -> Any:
    """Make raw JSON values safe for the no-float LFO-CJ1 hash.

    Package authors commonly write ``megapixels`` as ``0.4``.  LFO-CJ1
    intentionally rejects floats, so plan hashes normalize finite floats to
    their shortest decimal string while preserving integer and string values.
    The same normalization is used when creating and checking a lock.
    """

    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return format(value, ".15g")
    if isinstance(value, Mapping):
        return {str(key): _normalize_plan_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_normalize_plan_value(item) for item in value]
    return value


def _plan_extensions(value: object) -> object:
    """Return extensions with prompt-manifest evidence fields excluded.

    All non-manifest extensions stay fully locked.  The manifest's timing,
    dialogue and typed-reference records are retained, while its prompt bytes
    and self-referential/hash fields remain mutable evidence for a prompt-only
    revision.
    """

    if not isinstance(value, Mapping):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text == PROMPT_MANIFEST_EXTENSION and isinstance(item, Mapping):
            result[key_text] = {
                str(field): field_value
                for field, field_value in item.items()
                if str(field) not in PROMPT_MANIFEST_MUTABLE_FIELDS
            }
        else:
            result[key_text] = item
    return result


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def clip_plan_hash(clip: Mapping[str, Any]) -> str:
    """Compute the deterministic hash used by a production lock."""

    return hash_value(clip_plan_payload(clip))


def aggregate_plan_hash(clips: list[Mapping[str, Any]]) -> str:
    """Compute one stable plan hash from all clips in sequence order."""

    entries = [
        {"clip_id": str(clip.get("clip_id")), "plan_hash": clip_plan_hash(clip)}
        for clip in sorted(clips, key=lambda value: (value.get("sequence", 0), str(value.get("clip_id", ""))))
    ]
    return hash_value({"clips": entries})


def package_plan_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    """Return package-level fields that must remain stable after locking.

    The top-level lock itself is excluded to avoid a self-referential hash;
    all other extensions, assets, timeline and output settings affect what
    LFO executes and therefore belong to the immutable production plan.
    """

    extensions = package.get("extensions", {})
    if not isinstance(extensions, Mapping):
        extensions = {}
    clips = package.get("clips", [])
    if not isinstance(clips, list):
        clips = []
    timeline = package.get("timeline")
    if timeline is None:
        # ``VideoExecutionPackage.from_dict`` materializes an omitted timeline
        # as the sequence-ordered clip list.  Hash that effective plan so a
        # lock created from concise JSON still covers what LFO will execute.
        ordered_clips = sorted(
            (clip for clip in clips if isinstance(clip, Mapping)),
            key=lambda value: (
                value.get("sequence") if isinstance(value.get("sequence"), int) else 0,
                str(value.get("clip_id", "")),
            ),
        )
        timeline = {
            "segments": [
                {"clip_id": clip.get("clip_id")}
                for clip in ordered_clips
            ]
        }
    return _normalize_plan_value(
        {
            "package_id": package.get("package_id"),
            "revision": package.get("revision"),
            "project": package.get("project", {}),
            "assets": package.get("assets", []),
            "clips": [
                clip_plan_payload(clip)
                for clip in clips
                if isinstance(clip, Mapping)
            ],
            "timeline": timeline,
            "output": package.get("output", {}),
            "extensions": _plan_extensions(
                {
                    str(key): value
                    for key, value in extensions.items()
                    if key != PRODUCTION_LOCK_EXTENSION
                }
            ),
        }
    )


def package_plan_hash(package: Mapping[str, Any]) -> str:
    """Compute the hash for all locked package-level execution inputs."""

    return hash_value(package_plan_payload(package))


def build_production_lock(
    package: Mapping[str, Any],
    *,
    max_prompt_revisions: int = 1,
    status: str = LOCKED_STATUS,
) -> dict[str, Any]:
    """Build the lock extension for a validated execution-package mapping.

    The creative side calls this only after the storyboard, blueprint,
    storyboard board, and H3 prompt manifest have been approved.  It returns
    a new extension object; callers can attach it under ``package.extensions``
    without mutating the original clip objects.
    """

    if not isinstance(package, Mapping):
        raise TypeError("package must be an object")
    if (
        not isinstance(max_prompt_revisions, int)
        or isinstance(max_prompt_revisions, bool)
        or max_prompt_revisions < 0
    ):
        raise ValueError("max_prompt_revisions must be an integer >= 0")
    clips_value = package.get("clips", [])
    if not isinstance(clips_value, list) or any(not isinstance(item, Mapping) for item in clips_value):
        raise ValueError("package.clips must be an array of objects")
    clips = [item for item in clips_value if isinstance(item, Mapping)]
    entries: dict[str, dict[str, Any]] = {}
    for clip in clips:
        clip_id = clip.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id:
            raise ValueError("every clip must have a non-empty clip_id")
        if clip_id in entries:
            raise ValueError(f"duplicate clip_id: {clip_id}")
        entries[clip_id] = {
            "plan_hash": clip_plan_hash(clip),
            "prompt_revision": _prompt_revision_from_clip(clip),
        }
    return {
        "schema": LOCK_SCHEMA,
        "status": status,
        "plan_hash": aggregate_plan_hash(clips),
        "package_plan_hash": package_plan_hash(package),
        "max_prompt_revisions": max_prompt_revisions,
        "mutable_fields": sorted(PROMPT_MUTABLE_FIELDS),
        "clips": entries,
    }


def with_production_lock(
    package: Mapping[str, Any],
    *,
    max_prompt_revisions: int = 1,
) -> dict[str, Any]:
    """Return a package copy with a freshly computed production lock."""

    if not isinstance(package, Mapping):
        raise TypeError("package must be an object")
    result = dict(package)
    extensions = package.get("extensions", {})
    if not isinstance(extensions, Mapping):
        raise ValueError("package.extensions must be an object")
    result["extensions"] = dict(extensions)
    result["extensions"][PRODUCTION_LOCK_EXTENSION] = build_production_lock(
        package,
        max_prompt_revisions=max_prompt_revisions,
    )
    return result


def _prompt_revision_from_clip(clip: Mapping[str, Any]) -> int:
    extensions = clip.get("extensions")
    if not isinstance(extensions, Mapping):
        return 0
    value = extensions.get("lfo.prompt_revision.v1")
    if isinstance(value, Mapping):
        revision = value.get("revision", 0)
        if isinstance(revision, int) and not isinstance(revision, bool) and revision >= 0:
            return revision
    return 0


def validate_production_lock(
    package: Mapping[str, Any],
    *,
    require: bool = False,
) -> ValidationResult:
    """Validate an optional lock extension and its clip plan hashes.

    ``require=False`` is the migration-compatible default.  Production
    callers should enable it on ``VideoRuntime``; a missing lock then fails at
    package validation before assets are imported or generation is submitted.
    """

    result = ValidationResult()
    extensions = package.get("extensions")
    if not isinstance(extensions, Mapping):
        extensions = {}
    lock = extensions.get(PRODUCTION_LOCK_EXTENSION)
    if lock is None:
        if require:
            result.add(
                f"$.extensions.{PRODUCTION_LOCK_EXTENSION}",
                "required for production execution; lock the plan before entering LFO",
                "production_lock_required",
            )
        return result
    if not isinstance(lock, Mapping):
        result.add(
            f"$.extensions.{PRODUCTION_LOCK_EXTENSION}",
            "must be an object",
            "type",
        )
        return result

    path = f"$.extensions.{PRODUCTION_LOCK_EXTENSION}"
    if lock.get("schema") != LOCK_SCHEMA:
        result.add(f"{path}.schema", f"must be {LOCK_SCHEMA!r}", "schema")
    if lock.get("status") != LOCKED_STATUS:
        result.add(f"{path}.status", f"must be {LOCKED_STATUS!r}", "status")

    plan_hash = lock.get("plan_hash")
    if not isinstance(plan_hash, str) or not plan_hash:
        result.add(f"{path}.plan_hash", "required non-empty string", "required")
    elif not _is_sha256(plan_hash):
        result.add(f"{path}.plan_hash", "must be a 64-character SHA-256 hex string", "type")

    package_hash = lock.get("package_plan_hash")
    if package_hash is None:
        if require:
            result.add(
                f"{path}.package_plan_hash",
                "required for a production lock; regenerate the lock with the complete package plan",
                "required",
            )
    elif not _is_sha256(package_hash):
        result.add(
            f"{path}.package_plan_hash",
            "must be a 64-character SHA-256 hex string",
            "type",
        )

    max_revisions = lock.get("max_prompt_revisions", 1)
    if not isinstance(max_revisions, int) or isinstance(max_revisions, bool) or max_revisions < 0:
        result.add(
            f"{path}.max_prompt_revisions",
            "must be an integer >= 0",
            "type",
        )

    mutable = lock.get("mutable_fields", sorted(PROMPT_MUTABLE_FIELDS))
    if not isinstance(mutable, list) or any(not isinstance(item, str) for item in mutable):
        result.add(f"{path}.mutable_fields", "must be an array of strings", "type")
    elif set(mutable) != set(PROMPT_MUTABLE_FIELDS):
        result.add(
            f"{path}.mutable_fields",
            "must contain exactly prompt, negative_prompt and seed",
            "immutable_policy",
        )

    clips = package.get("clips")
    if not isinstance(clips, list):
        result.add("$.clips", "must be an array when a production lock is present", "type")
        return result
    clip_entries = lock.get("clips")
    if not isinstance(clip_entries, Mapping):
        result.add(f"{path}.clips", "must be an object keyed by clip_id", "type")
        clip_entries = {}

    seen: set[str] = set()
    for index, clip in enumerate(clips):
        clip_path = f"$.clips[{index}]"
        if not isinstance(clip, Mapping):
            continue
        clip_id = clip.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id:
            continue
        seen.add(clip_id)
        entry = clip_entries.get(clip_id)
        if not isinstance(entry, Mapping):
            result.add(
                f"{path}.clips.{clip_id}",
                "missing lock entry",
                "missing",
            )
            continue
        expected = entry.get("plan_hash")
        if not isinstance(expected, str) or not expected:
            result.add(
                f"{path}.clips.{clip_id}.plan_hash",
                "required non-empty string",
                "required",
            )
        elif not _is_sha256(expected):
            result.add(
                f"{path}.clips.{clip_id}.plan_hash",
                "must be a 64-character SHA-256 hex string",
                "type",
            )
        try:
            actual = clip_plan_hash(clip)
        except Exception as exc:
            result.add(
                clip_path,
                f"cannot compute immutable clip plan hash: {exc}",
                "plan_hash_error",
            )
            continue
        if expected != actual:
            result.add(
                f"{clip_path}",
                "immutable clip plan differs from the production lock; storyboard changes are not allowed after lock",
                "plan_hash_mismatch",
                {"expected": expected, "actual": actual},
            )
        clip_extensions = clip.get("extensions")
        manifest = (
            clip_extensions.get(PROMPT_MANIFEST_EXTENSION)
            if isinstance(clip_extensions, Mapping)
            else None
        )
        if isinstance(manifest, Mapping):
            manifest_clip_id = manifest.get("clip_id")
            if manifest_clip_id is not None and manifest_clip_id != clip_id:
                result.add(
                    f"{clip_path}.extensions.{PROMPT_MANIFEST_EXTENSION}.clip_id",
                    "must match the owning Clip id",
                    "manifest_binding",
                )
            manifest_plan_hash = manifest.get("plan_hash")
            if not _is_sha256(manifest_plan_hash):
                result.add(
                    f"{clip_path}.extensions.{PROMPT_MANIFEST_EXTENSION}.plan_hash",
                    "must be the owning Clip plan hash",
                    "manifest_binding",
                )
            elif manifest_plan_hash != actual:
                result.add(
                    f"{clip_path}.extensions.{PROMPT_MANIFEST_EXTENSION}.plan_hash",
                    "must match the owning Clip plan hash",
                    "manifest_binding",
                    {"expected": actual, "actual": manifest_plan_hash},
                )
        revision = entry.get("prompt_revision", 0)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            result.add(
                f"{path}.clips.{clip_id}.prompt_revision",
                "must be an integer >= 0",
                "type",
            )
        elif isinstance(max_revisions, int) and revision > max_revisions:
            result.add(
                f"{path}.clips.{clip_id}.prompt_revision",
                f"cannot exceed max_prompt_revisions ({max_revisions})",
                "maximum",
            )

    for clip_id in clip_entries:
        if isinstance(clip_id, str) and clip_id not in seen:
            result.add(
                f"{path}.clips.{clip_id}",
                "lock entry has no matching package clip",
                "orphan",
            )

    if isinstance(plan_hash, str) and plan_hash:
        try:
            actual_plan_hash = aggregate_plan_hash(
                [clip for clip in clips if isinstance(clip, Mapping)]
            )
        except Exception as exc:
            result.add(f"{path}.plan_hash", f"cannot compute package plan hash: {exc}", "plan_hash_error")
            return result
        if plan_hash != actual_plan_hash:
            result.add(
                f"{path}.plan_hash",
                "does not match the package's immutable clip plans",
                "plan_hash_mismatch",
                {"expected": plan_hash, "actual": actual_plan_hash},
            )
    if isinstance(package_hash, str) and package_hash:
        try:
            actual_package_hash = package_plan_hash(package)
        except Exception as exc:
            result.add(
                f"{path}.package_plan_hash",
                f"cannot compute package plan hash: {exc}",
                "plan_hash_error",
            )
        else:
            if package_hash != actual_package_hash:
                result.add(
                    f"{path}.package_plan_hash",
                    "does not match the package-level execution plan",
                    "plan_hash_mismatch",
                    {"expected": package_hash, "actual": actual_package_hash},
                )
    return result


def validate_audio_acceptance(value: object, path: str = "$") -> ValidationResult:
    """Validate the small backend-agnostic audio acceptance extension.

    Signal metrics and transcripts are evidence supplied by an analyzer after
    generation; the contract only declares expected speech windows and the
    allowed tolerance.  An analyzer may return ``INCONCLUSIVE`` without
    converting uncertainty into a creative/storyboard failure.
    """

    result = ValidationResult()
    if not isinstance(value, Mapping):
        result.add(path, "must be an object", "type")
        return result
    schema = value.get("schema", AUDIO_ACCEPTANCE_EXTENSION)
    if schema != AUDIO_ACCEPTANCE_EXTENSION:
        result.add(f"{path}.schema", f"must be {AUDIO_ACCEPTANCE_EXTENSION!r}", "schema")
    events = value.get("speech_events", [])
    if not isinstance(events, list):
        result.add(f"{path}.speech_events", "must be an array", "type")
        return result
    ids: set[str] = set()
    for index, event in enumerate(events):
        event_path = f"{path}.speech_events[{index}]"
        if not isinstance(event, Mapping):
            result.add(event_path, "must be an object", "type")
            continue
        for field in ("event_id", "speaker_id", "text"):
            value_field = event.get(field)
            if not isinstance(value_field, str) or not value_field.strip():
                result.add(f"{event_path}.{field}", "required non-empty string", "required")
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if event_id in ids:
                result.add(f"{event_path}.event_id", "must be unique", "unique")
            ids.add(event_id)
        for field in ("start_ms", "end_ms"):
            number = event.get(field)
            if not isinstance(number, int) or isinstance(number, bool) or number < 0:
                result.add(f"{event_path}.{field}", "must be an integer >= 0", "type")
        start = event.get("start_ms")
        end = event.get("end_ms")
        if isinstance(start, int) and isinstance(end, int) and end <= start:
            result.add(f"{event_path}.end_ms", "must be greater than start_ms", "range")
        allow_overlap = event.get("allow_overlap", False)
        if not isinstance(allow_overlap, bool):
            result.add(f"{event_path}.allow_overlap", "must be boolean", "type")
    require_audio = value.get("require_audio")
    if require_audio is not None and not isinstance(require_audio, bool):
        result.add(f"{path}.require_audio", "must be boolean or omitted", "type")
    if events and require_audio is not True:
        result.add(
            f"{path}.require_audio",
            "must be explicitly true when speech_events are declared",
            "audio_required",
        )
    for field in ("max_peak_db", "min_mean_db"):
        field_value = value.get(field)
        if field_value is not None and (
            isinstance(field_value, bool) or not isinstance(field_value, int | float)
        ):
            result.add(f"{path}.{field}", "must be a number or null", "type")
    tolerance = value.get("timing_tolerance_ms", 300)
    if not isinstance(tolerance, int) or isinstance(tolerance, bool) or tolerance < 0:
        result.add(
            f"{path}.timing_tolerance_ms",
            "must be an integer >= 0",
            "type",
        )
    similarity = value.get("transcript_similarity", 0.90)
    if (
        isinstance(similarity, bool)
        or not isinstance(similarity, int | float)
        or not 0 <= float(similarity) <= 1
    ):
        result.add(
            f"{path}.transcript_similarity",
            "must be a number between 0 and 1",
            "range",
        )
    return result


__all__ = [
    "AUDIO_ACCEPTANCE_EXTENSION",
    "LOCKED_STATUS",
    "LOCK_SCHEMA",
    "PLAN_FIELDS",
    "PRODUCTION_LOCK_EXTENSION",
    "PROMPT_MANIFEST_EXTENSION",
    "PROMPT_MANIFEST_MUTABLE_FIELDS",
    "PROMPT_MUTABLE_FIELDS",
    "aggregate_plan_hash",
    "build_production_lock",
    "clip_plan_hash",
    "clip_plan_payload",
    "package_plan_hash",
    "package_plan_payload",
    "validate_audio_acceptance",
    "validate_production_lock",
    "with_production_lock",
]
