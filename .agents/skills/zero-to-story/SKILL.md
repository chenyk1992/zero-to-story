---
name: zero-to-story
description: 从灵感、小说、剧本或 short-drama handoff 开始完成故事板、角色与必要视觉控制资产，并把已确认的单 Panel 输入交给 h3-prompt-writing 和 LFO。执行阶段每个 Panel 使用一份用户批准的 VideoExecutionPackage 精确文件字节 SHA-256 作为锁，并以相互隔离的执行单元串行调用 ComfyUI 官方 comfy-cli；不负责撰写 H3 视频提示词。
---

## GPT-6 适配变更说明

2026-09-07：入口只保留触发边界、角色分工、阶段路由和不可变执行契约；导演/Camera Setup/R2V 可变网格细节见按需引用。协作优先级、通用提问、测试和停止原则遵循项目 [AGENTS.md](../../../AGENTS.md)，不在此重复。

# 从零开始创作并交付短片

## 何时使用

用户要从灵感、小说、剧本或 short-drama handoff 形成故事板、角色资产、必要视觉控制资产和逐 Panel LFO 交接时使用。本 Skill 做创作规划和交接，不是通用的图像生成器、H3 提示词作者或视频执行器。用户只要某阶段的产物时，仅完成该产物及必要检查，不自动扩展到蓝图、资产或执行。

## 任务边界与角色

- 主 Agent 负责故事、章节导演决策、故事板、视觉资产计划、连续性和执行包准备。
- `$h3-prompt-writing` 负责已经确认的单 Panel H3 提示词；本 Skill 不撰写、优化或手工修补 H3 提示词。
- LFO 只消费 `lfo.video-execution.v1` 执行包和素材，不理解故事板语义；上游 Skill 不操作 LFO 数据库、ComfyUI 节点、模型文件或内部素材 ID。
- 调用方负责单段内容 `ACCEPT/REJECT`、真实尾帧登记和最终组装检查。

需要导演审阅时只在视点、调度或节奏仍有重要争议的关键戏委派一次独立审阅；主 Agent 决定是否采纳，不另建故事板、不代替用户批准、不直接改执行包或生成视频。

## 先按交付物读取

只读取当前阶段需要的引用，不把全部引用默认加载：

1. 故事、导演、Camera Setup、六 Beat、operation 或 R2V 分镜板：先读 [故事板与导演工作台](references/storyboard-production.md)，再按字段需要读 [故事板结构](references/storyboard-brief.md)、[创作蓝图](references/creative-blueprint.md) 或 [视觉资产规范](references/creative-assets.md)。
2. 角色卡、场景关键帧、尾帧或资产依赖：读 [角色与视觉控制资产规范](references/creative-assets.md)；其中的 R2V 规则与 [故事板与导演工作台](references/storyboard-production.md) 共同约束同一张板。
3. H3 handoff、execution package、Panel 执行或 assembly：先读 [Panel 交接与执行](references/panel-execution.md)，再按需读 [执行包格式](references/execution-package.md) 和 [视频接受检查](references/video-qc.md)。

上游 Skill 只能交付故事板、公共执行包和素材文件；不要让上游直接操作 LFO 内部状态。独立的 mmx H3 执行链属于用户明确选择的个人 Skill，不能与本 Skill 的 LFO 链混接，也不能作为 LFO 失败后的隐式重试。

## 不可变项目契约

- 当前只支持 `zero-to-story.creative-blueprint.v2` 和 breaking redesign；不为旧包、旧状态表、旧锁格式或旧入口维护兼容分支。
- `storyboard_brief.md` 是故事、视觉和连续性的唯一人工源文件；`creative_blueprint.json` 是编译索引和静态预检输入，不是第二套剧情。
- 1 Panel = 1 Clip。六个 Beat 是有序语义时刻，不是六格图像或六个镜头；真实 H3 `[Shot N]` 只来自 Camera Setup 的变化。
- 每个 Panel 一份独立 execution package，且只含当前 Panel 的一个非 `video.passthrough` Clip。所有 Panel 严格按顺序执行，不能并行提交生成 Clip。
- 执行路径是 `validate` → 当前完整文件字节 `package_sha256` → 该具体包的批准 → `execute --approved-sha256 <hash>`。包改变、批准缺失或 hash 不匹配时停止；不能用笼统“继续生成”代替尚不存在的精确批准，也不在运行中修改包。
- 每个生成工作流只提交一次；仅包显式开启时追加一次 SeedVR2。生成、超时、素材、引用模式、hash 或最小 QC 失败都停止当前执行链；不盲目重试、不保留失败候选、不维护恢复记录。
- 只有调用方对实际片段给出 `ACCEPT` 后，且下一 Panel 确实需要时，才从实际视频提取真实尾帧作为下一包的精确素材。全部 Panel `ACCEPT` 后才用一次独立批准的全 `video.passthrough` assembly 包组装，不调用生成模型。
- 新包和媒体遵守项目 [AGENTS.md](../../../AGENTS.md) 的 workspace 与 `RunArtifactLayout` 规则；不创建根级 `runs`/`exports`，不把临时文件放入真实 workspace。

## 阶段路由

### STEP 0：分析输入并锁定规格

读取小说、剧本、参考图、视频或 handoff，提取角色、场景因果、情绪推进、目标总时长、画幅、媒介和声音要求。按场景因果和每 Panel 4–15 秒估算 Panel 数，不按六格或固定切镜倒推。信息足够时直接写入故事板；需要具体字段时按 [故事板与导演工作台](references/storyboard-production.md) 的顺序推进。

### STEP 1：建立故事板和创作蓝图

首次创建复制 [故事板模板](assets/storyboard_brief.template.md)，完成导演检查、节奏图、Camera Setup、六 Beat、Panel/Clip 映射、operation 和资产计划。从最新故事板同步编译蓝图，运行：

```powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
```

只有 `CREATIVE PREFLIGHT: PASS` 才进入资产或视频阶段；具体字段和 R2V 布局规则见 [故事板与导演工作台](references/storyboard-production.md)。

### STEP 2：生成角色设定图

蓝图预检通过后，按 [角色与视觉控制资产规范](references/creative-assets.md) 为需要稳定身份的主要角色生成一张角色卡。角色描述逐字取自故事板，不混入剧情秘密或镜头安排；完成一次身份、服饰/道具、全身视图和画风的功能检查，把原始路径写入 `character_assets.md`。

### STEP 3：生成必要视觉控制资产

按蓝图的 `generation.panel_plans` 只物化运行时必要资产：`none`、`storyboard_board`、`scene_keyframe` 或 `last_frame`。先满足依赖；互不引用的资产可在工具额度内有限并行，但一张 R2V 分镜板始终一次生成，已有可用资产直接复用，`planning_only` 默认不生成。网格、格位和板内参考的详细规则见 [故事板与导演工作台](references/storyboard-production.md)。

### STEP 4–7：H3、执行包、逐 Panel 和 assembly

按 [Panel 交接与执行](references/panel-execution.md) 完成以下顺序：提供单 Panel 的确认事实给 `$h3-prompt-writing`；逐字复制已确认提示词到当前包；为每个 Panel 独立 `validate` 并取得该完整文件字节的批准；用隔离短生命周期执行单元严格串行调用官方 comfy-cli；调用方给出一次 `ACCEPT/REJECT`，按需登记真实尾帧；全部 Panel `ACCEPT` 后只做一次全 passthrough assembly。

包内只保存当前 Panel 的最小 runtime 输入和相对素材 URI；不要创建 `video_prompt_list.md`、prompt manifest、独立 production lock、评分型 QC 报告、失败候选清单或恢复日志。用户修改故事板、时长、画幅、角色锚点、引用、operation 或 H3 提示词时，受影响包使用新的正整数 `revision` 并重新取得该包 hash 批准；不维护独立 prompt revision 或失效表。

## 项目产物

创作阶段维护 `storyboard_brief.md`、`creative_blueprint.json`、`character_assets.md` 和按需的 `panels/<panel>/storyboard_board.png`、`scene_keyframe.png`、`last_frame.png`。每个 Panel 包及 assembly 包直接放在同一个 `workspace/projects/<project_id>/` 项目根目录，使用互不重复的文件名；媒体与运行中间产物由 `RunArtifactLayout` 管理。替换已接受片段时，按 [视频接受检查](references/video-qc.md#替换片段后的接缝) 核对新版与前后段及实际首帧引用，不默认整章返工。

## 继续与停止

故事板、蓝图或执行包草案的可逆问题，可在当前授权范围内按具体报错定点修正并复核；同一问题没有新依据时不重复修复。生成错误、素材不可用、模式与引用不兼容、精确批准缺失或不匹配、`REJECT` 和最小 QC 失败是硬停止：停止受影响 Panel，报告实际原因与路径。需要继续时，由新的用户指令、修正后的输入或新的已批准执行包明确开启新的当前 Panel 任务。
