# 导演节奏、镜头关系与生成模式优化验收记录

## 验收范围

- 分支：`codex/director-rhythm-routing`
- 方案：[导演节奏、镜头关系与生成模式优化实施计划](2026-08-28-director-rhythm-routing-plan.md)
- 目标：让六格板表达 Beat，让 Camera Setup 决定真实切镜；由导演阶段决定节奏和 H3 模式；由 QC 把问题送回唯一正确的返修位置。

## 契约级代表性样例

| 样例 | 验证内容 | 结果 |
|---|---|---|
| 追逐 / 同镜接力 | I2V 只接受一张 `first_frame`；Panel 保留 Beat→Setup 溯源，不因六格拆 Clip | PASS |
| 安静表演 / 首尾锁定 | FL2V 只接受 `first_frame` + `last_frame`；Setup 数独立于六格数 | PASS |
| 无主角空镜 / 多参考新机位 | T2V 不接受参考；R2V 接受 typed fixed `ref_image_N` | PASS |
| 旧式错误交接 | R2V 声称 exact/hard first-frame 时在适配器入口失败，不静默换模式 | PASS（按预期阻断） |

对应自动化测试位于 `tests/skill_adapter/test_zero_to_story.py` 的 `TestDirectorRhythmRouting`，并由现有 H3 后端与物化测试继续覆盖 operation/reference 约束。

## 三类样例真实生成

在临时 Run 目录中按同一套 9:16、0.4MP、24fps 参数完成了三次本机 ComfyUI H3 生成，并用 MiMo 做画面复核：

| 样例 | operation | 结果 | 画面复核 |
|---|---|---|---|
| 空镜 | `video.text_to_video` | PASS | 单一连续镜头，缓慢向前推进，无切镜、重复或环境突变 |
| 首帧接力 | `video.image_to_video` | PASS | 从首帧立即向前发展，人物身份/服装稳定，无回卷、无切镜 |
| 首尾连续路径 | `video.first_last_frame` | PASS（修正后） | 使用真实视频首尾帧后，单镜头连续行进，无重复，人物与古建筑背景稳定 |

首轮 FL2V 若把两张角色设定卡直接当首尾帧，MiMo 识别到静态拼贴和视角跳变；这次失败被归因到“首尾素材不是同一空间运动状态”，随后改为从真实 I2V 片段提取首尾帧重跑并通过。该 A/B 结果证明返修应回到素材/模式选择，不应只追加提示词或更换 seed。

## 《一蓑烟雨》定向抽样

为避免旧执行包的 R2V 首帧冲突掩盖新流程效果，又用现有第一章素材做了三段不落盘到项目目录的 spot-check：

- 追车段 I2V：以 `assets/tails/P005_tail.png` 为真实首帧。MiMo 复核为巢儿沿长街中轴向城门追赶，囚车、城门和两侧跪众保持同一空间，无回头、倒退、重复抬手或切镜。
- 授字段 FL2V：先以 `assets/tails/P012_tail.png` 生成同场景连续动作，再从该真实片段提取首尾帧进行首尾锁定。MiMo 复核为单一连续镜头，人物与书斋环境稳定，动作由首帧自然推进到尾帧，无回卷或重复。
- 眉山空镜 T2V：不传视觉参考，只使用场景文本锚点。复核画面为竹影、土白院墙、深色瓦檐、木格窗和柴捆的稳定单镜头；未见人物、切镜或重复动作。天气细节有轻微自由发挥，但不影响空间连续性。

这三段验证了新流程可以在同一故事内按镜头职责分别使用 I2V、FL2V 与 T2V；没有把旧章节的 12 个 Panel 直接重排或覆盖。

## H3 原生音频附加发现

本次画面验收通过，不代表原始 H3 文件的音频可直接交片。追车 I2V 与授字段 FL2V 的输出都包含 `H.264 + AAC 32 kHz stereo` 原生音轨；MiMo 听到追车段的男性含混念白，以及授字段的笑声和含混短句。两段都没有设计对白，这些声音属于 H3 联合视频/音频生成的随机结果，不是后期 TTS 混入。

原因链为：`MiniMaxH3ImageToVideo → VAEDecodeAudio → CreateVideo → SaveVideo`。当前 FL2VA 工作流没有 `mute` 输入；即使在调用元数据中写入 `native_audio: mute`，原始 Comfy 输出仍会带 AAC。使用 H3 三段式提示词并明确“无对白、无旁白、无人声”后，MiMo 只听到脚步和衣料声，但文件仍然带音轨，说明提示词只能降低风险，不能替代流程级静音。

最终生产应把“是否允许 H3 原生音频”作为独立的音频策略：无对白镜头使用 `clip.audio.native_audio = mute` 并在 `audio.mix` 阶段确认 `-an`；有对白镜头使用经确认的 ADR/TTS/录音轨并设为 `replace` 或 `mix`，不把 H3 自发人声当作台词。音频 QC 需在 `audio.mix` 之后复核，发现未批准的人声即阻断交片。

## 《一蓑烟雨》视频理解基线

使用 MiMo V2.5 两阶段流程中的描述阶段，对既有诊断片做客观复核：

- `diagnosis_pre_cut_10_12271.mp4`（2.25 秒）：描述显示两名差役从左侧搬来木枷，片尾木枷停在跪地人物肩部上方。
- `diagnosis_post_cut_12271_15.mp4`（2.75 秒）：描述从木枷已在人物前方开始，随后继续前移、下压并套到肩颈。
- `diagnosis_10_15_silent.mp4`（5 秒）：描述为接近→对位→下压→锁定的一条完整动作路径。

前两段的证据表明，边界动作横跨两段，若两段都把“接近/下压”当作自己的开场，就会产生重复或回卷风险。新 QC 要求给该动作登记唯一 `transition ownership`，下一段从真实尾帧后的第一个新动作开始；这类问题不再靠重复堆提示词修复。

## 运行与限制

已通过：

- 两个 Skill 的 `quick_validate.py`：均为 `Skill is valid!`
- `git diff --check`
- 适配器与契约测试：106 passed
- H3 后端、物化测试：55 passed
- 全量测试：1068 passed
- `ruff check`（适配器及其测试）：All checks passed
- H3 FL2VA T2V workflow dry-run：18 个节点准备成功、无引用。

本轮没有直接重生成整章或覆盖既有成片。三类代表性样例已经完成真实生成；尚未把《一蓑烟雨》整章按新导演契约重新编译并做追车段、授字段、空镜的三段 A/B。当前历史执行包仍是旧格式，含“R2V + exact previous last frame”冲突，已被新规则正确拒绝；本机 ComfyUI `/system_stats` 可达，但 LFO machine profile 的存储目录为空且记录版本为 0.30.0，而服务返回 0.33.4。下一步应先生成新的导演契约执行包，补齐 machine profile 后运行 `doctor` / `preflight`，再做整章 A/B。
