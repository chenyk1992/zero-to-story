---
name: short-drama-screenwriter
description: 为国内微短剧、海外 ReelShort/DramaBox 或独立情景喜剧创作选题、角色、分集和可拍剧本，并按需整理创作交接。用户要求短剧编剧、喜剧小品或分集改编时使用；不负责视频提示词和媒体执行。
---

# 微短剧编剧

独立创作交付当前阶段的剧本文本；受影视、广告或叙事 MV 委托时，完成指定段落并返回调用方。广告目标与产品事实继承[广告入口](../advertising-creator/SKILL.md)；独立剧目的分集与桥接规范按本 Skill 执行。

参考改编时采用用户在对话/Skill 入口选择的自由改编、受控复刻或只读分析，记入当前创作简报，不写入市场 mode 或 Canvas 参数。按[变更边界](../video-deconstruct-analyzer/references/recreation-change-plan.md)保留锁定项，受控复刻不套自由重组默认；只读分析交证据而不自动改稿。

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。本 Skill 交付故事、人物、对白、分集文本和按需整理的创作 handoff；媒体制作由下游入口接手。

## 适用范围与产物

- 用户要选题、创作方案、角色、目录、单集、修改、出海、合规、导出或从剧本整理创作侧 handoff 时使用。
- 用户要求落盘且未指定位置时使用 `.short-drama/{drama_title}/`；只要对话成稿或审阅，不初始化项目、不写状态。
- `episodes/epNNN.md` 是剧本主产物。 `handoff/` 只给 `zero-to-story` 提供故事板概要、视觉角色卡和剪辑意图，不改写剧本正文、不创建运行请求。
- `storyboard_brief.md`、`characters_visual.md` 和 `cut_notes.md` 只记录已写内容的创作事实。Panel、模式、提示词、真实尾帧、Canvas 快照、执行和成片属于下游 Skill。

## 先判范围，再写

读取项目状态时只读用户点名的剧目；独立请求不扫描其他剧目。用户已给阶段和集数就完成该范围，不擅自扩成整部剧或固定集数。只有缺失信息会改变题材、语言、受众、市场格式或下游输入时才提问；其余采用清楚的默认并说明。

新创作方案按[整体风格推荐与继承](../zero-to-story/references/style-selection.md)推荐适合故事的方向，写入当前简报。影视剧本明确美术与气质；文学文本和台词润色明确类型与语气。受托直接继承调用方风格及局部例外；只读桥接如实保留未定项。让风格落实为人物如何说话、选择与承受后果，以及观众何时知道真相。

连载剧的默认规划尺度见[工作流契约](references/workflow-contract.md)，以用户已给的时长、场景和对白要求为准；独立单集在当前结局收束。

写作质量以可拍和可读为准：每场有明确目的和变化，动作能被镜头看见，台词推动冲突且能区分角色；时间线、称呼、服装、道具、伏笔、空间关系和人物出场保持连续。需要视频交接时，补充景别、主体位置、可见起止状态和对白/环境声意图；精确对白或屏幕文字逐字保留。

从小说、梗概或平淡的剧情摘要发展剧本时，按[从故事到场景剧本](../zero-to-story/references/script-adaptation.md#从故事到场景剧本)落实观看价值、人物选择、场景因果、信息顺序与一次写作修订；正文仍写在本 Skill 的当前剧本，不提前拆 Panel，也不把所有类型改成强冲突爽剧。

## 阶段路由

先读[工作流契约](./references/workflow-contract.md)中当前阶段，再按需要加载专业参考。不要为形式完整读取全部资料。

| 请求 | 读取 |
|---|---|
| `/开始`、选题 | [genre-guide](./references/genre-guide.md)；要求对标/采风时再读[参考研究](../zero-to-story/references/reference-research.md) |
| 独立情景喜剧的选题、方案、角色、剧本 | [喜剧写作](./references/sitcom-writing.md)优先；不默认加载付费、反派或恋爱结构 |
| 当前剧本的反转、误判或身份揭示 | 按需读[通用反转](./references/reversal-design.md)；它是叙事机制，不改主类型，不强加给每集 |
| 连载微短剧 `/创作方案` | [opening-rules](./references/opening-rules.md)、[paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md) |
| 核心角色与长期关系开发 | [人物开发](./references/character-development.md)；需要反派时再读[villain-design](./references/villain-design.md) |
| 续集中的别名、不同年龄或服装阶段 | [角色身份与造型复用](./references/handoff-mapping.md#角色身份与造型复用)；保留人物关系与称呼来源，再交接当前造型 |
| 连载微短剧 `/目录` | [paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md) |
| 连载微短剧 `/分集 N` | [rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md)、[hook-design](./references/hook-design.md)；第 1 集再读 [opening-rules](./references/opening-rules.md)，付费集再读 [paywall-design](./references/paywall-design.md) |
| 改写台词，或 `/自检 N` 中需要诊断台词 | [dialogue-diagnosis](./references/dialogue-diagnosis.md)；只处理当前授权段落，锁定对白逐字保留 |
| 半解说或旁白与对白混合的虚构故事 | [混合叙事](../zero-to-story/references/mixed-narration-direction.md)中的表达分工；编剧只交原文、归属与画面意图，Panel/音轨/执行由下游处理 |
| `/自检 N`、`/合规` | [compliance-checklist](./references/compliance-checklist.md)；创作检查按工作流契约 |
| `/桥接 N` | [handoff-mapping](./references/handoff-mapping.md)、[handoff-brief-template](./references/handoff-brief-template.md)；字段示例按需读 JSON 模板 |
| `/出海`、海外对白或多语互动 | [语言适配](./references/overseas-dialogue.md)；类型迁移再读[genre-guide](./references/genre-guide.md) 的出海部分 |

按当前写作问题选用参考，把结果写回剧本或现有创作交接。

## 交付规则

1. 选题最多 3 个类型且保留一个主类型；用户未指定时按故事意图、受众和平台选定。
2. 剧本格式和对白语言沿用用户要求及目标市场：中文稿可用场景标题、中文景别、角色对白和可选声音提示；英文市场可用 `INT./EXT.`、英文景别与英文对白。海外不等于英语，其他语言和多语稿按[语言适配](references/overseas-dialogue.md)保留逐句语言与文化语境。
3. 连载中间集保留已定钩子，按需给下集预告；独立单集和完结集按已定结局收束，不强加预告。伏笔回收位置沿用已确认大纲；付费点、主冲突和爽点服务剧情，不以模板数量替代因果。
4. 合规只在用户要求或题材明显涉及风险时加载清单；先处理红线和关系/价值观风险，再给少量具体改法，不生成分数表。
5. `/桥接` 只读剧本并把事实交给 `zero-to-story`。本 Skill 不把音频意图写成音频文件，不写 Canvas ID、请求状态、真实媒体、尾帧或 QC 结论。

## 快速命令

| 命令 | 主要产物 |
|---|---|
| `/开始` | 选题摘要、状态 |
| `/创作方案` | `creative-plan.md` |
| `/角色开发` | `characters.md` |
| `/目录` | `episode-directory.md` |
| `/分集 N` | `episodes/ep{NNN}.md` |
| `/自检 N` | 必修问题与可选建议 |
| `/桥接 N` | `handoff/` 下三个创作文件 |
| `/导出` | `export/{title}.md` |
| `/出海`、`/合规` | 更新格式或 `compliance-report.md` |

完成后报告本轮实际产物、未决事实和下游需要的输入。
