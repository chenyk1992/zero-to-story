# P010 H3 prompt v03 root gate

- Panel: P010《文章要不要稳》 / 11.0s / R2V
- Prompt formal/candidate SHA-256: `8222E4DA439C8B6EAA03167176B401886AFFEDD07D7846FF7FC5451EE33CE199`; byte-identical.
- Revision reason: v02 corrected people count but still rendered book stacks, an inkstone/ink bowl, and text-like rows on the sheet. v03 keeps all narrative beats and timing while making the desk a bare counted set and using board_P010 only for blocking/axis, never its drawn props.
- References: Su Shi identity, Su Zhe identity, and approved board_P010; board is semantic blocking guidance only, not a prop reference.
- Camera setups: C019 0.0–5.5s, C020 5.5–11.0s.
- Voice lock: S8 苏辙 for D017; S5 苏轼 for D018. Each line is verbatim, once, and non-overlapping.

## Root checks

- PASS: global hard locks count exactly two people, one bare desk, one blank cream sheet, two candles, and one brush at every frame.
- PASS: all books, stacked pages, scrolls, inkstones, bowls, cups, seals, extra sheets, writing texture, pseudo-writing, text and edge-body fragments are explicitly excluded.
- PASS: the only mark is one thin oval/circle line made once by Su Zhe's brush in C019; C020 contains no new writing.
- PASS: C019/C020, D017/D018, one soft desk tap, B051 and the P011 boundary are unchanged.
- PASS: 11.0s, 9:16, 0.4 MP, 24 fps, native audio; direct semantic QC required, with no postproduction text or repair.

`ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`

This is the final planned P010 retry. If v03 still violates the counted prop/blank-sheet locks, stop generation and report the model limitation rather than creating another unreviewed variant.
