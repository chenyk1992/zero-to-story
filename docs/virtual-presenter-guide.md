# Virtual Presenter v1

`virtual-presenter` is the creative-side workflow for a natural, continuous talking-head
video. The Skill owns the approved presenter plan, Shot Contracts, H3 prompts, semantic QC
and retry decisions. LFO owns asset import, backend selection, technical QC, media
processing, timeline assembly and export.

## Project files

All project data stays under `workspace/projects/<project_id>/`:

```text
presenter_plan.md          creative and stage-state source of truth
inputs/                    byte-faithful character, panorama and voice inputs
environment-pack/          four direction views, contact sheet and manifest
packages/                  revisioned per-Shot and assembly packages
qc/                        semantic QC for every candidate
execution-package.json     package currently offered to LFO
outputs/ and final/        LFO-managed run and publication artifacts
```

The environment helper accepts a roughly 2:1 equirectangular panorama and uses FFmpeg
`v360` to create 1024-square views at yaw `0`, `90`, `180` and `-90`, pitch `0`, and a
90-degree field of view. It rejects other aspect ratios instead of stretching them.

## Execution boundary

An approved Shot Contract is converted with
`lfo.skill_adapter.virtual_presenter.build_shot_package`. The package uses
`video.virtual_presenter`; the materializer selects `comfyui.h3-presenter`, and the video
router dispatches the task to the H3 Presenter workflow without teaching Runtime any
presenter semantics.

The first accepted Shot normally uses the standalone voice anchor. Later Shots add the
same-aspect previous accepted clip as `ref_video_0` and default to its paired soundtrack.
They add `ref_audio_0` as well only when the documented Scene-D comparison accepts the
voice and continuity scores. Each package must pass `validate` and `plan` before execution.

After both aspect-ratio baselines are accepted, unchanged remaining Shots run in sequence.
Each aspect ratio keeps an independent previous-clip chain. Semantic retries first change
the seed and then refine the prompt without changing the Shot Contract; two failed semantic
regenerations, an unparseable MiMo result after one retry, or a needed baseline change
pauses automation.

Accepted clips are converted with
`lfo.skill_adapter.virtual_presenter.build_assembly_package`. Every clip uses
`video.passthrough`, then follows technical QC, audio, subtitle,
timeline and export DAG.

Real H3 generation is intentionally serial on one local ComfyUI/GPU. Static validation and
tests do not require user media, but the approximately 30-second 9:16 and 16:9 acceptance
run requires a character image, a 360-degree panorama, approved copy and a voice sample.
