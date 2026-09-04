---
name: zero-to-story
description: 从一句灵感、小说、剧本或 short-drama handoff 开始，逐阶段完成故事设计、storyboard_brief.md、角色设定图和按 Panel 规划的必要视觉控制资产（可选 2×3 六格黑白分镜板、场景关键帧或目标尾帧），并把已确认的单 Panel 创作输入交给专用视频提示词 Skill 和 LFO。适用于从零分镜、短剧或小说改视频、续做已有故事板，以及修订角色一致性、分镜连续性、资产路由或 LFO 交付；不负责撰写、优化或改写 H3 视频提示词，H3 提示词任务必须使用 h3-prompt-writing。
---

# 从零开始创作并交付短片

## 目标与边界

按固定顺序完成：输入分析 → 故事板与逐 Panel 资产路由 → 角色设定图 → 必要视觉控制资产 → 单 Panel 提示词交接 → LFO 执行。

本 Skill 只负责故事与视觉创作决策、角色和分镜资产、连续性以及对应阶段的用户确认。它不撰写、优化、补充或修订 H3 视频提示词，也不维护 H3 字段、模式、标签、时间语法、对白语法、负向词或能力说明。

需要视频提示词时，必须另外使用 `$h3-prompt-writing`。该 Skill 是 H3 提示词结构和写法的唯一权威来源；本 Skill 只提供已确认的 Panel 创作事实，并逐字消费其经用户确认的最终输出。LFO Runtime 负责素材导入、视频生成、字幕、混音和导出。

只向 LFO 交付已确认的文件路径、素材语义、绑定和外部生成的最终提示词，不写数据库、ComfyUI 节点、模型路径或内部素材 ID。

## 不可变工作契约

- `storyboard_brief.md` 是故事、视觉设计和连续性的唯一信息中枢。用户编辑后必须重新读取，不从旧对话补写。
- `creative_blueprint.json` 是从最新 `storyboard_brief.md` 同步编译的机器可读创作索引，只用于低成本静态预检，不是第二套剧情或第二个源文件；两者不一致时以故事板为准并重新编译。
- 新项目的蓝图使用 `zero-to-story.creative-blueprint.v2`，在进入任何资产或视频生成前一次性锁定对白、说话人、动作时窗、头尾保护区和镜头容量；进入 LFO 后不再回退重排故事板。
- `1 Panel = 1 条 Clip`，每个 Panel 必须有六个有序 Beat/可见时刻，但不必然生成 2×3 图像。只有 `visual_asset_policy: "board"` 的 Panel 才生成一张六格板；其他 Panel 可以不生成图，或只生成一张场景/首帧关键帧、一张目标尾帧。六格语义映射始终保留在 `storyboard_brief.md`。P002 起第一个 Beat 是上一 Panel 已完成可见末态的**零时长边界锚点**，不分配动作、台词或视频时长；其余五个 Beat 才是当前 Panel 的新内容。
- 分镜板是可选的构图/多参考控制资产，不是模式选择信号。不得因为已经有分镜板就选择 R2V；先根据镜头关系锁定 operation，再决定 STEP 3 需要补齐哪种资产。
- Camera Setup 才是实际摄影镜头和 H3 `[Shot N]` 的来源。只有 Setup 改变才产生 cut；六格数量不再决定 H3 镜头数量，也不再使用跨 Panel 的唯一镜头公式。
- 默认每个 Panel 只作为 4–15 秒的技术容器，10 秒仅是信息不足时的估算值，不是剪辑节拍。Panel 时长、Setup 数量和各 Setup 时长由全章节奏图与表演信息量决定；P002 起边界锚点为 0 秒，其余有效 Beat/Setup 的独占时间合计为 Panel 时长。默认无非叙事性音乐，除非用户明确要求。
- 每个跨 Panel 边界必须明确 `transition ownership`：共享边界动作只能归前一个或后一个 Panel，不能两段各演一遍。后一个 Panel 从锚点的已完成状态立即推进新动作，禁止倒带、重置、回到动作起点或重演上一段的收尾。
- 同场连续接力优先使用 I2VA 的真实上一镜尾帧首帧锁；只有需要同时硬锁首尾才用 FL2VA；多参考或明确硬切才用 R2V。R2V 必须使用 `placement: "fixed"` 与明确的 `ref_image_N`、`ref_video_N` 或 `ref_audio_N` 槽位；参考图只能提供身份、构图或风格依据，不能声称精确锁定视频首帧。
- 每个相邻边界必须做成对 QC：上一段尾 2 秒与下一段头 3 秒放在同一审查单元，检查重复动作、回卷、姿态/视线/屏幕方向跳变和道具状态跳变。
- 只有用户明确确认才能进入下一阶段。沉默、素材已生成、handoff 字段或 agent 自己判断都不算确认。
- 不创建 `video_prompt_list.md`，不复制或维护 H3 提示词模板、提示词分档、PromptControlPlan 或 H3 能力记录。

## 项目产物

在用户指定项目目录维护：

```text
storyboard_brief.md
character_assets.md
creative_blueprint.json
prompt-manifests/<panel>.json
execution-package.json
```

`execution-package.json` 只能在每个待执行 Panel 已取得 `$h3-prompt-writing` 的最终输出并经用户确认后生成。不要为了固定目录重命名、移动或复制平台返回的素材；把原始路径记录到对应文档。执行包必须写稳定的 `project.project_id`，而不是绝对输出路径。

## 启动、恢复与审批状态

1. 读取用户输入、现有项目文件和上游 handoff。
2. 若已有 `storyboard_brief.md`，完整读取流程状态和当前内容，从第一个 `待确认` 或 `需重审` 阶段继续。
3. 没有流程状态表时补建，不把历史产物自动标为已确认。
4. 用户修改已确认的时长、画幅、故事板、角色锚点或镜头时，将受影响阶段及所有下游阶段改为 `需重审`。
5. 每次继续前重新读取最新文档；只有直接上游阶段为 `已确认` 才执行生成动作。

`creative_blueprint.json` 随 STEP 1 同步更新，不单独请求用户确认。恢复时若蓝图缺失、过期或预检失败，先回到 STEP 1 修复创作设计；不得用已有图片或视频结果替代蓝图。

在 `storyboard_brief.md` 维护：

| 阶段 | 状态 | 确认依据 |
|---|---|---|
| 规格与目标时长 | 待确认 / 已确认 / 需重审 | 用户确认摘要 |
| 故事板概要 | 待确认 / 已确认 / 需重审 | 用户确认摘要 |
| 角色设定图 | 待确认 / 已确认 / 需重审 | 已确认资产路径 |
| 视觉控制资产 | 待确认 / 已确认 / 需重审 | 选择性资产清单、用途与已确认路径 |
| LFO 执行计划 | 待确认 / 已确认 / 需重审 | revision 与计划摘要 |

H3 视频提示词的生成和确认不属于本状态表；它由 `$h3-prompt-writing` 的调用任务负责。本 Skill 恢复执行前只核对当前 Panel 是否已有明确的已确认最终输出。

## STEP 0：分析输入并确认规格

读取小说、剧本、参考图、视频或 handoff，提取角色、场景、一句话故事、情绪推进、目标时长、画幅和视觉媒介。

信息不足时一次合并询问作品类型、主要角色、场景、一句话故事、目标时长、画幅和媒介；不要逐题阻塞。若时长未明确，说明依据并给出精简、标准、完整三个选项，按场景因果单元和每 Panel 4–15 秒估算 Panel 数；不按固定六格或固定切镜数倒推时长。自定义总时长不是 10 秒整数倍时，仍让每段保持 4–15 秒，不留下不足 4 秒尾段。

展示结构化输入摘要。用户确认时长和画幅后，将“规格与目标时长”标为 `已确认`。

## STEP 1：生成故事板文档

完整读取 [故事板文档结构与填充规则](references/storyboard-brief.md)，首次创建时复制 [storyboard_brief 模板](assets/storyboard_brief.template.md)，建立 Medium Lock、Style Brief、角色与场景锚点，并创建或更新唯一的 `storyboard_brief.md`。至少包含：

- 项目信息、Panel 精确时长表、Panel/Clip 数、按策略计算的视觉资产数和全章节奏图。
- 故事梗概、情绪弧线、Medium Lock、Style Brief、角色表和场景表；角色与场景各写一份可复用的文本锚点及可变状态。
- Camera Setup 表：实际镜头的景别、机位、运镜、轴线侧、人物朝向、目标/视线、屏幕运动、声音和锁定末态。
- 六格 Beat 映射表：每格的可见时刻、所属 Setup、初态来源、末态去向和转场/承接说明；相邻格可标为“同镜继续”，不能因换格自动增加 cut。
- 每个 Panel 的生成与视觉资产计划：先锁定 operation，再填写 `visual_asset_policy`（`none` / `board` / `scene_keyframe` / `last_frame`）、精确首帧/尾帧来源、`runtime_input_keys`、`planning_only_asset_keys`、连续/硬切关系和一句选择理由。
- Panel QC 约束：只预先登记真正会阻断剧情、身份、可读文字、关键道具、连续性或合规的硬失败条件，同时写明可修复/可接受偏差。
- 连续性账本和确定性后期资产清单。

### 创作蓝图预检（与故事板同一阶段）

从同一份原文和 `storyboard_brief.md` 同步编译 `creative_blueprint.json`，至少写清：原文冲突及取舍、`must_show` / `must_explain` 故事覆盖、每场的入场/转折/离场状态、场景和 Panel 桥接、逐字对白顺序，以及每个 Camera Setup 的主动作、关键人物、参考槽位和运镜预算。v2 还必须在 `generation.panel_plans` 中为每个 Panel 锁定 operation、STEP 3 资产策略、首尾帧来源、运行时素材与仅规划资产。它是创作编译检查，不是额外用户审批。

在生成角色卡、分镜板或任何视频前执行：

```powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
```

只有 `CREATIVE PREFLIGHT: PASS` 才能进入 STEP 2；新项目使用 v2，旧 v1 项目应先迁移。失败时一次性修复故事板和蓝图，不把缺失剧情、状态跳变、对白抢拍风险或超载镜头留给 H3，也不为此消耗视频生成资源。

v2 的 `production` 区域是一次性的前置准备度闸门：为每个说话人登记稳定 `speaker_id`，为每句对白填写逐字文本、测量/估算时长和 `planned_start_ms`/`planned_end_ms`，为每个 Camera Setup 填写 `start_ms`/`end_ms` 与 `action_schedule`。校验器按“对白时长 + 说话人间隔 + 串行动作 + 头尾保护区，再加安全余量”的关键路径公式检查是否超载；发现问题必须在 STEP 1 修复，不能把时间压力转嫁给提示词或 LFO。

每个 Beat 只承担一个可见变化或表演时刻，但相邻 Beat 可以属于同一 Camera Setup。P001 的六格都是有效 Beat；后续每个 Panel 左上只写上一 Panel 的可见末态锚点，另写五个新 Beat。Setup 的建议时长由表演和信息量决定，不能默认平均分配。每个 Panel 默认最多 1–2 句短对白；过密时删次要信息、改画外音或增加时长，不静默硬塞。本项目默认无后期叠字/补音；需要真实文字或对白时，必须在前置提示词和音频计划中写清。角色对白必须逐字记录原文、标点和语言，不得只写对白大意。

完成后检查 Panel/Clip 数相等、每 Panel 恰好六个语义 Beat、Beat 到 Camera Setup 的映射完整、每次 cut 都有新信息理由、空间和道具连续、边界锚点为零时长、Setup 时长可执行，且每个 Panel 恰好一份资产计划。用资产汇总数量显示节省后的生成量，展示文档并请求确认；确认后才进入 STEP 2。

## STEP 2：生成角色设定图

确认故事板概要且创作蓝图预检通过后，重新读取最新故事板和蓝图，再完整读取 [角色与视觉控制资产规范](references/creative-assets.md)，并使用其中链接的角色卡图片 Prompt 模板。每个需锁定身份的主要角色单独生成一张角色卡，角色描述逐字取自故事板，不混入剧情秘密或镜头安排。

记录平台原始路径、来源、角色锚点和目视检查结果到 `character_assets.md`。检查身份、服饰、道具数量、全身完整性、人物数量和无文字；只重做失败资产。展示并请求用户确认，确认后才进入 STEP 3。

## STEP 3：生成必要视觉控制资产

确认角色资产后，重新读取故事板、蓝图和角色资产，再按 [角色与视觉控制资产规范](references/creative-assets.md) 执行；蓝图中的故事覆盖、状态链、operation、资产路由和镜头预算不得在本步骤临时改写：

1. 先汇总 `generation.panel_plans`，列出四类数量和待生成清单：`none` 不调用图片模型；`board` 生成一张 2×3 六格板；`scene_keyframe` 生成或复用一张批准的场景/首帧关键帧；`last_frame` 生成一张精确目标尾帧。已有且通过 QC 的同语义资产直接复用，不重复生成。
2. 按 Panel 顺序只物化清单中的必需资产。`board` 使用 [2×3 六格黑白分镜板 Prompt 模板](assets/storyboard_board_prompt.template.md)，一次直出整板；`scene_keyframe` 和 `last_frame` 使用 [单帧视觉控制图 Prompt 模板](assets/visual_keyframe_prompt.template.md)，一次只生成一张与成片画幅一致的独立帧。
3. 对六格板检查网格、Beat 顺序、Setup 轴线和边界末态；对单帧检查精确构图、人物/道具状态、空间方向、光线与无伪文字。失败只重做当前资产。
4. 为每份资产记录原始路径、对应 asset key、QC 结果和用途：`runtime_input` 或 `planning_only`。既有分镜板若未在 `runtime_input_keys` 中，必须标为 `planning_only`，不得因它已存在而改选 R2V。

展示“按计划应生成 / 实际复用 / 新生成 / 不生成”汇总和所有新资产原始路径，请求用户确认。若本章全部为 `none` 且无待补资产，也要明确展示“STEP 3 无需图片生成”并取得确认。确认后才进入 STEP 4。

## STEP 4：把单 Panel 交给 h3-prompt-writing

本步骤只做跨 Skill 交接，不撰写视频提示词。对当前已确认且蓝图预检通过的 Panel 明确使用 `$h3-prompt-writing`，并按该 Skill 要求完整读取对应模式的官方 reference。每次只处理一个 Panel，不批量生成整集提示词。

向 `$h3-prompt-writing` 提供原始创作输入，而不是预写好的提示词草稿：

- 当前 Panel 的精确时长、画幅、Medium Lock 和 Style Brief。
- 全章节奏图中本段的节奏意图，以及当前 Panel 的六个 Beat 到 Camera Setup 的映射。
- 每个 Camera Setup 的构图、机位、轴线侧、角色位置与朝向、目标/视线、屏幕运动、动作变化、运镜意图、声音和锁定末态；只有 Setup 改变才生成 H3 `[Shot N]`。
- 每句对白的说话人、原文、标点、语言、是否画外音；禁止概括、改写或遗漏对白。
- 当前 Panel 的生成策略：推荐模式、精确首帧/尾帧要求、必需参考、连续/硬切关系和选择理由。
- 当前 Panel 的 `runtime_input_keys` 及对应的已确认角色卡、场景关键帧、分镜板、真实首帧/尾帧、视频或音频参考与各自用途。`planning_only_asset_keys` 可在人工说明中提及，但禁止传给 `$h3-prompt-writing` 作为模型参考。
- 上一 Panel 的最小可见末态、边界动作归属（前段或后段）和确定性后期资产要求；若为 P002 起，明确左上格是零时长锚点，首个有效新动作从后续镜头开始。

推荐模式和镜头关系先由本 Skill 的导演阶段确定；`$h3-prompt-writing` 负责检查该策略与实际素材/operation 是否兼容，并按对应模式编译正式字段、引用标签、镜头时间、对白标记、声音段落和最终措辞。分镜板的存在不得作为 R2V 选择理由。若模式与 `runtime_input_keys` 不兼容，返回冲突并退回 STEP 1 修正，不得静默换模式、丢弃必需引用或重新设计节奏。本 Skill 不提供第二套 H3 格式规则，不在输出前后追加自定义字段、说明前缀、负向词块或“优化”文本。

展示 `$h3-prompt-writing` 的原始最终输出供用户确认。需要修改时重新调用该 Skill；不得在本 Skill 内手工改写。用户确认后，才把该输出逐字交给 STEP 5。与此同时生成 `prompt-manifests/<panel>.json` 并运行：

```powershell
python .agents/skills/h3-prompt-writing/scripts/validate_prompt_manifest.py prompt-manifests/P001.json
```

清单至少绑定 `clip_id`、提示词 SHA-256、锁定 `plan_hash`、Setup 时窗、对白事件和 H3 参考槽位；清单失败时只修订当前 Panel 的提示词输出，不改变已确认的 Camera Setup、对白时窗、时长或参考策略。

## STEP 5：交付 LFO Runtime

完整读取 [VideoExecutionPackage 交付格式](references/execution-package.md)，生成 `execution-package.json`。`generation.prompt` 只逐字复制当前 Panel 已确认的 `$h3-prompt-writing` 最终输出；不添加标题、解释、负向词、Markdown 包裹或本 Skill 自创元数据。

创建首个执行包前，若用户尚未明确确认 `generation.requirements.megapixels`，必须先让用户从以下四项中选择，不能静默采用推荐项：

1. `0.4 MP`（推荐，优先保证本地生成稳定性）
2. `0.6 MP`
3. `1.0 MP`
4. 自定义（请用户给出大于 0 的具体 MP 数值）

用户未选择时停止，不得从 `output.width/height`、图片素材的 `2K` 标记、外部视频 API 的 `768P` / `2K` 档位、模型能力或 agent 自己的质量判断推导 `megapixels`。把用户选择的精确值和确认依据记录到 `storyboard_brief.md` 的“LFO 执行计划”确认摘要；确认后的值用于当前项目后续 Panel 和 revision。用户主动更改，或后端、机器资源与原确认条件发生实质变化时，重新询问并提升受影响执行包的 revision。

每个 Clip 只引用本 Panel 所需且已确认的素材，并严格按已批准的 Panel 生成策略和 operation 绑定：I2VA 只用 `first_frame`，FL2VA 只用 `first_frame` 与 `last_frame`，R2V 才使用 `placement: "fixed"` 与明确的 `ref_image_N`、`ref_video_N` 或 `ref_audio_N` 槽位。引用顺序必须与 `$h3-prompt-writing` 输出中的 `<Picture N>`、`<Subject N>`、`<Video N>` 和 `<Audio N>` 含义一致。`dependencies` 只表达执行顺序，不等于上一 Clip 末帧自动传入。

把边界方式连同创作输入交给 `$h3-prompt-writing`，不要在执行包阶段补写提示词：同场连续接力用 `video.image_to_video`（I2VA）并将上一段真实尾帧作为唯一精确首帧；需要同时硬锁首尾才用 `video.first_last_frame`（FL2VA）；多参考或明确硬切才用 `video.reference_to_video`（R2V），R2V 不能宣称精确首帧锁定。P002 起首格只是零时长锚点，视频动作必须从锚点后的新镜头立即推进。

执行包边界只交付 `lfo.video-execution.v1` 与已确认的素材语义；不要写数据库、ComfyUI 节点、模型路径、内部 ID 或绝对输出路径。执行包进入 LFO 前必须附带 `lfo.production_lock.v1`：它记录全部 Clip 的不可变计划哈希、允许的提示词修订次数（默认 1）和每 Clip 哈希。锁定后 LFO 不接受故事板、Panel 时长、镜头顺序、对白时窗、引用或 operation 的修改；失败只允许同一 Clip 的确定性重试，或由 `$h3-prompt-writing` 重新提交完整提示词并携带相同 `plan_hash`。LFO 统一写入 `workspace/projects/<project_id>/outputs/<run_id>/` 和 `workspace/projects/<project_id>/final/<output.directory>/`。当前 LFO 最终组装只执行 `cut`；`match-cut` 是创作/剪辑关系，仍以一次 `cut` 落地，不在 `output.transitions` 中写 `dissolve`、`fade` 或音频桥接。若需要淡化、黑场或声音桥接，必须由单个 Clip 完整持有，或先制作并确认派生素材，再交给组装。

每个 Clip 生成后，完整读取并执行 [生成视频分级 QC 与重试止损规则](references/video-qc.md)。LFO 的 boundary evidence 只提供尾帧、首帧、5 秒预览、接触表和技术 metrics 等客观审计素材，不替代创作侧语义判定。创作侧必须对上一段尾 2 秒 + 当前段头 3 秒做成对审查，并给出 `PASS`、`PASS_WITH_REPAIR` 或 `FAIL`；不得把提示词中的每个细节偏差自动判为失败。

最终组装执行包只有在每个相邻边界都已有创作侧 `PASS` 或完成确定性修复并复核后的 `PASS_WITH_REPAIR` 记录时，才能创建和执行。缺少边界记录或存在 `FAIL` 时，只能修复/重生成对应后一 Panel，不能进入最终 assembly。

### 逐镜接力执行（强制）

ComfyUI 是单任务队列，多 Clip 并行只是排队。因此必须逐 Panel 接力：

1. 使用 `$h3-prompt-writing` 完成并确认 P001 的最终提示词，创建只含 P001 的执行包，依次运行 `validate`、`plan` 和经批准的 `execute`。
2. 只对 P001 做单片分级 QC。`PASS` 可进入 P002；`PASS_WITH_REPAIR` 先完成并复核确定性修复；`FAIL` 则拒绝 P001。此时不要虚构 P001→P002 的成对结论，因为 P002 尚未生成。
3. 从 P001 的通过版本提取真实末帧 PNG。若 P002 计划为 I2VA 或 FL2VA，将它作为 P002 的 `first_frame_source`；若 P002 为 T2V 或硬切 R2V，它只用于边界 QC，不绑定为模型参考。连同 P002 创作输入重新交给 `$h3-prompt-writing`；不要手工给旧提示词换编号或追加末帧说明。
4. 用户确认 P002 输出后，创建新 revision；严格按 `generation.panel_plans` 绑定素材：I2VA 写入唯一 `first_frame`，FL2VA 写入 `first_frame` 与 `last_frame`，R2V 只写与实际 H3 标签一致的 typed fixed slot，T2V 不带视觉引用。随后运行 `validate`、`plan` 和经批准的 `execute`。
5. P002 生成后，才截取 P001 尾 2 秒 + P002 头 3 秒，使用 LFO boundary evidence 作为客观审计素材，由创作侧完成成对语义 QC。只有 `PASS` 或确定性修复并复核后的 `PASS_WITH_REPAIR` 才接受 P002，并从接受版本提取真实末帧；它只在 P003 的计划声明精确首帧时才作为接力输入。`FAIL` 不得接入下一段。
6. 按“生成当前 Panel → 单片 QC → 生成下一 Panel → 成对边界 QC → 接受并提取尾帧”的顺序重复，直到最后一个 Panel。最终 assembly 只能在所有边界记录为 `PASS` 或 `PASS_WITH_REPAIR` 后创建/执行。失败 run、修复源和采用产物保留并记录，不覆盖旧产物。

每 Clip 都提取通过版真实末帧作为边界 evidence；只有下一 Clip 的 I2V/FL2V 计划声明它为 `first_frame_source` 时，才成为显式模型参考。需要精确接力时禁止用文字描述“脑补”末态替代真实帧。边界 evidence 只是客观审计素材，不能自动产生语义通过；必须由创作侧写入边界记录。`PASS_WITH_REPAIR` 只有在修复完成并复核后才接受；若修复改变尾帧，先从修复成品提取并复核新的真实尾帧。每次引用、顺序、时长或提示词发生变化都提升 revision，并重新验证、计划和请求确认。

## 失败即停规则

- 任一阶段没有直接上游用户确认：停止，不生成下游资产。
- Panel 和 Clip 数不一致，任一 Panel 不是六个语义 Beat，Beat 到 Camera Setup 的映射不完整，或 `generation.panel_plans` 不是每 Panel 恰好一条：退回 STEP 1。
- I2V/FL2V 的 `runtime_input_keys` 中出现 `board.*`，首尾帧来源与 operation 不匹配，或 `planning_only_asset_keys` 被当作运行时引用：退回 STEP 1；不得在 STEP 3/4 就地换模式。
- `creative_blueprint.json` 缺失、与最新故事板不同步或预检不是 `PASS`：退回 STEP 1；不得用图片、视频或加重成片 QC 来补偿创作设计缺口。
- Camera Setup 缺少机位、轴线侧、人物朝向、目标/视线或屏幕运动，且该关系对镜头可读性有影响：退回 STEP 1。
- 只因分镜格变化就增加 H3 cut，或相邻 Setup 没有新信息理由：退回 STEP 1，合并为同镜继续。
- 任何单段不在 4–15 秒，或台词、动作明显无法容纳：在生产锁前退回故事板调整内容或时长，不把超载交给提示词 Skill 猜测；生产锁后不得重排，只能停止该 Clip 并请求提示词重写或用户决策。
- 当前 Panel 没有由 `$h3-prompt-writing` 生成且经用户确认的最终输出：不得创建或执行 Package。
- `$h3-prompt-writing` 输出与素材标签、顺序或实际引用不一致：带正确输入重新调用该 Skill；不得由本 Skill 局部修补提示词。
- 相邻 Panel 共同演出同一边界动作、下一段从锚点前回卷或首个有效镜头没有立即推进：按边界 QC 判为 `FAIL`，重新明确 transition ownership 与生成模式后再生成。
- 边界 evidence 未完成，或创作侧边界记录不是 `PASS` / 已复核的 `PASS_WITH_REPAIR`：阻断尾帧链和最终 assembly；`FAIL` 必须先修复或重生成后一 Panel。
- `PASS_WITH_REPAIR` 必须优先走确定性修复并复核，轻微偏差记录为 `PASS`，不得为了追求提示词逐字命中而无限重生成。
- 生产锁前同一根因连续两次 `FAIL`：停止只换 seed 或继续堆约束，回到最近的创作输入一次性修正。生产锁后禁止退回故事板重排；只允许 `retry_same`、一次 `rewrite_prompt`（保持 `plan_hash`）或 `block_for_user`，超过预算直接停在当前 Clip。
- `validate`、`plan` 任一失败，或用户未确认计划摘要：不得执行。
- 一次性并行执行所有 Clip：停止并改为逐 Panel 接力，每段成功后提取真实末帧。

## 资源导航

- 故事板结构、六格表、节奏和连续性： [storyboard-brief.md](references/storyboard-brief.md)
- 故事覆盖、场景状态链和生成复杂度预检： [creative-blueprint.md](references/creative-blueprint.md)
- 角色卡、选择性分镜/关键帧、连续性和运镜词典： [creative-assets.md](references/creative-assets.md)
- LFO 公共契约、执行包和外部提示词透传边界： [execution-package.md](references/execution-package.md)
- 视频技术/语义分级 QC、接力与重试止损： [video-qc.md](references/video-qc.md)
- 可复制的故事板与图片资产 Prompt： [assets/](assets/)
