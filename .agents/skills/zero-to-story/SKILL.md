---
name: zero-to-story
description: 将灵感、小说、剧本或短剧交接转成故事板、角色与必要视觉资产，再按 Panel 交给 H3 提示词和 Canvas 生产。用于故事分镜与视频创作交接；不直接编写 H3 提示词或调用视频提供方。
---

# 故事到分镜与视频交接

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。只完成用户要求的阶段；单独要角色图、故事板或交接时，不自动扩展为整片生产。

## 先判断当前任务

读取已有创作源和用户规格：剧情、目标时长、画幅、画风、对白/声音、交付阶段。复用已有决定；只在关键事实缺失或冲突时集中说明缺口。主会话负责导演选择，下游按确定的事实写提示词和执行。

| 当前交付 | 读取时机与资源 |
| --- | --- |
| 故事板与导演设计 | 读[故事板与导演工作台](references/storyboard-production.md)，填字段时查[故事板结构](references/storyboard-brief.md) |
| 完整故事生产的结构化蓝图 | 从故事板编译时读[创作蓝图](references/creative-blueprint.md) |
| 角色图、分镜板、关键帧 | 只在准备相应资产时读[视觉资产](references/creative-assets.md) |
| 单 Panel 提示词和生成交接 | 输入准备好后读[Panel 交接](references/panel-execution.md)，调用 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) |
| 实际结果验收或成片 | 结果可用后读[视频验收](references/video-qc.md)；不在规划时预先加载 |

## 创作与交付步骤

1. **设计故事和镜头。** 先决定观众此刻应理解什么、人物为何行动，再安排走位、景别、切镜和声音。对白按正常表演留出反应时间。具体导演依据见工作台，不另写评分表。
2. **记录可执行计划。** 完整故事生产使用[故事板模板](assets/storyboard_brief.template.md)。`storyboard_brief.md` 是人工创作源；`creative_blueprint.json` 是它的结构化索引，使用 `zero-to-story.creative-blueprint.v2`，不另编一套剧情。只做局部交付时不强制建立整章蓝图。
3. **准备必要资产。** 完整生产的蓝图先做一次静态预检；按报错修正后再查，不由模型逐项复算脚本已验证的字段。按当前 Panel 的控制需求复用或生成角色卡、分镜板、关键帧；`planning_only` 资产默认不生成。每张资产只检查能否承担用途。
4. **写提示词并交接。** 将已确定的单 Panel 事实交给 H3 Skill，把返回提示词与素材、参数原样交给 [canvas-workspace](../canvas-workspace/SKILL.md)。每个 Panel 对应一个视频节点。已有授权覆盖时按共享规则执行；只要草稿时停在保存。
5. **处理实际结果。** 按视频验收做一次结论。下游需要精确首帧时，才从已接受视频提取真实尾帧。用户要求完整成片时，对已接受输出完成确定性后期和一次最终视听检查。

完整故事生产的静态预检命令：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py <creative_blueprint.json>
~~~

`CREATIVE PREFLIGHT: PASS` 只表示结构与引用可用，不保证创作质量或成片已接受。故事板/蓝图变化后复核受影响输入；无变化不重复预检。

## 容易混淆的契约

- 一个 Panel 是一条 4–15 秒 Clip；六个 Beat 是语义时刻，Camera Setup 才对应真实摄影镜头和 H3 Shot。不要为六个 Beat 凑六次动作或切镜。
- 先选镜头控制方式，再决定资产。分镜板只用于采用该策略的 R2V；整板一次生成，不拆格生图或后期拼板。I2V/FL2V 只用其精确帧输入。
- 像素预算 `megapixels`、采样模式 `sampler_profile` 和步数 `steps` 属于项目制作规格，最迟在首个视频确认前补齐，记录到故事板和蓝图 `user_constraints`，以后直接继承。步数不能代替模式，不从模板猜用户选择。
- 当前 Panel 输入齐全即可推进；只有真实依赖前段状态时才等它 `ACCEPT`。准备可并行，视频提交仍串行。
- 生成失败、状态未知、`REJECT` 或 `INCONCLUSIVE` 只停止受影响单元及其依赖。先核对原任务或修正草稿；新生成按已有授权范围确认新的快照，不自动重提。

## 返回结果

交付用户所需的故事板、蓝图、`character_assets.md` 或实际资产路径，并说明尚缺的决定或依赖。文件位置遵守 [AGENTS.md](../../../AGENTS.md)。生产状态以 Canvas 为准；保留原快照与历史媒体，替换片段时只核对受影响的[接缝](references/video-qc.md#替换片段后的接缝)。
