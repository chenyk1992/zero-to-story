---
name: virtual-presenter
description: 规划数字人或虚拟实拍的连续口播，处理角色、环境、自然表演、文案、声音参考、H3 提示词和 Canvas 交接。明确的数字人口播请求使用；纯MG、B-roll和普通文案不触发；完整广告由advertising-creator统筹，本Skill处理限定口播范围。
---

# 虚拟实拍口播

独立口播用本计划；受广告委托只交指定口播范围与当前ad_plan版本，不改广告目标、音乐/对白或另建全片源。presenter_plan只保存该专业范围。广告委托不取消L0/L1/L2、4～15秒及同镜续演真实ACCEPT尾帧要求。

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。本 Skill 负责创作规划和单 Panel 交接，不直接调用视频提供方、ComfyUI 或 Canvas 数据库。

## 适用范围

用户要做数字人口播、虚拟实拍讲解、连续角色出镜，或要把已有角色和口播整理成可生成方案时使用。用户只要输入规格、口语化文案、Shot Plan、H3 交接或某一 Panel 时，完成该阶段即可；不自动继续生成或成片。

项目用一个 presenter_plan.md 记录创作事实。首次创建计划时复制 [模板](assets/presenter_plan.template.md)；只维护这一份计划。计划中的状态表示创作进度，不代替 Canvas 快照状态。

## 输入就绪

先沿用当前指令和已有计划，再整理：

- 角色身份锚点与角色图；
- 口播目的、受众、语言/地区、逐字文案；有音频时区分声音/节奏参考与需保留的实际音轨；
- 一个目标画幅、总时长和发布限制；
- 环境来源、需要的区域/站位、方向和光线；
- 自然表演禁区、字幕要求和连续性要求。

只在缺失信息会改变成品或无法绑定输入时提问。只有 Shot 需要确定空间方向和站位时才运行 scripts/build_environment_pack.py，并登记其实际 manifest、方向视图和 contact sheet；不需要 360°空间依赖时不生成环境包。没有可用探查工具或比例不合格时，只暂停受影响阶段并说明缺口。

## 创作流程

1. **计划与文案**：明确一个口播意图，在允许改写的范围内把书面稿改成可说的短句；准确复述或已锁定文案保留逐字内容。记录停顿、重音、发音和声音尾音。有实际音频时先听审采用版本，按其音色、节奏或原音轨用途记录所需事实；只有文案时标注估计时长，沿用已定 H3 声音方案。详见 Shot Contract 的[声音与动作记录](references/presenter-plan-shot-contract.md#声音与动作按需记录)。
2. **Shot Plan**：按场景因果拆分，每个 Shot/Panel 为 4–15 秒、一个信息意图和一个主要动作；写起始状态、动作、镜头、空间、声音、结束状态和连续性输入。动作预算用 L0（静态）、L1（轻微交流）、L2（一次主动作）；强调动作按需关联词或停顿。超出时长时按 [动作预算](references/presenter-plan-shot-contract.md#动作预算)调整，保留锁定文案和完整词音。
3. **提示词与交接**：读取 [Shot Contract](references/presenter-plan-shot-contract.md) 整理单 Panel 事实，再交给 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) 生成最终 H3 文本；按 [Canvas handoff](references/canvas-handoff.md) 把提示词、模式、参数、素材、音频/后期责任和验收要求保存到 Canvas。
4. **授权与执行**：保存是草稿。页面确认或对话明确授权后由 Canvas 冻结快照并按已选能力提交一次；选择 comfy 时由 Canvas 服务调用 [comfy-video-executor](../comfy-video-executor/SKILL.md)。本 Skill 不另建执行入口。
5. **结果与接力**：按 [Presenter 最小 QC](references/qc-rubric.md) 检查当前实际采用文件，记录本阶段的末态、音频证据和一次判断。同一连续镜头的下一条必须从上一条同画幅完整 ACCEPT 的实际采用版本提取真实尾帧，绑定为 `first_frame`；完整视频参考仅作补充。本条为同镜头续接时，实际连看前段结尾与本段开头后才能接受。失败、拒绝或未知时停止受影响接力，不自动重试。

全部 Panel 接受后，如用户要求成片，对已接受输出做确定性连接、音频和字幕处理；完成全部后期后，对最终实际文件做一次完整视听检查。

## 导演标准

按需复用[细腻表演](../zero-to-story/references/performance-direction.md)，只增强同一主动作的发展，保留 L0/L1/L2、锁定文案及连续镜头。总时长等于 Panel 合计，Canvas 与 Panel 一致，不生成余量后裁切或自动变速。参考片按[变更交接](../video-deconstruct-analyzer/references/recreation-change-plan.md)记方式到当前计划，不改 Canvas 页面。

每个 Shot 写清四件事：镜头为什么存在、观众看到什么可观察动作、镜头怎样帮助叙事、画面和声音怎样在末态收束。自然呼吸、眨眼、视线和重心变化作为底层表演；一条短片只安排少量语言强调动作和一种主运镜。同镜头续接时，起始姿态、手持物、朝向、光向和空间关系必须能从上一条末态承接。不要用“更真实”“自然一点”等抽象词替代动作、速度和停点。

讲解要点可用一次小手势落在关键词上；提醒或反问可用目光和停顿给观众反应空间；需要展示物件时才安排一次 L2 主动作。按表达选择，不为每句话配手势。关键口型、表情或手势需要看清时，先检查所选景别、侧脸角度、道具和字幕位置是否遮住它们；只补当前镜头影响用途的可见性事实。

连续口播默认保持同一镜头：机位、景别、人物画面位置与大小、背景布局和光线不因 Panel 分段而重置；无已定运镜时锁定机位，有运镜时按计划连续承接，不在段界重新起镜。只有计划明确安排的切镜或换场才允许改变镜头，并作为新镜头起点准备输入；拆分长口播本身不是切镜理由。首条与明确的新镜头起点不要求前段尾帧，其余同镜头后续条必须使用真实尾帧；缺少尾帧或所选能力不能兼容首帧与必要参考时，暂停该条并报告缺口，不退回仅视频参考的接力。

## 引用槽位

用途与编号分开。身份、环境源、方向图、声音、原片与前段视频按需要绑定，编号依 Canvas 解析后的紧凑顺序从零基转一基，不预留空槽、不填无用素材。具体见[引用编号](references/h3-presenter-prompt.md#引用编号)。首条可有原片 Video 1，不虚构前段 ACCEPT。

`first_frame` 是独立首帧输入，不占普通参考编号。同镜头接力必填；首帧引导不保证像素级一致或音频自动连续。contact sheet 只用于审阅，不替代方向视图。普通视频参考不等于精确首帧；不能用失败输出、推测路径或未生成尾帧接力。

声音参考与原音轨保留按 [Shot Contract](references/presenter-plan-shot-contract.md#声音与动作按需记录) 分别记录；参考绑定与提示时点不能证明实际同步。控制能力见 [H3 控制与后期责任](../h3-prompt-writing/references/control-boundaries.md)。

## 按需读取

- [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)：创建或修改计划、Shot、Panel 字段时读取。
- [H3 Presenter Prompt](references/h3-presenter-prompt.md)：整理交给 h3-prompt-writing 的事实时读取。
- [Canvas handoff](references/canvas-handoff.md)：保存或确认 Canvas 节点时读取。
- [Presenter 最小 QC](references/qc-rubric.md)：只有实际输出需要验收时读取；它只补充任务相关观察项，不重复共享规则。
- [方法来源与采纳边界](references/method-sources.md)：维护或审查本 Skill 的创作方法时读取，不是执行依赖。

## 交付边界

计划阶段交付可审阅的 plan、文案和 Shot 列表；交接阶段交付单 Panel 的完整输入；执行后只报告实际文件、末态、音频证据、一次判断和未解决问题。不同画幅另建完整序列，不能共用上一条视频参考。
