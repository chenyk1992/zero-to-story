---
name: virtual-presenter
description: 规划数字人或虚拟实拍的连续口播，处理角色、环境、自然表演、文案、声音参考、H3 提示词和 Canvas 交接。明确的数字人口播请求使用；纯 MG、B-roll 和普通文案不触发。
---

# 虚拟实拍口播

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。本 Skill 负责创作规划和单 Panel 交接，不直接调用视频提供方、ComfyUI 或 Canvas 数据库。

## 适用范围

用户要做数字人口播、虚拟实拍讲解、连续角色出镜，或要把已有角色和口播整理成可生成方案时使用。用户只要输入规格、口语化文案、Shot Plan、H3 交接或某一 Panel 时，完成该阶段即可；不自动继续生成或成片。

项目用一个 presenter_plan.md 记录创作事实。首次创建计划时复制 [模板](assets/presenter_plan.template.md)；只维护这一份计划。计划中的状态表示创作进度，不代替 Canvas 快照状态。

## 输入就绪

先沿用当前指令和已有计划，再整理：

- 角色身份锚点与角色图；
- 口播目的、受众、语言/地区、文案和声音参考；
- 一个目标画幅、总时长和发布限制；
- 环境来源、需要的区域/站位、方向和光线；
- 自然表演禁区、字幕要求和连续性要求。

只在缺失信息会改变成品或无法绑定输入时提问。只有 Shot 需要确定空间方向和站位时才运行 scripts/build_environment_pack.py，并登记其实际 manifest、方向视图和 contact sheet；不需要 360°空间依赖时不生成环境包。没有可用探查工具或比例不合格时，只暂停受影响阶段并说明缺口。

## 创作流程

1. **计划与文案**：明确一个口播意图，把书面稿改成可说的短句；记录停顿、重音、发音和声音尾音。外部音频以实际音频为节奏基准。
2. **Shot Plan**：按场景因果拆分，每个 Shot/Panel 为 4–15 秒、一个信息意图和一个主要动作；写起始状态、可拍动作、镜头、空间、声音、结束状态和连续性输入。动作预算可用 L0（静态）、L1（轻微交流）、L2（一次主动作），无法自然完成就删信息、延长或拆条。
3. **提示词与交接**：读取 [Shot Contract](references/presenter-plan-shot-contract.md) 整理单 Panel 事实，再交给 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) 生成最终 H3 文本；按 [Canvas handoff](references/canvas-handoff.md) 把提示词、模式、参数、素材、音频/后期责任和验收要求保存到 Canvas。
4. **授权与执行**：保存是草稿。页面确认或对话明确授权后由 Canvas 冻结快照并按已选能力提交一次；选择 comfy 时由 Canvas 服务调用 [comfy-video-executor](../comfy-video-executor/SKILL.md)。本 Skill 不另建执行入口。
5. **结果与接力**：查看实际输出，记录任务相关的实际末态和音频证据，做一次 ACCEPT、REJECT 或证据不足时的 INCONCLUSIVE。下一条只引用上一条同画幅的完整 ACCEPT 结果；精确首帧需要时才从该结果提取真实尾帧。失败、拒绝或未知时停止受影响接力，不自动重试。

全部 Panel 接受后，如用户要求成片，只对已接受输出做确定性连接、音频和字幕处理，并检查实际文件的可播放性、顺序、接缝及需要的音画同步。

## 导演标准

每个 Shot 写清四件事：镜头为什么存在、观众看到什么可观察动作、镜头怎样帮助叙事、画面和声音怎样在末态收束。自然呼吸、眨眼、视线和重心变化作为底层表演；一条短片只安排少量语言强调动作和一种主运镜。起始姿态、手持物、朝向、光向和空间关系必须能从上一条末态承接。不要用“更真实”“自然一点”等抽象词替代动作、速度和停点。

## 引用槽位

槽位编号从 0 开始，H3 标签从 1 开始，缺少某项时不顺延：

| Canvas 槽位 | H3 标签 | 语义 |
|---|---|---|
| ref_image_0 | <Picture 1> | 角色/身份锚点 |
| ref_image_1 | <Picture 2> | 全景或 360°环境源 |
| ref_image_2 | <Picture 3> | 当前 yaw、pitch、FOV 方向视图 |
| ref_audio_0 | <Audio 1> | 声音参考 |
| ref_video_0 | <Video 1> | 同画幅上一条完整 ACCEPT 片；首条省略 |

contact sheet 只用于审阅，不替代方向视图。普通视频参考不等于精确首帧；不能用失败输出、推测路径或未生成尾帧接力。

## 按需读取

- [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)：创建或修改计划、Shot、Panel 字段时读取。
- [H3 Presenter Prompt](references/h3-presenter-prompt.md)：整理交给 h3-prompt-writing 的事实时读取。
- [Canvas handoff](references/canvas-handoff.md)：保存或确认 Canvas 节点时读取。
- [Presenter 最小 QC](references/qc-rubric.md)：只有实际输出需要验收时读取；它只补充任务相关观察项，不重复共享规则。

## 交付边界

计划阶段交付可审阅的 plan、文案和 Shot 列表；交接阶段交付单 Panel 的完整输入；执行后只报告实际文件、末态、音频证据、一次判断和未解决问题。不同画幅另建完整序列，不能共用上一条视频参考。
