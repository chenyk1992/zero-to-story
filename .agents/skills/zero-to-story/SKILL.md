---
name: zero-to-story
description: 从一句灵感、小说、剧本或 short-drama handoff 开始，逐阶段完成故事设计、storyboard_brief.md、角色设定图、2×3 六镜黑白分镜板、经用户确认的 MiniMax H3 Panel 视频提示词，并交付 lfo.video-execution.v1 执行包。适用于从零分镜、从零创建分镜、短剧或小说改视频、续做已有故事板，以及修订角色一致性、分镜连续性、H3 提示词或 LFO 交付。
---

# 从零开始创作并交付短片

## 目标与边界

按固定顺序完成：输入分析 → 故事板文档 → 角色设定图 → 2×3 六镜黑白分镜板 → H3 提示词确认 → LFO 执行。

本 Skill 负责创作决策、视觉资产、提示词和用户确认；LFO Runtime 负责素材导入、视频生成、字幕、混音和导出。只向 LFO 交付已确认的文件路径、素材语义和绑定，不写数据库、ComfyUI 节点、模型路径或内部素材 ID。

## 不可变工作契约

- `storyboard_brief.md` 是唯一信息中枢。用户编辑后必须重新读取，不从旧对话补写。
- `1 Panel = 1 张 2×3 六镜板 = 1 条 H3 Clip`。六格是六个视觉节拍；提示词阶段允许把相邻连续节拍合并为 3–6 个执行节拍，但不得改变六个 Shot ID 或 Panel/Clip 数量。
- P001 使用 Shot 01–06；P002 使用 Shot 06–11；P003 使用 Shot 11–16。后一 Panel 的第一个格位复用上一 Panel 的最后一个 Shot，只承接可见末态，不引入新动作。
- N 个 Panel 的唯一镜头数为 `6 + (N - 1) × 5`，Panel 数、分镜板数和 Clip 数必须相等。
- 默认每个 Panel 10 秒；单段自定义时长保持 4–15 秒。默认无非叙事性音乐，除非用户明确要求。
- 只有用户明确确认才能进入下一阶段。沉默、素材已生成、handoff 字段或 agent 自己判断都不算确认。

## 项目产物

在用户指定项目目录维护：

```text
storyboard_brief.md
character_assets.md
video_prompt_list.md
execution-package.json
```

不要创建重复的故事板或提示词确认文档。不要为了固定目录重命名、移动或复制平台返回的素材；把原始路径记录到对应文档。执行包必须写稳定的 `project.project_id`，而不是绝对输出路径。

## 启动、恢复与审批状态

1. 读取用户输入、现有项目文件和上游 handoff。
2. 若已有 `storyboard_brief.md`，完整读取流程状态和当前内容，从第一个 `待确认` 或 `需重审` 阶段继续。
3. 没有流程状态表时补建，不把历史产物自动标为已确认。
4. 用户修改已确认的时长、画幅、故事板、角色锚点或镜头时，将受影响阶段及所有下游阶段改为 `需重审`。
5. 每次继续前重新读取最新文档；只有直接上游阶段为 `已确认` 才执行生成动作。

在 `storyboard_brief.md` 维护：

| 阶段 | 状态 | 确认依据 |
|---|---|---|
| 规格与目标时长 | 待确认 / 已确认 / 需重审 | 用户确认摘要 |
| 故事板概要 | 待确认 / 已确认 / 需重审 | 用户确认摘要 |
| 角色设定图 | 待确认 / 已确认 / 需重审 | 已确认资产路径 |
| 2×3 黑白分镜板 | 待确认 / 已确认 / 需重审 | 已确认板路径 |
| H3 视频提示词 | 待确认 / 已确认 / 需重审 | `video_prompt_list.md` 版本 |
| LFO 执行计划 | 待确认 / 已确认 / 需重审 | revision 与计划摘要 |

## STEP 0：分析输入并确认规格

读取小说、剧本、参考图、视频或 handoff，提取角色、场景、一句话故事、情绪推进、目标时长、画幅和视觉媒介。

信息不足时一次合并询问作品类型、主要角色、场景、一句话故事、目标时长、画幅和媒介；不要逐题阻塞。若时长未明确，说明依据并给出精简、标准、完整三个选项，按每 Panel 10 秒估算 Panel 数和唯一镜头数。自定义总时长不是 10 秒整数倍时，仍让每段保持 4–15 秒，不留下不足 4 秒尾段。

展示结构化输入摘要。用户确认时长和画幅后，将“规格与目标时长”标为 `已确认`。

## STEP 1：生成故事板文档

完整读取 [故事板文档结构与填充规则](references/storyboard-brief.md)，首次创建时复制 [storyboard_brief 模板](assets/storyboard_brief.template.md)，建立 Medium Lock、Style Brief、角色与场景锚点，并创建或更新唯一的 `storyboard_brief.md`。至少包含：

- 项目信息、Panel 精确时长表、Panel/板/Clip 数和唯一镜头公式。
- 故事梗概、情绪弧线、Medium Lock、Style Brief、角色表和场景表。
- 唯一 Shot 表：景别、运镜、空间关系、台词、声音、锁定末态，以及“与前镜关系、时长权重、必须独立”。
- Panel 映射表：每个 Panel 恰好六个 Shot、六格阅读顺序、相邻节拍的合并建议与不可合并标记。
- 连续性账本和确定性后期资产清单。

每个 Shot 只承担一个清晰动作或信息转折。P001 写六个新镜头；后续每个 Panel 只新增五镜。每个 Panel 默认最多 1–2 句短对白；过密时删次要信息、改画外音/后期字幕或增加时长，不静默硬塞。

完成后检查 Panel/板/Clip 数相等、唯一镜头公式正确、每 Panel 恰好六镜、空间和道具连续、时长可执行。展示文档并请求确认；确认后才进入 STEP 2。

## STEP 2：生成角色设定图

确认故事板概要后，重新读取最新故事板，再完整读取 [角色与六镜分镜资产规范](references/creative-assets.md)，并使用其中链接的角色卡 Prompt 模板。每个需锁定身份的主要角色单独生成一张角色卡，角色描述逐字取自故事板，不混入剧情秘密或镜头安排。

记录平台原始路径、来源、角色锚点和目视检查结果到 `character_assets.md`。检查身份、服饰、道具数量、全身完整性、人物数量和无文字；只重做失败资产。展示并请求用户确认，确认后才进入 STEP 3。

## STEP 3：生成 2×3 六镜黑白分镜板

确认角色资产后，重新读取故事板和角色资产，再按 [角色与六镜分镜资产规范](references/creative-assets.md) 执行：

1. 按已确认映射读取当前 Panel 六个 Shot，不临时改写剧情、顺序或空间关系。
2. 一次调用图片生成模型直出一张恰好 2 行 × 3 列、六个等大格的黑白板，按左上→右下写入六个 Shot。
3. 传入当前 Panel 出场角色卡；P002 起同时传入上一张已确认分镜板，要求新板左上格承接上一板右下格的构图、人物/道具状态和动作末态。
4. 检查无并格、跨格、漏格、伪文字、彩色、精致角色卡、人物漂移或动作换序。

失败时只重做当前整板；不自动拆成六图、裁切或脚本拼板。展示完整分镜板和原始路径并请求确认，确认后才进入 STEP 4。

## STEP 4：生成并确认 H3 视频提示词

确认分镜板后，重新读取最新故事板和资产清单，完整读取 [H3 Panel 视频提示词规范](references/h3-prompts.md)。只有在需要当前平台能力、首尾帧、混合输入、视频/音频参考或 TTS 等特殊模式时，才按该文档指示按需读取 [H3 能力核验记录](references/h3-capabilities.md)。首次创建时复制 [video_prompt_list 模板](assets/video_prompt_list.template.md)，只创建或更新一个 `video_prompt_list.md`。

对每个 Panel 在推理中建立 `PromptControlPlan`，不新增项目文件。依次整理引用与控制维度、全局锁、跨 Panel 连续性锚、3–6 个执行节拍、音频计划和 3–5 个关键负向。控制维度发生冲突时暂停并复核，不让提示词自行裁决。

按 h3-prompts.md 的复杂度评分选择精简、结构化或精确档；按动态时序算法分配执行节拍时长，记录 `duration / tier / score / execution beat count / reference mapping`。提示词正文只复制最终提示词，不复制 plan、推理、日志或文档表格。写入 `### 最终提示词` 和 `### 审批记录`，依据 H3 reference 做内容自检，再展示并请求确认。

P002 起只携带最小状态差：位置、朝向、双手、道具、未完成动作、镜头方向或音频尾音。若新增真实上一镜尾帧，必须把它设为图片1、所有其他引用顺延，`revision++`，重新 `validate`、`plan` 和请求确认。

确认后将“H3 视频提示词”标为 `已确认`，才进入 STEP 5。

## STEP 5：交付 LFO Runtime

完整读取 [VideoExecutionPackage 交付格式](references/execution-package.md)，生成 `execution-package.json`。每个 Clip 只引用本 Panel 出场角色卡和对应 2×3 板，使用 `placement: "fixed"` 与 `slot: "ref_image_N"`。`dependencies` 只表达执行顺序，不等于上一 Clip 末帧自动传入。

执行包边界只交付 `lfo.video-execution.v1` 与已确认的素材语义；不要写数据库、ComfyUI 节点、模型路径、内部 ID 或绝对输出路径。LFO 统一写入 `workspace/projects/<project_id>/outputs/<run_id>/` 和 `workspace/projects/<project_id>/final/<output.directory>/`。

先运行：

```powershell
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
```

逐 Clip 核对 `resolved_references` 与提示词“图片 N”一一对应、Clip/Panel/板数量、时长、素材、后端、字幕本地时间和输出规格。任何顺序、引用、提示词或时长变化都提升 revision，并重新验证与计划。只有用户确认计划摘要后才执行：

```powershell
python -m lfo.cli.main execute execution-package.json --approve
```

## 失败即停规则

- 任一阶段没有直接上游用户确认：停止，不生成下游资产。
- Panel、分镜板和 Clip 数不一致，任一 Panel 不是六格，或唯一镜头公式错误：退回 STEP 1。
- 任何单段不在 4–15 秒、台词或动作无法容纳、或动态时序超载：按 h3-prompts.md 规则重写、延长、合并、拆 Panel 或退回故事板。
- 提示词图片编号与 `ref_image_N` 不一致，必需引用未声明，P002 起缺少连续性，或分镜板负向排除不完整：不得交付 LFO。
- 提示词含模型名、文件路径、数据库、工作流或最终导出分辨率，或把 `negative_prompt` 当成有效控制字段：人工检查并修正。
- `validate`、`plan` 任一失败，或用户未确认计划摘要：不得执行。

## 资源导航

- 故事板结构、六镜表、合并和时序： [storyboard-brief.md](references/storyboard-brief.md)
- 角色卡、整板直出、连续性和唯一运镜词典： [creative-assets.md](references/creative-assets.md)
- H3 PromptControlPlan、复杂度、时序、三档模板和编号映射： [h3-prompts.md](references/h3-prompts.md)
- 易变能力、特殊模式和最后核验来源： [h3-capabilities.md](references/h3-capabilities.md)
- LFO 公共契约、执行包和负向控制边界： [execution-package.md](references/execution-package.md)
- 可复制的项目骨架与生成 Prompt： [assets/](assets/)
