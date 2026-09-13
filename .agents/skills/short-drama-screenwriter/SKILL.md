---
name: short-drama-screenwriter
description: 为国内竖屏微短剧或海外 ReelShort/DramaBox 格式创作选题、人物、分集和剧本，并按需提供视频创作 handoff。用户要求短剧编剧、微短剧或分集创作时使用；普通视频提示词、代码脚本和现有短剧的纯视频执行不触发。
---

# 微短剧编剧

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。主会话负责本 Skill 的故事、人物、对白和 handoff 创意决定；下游执行子代理只消费冻结 handoff 完成一个有边界的工作单元，不在本 Skill 中建立监控代理或视频验收流程。

本 Skill 负责短剧的选题、角色、分集目录、单集剧本、合规检查、导出和可选的创作侧 handoff。按用户给出的范围直接交付：可以写一集、修改已有文本、批量写指定集数或完成整部剧，不擅自扩展为 50–100 集。

## 适用边界

- 用户要求微短剧、短剧编剧、分集创作、海外短剧改编或从已写剧本生成创作侧 handoff 时使用。
- 只写剧本和 `.short-drama/{drama_title}/` 下的可选 handoff；不修改运行时代码，不调用 Canvas、ComfyUI 或视频生成能力。
- `episodes/epNNN.md` 是编剧主产物；`handoff/` 是给 `zero-to-story` 的伴生材料。handoff 不改写剧本正文，也不生成运行时请求或执行状态。
- `storyboard_brief.md` 和 `characters_visual.md` 交给 `zero-to-story`；单 Panel H3 提示词由 `h3-prompt-writing` 处理。Panel、模式、实际尾帧、Canvas 固定快照和最终成片处理由下游负责。
- handoff 默认留在 `.short-drama/`；只有用户明确进入视频制作后，下游才按项目规则复制已确认素材到 `workspace/projects/<project_id>/`。本 Skill 不自动写入 `workspace/`。

## 交付与状态

- 用户要求保存、创建或续写项目时，使用 `./.short-drama/{drama_title}/` 及 `.drama-state.json`，按当前阶段只创建必要文件；用户指定其他保存位置时沿用该位置。只要对话中的单集、成稿或审阅时，直接交对应内容，不初始化项目或写状态文件。目录与字段见 [工作流契约](./references/workflow-contract.md)。
- 继续一个已确定项目时读取其状态；没有指定项目的独立写作请求，不扫描其他剧目或套用它们的阶段、角色和集数。
- 用户已明确阶段或范围时直接完成该范围；未指定时按工作流推进到当前请求能确定的最小完整产物。只有缺失信息会改变类型、结构、语言、受众或下游输入时才提问。
- 用户要求审阅、修改或只做某阶段时停在指定边界；用户要求继续时沿用已有状态和授权，不重复问已知事项。

## 工作流路由

按任务读取 [工作流契约](./references/workflow-contract.md) 的对应小节，不预读整份专业参考：

| 请求/阶段 | 必要参考 |
| --- | --- |
| `/开始` 或选题 | [genre-guide](./references/genre-guide.md) |
| `/创作方案` | [opening-rules](./references/opening-rules.md)、[paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md) |
| `/角色开发` | [villain-design](./references/villain-design.md) |
| `/目录` | [paywall-design](./references/paywall-design.md)、[rhythm-curve](./references/rhythm-curve.md) |
| `/分集 N` | [rhythm-curve](./references/rhythm-curve.md)、[satisfaction-matrix](./references/satisfaction-matrix.md)、[hook-design](./references/hook-design.md)；第 1 集另读 [opening-rules](./references/opening-rules.md)；付费集另读 [paywall-design](./references/paywall-design.md) |
| `/自检 N` 或合规 | [compliance-checklist](./references/compliance-checklist.md)；创作检查按工作流契约执行 |
| `/桥接 N` | [handoff-mapping](./references/handoff-mapping.md)、[handoff-brief-template](./references/handoff-brief-template.md)；需要字段示例时再读 [handoff-intake-template](./references/handoff-intake-template.json) |
| `/出海` | [genre-guide](./references/genre-guide.md) 的出海部分 |

参考文件只在命中对应阶段、类型或检查项时读取；它们是具体创作约束，不是额外审批流程。

## 创作不变量

- 选题最多叠加 3 个类型，保留一个主类型；没有用户指定时按故事意图、受众和平台作合理默认，并在摘要中说明。
- 连载剧在用户未指定单集预算时可参考 3–6 场、15–25 句对白、至少一个主冲突和一个副冲突；独立单集按用户给出的时长、场景预算和交付格式执行，不强制下集预告。连载集保留钩子和下集预告；第 1 集、付费集按对应参考设计。
- 写作中保持角色称呼、时间线、道具、伏笔与已写集一致；动作要可拍，台词要能区分角色。
- 国内格式使用场景标题、中文景别、角色对白和可选音乐提示；海外格式使用 `INT./EXT.`、英文景别和英文对白。精确格式示例、字段和目录指标见工作流契约。
- 合规检查按 P0–P3 输出问题；红线、灰区、类型和海外市场约束以 `compliance-checklist.md` 为准，不凭印象补规则。

## Handoff 不变量

`/桥接` 只把已写集整理为创作侧 brief、可拍角色卡和剪辑说明：

- 用户授权压缩时，常规连载集可参考将 3–6 场压成 brief 内 1–2 个场景；其余保留用户指定的场景、角色和时长，不为套用数量增删内容。每条候选 Panel/节拍写空间关系和可见结束状态。
- 一集常见默认时长为 15–60 秒，不覆盖用户指定的总时长；下游按 4–15 秒 Panel 拆分；不把整集或剧本镜头数量直接当作一个 Canvas 视频节点。
- 对白按可拍节拍组织；用户要求逐字保留时完整转交。钩子、预告和付费墙留在 `cut_notes.md`；音频意图不冒充已存在的音频文件。
- 只读剧本正文并写入 `.short-drama/`；不记录 Canvas 请求、真实尾帧、运行结果或 QC。

完整字段映射和下游边界见 [handoff mapping](./references/handoff-mapping.md)。

## 快速命令

| 命令 | 产物 |
| --- | --- |
| `/开始` | 选题摘要和状态 |
| `/创作方案` | `creative-plan.md` |
| `/角色开发` | `characters.md` |
| `/目录` | `episode-directory.md` |
| `/分集 N` | `episodes/ep{NNN}.md` |
| `/自检 N` | 指定集的简洁创作检查 |
| `/桥接 N` | `handoff/` 下 brief、角色卡、cut notes |
| `/导出` | `export/{title}.md` |
| `/出海` | 更新状态中的海外格式和语言 |
| `/合规` | `compliance-report.md` |

详细前置条件、阶段输出、模板和检查清单集中在 [工作流契约](./references/workflow-contract.md)，只在当前阶段需要时读取。
