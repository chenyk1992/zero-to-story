# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P009 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P009｜第一个说我安静的人｜13.0s |
| 生成模式 | I2V；唯一 `first_frame` 为 P008 r002 真实尾帧。 |
| Prompt formal/candidate SHA-256 | `342FA4297F1C3C8AD813688B64FD3B8368B7F08D19B993D222BACC2FD4685AC0`；两份逐字节一致。 |
| 对白 | D015 由 S7 王弗先说；D016 由 S5 苏轼后说；均逐字、一次、无重叠。 |
| 边界 | B041 由 P008 继承；P009 拥有看水解释、D016 私人承认和 B046 静默尾态；P010 拥有夜书房硬切。 |

## v01 根控与执行

- `ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`。
- 执行包：`workspace/projects/yisuo-ep003-codex-director/packages/execution-package-p009-r001.json`；revision 1；ComfyUI H3 I2V 计划通过。
- LFO run：`run-39c31549525b`；状态 `COMPLETED`。
- 成片：`workspace/projects/yisuo-ep003-codex-director/final/p009-r001/yisuo-ep003-p009-r001-run-39c31549525b.mp4`；SHA-256：`5FCF85F997A334FC89E375563C88DBA0E27DBD15D951DBF7D7E3D3ED441E7F3F`。
- 实测：13.125s、1080×1920、H.264/AAC、24fps；主控 `SEMANTIC_QC: PASS_WITH_POST_CONSTRAINTS`。
- QC：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p009-r001-root.md`；密集抽帧：`qc/semantic-p009-r001-dense-contact.png`。
- 真实尾帧：`workspace/projects/yisuo-ep003-codex-director/tails/P009_tail_r001.png`；SHA-256：`A83C1EDF9B274F0FD1E097BF0C635AB8F154C9C19F59A673DE6AC248C569B1A4`；已同步至 `packages/assets/tails/P009_tail_r001.png`。

## 当前状态

P009 r001 已通过主控语义与技术门（保留 B046 琴音后期约束），已解锁 P010。P010 必须从竹径切至夜书房的新时空，不得把 P009 的人物道具或琴音跨 Clip 带入。

