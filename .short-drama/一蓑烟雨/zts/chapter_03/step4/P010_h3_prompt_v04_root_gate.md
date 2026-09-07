# P010 H3 prompt v04 root gate

- Panel: P010《文章要不要稳》 / 11.0s / R2V
- Prompt formal/candidate SHA-256: `2535CF0E48BF1C65E6649BE47D45A5AEE2F772818332CC548838641C078DC4A8`; byte-identical.
- Revision reason: v02/v03 accidentally treated ordinary bookroom props and background paper ink as forbidden. Canonical scene text says “桌上摊满科举文章”; v04 restores spread examination papers and a restrained inkstone, and only targets the actual boundary defect observed in r002: a persistent human-shaped wall shadow before P011.
- References: Su Shi identity, Su Zhe identity, and approved board_P010. Board is used for blocking, axis, candles, paper, brush and beat order; canonical scene text governs legitimate desk context.
- Camera setups: C019 0.0–5.5s, C020 5.5–11.0s.
- Voice lock: S8 苏辙 for D017; S5 苏轼 for D018. Each line is verbatim, once, and non-overlapping.

## Root checks

- PASS: two brothers remain screen-left/right; no third human body, extra brush, modern object, or wrong readable text.
- PASS: several spread examination papers and a modest inkstone are explicitly legitimate S003 context; natural small unreadable paper ink is allowed, while large readable wrong/modern text is not.
- PASS: C019 owns one brush-circle on a risky passage and D017; C020 owns exactly one light desk tap, D018 and B051.
- PASS: rear wall stays ordinary dim plaster/timber; P011's deliberate stacked-hands wall-shadow tableau cannot appear early.
- PASS: 11.0s, 9:16, 0.4 MP, 24 fps, native audio; direct semantic QC only, no postproduction text or repair.

`ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`

v04 is the corrected, final planned P010 retry. If the wall remains an ambiguous natural shadow but the scene otherwise matches the canonical script, report the ambiguity rather than inventing a prop-count failure.
