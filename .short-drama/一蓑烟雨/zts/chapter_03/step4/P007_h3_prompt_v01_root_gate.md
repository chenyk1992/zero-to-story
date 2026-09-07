# P007 H3 prompt v01 root gate

- Panel: P007《鱼乐之问》 / 11.0s / R2V
- Prompt formal/candidate SHA-256: `BE503C34FB239FA95FF2FD6DEE9D808D6F85F1BDBF34E0EEDB89696FD58E43A3`; byte-identical.
- References: Su Shi identity, Wang Fu identity, and approved board_P007; all are semantic guidance, not an exact first frame.
- Camera setups: C013 0.0–6.0s, C014 6.0–11.0s
- Voice lock: S7 王弗 for D011; S5 苏轼 for D012. Each line is verbatim, on-camera, once, and non-overlapping.
- Transition lock: P006 B031 is a semantic story anchor only; P007 owns the bamboo-path hard cut, first meeting, both lines, and B036. P008 owns the next “稳” evaluation.

## Root checks

- PASS: R2V is appropriate for a new space; no false exact-first-frame claim and no P006 paper/title/crowd carried into the shot.
- PASS: Wang Fu is screen-left, Su Shi enters from screen-right, and the maid remains half a step behind Wang Fu; the axis must not flip.
- PASS: C013 gives Wang Fu the complete D011 first, with visible mouth and S7 voice; C014 gives Su Shi the complete D012 after a beat, with visible mouth and S5 voice.
- PASS: D011 and D012 are copied verbatim from the speaker registry; no “稳” line or P006 D010 replay is allowed.
- PASS: The board's B036 end state is explicit: Wang Fu has already begun a restrained natural smile, Su Shi remains opposite, maid in rear, all three empty-handed.
- PASS: 11.0s, 9:16, 0.4 MP, 24 fps, native audio, no generated on-screen text or props.

ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED

Independent subagent QC is unavailable in this run because the user has asked root to execute directly; root will perform dense video, dialogue, identity, axis, and B036 boundary QC before P008 unlock.
