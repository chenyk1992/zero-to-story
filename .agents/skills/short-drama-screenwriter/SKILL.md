---
name: short-drama-screenwriter
description: 为国内竖屏微短剧或海外 ReelShort/DramaBox 创作选题、角色、分集和可拍剧本，并按需整理创作侧 handoff。用户要求短剧编剧、分集创作或海外短剧改编时使用；普通视频提示词、代码和纯视频执行不触发。
---

# 微短剧编剧

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。本 Skill 只负责故事、人物、对白、分集文本和可选 handoff；不调用 Canvas、ComfyUI 或视频提供方，也不记录运行状态。

## 适用范围与产物

- 用户要选题、创作方案、角色、目录、单集、修改、出海、合规、导出或从剧本整理创作侧 handoff 时使用。
- 用户要求落盘且未指定位置时使用 `.short-drama/{drama_title}/`；只要对话成稿或审阅，不初始化项目、不写状态。
- `episodes/epNNN.md` 是剧本主产物。 `handoff/` 只给 `zero-to-story` 提供故事板概要、视觉角色卡和剪辑意图，不改写剧本正文、不创建运行请求。
- `storyboard_brief.md`、`characters_visual.md` 和 `cut_notes.md` 只记录已写内容的创作事实。Panel、模式、提示词、真实尾帧、Canvas 快照、执行和成片属于下游 Skill。

## 先判范围，再写

读取项目状态时只读用户点名的剧目；独立请求不扫描其他剧目。用户已给阶段和集数就完成该范围，不擅自扩成整部剧或固定集数。只有缺失信息会改变题材、语言、受众、市场格式或下游输入时才提问；其余采用清楚的默认并说明。

连载剧在用户未给预算时可参考每集 3–6 场、约 15–25 句对白、一个主冲突和一个副冲突；这是规划参考，不得覆盖用户的时长、场景或对白要求。独立单集按用户规格收束，不强加下集预告。

写作质量以可拍和可读为准：每场有明确目的和变化，动作能被镜头看见，台词推动冲突且能区分角色；时间线、称呼、服装、道具、伏笔、空间关系和人物出场保持连续。需要视频交接时，补充景别、主体位置、可见起止状态和对白/环境声意图；精确对白或屏幕文字逐字保留。

## 阶段路由

先读[工作流契约](./references/workflow-contract.md)中当前阶段，再按需要加载专业参考。不要为形式完整读取全部资料。

| 请求 | 读取 |
|---|---|
| `/开始`、选题 | [genre-guide](./references/genre-guide.md) |
| `/创作方案` | [opening-rules](./references/opening-rules.md)、[paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md) |
| `/角色开发` | [villain-design](./references/villain-design.md) |
| `/目录` | [paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md) |
| `/分集 N` | [rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md)、[hook-design](./references/hook-design.md)；第 1 集再读 [opening-rules](./references/opening-rules.md)，付费集再读 [paywall-design](./references/paywall-design.md) |
| `/自检 N`、`/合规` | [compliance-checklist](./references/compliance-checklist.md)；创作检查按工作流契约 |
| `/桥接 N` | [handoff-mapping](./references/handoff-mapping.md)、[handoff-brief-template](./references/handoff-brief-template.md)；字段示例按需读 JSON 模板 |
| `/出海` | [genre-guide](./references/genre-guide.md) 的出海部分 |

这些参考是创作方法，不是额外审批或视频 QC。

## 交付规则

1. 选题最多 3 个类型且保留一个主类型；用户未指定时按故事意图、受众和平台选定。
2. 国内格式使用场景标题、中文景别、角色对白和可选声音提示；海外格式使用 `INT./EXT.`、英文景别和英文对白，并做文化适配而非逐字直译。
3. 连载集保留本集钩子和下集预告；付费点、主冲突、爽点和伏笔服务剧情，不以模板数量替代因果。
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

完成后只报告本轮实际产物、未决事实和下游需要的输入；未执行的阶段不要声称已完成。
