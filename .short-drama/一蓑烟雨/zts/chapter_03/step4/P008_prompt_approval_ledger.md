# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P008 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P008｜不是快，是稳｜10.0s |
| 生成模式 | I2V；唯一 `first_frame` 为 P007 r001 真实尾帧。 |
| Prompt v01 SHA-256 | `1C01FC545C0616B3D1C8004A6D02CA5D5D54C191934D71F634D5C41A067B439C`；formal/candidate 逐字节一致。 |
| 对白 | D013 由 S7 王弗先说；D014 由 S5 苏轼后说；均逐字、一次、无重叠。 |
| 边界 | B036 由 P007 继承；P008 拥有“稳”评价、D014 和 B041；P009 才拥有池水解释。 |

## v01 执行与失败

- 执行包：`workspace/projects/yisuo-ep003-codex-director/packages/execution-package-p008-r001.json`；revision 1。
- LFO run：`run-d846f97a35db`；状态 `COMPLETED`。
- 成片：`workspace/projects/yisuo-ep003-codex-director/final/p008-r001/yisuo-ep003-p008-r001-run-d846f97a35db.mp4`；SHA-256：`7FC32BBADC64ACBE09F5CBA8304D2075136ACB5EE90A60E9FB3603137A09EFE8`。
- 实测：10.125s、1080×1920、H.264/AAC、24fps。
- 主控 QC：`SEMANTIC_QC: FAIL`；报告：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p008-r001-root.md`。
- 失败根因：约 2s 后王弗手中凭空出现黄色纸笺，约 6–8s 展开并生成伪字；同时苏轼出现低头看纸的错误动作。该道具违反 P008 双手空/无纸硬约束，尾帧未登记。

## v02 修订门

- Prompt v02 formal/candidate SHA-256：`82343468849B9319251131F7211D8B2650F8031E071B395AB753D03503E40454`；两份逐字节一致。
- `ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`。修订仅针对“全程双手空、无纸/卷轴/文字/书笔扇、禁止低头看纸”道具污染；保留 P007 B036 首帧、D013/D014、S7→S5、轴线与 B041。
- v02 执行包：`workspace/projects/yisuo-ep003-codex-director/packages/execution-package-p008-r002.json`；revision 2；LFO run `run-d7dc4956fe5d`。
- v02 成片 SHA-256：`A11F67FFCA5DAA21AE5AA0EE6FD2839DFC03BA1CE31F67B671B732659BBC606B`；主控 `SEMANTIC_QC: PASS_WITH_POST_CONSTRAINTS`。
- v02 密集抽帧确认全片无纸、无伪字、无额外道具；真实尾帧 `tails/P008_tail_r002.png` SHA-256：`F7197B3E315005E8E2ED1B282CA643156F53084D1B7E9C7465E90E4DFB9CD4EB`，已同步至 `packages/assets/tails/P008_tail_r002.png`。
- `P008_h3_prompt_v01_root_gate.md` 记录 v01 根控门；v02 完成后新增版本文件、哈希和执行包，不覆盖 v01 失败记录。

## 当前状态

P008 r002 已通过并登记真实尾帧；P009 已解锁。不得使用 P008 r001 尾帧作为接力首帧。
