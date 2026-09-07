# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P007 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P007｜鱼乐之问｜11.0s |
| 生成模式 | R2V；固定 `ref_image_0` 苏轼、`ref_image_1` 王弗、`ref_image_2` P007 黑白分镜板；均为语义参考，无首帧绑定。 |
| Prompt formal/candidate SHA-256 | `BE503C34FB239FA95FF2FD6DEE9D808D6F85F1BDBF34E0EEDB89696FD58E43A3`；两份逐字节一致。 |
| 对白 | D011 由 S7 王弗先说；D012 由 S5 苏轼后说；均逐字、一次、无重叠。 |
| 边界 | P006 B031 仅作故事语义锚点；P007 拥有竹径硬切、初见、D011、D012 与 B036；P008 才拥有“稳”的评价。 |

## v01 根控门

- `ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`
- 执行包：`workspace/projects/yisuo-ep003-codex-director/packages/execution-package-p007-r001.json`；revision 1。
- R2V 计划通过；ComfyUI H3 backend `comfyui.h3`。

## v01 通过记录

- LFO run：`run-e6bb38a2e956`；状态 `COMPLETED`。
- 成片：`workspace/projects/yisuo-ep003-codex-director/final/p007-r001/yisuo-ep003-p007-r001-run-e6bb38a2e956.mp4`。
- 视频 SHA-256：`C61D4125EFFC42DFA4D0E7C165810864C32DF736DC3B0C135D386FCB08085D82`；实测 11.125s、1080×1920、H.264/AAC、24fps。
- 主控 QC：`SEMANTIC_QC: PASS_WITH_POST_CONSTRAINTS`；报告：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p007-r001-root.md`。
- Mimo 时序描述：`workspace/projects/yisuo-ep003-codex-director/qc/mimo-description-p007-r001.txt`；密集抽帧证据：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p007-r001-dense-contact.png`。
- 真实尾帧：`workspace/projects/yisuo-ep003-codex-director/tails/P007_tail_r001.png`；SHA-256：`385AAF616361ADBB38A6A8D183DB887FD0A56A18D8A890FAB7C5737E6F6F8352`；已同步至 `packages/assets/tails/P007_tail_r001.png`。

## 当前状态

P007 r001 已通过主控语义与技术门（保留最终 SRT 后期约束），已解锁 P008。P008 必须以 `P007_tail_r001.png` 为唯一真实首帧，保持王弗左、苏轼右、丫鬟后景和 B036 已起笑状态，不得重演 D011/D012。

