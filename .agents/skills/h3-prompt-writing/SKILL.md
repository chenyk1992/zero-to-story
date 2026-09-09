---
name: h3-prompt-writing
description: Write one complete MiniMax H3 video-generation prompt for a single approved Panel in T2VA, I2VA, FL2VA, or Ref2VA form supported by the current LFO contract. Use when composing the required H3 sections, aligning keyframes and timing, or defining reference labels; return only the prompt text, with no manifest, lock, hash, retry or QC sidecar.
---

# H3 Prompt Writing

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。本 Skill 只完成一个已确认 Panel 的提示词工作单元，不执行生成、不做内容 `ACCEPT`、不建立监控代理；下游必须依据实际视频和实际音频证据验收。

## Priority and stop conditions

The current user instruction is authoritative over this Skill's defaults. When the user or upstream handoff supplies the operation, timing, references and dialogue needed for one Panel, write and return the prompt directly without another confirmation round. Project-level LFO contracts, platform permissions and safety boundaries still apply; user priority does not authorize unsupported modes or fabricated assets.

Stop after one concise incompatibility report when a required mode, asset, field, timing value or reference mapping is missing or contradictory. Do not silently redesign the Panel, invent a reference, emit an unusable prompt or retry the same inputs. Continue only when the user or upstream caller supplies a concrete correction or new approved input.

## Workflow

1. Identify the input mode: T2VA, I2VA, FL2VA, or full-reference Ref2VA. Last-frame-only L2VA is not an executable LFO mode; stop with a concise incompatibility report naming the supported correction instead of emitting an unusable prompt or repeating a confirmation request.
2. When a zero-to-story director plan or current user specification is supplied, treat its operation, Camera Setup sequence, timing and pacing as fixed input. Do not independently redesign the scene unless the user explicitly asks for that change.
3. For base text/keyframe modes, read references/base-en.txt. For full-reference mode, read references/ref-en.txt.
4. Preserve the exact field names, section order, labels and timing notation required by the selected guide.
5. Run a mandatory shot-header format gate before returning: the first header must be `[Shot 1]` followed directly by descriptive prose. `[Shot 1] At ...`, `[Shot 1] From ...`, `[Shot 1] 00:...` and any first-shot time range are invalid and must be rewritten. Every later shot header must use `[Shot N] At <approved-cut-time>, ...`.
6. Return one complete prompt for the single Panel. The prompt is passed unchanged into the approved execution package; do not emit a sidecar manifest, lock object, hash record or duplicate QC document.

## Base Modes

- T2VA: build the audiovisual timeline from text and approved text anchors.
- I2VA: start from the supplied first frame and develop forward.
- FL2VA: describe one continuous path between supplied first and last frames.
- Ref2VA/R2V: use the full-reference six-section form whenever the approved operation is `video.reference_to_video`, including when its only visual input is one variable-grid storyboard board.

Use integrated_multimodal_description, overall_soundscape and non_diegetic_music in the order shown in references/base-en.txt.

## Director-plan handoff

The upstream creative plan is authoritative for dramatic pacing, operation, Camera Setup count, cut points, camera position, axis side, subject facing, gaze target, screen direction and visual anchors. Treat an approved variable-grid storyboard board as one ordered planning reference. For a zero-to-story handoff, preserve its locked `rowsxcolumns` layout of 2–6 cells and row-major cell mapping, but do not create a separate reference image or H3 [Shot N] for each cell. Emit one [Shot N] for each actual Camera Setup, preserving same-setup development inside one shot.

Use approved character and scene text anchors whenever the selected mode needs stable visual detail. Do not invent a second identity or environment description. If a required anchor is absent, report the incompatibility to the caller instead of silently deleting a reference or changing the mode; if all required anchors are present, continue directly.

## Continuity handoff constraints

Validate the operation against the approved director intent and actual shot relationship:

- Same-scene continuous handoff: prefer I2VA (video.image_to_video) with the previous clip's real tail frame as the exact first frame. Treat it as an already completed visible state and start the new action immediately; never rewind or replay the boundary action.
- Exact first and last frame together: use FL2VA (video.first_last_frame) and describe one forward path between those keyframes.
- When the approved operation is Ref2VA/R2V (video.reference_to_video), consume its variable-grid storyboard board, other full references or intentional hard-cut plan without changing the mode. The whole storyboard board is one ordinary reference image; it may guide ordered viewpoints, identity, composition or state, but it is not an exact video first-frame lock.

The current user or upstream plan chooses the operation. This Skill checks that the selected mode can consume the supplied assets and writes the corresponding H3 form. If it cannot, stop with a concise incompatibility report.

The supplied timing is authoritative. Do not stretch, compress, reorder, merge or invent dialogue/action windows. Preserve the approved duration and Camera Setup boundaries. For P002 and later, the upstream plan's boundary Beat is zero-duration context, not necessarily a storyboard cell. If the approved cell mapping includes that boundary state, it adds no shot, action, dialogue or duration; if it does not, do not invent a replacement cell. For a continuous handoff, the first effective shot must advance from the completed pose, gaze, screen direction and prop state. For an approved hard cut or new scene, begin with the first current-Panel Setup instead of inserting or replaying the prior boundary state. Keep one transition ownership per boundary so adjacent clips do not repeat the same closing action.

## Full-Reference Mode

Ref2VA rewrites use subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape and non_diegetic_music in that order. Reference labels stay consistent across every section.

When the handoff supplies fixed typed LFO slots, preserve their identities: `ref_image_0` maps to `<Picture 1>`, `ref_video_0` to `<Video 1>` and `ref_audio_0` to `<Audio 1>`, with the same zero-based-to-one-based mapping for later slots. Define only assets actually supplied; do not renumber, duplicate or invent references.

Read references/ref-en.txt for label rules, retention analysis and the complete example.

## Output Rules

- Write rewrite sections in English; preserve dialogue, lyrics and visible scene text in their original language.
- Describe every actual shot by composition, subjects, environment, actions, camera, sound and the exact point where referenced content appears.
- Shot-header syntax is strict: write `[Shot 1]` followed immediately by its prose description. Never put `At 00:00.000`, `From 00:00.000`, a time range or any other timestamp after `[Shot 1]`. Express its end only through the next header, such as `[Shot 2] At 00:04.000`; only later shots carry approved strictly increasing cut times. Before returning, rewrite the prompt if the first shot header contains any time expression.
- Keep [Shot N] count and cut times aligned with the approved Camera Setup plan, not the number of storyboard cells.
- Represent one storyboard-board asset with one `<Picture N>` label; never invent labels or input images for its individual cells.
- Preserve every approved dialogue event verbatim, including speaker, language and timing. Use the required H3 dialogue markers from the selected guide.
- Avoid plot summaries, unresolved reference labels, invented timing, extra shots and unapproved references.
- Return the complete H3 prompt as the sole execution text. Do not add a title, explanation, Markdown fence, negative-prompt block, manifest, lock metadata or hash line.
