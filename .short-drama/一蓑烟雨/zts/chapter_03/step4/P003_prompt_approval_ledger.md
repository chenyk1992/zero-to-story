# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P003 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P003｜众题落空｜10.0s |
| v01 | 正式稿/候选 SHA-256：`C29A1D20E5B3DE5606B83E259F484DA12894CE9452A30AE44C64711CB985F2EC`；独立 QC **FAIL**，唯一硬阻断为 C006 动作与两句对白过密；历史文件保留。 |
| v02 Prompt | 正式稿与 immutable candidate SHA-256：`C5AFBBB0BA9D0C7AE3ECE25967B232A14149A94CF21E6B6A15D169CA9DC34A5E`。 |
| v02 H3 body | SHA-256：`480C028C0AA876B73543CEF33052D67A06134CBE30323BB278499FB75269C3DE`。 |
| 独立 QC | **PASS**；D005 `5.55–6.35s`、钱翁单次连贯起身 `6.40–7.45s`、D006 `7.55–9.35s`、B016 hold `9.45–10.00s`，已解除抢词/截断/动作未完成风险。 |
| 首帧 | `workspace/projects/yisuo-ep003-codex-director/tails/P002_tail_r003.png`；SHA-256：`80FC0BC4BA306DE7D2E4B1944364E50BC3E5815F4910D4ED9E9ABA7F060119D3`；P002 r003 已 `PASS_WITH_REPAIR`。 |
| 生成模式 | I2V；唯一 `first_frame`，黑白分镜只作规划输入，不作为运行时参考图。 |
| 对白 | S3/D003 → S1/D004 → S4/D005 → S2/D006；逐字各一次；题名仅听见，不在题笺或字幕中显示。 |
| 边界 | B011 为零时长锚点；B016 只到“将笑未笑”，笑声与大笑动作归 P004。 |
| 主代理最终门检 | **PASS**；批准建立 P003 revision 1 execution package 并执行。 |
| 当前状态 | **STEP4 approved; STEP5 package/execute authorized; P004 blocked pending P003 video QC** |

### 交接约束

P003 只允许使用已封存的 P002 r003 真实尾帧作为 first-frame lock。生成后先做技术 QC、语义/对白 QC 与 P002→P003 成对边界 QC；通过前不得把 P003 尾帧交给 P004。失败 Run 必须保留，不覆盖历史。

## STEP5 视频执行与版本门禁

| 版本 | 结果 | 记录 |
|---|---|---|
| r001 | **FAIL（语义画面）** | 技术通过，但钱翁展开折扇并出现明显汉字/伪字样；保留 Run `run-0591805e2ed4` 与原始产物，不向 P004 交接。 |
| v03 修订 | **PROMPT_INDEPENDENT_QC: PASS** | 只收紧折扇为合拢/扇套/侧背向镜头；文件 SHA `5053C3054E86AD887234DB9C314C939D8712C1FB4CB21210649BBFD08F80B1E7`；H3 body SHA `E64FCE8011B0A807588AC3FD76F750B5A9144CA2A9C78E3D700A20513ACA7DDC`。 |
| r002 | **PASS（画面语义）** | Run `run-d0b184b41142`；技术 `PASS_NO_HARD_TECHNICAL_BLOCKER`，10.125s、1080×1920、24fps、H.264/AAC、无黑帧/冻结；独立关键帧 QC **PASS**，扇面无可读字、钱翁一次起身并站定持笺/合扇、苏轼坐着；对白身份因静帧无法确认标 `UNCERTAIN`，需后期听审。 |
| r002 终片 | `workspace/projects/yisuo-ep003-codex-director/final/p003-r002/yisuo-ep003-p003-r002-run-d0b184b41142.mp4`；SHA-256：`325005CE2A8BCEF6C1B6998549B04CE3FF1595F6A21C5DEB7D0E32DFC4513892`。 |
| r002 真实尾帧 | `workspace/projects/yisuo-ep003-codex-director/tails/P003_tail_r002.png`；SHA-256：`06C765A7A19030FB11ACA4F8E221142A434BEA6DFC7B165CEE5A8DC75C50E766`。 |
| 当前状态 | **P003 r002 accepted for P004 first-frame handoff; P004 STEP4 can start; audio/dialogue listen-through remains flagged for final assembly review.** |
