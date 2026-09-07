# P008 H3 prompt v02 root gate

- Panel: P008《不是快，是稳》 / 10.0s / I2V
- Prompt formal/candidate SHA-256: `82343468849B9319251131F7211D8B2650F8031E071B395AB753D03503E40454`; byte-identical.
- Input tail: `tails/P007_tail_r001.png` / `385AAF616361ADBB38A6A8D183DB887FD0A56A18D8A890FAB7C5737E6F6F8352`
- Revision reason: v01 generated a yellow paper/scroll and pseudo-writing from approximately 2s; v02 adds a global all-frame empty-hands/no-prop lock and removes any ambiguous presentation gesture.
- Camera setups: C015 0.0–7.0s, C016 7.0–10.0s
- Voice lock: S7 王弗 for D013; S5 苏轼 for D014. Each line is verbatim, on-camera, once, and non-overlapping.
- Transition lock: B036 inherited exactly; P008 owns “稳”, D014, and B041; P009 owns the pool-water explanation.

## Root checks

- PASS: v02 preserves the only first-frame reference, exact B036 start, same axis, D013/D014, and B041; no story beat is changed.
- PASS: a global active constraint keeps Wang Fu, Su Shi, and the maid empty-handed at every frame and explicitly bans paper, scrolls, books, fans, brushes, flat rectangles, pseudo-writing, and looking at an object.
- PASS: C015 still gives Wang Fu one tiny formal empty-hand settling gesture and complete S7 D013; C016 gives only S5 D014 after a beat.
- PASS: Wang Fu remains screen-left, Su Shi screen-right, maid rear; the final turn is only toward the implied pool and D015 remains owned by P009.
- PASS: 10.0s, 9:16, 0.4 MP, 24 fps, native audio, no generated on-screen text.

ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED

Independent subagent QC is unavailable in this run because the user has asked root to execute directly; root will perform dense video, prop, dialogue, identity, axis, and B041 boundary QC before P009 unlock.
