# P002 H3 Prompt v01 — 独立自检报告

- 检查时间：2026-08-31 08:58:32 +08:00
- 检查范围：`step4/candidates/P002_h3_prompt_v01.md`、`step4/P002_h3_prompt.md`、`storyboard_brief.md`（P002/B006–B011/C003–C004）、`step4/speaker_registry.md`、P001 r002 真实尾帧。
- 执行范围：仅检查 STEP4 I2VA 提示词编译、引用语义和可执行性；不执行 LFO、不提交 ComfyUI、不修改视频、分镜或角色资产。

## 结论

`PROMPT_SELF_QC: PASS`

P002 v01 已按 `h3-prompt-writing` 的 I2VA base form 编译，允许交由根代理进行独立 H3/执行包 QC。未发现需要阻断当前提示词的结构、对白、时序、引用或边界语义问题。

## 1. 不可变文件与 SHA-256

| 文件 | SHA-256 | 备注 |
|---|---|---|
| `step4/candidates/P002_h3_prompt_v01.md` | `93815D6183B5E4BA38BF07040BCE3AE153E5A7A8C95A63FBADB4EFA9E4977763` | 本次 immutable candidate |
| `step4/P002_h3_prompt.md` | `93815D6183B5E4BA38BF07040BCE3AE153E5A7A8C95A63FBADB4EFA9E4977763` | 正式文件，与 candidate 逐字节一致 |
| 正式/候选中的最终 H3 prompt body | `C8A39EDDDE56E5AD61F73307D06DD26D343AFCEF02A47B8FBF3F469F60EABA9A` | UTF-8、仅 code block 内最终提示词内容 |
| `workspace/projects/yisuo-ep003-codex-director/tails/P001_tail_r002.png` | `A055D3DFD279A281E51AFEAB34D2A8678CEA0AD9C5EADFBA0F027B715149E529` | 唯一精确 first_frame 资产 |
| `assets/boards/board_P002.png` | `731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E` | 分镜规划输入，未作为 I2VA runtime ref |

## 2. I2VA 结构与引用检查

- [x] 最终提示词首行严格为 `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`。
- [x] `<Picture 1>` 明确指向 P001 r002 的真实尾帧，语义为唯一精确视频首帧；未加入第二个 first-frame、last-frame 或普通 `ref_image_N` 槽位。
- [x] P002 使用 `video.image_to_video`，与同场连续接力的导演策略一致；没有静默改成 R2V 或 FL2VA。
- [x] 正文按要求使用 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`，顺序正确，没有自定义 negative prompt 块或未定义引用标签。
- [x] `board_P002.png` 只作为 B006–B011 的有序规划输入被吸收进动作与构图，不被伪装成 I2VA 的额外运行时参考。

## 3. 边界、Setup 与 Beat 检查

- [x] B006 被明确写为零时长、已完成的上一 Panel 末态：文士已经开始挥毫，钱翁已经侧眼但尚未说话，苏轼已经看水；没有给 B006 新动作、台词或时长。
- [x] 第一个有效动作立即进入 C003：钱翁从保留姿态继续转向苏轼并作小幅扇动；没有重演 P001 的动笔、侧眼或王方 D001。
- [x] C003 为 P002 00:00.000–00:07.000 的同轴钱翁前景/苏轼后景 medium two-shot，含小幅慢速 dolly in 和钱翁的 D002。
- [x] C004 在 00:07.000 cut 到同一池畔轴线的 fixed medium close-up，承接苏轼看水的无视选择；题笺从右后向呈笺处移动，不增加第三个 Setup。
- [x] 末态明确落在 B011：多张题笺待呈、均不可读；钱翁持自己题笺、准备起身但不正式报题；苏轼仍看鱼。
- [x] 没有提前执行 P003 的正式报题，也没有让 P002 说 D003–D006；P003 的 transition ownership 保持在后 Panel。

## 4. 对白与说话人检查

- [x] D002 只出现一次，使用全局 `S2`，说话人身份和 delivery 在 `<d>` 外说明。
- [x] `<d>` 内仅保留原语言标签与 canonical 原文：`听闻苏家小郎也有意一试？啧。书香是书香，可惜家底薄了些——取名这种雅事，讲究个气度。`；字词、标点、破折号未改写。
- [x] 明确禁止 P001 的 D001 重复、额外旁白、第二次讥讽和其他人物插话；苏轼不回嘴、不发声。
- [x] D002 的自然停顿限定在原标点内，并要求在 C003 的七秒 setup 内完整结束；没有跨切对白，因此无需 `<scenetrans>` 或 `<cutoff>`。

## 5. 连续性与通用事务逻辑

- [x] 苏轼持续凭栏/临水观察鱼，不因钱翁开口而回头或做反应，符合“以观察代替争辩”的事件因果。
- [x] 钱翁的折扇与自己题笺被定义为分开的物件；转向前退出书写面，末态持自己的不可读题笺准备起身，不宣布题名。
- [x] 纸笺和书写保持不可读，避免生成错误汉字；题名正式呈报延后到 P003。
- [x] 保留池水、水榭、石栏、午后光线、既有人员位置和岸线轴；不添加现代物件、清宫服饰、额外角色、字幕、水印或 UI。
- [x] `overall_soundscape` 只总结流水、风、笔触、纸张、衣料、座椅和折扇等可见声源；`non_diegetic_music` 为 `N/A`，符合本段无非叙事配乐原则。

## 交接意见

提示词自检通过。交给根代理后，执行包必须只把该 prompt body 逐字写入 `generation.prompt`，并把同一 P001 r002 尾帧绑定为唯一 `first_frame`；不得把黑白分镜板、角色卡或普通图片追加为 I2VA 引用。LFO 生成后仍须先做 P002 单片语义 QC，再做 P001 尾 2 秒 + P002 头 3 秒成对边界 QC；本报告不替代视频级 QC。

