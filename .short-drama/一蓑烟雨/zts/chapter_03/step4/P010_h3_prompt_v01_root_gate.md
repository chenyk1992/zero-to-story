# P010 H3 prompt v01 root gate

- Panel: P010《文章要不要稳》 / 11.0s / R2V
- Prompt formal/candidate SHA-256: `1C648B790DB822E7348D22DD6DA3DFDA851CC97196B6AEE677F1A5385BF2238F`; byte-identical.
- References: Su Shi identity, Su Zhe identity, and approved board_P010; all are semantic guidance, no temporal frame binding.
- Camera setups: C019 0.0–5.5s, C020 5.5–11.0s
- Voice lock: S8 苏辙 for D017; S5 苏轼 for D018. Each line is verbatim, on-camera, once, and non-overlapping.
- Transition lock: P009 B046 is a story anchor only; P010 owns the night-study hard cut, D017, one desk tap, D018, and B051; P011 owns brush release, promise, and stacked hands.

## Root checks

- PASS: R2V establishes the new night study and does not claim exact continuity from P009; bamboo, water, Wang Fu, maid, and guqin do not carry over.
- PASS: Su Zhe is screen-left and distinct from Su Shi; he alone holds one brush and speaks D017 first. Su Shi is screen-right and has no brush in C019.
- PASS: the desk paper remains deliberately unreadable; no generated Chinese characters, pseudo-writing, subtitles, or UI are permitted.
- PASS: C020 owns exactly one light desk tap, complete S5 D018, and B051 hand-at-paper-edge; no P011 brush release, hand stack, promise, or wall-shadow tableau.
- PASS: 11.0s, 9:16, 0.4 MP, 24 fps, native audio; optional short strings are a post-only layer.

ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED

Independent subagent QC is unavailable in this run because the user has asked root to execute directly; root will perform dense identity, brush-count, paper-text, tap-count, dialogue, and B051 boundary QC before P011 unlock.
