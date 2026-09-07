# P008 H3 prompt v01 root gate

- Panel: P008《不是快，是稳》 / 10.0s / I2V
- Prompt formal/candidate SHA-256: `1C01FC545C0616B3D1C8004A6D02CA5D5D54C191934D71F634D5C41A067B439C`; byte-identical.
- Input tail: `tails/P007_tail_r001.png` / `385AAF616361ADBB38A6A8D183DB887FD0A56A18D8A890FAB7C5737E6F6F8352`
- Camera setups: C015 0.0–7.0s, C016 7.0–10.0s
- Voice lock: S7 王弗 for D013; S5 苏轼 for D014. Each line is verbatim, on-camera, once, and non-overlapping.
- Transition lock: B036 is inherited exactly; P008 owns Wang Fu's “稳” evaluation, Su Shi's D014, and B041; P009 owns the pool-water explanation.

## Root checks

- PASS: the only first-frame reference is the accepted real P007 r001 tail; no new scene, no re-establishing entrance, and no replay of D011/D012.
- PASS: Wang Fu remains screen-left and Su Shi screen-right throughout; the maid stays half a step behind Wang Fu and no paper/prop returns.
- PASS: C015 starts from Wang Fu already smiling, then owns one restrained 敛衽礼 and complete S7 D013; Su Shi listens and his smile settles.
- PASS: C016 owns only the complete S5 D014 after a beat; Wang Fu turns slightly toward the implied pool direction only at the end and does not start D015.
- PASS: B041 is explicit: Wang Fu looks toward the pool preparing to answer, Su Shi watches her, positions unchanged, all hands empty.
- PASS: 10.0s, 9:16, 0.4 MP, 24 fps, native audio, no generated on-screen text or props.

ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED

Independent subagent QC is unavailable in this run because the user has asked root to execute directly; root will perform dense video, dialogue, identity, axis, and B041 boundary QC before P009 unlock.
