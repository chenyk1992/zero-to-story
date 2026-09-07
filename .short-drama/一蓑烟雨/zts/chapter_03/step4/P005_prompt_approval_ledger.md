# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P005 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P005｜三掌群鱼｜10.0s |
| 首帧 | `workspace/projects/yisuo-ep003-codex-director/tails/P004_tail_r008.png`；SHA-256：`FBD5718CB3D204D56D52012D628C8D09DA81CBD26B51C659CE4A51C1F961890F` |
| 生成模式 | I2V；唯一 `first_frame`；`board_P005.png` 仅作创作/分镜输入。 |
| 对白 | D009，由 S6 丫鬟逐字一次；P005 不得新增 P006 的揭晓对白。 |
| 边界 | B021 零时长锚点不重演题名/抬手；三次击掌、鱼群响应、丫鬟入场和托笺归 P005；B026 只到丫鬟站定托唯一未读题笺，交接/展开归 P006。 |

## r001 记录

- Prompt formal/candidate SHA-256：`B1F7AAFACAE86A52E421B96AC42E74A25B334C035545283C10EB90442E595A1B`；两份文件逐字节一致。
- 执行包：`packages/execution-package-p005-r001.json`；LFO run：`run-e6ec847ca03f`。
- 成片：`final/p005-r001/yisuo-ep003-p005-r001-run-e6ec847ca03f.mp4`；实测 10.125s、1080×1920、H.264/AAC、24fps。
- 主控 QC：`SEMANTIC_QC: FAIL`，报告：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p005-r001-root.md`。
- 硬阻断：密集逐帧检查发现 0.2–2.9s 多次反复接触，无法证明恰好三次离散击掌；因此不提取/登记 r001 尾帧，P006 保持锁定。

## r002 记录

- Prompt formal/candidate SHA-256：`42DB7DD99EF8B47A5F63C24C878EA32AFB98893AC02F55ECE8B815ABF68BF9EE`；两份文件逐字节一致。
- 执行包：`packages/execution-package-p005-r002.json`；LFO run：`run-1bfbf1d760ee`；成片：`final/p005-r002/yisuo-ep003-p005-r002-run-1bfbf1d760ee.mp4`。
- 主控 QC：FAIL；密集抽帧仍见多于三次可疑接触，未登记尾帧。失败 Run 保留。

## r003 记录

- Prompt formal/candidate SHA-256：`AF7E3F8AB51D678D021F84A164F0A85862EA0339C915CCB02E707D8B493A77AC`；两份文件逐字节一致。
- 执行包：`packages/execution-package-p005-r003.json`；revision 3；LFO run：`run-a6969a82e4b8`。
- 成片：`final/p005-r003/yisuo-ep003-p005-r003-run-a6969a82e4b8.mp4`；视频 SHA-256：`0C4EF1A7329C36E0C5D94CFF67F5729E978216FDA765015BE05D2D33C651D7C2`；实测 10.125s、1080×1920、H.264/AAC、24fps。
- 主控 QC：`SEMANTIC_QC: PASS_WITH_POST_CONSTRAINTS`；报告：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p005-r003-root.md`。
- C009 24fps 抽帧与音频波形均支持三次独立击掌及鱼群因果；C010 单丫鬟/单笺、D009 逐字口型与 B026 未交接边界通过。
- 真实尾帧：`tails/P005_tail_r003.png`；SHA-256：`BAB7D9FEAE91B98FA7F9CB41F190A20C2C77B349264FC56512708C576DA4043B`。

## 当前状态

P005 r003 已通过主控语义与技术门（带字幕后期约束），已解锁 P006。P006 必须从 `P005_tail_r003.png` 真实尾帧接力，第一有效动作只能是交接并展开题笺；不得回放击掌、涟漪或丫鬟入场。
