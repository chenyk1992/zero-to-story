# P002 H3 Prompt v02 — 自检报告

- 检查时间：2026-08-31 09:43:09 +08:00
- 检查范围：P002 v02 immutable candidate、formal prompt、`storyboard_brief.md` 的 P002/B006–B011/C003–C004、`speaker_registry.md`、P001 r002 真实尾帧绑定。
- 执行范围：仅检查 STEP4 I2VA 提示词结构、输入引用、时序、对白归属和修复约束；不执行 LFO、ComfyUI 或视频生成，不修改 v01、视频、分镜或角色资产。

## 结论

`PROMPT_SELF_QC: PASS`

该结论只表示 v02 提示词能够按已确认的创作输入编译并覆盖本次语义修复；不代表视频已经生成或视频级语义 QC 已通过。

## 不可变版本与 SHA-256

| 文件 / 资产 | SHA-256 | 备注 |
|---|---|---|
| `step4/candidates/P002_h3_prompt_v02.md` | `C7438D36B95B583F48A2F0B78F1C48DC60CF96C88EA9FC5D5B617FB65DEC4E08` | 本次 immutable candidate |
| `step4/P002_h3_prompt_v02.md` | `C7438D36B95B583F48A2F0B78F1C48DC60CF96C88EA9FC5D5B617FB65DEC4E08` | formal prompt；与 candidate 逐字节一致 |
| v02 最终 H3 prompt body | `7464E616199317FE5F1EF52D291EA64AFA997914B8FA1A4B9634DE20F551320D` | code block 内正文，UTF-8 SHA-256 |
| `step4/candidates/P002_h3_prompt_v01.md` | `93815D6183B5E4BA38BF07040BCE3AE153E5A7A8C95A63FBADB4EFA9E4977763` | 历史版本，未修改 |
| `step4/P002_h3_prompt.md` | `93815D6183B5E4BA38BF07040BCE3AE153E5A7A8C95A63FBADB4EFA9E4977763` | v01 formal，未修改 |
| `workspace/projects/yisuo-ep003-codex-director/tails/P001_tail_r002.png` | `A055D3DFD279A281E51AFEAB34D2A8678CEA0AD9C5EADFBA0F027B715149E529` | 唯一精确 first-frame 资产 |
| `assets/boards/board_P002.png` | `731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E` | 仅作 B006–B011 规划输入，未作为 I2V runtime reference |

## 固定规格与引用

- [x] 保留 `I2V / video.image_to_video`，用于同场连续接力；没有静默换成 R2V 或 FL2VA。
- [x] 保留 12.0 秒、24 fps、9:16、已确认的 0.4 MP profile；C003 为 `00:00.000–00:07.000`，C004 为 `00:07.000–00:12.000`。
- [x] 首行严格使用 I2VA 格式，把 `<Picture 1>` 绑定到 `P001_tail_r002.png` 的 0.00 秒；运行时只使用这一张首帧图。
- [x] 分镜板、角色卡和其他普通图片只作为已吸收的创作输入，未增加第二个运行时图片引用。
- [x] B006 被明确为 P001 已完成末态的零时长锚点；第一有效动作从既有姿态继续，不重演动笔、侧眼或 D001。

## C003（00:00–00:07）语义修复

- [x] 钱翁全程固定在右前原位：臀部/髋部压在原座位，膝盖保持弯曲；禁止抬臀、伸膝、起身、站立、跪下、走动、换位或与他人交换位置。
- [x] 钱翁只执行必要的连续动作：若首帧可见毛笔，先把笔尖移离纸面并放到既有笔托/桌边一次；随后只作小幅头眼转向和一次克制的折扇左右摇动；不再落纸、不重新拿笔、不把笔与扇合并。
- [x] D002 只由右前钱翁、全局 speaker `S2` 说一次，逐字保留原文和标点；口型只对应该句，禁止第二次讥讽、旁白、笑声台词或其他人物插话。
- [x] 苏轼保持左/后景坐姿、朝水看鱼，始终静默，不回头、不回应、不以表情承接钱翁；其他文士只作小幅坐姿书写或短暂看向交流。

## C004（00:07–00:12）语义修复

- [x] `00:07.000` 只切至同一池畔轴线的固定 medium close-up，继续呈现苏轼看水；不是宽幅池景、反轴、俯拍或新地点。
- [x] 苏轼全程坐着、静默、看鱼；题笺沿既有桌面从右后向呈笺处安静递送，所有题笺保持空白/不可读，不生成汉字、伪文字或标题。
- [x] `00:07.000–00:12.000` 文会所有人仍坐在原位；禁止任何人抬臀、伸腿、走到石栏、把纸带到池栏、站起或群体站立。
- [x] 钱翁在画面右侧保持可见并继续坐在右前原位；`00:11.500–00:12.000` 只做 B011 准备：仍坐着，手持自己的一张不可读题笺，身体前倾约 10°，准备下一 Panel 起身但不完成起身、不报题、不再说话。
- [x] 钱翁的折扇与题笺为分开的单一道具；无毛笔、第二张题笺、第二把扇、可读题名或人物复制。苏轼无反应，最后一帧不新增对白、揭示标题、淡出或溶解。

## H3 结构与连续性

- [x] 按 `h3-prompt-writing` I2VA base form 输出：首行 first-frame instruction，随后依次为 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`。
- [x] 只定义 C003/C004 两个实际 `[Shot]`；切点单调且为已确认的 `00:07.000`，没有按六格机械拆镜。
- [x] 对白正文只保留 `[Chinese]` 与用户确认的 D002 原文；没有补写 D003–D006、可读屏幕文字、字幕、水印、UI 或自造 negative prompt 区块。
- [x] `overall_soundscape` 只描述池水、风、笔纸、衣料、座椅和折扇等现场声；`non_diegetic_music: N/A` 与本段无非叙事配乐设定一致。

## 交接意见

v02 candidate 与 formal prompt 已封存且逐字节一致，v01 两个文件哈希保持不变。可交由根代理进行用户确认；在用户确认前不得创建/执行 P002 execution package。若后续执行，仍必须先做 P002 单片技术/语义 QC，再做 P001 尾 2 秒 + P002 头 3 秒成对边界 QC；本报告不替代视频级证据。
