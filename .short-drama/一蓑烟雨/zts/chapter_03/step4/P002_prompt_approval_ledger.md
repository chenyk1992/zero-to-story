# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P002 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P002｜钱翁轻慢｜12.0s |
| Prompt | v01；正式文件与 immutable candidate SHA-256：`93815D6183B5E4BA38BF07040BCE3AE153E5A7A8C95A63FBADB4EFA9E4977763` |
| H3 body | SHA-256：`C8A39EDDDE56E5AD61F73307D06DD26D343AFCEF02A47B8FBF3F469F60EABA9A` |
| 独立 QC | **PASS**；I2V 结构、唯一 first_frame、首个动作不回卷、D002/S2、7 秒切点、B011 尾态均通过。 |
| 首帧 | `workspace/projects/yisuo-ep003-codex-director/tails/P001_tail_r002.png`；SHA-256：`A055D3DFD279A281E51AFEAB34D2A8678CEA0AD9C5EADFBA0F027B715149E529`；用户已明确放行 P001 r002。 |
| 生成模式 | I2V（`video.image_to_video`）；仅 `first_frame`，不追加普通参考图。 |
| 镜头结构 | C003 `00:00–00:07`；C004 `00:07–00:12`；B006 为零时长锚点，首个有效动作归 P002。 |
| 对白 | D002；钱翁；全局 speaker ID `S2`；逐字一次。 |
| 主代理最终门检 | **PASS**；批准进入 STEP5 package/execute。 |
| 当前状态 | **STEP4 approved; STEP5 package pending** |

## v02 修订闸门（针对 P002 r001 语义失败）

| 项目 | 记录 |
|---|---|
| 失败依据 | P002 r001 技术 PASS，但语义 QC 记录约 00:05–00:06.5 钱翁明显直立、00:11.5–00:12 多人站起；另有可见底部字幕，B011 坐姿准备状态未成立。详见 `workspace/projects/yisuo-ep003-codex-director/qc/semantic-p002-r001-fallback.md`。 |
| Prompt | v02；正式文件与 immutable candidate SHA-256：`C7438D36B95B583F48A2F0B78F1C48DC60CF96C88EA9FC5D5B617FB65DEC4E08` |
| H3 body | SHA-256：`7464E616199317FE5F1EF52D291EA64AFA997914B8FA1A4B9634DE20F551320D` |
| 独立 QC | **PASS（提示词层面）**；收紧钱翁 00:00–00:07 全程坐姿、D002 唯一发声、00:07–00:12 全员坐姿、末 0.5 秒仅前倾 10°，并禁止字幕/宽景/站立。详见 `step4/P002_h3_prompt_v02_independent_qc.md`。 |
| 首帧 | 仍为 `workspace/projects/yisuo-ep003-codex-director/tails/P001_tail_r002.png`；SHA-256：`A055D3DFD279A281E51AFEAB34D2A8678CEA0AD9C5EADFBA0F027B715149E529`。 |
| 主代理最终门检 | **PASS**；允许以 v02 新建 revision 2 execution package 并重跑 P002。 |
| 当前状态 | **P002 v02 STEP4 approved; STEP5 package pending; P003 blocked until repaired P002 passes video QC** |

### 交接约束

P002 生成后必须先做单片技术/语义 QC，再与 P001 r002 做尾 2 秒 + P002 头 3 秒成对边界 QC；只有用户已批准的 P001 r002 尾帧作为真实首帧，不得用文字描述替代。若 P002 通过，提取新的真实尾帧交给 P003；失败 run 保留，不覆盖历史。

## r003 确定性修复与最终视频门禁

| 项目 | 记录 |
|---|---|
| 修复依据 | r002 在约 10 秒后出现多人起身，破坏 B011；保留 0–7 秒原速与 7–9.5 秒安全坐姿段，将后者等速延展至 5 秒，并同步处理音频；未使用源片 10 秒后的坏段。 |
| Run | `run-eba686d4bb2f`；全部任务 `SUCCEEDED`；Package revision `3`。 |
| 最终视频 | `workspace/projects/yisuo-ep003-codex-director/final/p002-r003/yisuo-ep003-p002-r003-run-eba686d4bb2f.mp4`；SHA-256：`C2563012816A07D961E51FB282E0B12879606B1FE3FECF1EA2DA454D60CEE78D`。 |
| 技术 QC | **PASS_NO_HARD_TECHNICAL_BLOCKER**；12.021s、1080×1920、24fps、H.264/AAC、48kHz 双声道；无解码错误、黑帧或冻结帧；见 `qc/technical-p002-r003.json`。 |
| 独立语义/边界 QC | **PASS**，无硬阻断项；钱翁 0–7 秒保持右前座，7–12 秒可见人物维持坐姿，末 0.5 秒钱翁仍坐并一手持扇、一手持一张不可读题笺；P001 尾帧→P002 首帧连续；见 `qc/semantic-p002-r003-fast.md`。对白声源身份仅凭快速本地证据标记为 `UNCERTAIN`，不作为画面硬阻断。 |
| 真实末帧 | `workspace/projects/yisuo-ep003-codex-director/tails/P002_tail_r003.png`；SHA-256：`80FC0BC4BA306DE7D2E4B1944364E50BC3E5815F4910D4ED9E9ABA7F060119D3`。 |
| 主代理最终门检 | **PASS_WITH_REPAIR**；P002 r003 封存为 P003 的唯一真实 first-frame 来源。 |
| 当前状态 | **P002 accepted; P003 unblocked for STEP4 prompt creation** |
