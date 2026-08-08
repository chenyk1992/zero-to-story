"""Video Prompt Blueprint Compilers.

Each compiler extracts semantic parts from a shot and assembles a PromptBlueprint.
The blueprint captures the prompt structure before asset materialization.

Supported compilers:
- compile_t2va_blueprint: text-only, no image dependencies
- compile_i2v_blueprint: prompt with symbolic start frame reference
- compile_first_last_blueprint: prompt with symbolic start + end frame references
- compile_r2v_blueprint: prompt with symbolic <Picture N> references
"""
from __future__ import annotations

from lfo.storyboard.storyboard import Shot, Storyboard

from .schema import PromptBlueprint, PromptPart, ReferenceBinding


def _build_base_parts(shot: Shot, storyboard: Storyboard) -> list[PromptPart]:
    """Extract common semantic parts from a shot."""
    parts: list[PromptPart] = []

    # Subject: from characters and their actions
    subject_parts: list[str] = []
    for char_app in shot.characters:
        char = storyboard.character_by_id(char_app.character_id)
        char_name = char.name if char else char_app.character_id
        action = char_app.action
        if action:
            subject_parts.append(f"{char_name} {action}")
        else:
            subject_parts.append(char_name)
    if subject_parts:
        parts.append(PromptPart(
            part_type="subject",
            content=", ".join(subject_parts),
            source="shot.characters",
        ))

    # Scene: from scene description
    scene = storyboard.scene_by_id(shot.scene_id)
    if scene and scene.description:
        parts.append(PromptPart(
            part_type="scene",
            content=scene.description,
            source="scene.description",
        ))
    elif shot.description:
        parts.append(PromptPart(
            part_type="scene",
            content=shot.description,
            source="shot.description",
        ))

    # Action: from action_beats
    if shot.action_beats:
        beat_descriptions = [b.description for b in shot.action_beats if b.description]
        if beat_descriptions:
            parts.append(PromptPart(
                part_type="action",
                content=" then ".join(beat_descriptions),
                source="shot.action_beats",
            ))

    # Camera: from camera spec
    cam = shot.camera
    camera_parts: list[str] = []
    if cam.shot_size and cam.shot_size != "medium":
        camera_parts.append(cam.shot_size)
    if cam.angle and cam.angle != "eye_level":
        camera_parts.append(cam.angle)
    if cam.movement and cam.movement != "static":
        camera_parts.append(cam.movement)
    if cam.focus:
        camera_parts.append(f"focus on {cam.focus}")
    if camera_parts:
        parts.append(PromptPart(
            part_type="camera",
            content=", ".join(camera_parts),
            source="shot.camera",
        ))

    # End state: from continuity
    if shot.continuity.end_state:
        parts.append(PromptPart(
            part_type="end_state",
            content=shot.continuity.end_state,
            source="shot.continuity.end_state",
        ))

    # Audio: from audio policy hints
    audio = storyboard.audio_policy
    if audio and audio.mode != "none":
        audio_parts: list[str] = []
        if audio.music != "none":
            audio_parts.append(f"music: {audio.music}")
        if audio.sound_effects != "none":
            audio_parts.append(f"sound_effects: {audio.sound_effects}")
        if audio.ambient != "none":
            audio_parts.append(f"ambient: {audio.ambient}")
        if audio.dialogue != "none":
            audio_parts.append(f"dialogue: {audio.dialogue}")
        if audio_parts:
            parts.append(PromptPart(
                part_type="audio",
                content=", ".join(audio_parts),
                source="storyboard.audio_policy",
            ))

    # Style: from StyleGuide (medium lock + keywords)
    style = storyboard.style
    if style.medium_lock:
        parts.append(PromptPart(
            part_type="style",
            content=style.medium_lock,
            source="storyboard.style.medium_lock",
        ))
    if style.style_keywords:
        parts.append(PromptPart(
            part_type="style_keywords",
            content=", ".join(style.style_keywords),
            source="storyboard.style.style_keywords",
        ))

    # Negative: standard negative prompts
    parts.append(PromptPart(
        part_type="negative",
        content="blurry, distorted, low quality, watermark, text",
        source="standard_negative",
    ))

    return parts


def compile_t2va_blueprint(shot: Shot, storyboard: Storyboard) -> PromptBlueprint:
    """T2VA: directly materializes final prompt (no image dependencies)."""
    parts = _build_base_parts(shot, storyboard)
    return PromptBlueprint(
        blueprint_id=f"pb_t2va_{shot.shot_id}",
        compiler_name="h3_t2va_prompt_blueprint",
        target_shot_ids=[shot.shot_id],
        workflow_mode="t2va",
        parts=parts,
        symbolic_references=[],
        materialization_status="complete",
    )


def compile_i2v_blueprint(shot: Shot, storyboard: Storyboard) -> PromptBlueprint:
    """I2V: prompt with symbolic reference to start frame."""
    parts = _build_base_parts(shot, storyboard)
    symbolic_refs = [
        ReferenceBinding(
            slot=1,
            asset_id=f"SYMBOLIC_{shot.shot_id}_start_frame",
            entity_id=shot.shot_id,
            role="composition",
            is_symbolic=True,
        ),
    ]
    return PromptBlueprint(
        blueprint_id=f"pb_i2v_{shot.shot_id}",
        compiler_name="h3_i2v_prompt_blueprint",
        target_shot_ids=[shot.shot_id],
        workflow_mode="i2v",
        parts=parts,
        symbolic_references=symbolic_refs,
        materialization_status="waiting_assets",
    )


def compile_first_last_blueprint(shot: Shot, storyboard: Storyboard) -> PromptBlueprint:
    """First-Last: prompt with symbolic references to start + end frame."""
    parts = _build_base_parts(shot, storyboard)
    symbolic_refs = [
        ReferenceBinding(
            slot=1,
            asset_id=f"SYMBOLIC_{shot.shot_id}_start_frame",
            entity_id=shot.shot_id,
            role="composition",
            is_symbolic=True,
        ),
        ReferenceBinding(
            slot=2,
            asset_id=f"SYMBOLIC_{shot.shot_id}_end_frame",
            entity_id=shot.shot_id,
            role="composition",
            is_symbolic=True,
        ),
    ]
    return PromptBlueprint(
        blueprint_id=f"pb_first_last_{shot.shot_id}",
        compiler_name="h3_first_last_prompt_blueprint",
        target_shot_ids=[shot.shot_id],
        workflow_mode="first_last",
        parts=parts,
        symbolic_references=symbolic_refs,
        materialization_status="waiting_assets",
    )


def compile_r2v_blueprint(
    shot: Shot,
    storyboard: Storyboard,
    reference_bindings: list[ReferenceBinding] | None = None,
) -> PromptBlueprint:
    """R2V: prompt with symbolic <Picture N> references."""
    parts = _build_base_parts(shot, storyboard)
    refs = reference_bindings or []

    # Add picture reference hints to the subject part
    if refs:
        picture_refs = ", ".join(
            f"<Picture {r.slot}>" for r in sorted(refs, key=lambda x: x.slot)
        )
        parts.insert(0, PromptPart(
            part_type="subject",
            content=f"Guided by references: {picture_refs}",
            source="reference_bindings",
        ))

    return PromptBlueprint(
        blueprint_id=f"pb_r2v_{shot.shot_id}",
        compiler_name="h3_r2v_prompt_blueprint",
        target_shot_ids=[shot.shot_id],
        workflow_mode="r2v",
        parts=parts,
        symbolic_references=refs,
        materialization_status="waiting_assets" if refs else "complete",
    )
