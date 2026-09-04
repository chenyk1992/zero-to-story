---
name: h3-prompt-writing
description: Write MiniMax H3 video generation prompts for T2VA, I2VA, FL2VA, L2VA, and Ref2VA. Use when rewriting multimodal requests into H3 prompt structures, composing integrated_multimodal_description, overall_soundscape, and non_diegetic_music, aligning keyframes, or defining reference labels for images, videos, and audio.
---

# H3 Prompt Writing

## Workflow

1. Identify the input mode: T2VA, I2VA, FL2VA, L2VA, or full-reference Ref2VA. When a zero-to-story director plan is supplied, treat its recommended mode and Camera Setup sequence as fixed input; do not independently choose a creative mode or pacing.
2. For base text/keyframe modes, read `references/base-en.txt` and follow its final prompt structure.
3. For full-reference mode, read `references/ref-en.txt` and follow its six-section rewrite format.
4. Preserve the exact field names, section order, labels, and timing notation from the selected guide.
5. Emit a prompt manifest sidecar for the single Panel. The manifest is a
   preflight artifact, not an alternate prompt: it records the approved
   ``plan_hash``, prompt hash, Setup windows, dialogue events, and typed
   reference slots so accidental drift is caught before LFO.

## Base Modes

- T2VA: build the full audiovisual timeline from text.
- I2VA: start from the first frame and develop forward from it.
- FL2VA: describe the continuous path between the first and last frames.
- L2VA: infer a plausible opening and converge to the supplied last frame.

Use `integrated_multimodal_description`, `overall_soundscape`, and `non_diegetic_music` in the order shown in `references/base-en.txt`.

## Director-plan handoff

The upstream creative plan is authoritative for dramatic pacing, Camera Setup count, cut points, camera position, axis side, subject facing, gaze target, screen direction, visual anchors, and the recommended generation mode. Treat six-cell storyboard boards as ordered Beat/visible moments; do not turn each cell into an H3 `[Shot N]`. Emit one `[Shot N]` for each actual Camera Setup, preserving `same_setup` as continuous development inside one shot.

Use the project's approved character and scene text anchors whenever T2VA or I2VA needs stable visual detail. Do not invent a second identity or environment description. If a required visual anchor is absent from the selected mode's inputs, report the conflict and return it to the creative stage; do not silently delete a reference, change the mode, or redesign the rhythm.

## Continuity handoff constraints

Choose/validate the operation from the approved director control intent and actual shot relationship, not from a generic reference list:

- Same-scene continuous handoff: prefer I2VA (`video.image_to_video`) with the previous clip's real tail frame as the exact first frame. Treat that frame as an already completed visible state and start the new action immediately; never rewind, reset, or replay the boundary action.
- Exact first and last frame together: use FL2VA (`video.first_last_frame`) and describe one forward path between those two keyframes. Do not add ordinary references as substitutes for either keyframe.
- Multiple references or an intentional hard cut: use Ref2VA/R2V (`video.reference_to_video`). Reference images may guide identity, composition, or style, but must not be described as an exact video first-frame lock.

The mode recommendation is made upstream after the full-story rhythm and Camera Setup design. This Skill only checks that the recommendation can consume the supplied assets and writes the corresponding H3 form. If it cannot, stop with a concise incompatibility report instead of making a quiet fallback.

The supplied production timing is authoritative. Do not stretch, compress,
reorder, merge, or invent dialogue/action windows while rewriting prose. If a
prompt cannot express the approved schedule, report the conflict to
``zero-to-story`` before LFO; after the production lock, only wording-level
prompt revision is allowed and it must carry the same ``plan_hash``.
When revising a locked prompt, regenerate the manifest's prompt bytes and
``prompt_hash`` while preserving its Setup windows, dialogue events,
references, and ``plan_hash``; do not use a revision to alter timing or
coverage.

For P002 and later, the shared storyboard first cell is a zero-duration boundary anchor: preserve its completed pose, gaze, screen direction, and prop state without assigning it a new action, beat, dialogue, or duration. The first effective shot must advance from that state. Keep one `transition ownership` per boundary so adjacent clips cannot perform the same closing action twice.

## Full-Reference Mode

Ref2VA rewrites use `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, and `non_diegetic_music` in that order. Reference labels stay consistent across all sections.

Read `references/ref-en.txt` for label rules, retention analysis, and complete examples.

## Output Rules

- Write rewrite sections in English; preserve dialogue, lyrics, and visible scene text in their original language.
- Describe each shot by composition, subjects, environment, actions, camera, sound, and the exact point where referenced content appears.
- Avoid plot summaries, unresolved reference labels, and timing that does not match the requested duration.
- Alongside the confirmed prompt, write ``prompt-manifests/<panel>.json`` with
  this minimum shape (all times are local milliseconds):

  ```json
  {
    "schema": "h3.prompt-manifest.v1",
    "clip_id": "P001",
    "plan_hash": "<64-char SHA-256 from the locked Clip plan>",
    "prompt_hash": "<SHA-256 of the exact UTF-8 prompt>",
    "operation": "video.image_to_video",
    "duration_ms": 8000,
    "prompt": "<the complete confirmed H3 prompt>",
    "setup_windows": [{"id": "C001", "start_ms": 0, "end_ms": 8000}],
    "dialogue_events": [{
      "event_id": "D001", "speaker_id": "S1", "text": "逐字对白",
      "start_ms": 1200, "end_ms": 1800, "allow_overlap": false
    }],
    "references": [{"label": "Picture 1", "slot": "first_frame", "media_type": "image"}]
  }
  ```

  Validate it before handing the prompt to LFO:

  ```powershell
  python .agents/skills/h3-prompt-writing/scripts/validate_prompt_manifest.py prompt-manifests/P001.json
  ```
