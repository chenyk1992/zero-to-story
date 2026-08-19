"""Pure adapter for the virtual-presenter Skill.

The Skill owns presenter planning and approval.  This module only maps that
approved plan to the public ``VideoExecutionPackage`` contract; it performs
no file I/O and never exposes LFO-internal asset or database identifiers.
"""
from __future__ import annotations

import re
from typing import Any

from lfo.contracts.assets import AssetSource, AssetSpec, ProvenanceSpec, ReviewDeclaration
from lfo.contracts.builder import VideoPackageBuilder
from lfo.contracts.clips import (
    BindingPolicy,
    ClipSpec,
    GenerationRequirements,
    GenerationSpec,
    ReferenceSpec,
    SubtitleSpec,
)
from lfo.contracts.package import ApprovalDeclaration, VideoExecutionPackage
from lfo.contracts.timeline import OutputPolicy

_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _required_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _required_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _package_relative_uri(value: Any, path: str) -> str:
    """Validate a URI that will later be resolved relative to the package."""

    uri = _required_string(value, path)
    normalised = uri.replace("\\", "/")
    if (
        normalised.startswith("/")
        or normalised.startswith("//")
        or (len(normalised) >= 2 and normalised[1] == ":")
        or _URI_SCHEME.match(uri) is not None
    ):
        raise ValueError(f"{path} must be a package-relative URI")
    if any(part == ".." for part in normalised.split("/")):
        raise ValueError(f"{path} must not contain '..'")
    return uri


def _validate_revision(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("package_revision must be a positive integer")
    return value


def _validate_project(plan: dict[str, Any]) -> tuple[dict[str, Any], str, str, str | None]:
    project = _required_mapping(plan.get("project"), "plan.project")
    project_id = _required_string(project.get("project_id"), "plan.project.project_id")
    title = _required_string(project.get("title"), "plan.project.title")
    locale = project.get("locale")
    if locale is not None and not isinstance(locale, str):
        raise ValueError("plan.project.locale must be a string when provided")
    return project, project_id, title, locale


def _validate_inputs(plan: dict[str, Any]) -> dict[str, Any]:
    inputs = _required_mapping(plan.get("inputs"), "plan.inputs")
    _package_relative_uri(inputs.get("character_uri"), "plan.inputs.character_uri")
    _package_relative_uri(inputs.get("panorama_uri"), "plan.inputs.panorama_uri")
    voice = inputs.get("voice_uri")
    if voice is not None:
        _package_relative_uri(voice, "plan.inputs.voice_uri")
    return inputs


def _validate_approval(plan: dict[str, Any]) -> dict[str, Any]:
    approval = _required_mapping(plan.get("approval"), "plan.approval")
    if approval.get("status") != "approved":
        raise ValueError("plan.approval.status must be 'approved'")
    return approval


def _validate_duration(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path} must be an integer")
    if value < 4_000 or value > 15_000:
        raise ValueError(f"{path} must be between 4000ms and 15000ms")
    return value


def _subtitle_spec(value: Any, path: str, duration_ms: int) -> SubtitleSpec:
    if value is None:
        return SubtitleSpec()
    if isinstance(value, list):
        value = {"cues": value}
    subtitles = SubtitleSpec.from_dict(_required_mapping(value, path), path)
    for index, cue in enumerate(subtitles.cues):
        if cue.end_ms > duration_ms:
            raise ValueError(f"{path}.cues[{index}].end_ms exceeds shot duration")
    return subtitles


def _validate_shots(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw_shots = plan.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("plan.shots must be a non-empty list")
    shots: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    seen_sequences: dict[int, int] = {}
    for index, raw in enumerate(raw_shots):
        shot = _required_mapping(raw, f"plan.shots[{index}]")
        shot_id = _required_string(shot.get("shot_id"), f"plan.shots[{index}].shot_id")
        sequence = shot.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ValueError(f"plan.shots[{index}].sequence must be an integer")
        if shot_id in seen_ids:
            raise ValueError(
                f"duplicate shot_id {shot_id!r} (first at index {seen_ids[shot_id]})"
            )
        if sequence in seen_sequences:
            raise ValueError(
                f"duplicate sequence {sequence} (first at index {seen_sequences[sequence]})"
            )
        seen_ids[shot_id] = index
        seen_sequences[sequence] = index
        duration_ms = _validate_duration(
            shot.get("duration_ms"), f"plan.shots[{index}].duration_ms"
        )
        _required_string(shot.get("prompt"), f"plan.shots[{index}].prompt")
        _package_relative_uri(
            shot.get("environment_view_uri"),
            f"plan.shots[{index}].environment_view_uri",
        )
        seed = shot.get("seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise ValueError(f"plan.shots[{index}].seed must be an integer")
        include_voice = shot.get("include_voice_reference")
        if include_voice is not None and not isinstance(include_voice, bool):
            raise ValueError(
                f"plan.shots[{index}].include_voice_reference must be a boolean"
            )
        _subtitle_spec(shot.get("subtitles"), f"plan.shots[{index}].subtitles", duration_ms)
        shots.append(shot)
    return shots


def _validate_common(plan: dict[str, Any]) -> tuple[
    dict[str, Any], str, str, str | None, dict[str, Any], OutputPolicy, dict[str, Any], list[dict[str, Any]]
]:
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    project, project_id, title, locale = _validate_project(plan)
    inputs = _validate_inputs(plan)
    output_data = _required_mapping(plan.get("output"), "plan.output")
    output = OutputPolicy.from_dict(output_data, "plan.output")
    approval = _validate_approval(plan)
    shots = _validate_shots(plan)
    return project, project_id, title, locale, inputs, output, approval, shots


def _approval_declaration(approval: dict[str, Any]) -> ApprovalDeclaration:
    approved_by = approval.get("approved_by") or approval.get("reviewer") or "virtual-presenter"
    if not isinstance(approved_by, str):
        raise ValueError("plan.approval.approved_by must be a string when provided")
    approved_at = approval.get("approved_at")
    if approved_at is not None and not isinstance(approved_at, str):
        raise ValueError("plan.approval.approved_at must be a string when provided")
    notes = approval.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("plan.approval.notes must be a string when provided")
    return ApprovalDeclaration(approved_by=approved_by, approved_at=approved_at, notes=notes)


def _asset(asset_key: str, media_type: str, uri: str) -> AssetSpec:
    return AssetSpec(
        asset_key=asset_key,
        media_type=media_type,
        source=AssetSource(uri=uri),
        provenance=ProvenanceSpec(
            source_type="external_skill",
            producer="virtual-presenter",
            operation="media.reference",
        ),
        review=ReviewDeclaration(required=True),
    )


def _reference(
    reference_id: str,
    asset_key: str,
    semantic_usage: str,
    slot: str,
    *,
    required: bool = True,
) -> ReferenceSpec:
    return ReferenceSpec(
        reference_id=reference_id,
        asset_key=asset_key,
        semantic_usage=semantic_usage,
        binding=BindingPolicy(
            required=required,
            priority=100 if required else 50,
            placement="fixed",
            slot=slot,
            on_unsupported="fail" if required else "drop",
        ),
    )


def _requirements(output: OutputPolicy) -> GenerationRequirements:
    return GenerationRequirements(
        width=output.width,
        height=output.height,
        fps=output.fps,
        native_audio="allowed",
    )


def _source_context(shot: dict[str, Any], shot_id: str) -> dict[str, Any]:
    return {
        "skill": "virtual-presenter",
        "shot": shot_id,
        # Runtime preserves this record for audit and recovery but does not
        # interpret any presenter-specific semantics inside it.
        "shot_contract": dict(shot),
    }


def _shot_package_id(project_id: str, shot_id: str) -> str:
    return f"{project_id}-shot-{shot_id}"


def _assembly_package_id(project_id: str) -> str:
    return f"{project_id}-assembly"


def build_shot_package(
    plan: dict[str, Any],
    shot_id: str,
    *,
    previous_clip_uri: str | None = None,
    package_revision: int = 1,
) -> VideoExecutionPackage:
    """Build one approved ``video.virtual_presenter`` clip package."""

    _required_string(shot_id, "shot_id")
    _validate_revision(package_revision)
    _, project_id, title, locale, inputs, output, approval, shots = _validate_common(plan)
    shot = next((item for item in shots if item.get("shot_id") == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot_id {shot_id!r}")
    if previous_clip_uri is not None:
        previous_clip_uri = _package_relative_uri(previous_clip_uri, "previous_clip_uri")

    character_uri = _package_relative_uri(inputs["character_uri"], "plan.inputs.character_uri")
    panorama_uri = _package_relative_uri(inputs["panorama_uri"], "plan.inputs.panorama_uri")
    direction_uri = _package_relative_uri(
        shot["environment_view_uri"], f"shot[{shot_id}].environment_view_uri"
    )
    builder = VideoPackageBuilder(
        _shot_package_id(project_id, shot_id),
        title,
        revision=package_revision,
        locale=locale,
        project_id=project_id,
    )
    builder.add_asset(_asset("character", "image", character_uri))
    builder.add_asset(_asset("panorama", "image", panorama_uri))
    builder.add_asset(_asset("direction", "image", direction_uri))

    references = [
        _reference("character", "character", "subject.identity", "ref_image_0"),
        _reference("panorama", "panorama", "environment.panorama", "ref_image_1"),
        _reference("direction", "direction", "environment.direction", "ref_image_2"),
    ]
    voice_uri = inputs.get("voice_uri")
    include_voice = shot.get("include_voice_reference")
    if include_voice is None:
        # The first shot uses the standalone voice anchor.  Once a prior
        # accepted clip exists, its paired soundtrack is the safer continuity
        # default; a Shot Contract may opt back into standalone voice only
        # after the Scene-D comparison accepts it.
        include_voice = voice_uri is not None and previous_clip_uri is None
    if include_voice and voice_uri is None:
        raise ValueError(
            f"shot[{shot_id}].include_voice_reference requires plan.inputs.voice_uri"
        )
    if include_voice and voice_uri is not None:
        builder.add_asset(_asset("voice", "audio", _package_relative_uri(voice_uri, "plan.inputs.voice_uri")))
        references.append(_reference("voice", "voice", "voice.reference", "ref_audio_0", required=False))
    if previous_clip_uri is not None:
        builder.add_asset(_asset("previous", "video", previous_clip_uri))
        references.append(_reference("previous", "previous", "continuity.previous_clip", "ref_video_0", required=False))

    duration_ms = int(shot["duration_ms"])
    subtitle_spec = _subtitle_spec(shot.get("subtitles"), f"shot[{shot_id}].subtitles", duration_ms)
    builder.add_clip(ClipSpec(
        clip_id=shot_id,
        sequence=int(shot["sequence"]),
        duration_ms=duration_ms,
        generation=GenerationSpec(
            operation="video.virtual_presenter",
            prompt=str(shot["prompt"]),
            seed=shot.get("seed"),
            requirements=_requirements(output),
            references=references,
        ),
        subtitles=subtitle_spec,
        source_context=_source_context(shot, shot_id),
    ))
    return builder.output(output).approval(_approval_declaration(approval)).build()


def _accepted_clip_values(
    accepted: Any,
    index: int,
) -> tuple[str, int, int, str, SubtitleSpec, dict[str, Any]]:
    item = _required_mapping(accepted, f"accepted_clips[{index}]")
    shot_id = _required_string(item.get("shot_id"), f"accepted_clips[{index}].shot_id")
    sequence = item.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError(f"accepted_clips[{index}].sequence must be an integer")
    duration_ms = _validate_duration(item.get("duration_ms"), f"accepted_clips[{index}].duration_ms")
    uri = _package_relative_uri(item.get("uri"), f"accepted_clips[{index}].uri")
    subtitles = _subtitle_spec(item.get("subtitles"), f"accepted_clips[{index}].subtitles", duration_ms)
    return shot_id, sequence, duration_ms, uri, subtitles, item


def build_assembly_package(
    plan: dict[str, Any],
    accepted_clips: list[dict[str, Any]],
    *,
    package_revision: int = 1,
) -> VideoExecutionPackage:
    """Build an assembly package that passes accepted clips through LFO."""

    _validate_revision(package_revision)
    _, project_id, title, locale, _, output, approval, shots = _validate_common(plan)
    if not isinstance(accepted_clips, list) or not accepted_clips:
        raise ValueError("accepted_clips must be a non-empty list")
    plan_shot_ids = {str(shot["shot_id"]) for shot in shots}
    plan_shot_by_id = {str(shot["shot_id"]): shot for shot in shots}
    seen_ids: dict[str, int] = {}
    seen_sequences: dict[int, int] = {}
    values: list[tuple[str, int, int, str, SubtitleSpec, dict[str, Any]]] = []
    for index, accepted in enumerate(accepted_clips):
        shot_id, sequence, duration_ms, uri, subtitles, item = _accepted_clip_values(accepted, index)
        if shot_id in seen_ids:
            raise ValueError(
                f"duplicate accepted shot_id {shot_id!r} (first at index {seen_ids[shot_id]})"
            )
        if sequence in seen_sequences:
            raise ValueError(
                f"duplicate accepted sequence {sequence} (first at index {seen_sequences[sequence]})"
            )
        if shot_id not in plan_shot_ids:
            raise ValueError(f"accepted_clips[{index}].shot_id {shot_id!r} is not in plan.shots")
        planned_shot = plan_shot_by_id[shot_id]
        if sequence != planned_shot["sequence"]:
            raise ValueError(
                f"accepted_clips[{index}].sequence does not match plan.shots for {shot_id!r}"
            )
        if duration_ms != planned_shot["duration_ms"]:
            raise ValueError(
                f"accepted_clips[{index}].duration_ms does not match plan.shots for {shot_id!r}"
            )
        if "subtitles" not in item:
            subtitles = _subtitle_spec(
                planned_shot.get("subtitles"),
                f"plan.shots[{seen_ids.get(shot_id, index)}].subtitles",
                duration_ms,
            )
        seen_ids[shot_id] = index
        seen_sequences[sequence] = index
        values.append((shot_id, sequence, duration_ms, uri, subtitles, item))

    missing_shots = plan_shot_ids - set(seen_ids)
    if missing_shots:
        raise ValueError(
            "accepted_clips must include every planned shot; missing "
            + ", ".join(sorted(missing_shots))
        )

    values.sort(key=lambda item: item[1])

    builder = VideoPackageBuilder(
        _assembly_package_id(project_id),
        title,
        revision=package_revision,
        locale=locale,
        project_id=project_id,
    )
    for shot_id, sequence, duration_ms, uri, subtitles, item in values:
        asset_key = f"source_video.{shot_id}"
        builder.add_asset(_asset(asset_key, "video", uri))
        context: dict[str, Any] = {"skill": "virtual-presenter", "shot": shot_id}
        continuity = item.get("continuity", plan_shot_by_id[shot_id].get("continuity"))
        if continuity is not None:
            context["continuity"] = continuity
        builder.add_clip(ClipSpec(
            clip_id=shot_id,
            sequence=sequence,
            duration_ms=duration_ms,
            generation=GenerationSpec(
                operation="video.passthrough",
                prompt=f"Pass through accepted virtual-presenter clip {shot_id}",
                requirements=_requirements(output),
                references=[_reference(
                    "source_video",
                    asset_key,
                    "source.accepted_video",
                    "source_video",
                )],
            ),
            subtitles=subtitles,
            source_context=context,
        ))
    return builder.output(output).approval(_approval_declaration(approval)).build()


__all__ = ["build_assembly_package", "build_shot_package"]
