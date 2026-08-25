---
name: zero-to-story
description: 从一句灵感、小说、剧本或 short-drama handoff 开始，逐阶段完成故事设计、storyboard_brief.md、角色设定图、2×3 六镜黑白分镜板，并把已确认的单 Panel 创作输入交给专用视频提示词 Skill 和 LFO。适用于从零分镜、短剧或小说改视频、续做已有故事板，以及修订角色一致性、分镜连续性或 LFO 交付；不负责撰写、优化或改写 H3 视频提示词，H3 提示词任务必须使用 h3-prompt-writing。
---

# 从零开始创作并交付短片

## 目标与边界

按固定顺序完成：输入分析 → 故事板文档 → 角色设定图 → 2×3 六镜黑白分镜板 → 单 Panel 提示词交接 → LFO 执行。

本 Skill 只负责故事与视觉创作决策、角色和分镜资产、连续性以及对应阶段的用户确认。它不撰写、优化、补充或修订 H3 视频提示词，也不维护 H3 字段、模式、标签、时间语法、对白语法、负向词或能力说明。

需要视频提示词时，必须另外使用 `$h3-prompt-writing`。该 Skill 是 H3 提示词结构和写法的唯一权威来源；本 Skill 只提供已确认的 Panel 创作事实，并逐字消费其经用户确认的最终输出。LFO Runtime 负责素材导入、视频生成、字幕、混音和导出。

只向 LFO 交付已确认的文件路径、素材语义、绑定和外部生成的最终提示词，不写数据库、ComfyUI 节点、模型路径或内部素材 ID。

## 不可变工作契约

- `storyboard_brief.md` 是故事、视觉设计和连续性的唯一信息中枢。用户编辑后必须重新读取，不从旧对话补写。
- `1 Panel = 1 张 2×3 六镜板 = 1 条 Clip`。六格是当前 Panel 的六个有序视觉节拍，不在本 Skill 内把它们改写成 H3 提示词结构。
- P001 使用 Shot 01–06；P002 使用 Shot 06–11；P003 使用 Shot 11–16。后一 Panel 的第一个格位复用上一 Panel 的最后一个 Shot，只承接可见末态，不引入新动作。
- N 个 Panel 的唯一镜头数为 `6 + (N - 1) × 5`，Panel 数、分镜板数和 Clip 数必须相等。
- 默认每个 Panel 10 秒；单段自定义时长保持 4–15 秒。默认无非叙事性音乐，除非用户明确要求。
- 只有用户明确确认才能进入下一阶段。沉默、素材已生成、handoff 字段或 agent 自己判断都不算确认。
- 不创建 `video_prompt_list.md`，不复制或维护 H3 提示词模板、提示词分档、PromptControlPlan 或 H3 能力记录。

## 项目产物

在用户指定项目目录维护：

```text
storyboard_brief.md
character_assets.md
execution-package.json
```

`execution-package.json` 只能在每个待执行 Panel 已取得 `$h3-prompt-writing` 的最终输出并经用户确认后生成。不要为了固定目录重命名、移动或复制平台返回的素材；把原始路径记录到对应文档。执行包必须写稳定的 `project.project_id`，而不是绝对输出路径。

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
| LFO 执行计划 | 待确认 / 已确认 / 需重审 | revision 与计划摘要 |

H3 视频提示词的生成和确认不属于本状态表；它由 `$h3-prompt-writing` 的调用任务负责。本 Skill 恢复执行前只核对当前 Panel 是否已有明确的已确认最终输出。

## STEP 0：分析输入并确认规格

读取小说、剧本、参考图、视频或 handoff，提取角色、场景、一句话故事、情绪推进、目标时长、画幅和视觉媒介。

信息不足时一次合并询问作品类型、主要角色、场景、一句话故事、目标时长、画幅和媒介；不要逐题阻塞。若时长未明确，说明依据并给出精简、标准、完整三个选项，按每 Panel 10 秒估算 Panel 数和唯一镜头数。自定义总时长不是 10 秒整数倍时，仍让每段保持 4–15 秒，不留下不足 4 秒尾段。

展示结构化输入摘要。用户确认时长和画幅后，将“规格与目标时长”标为 `已确认`。

## STEP 1：生成故事板文档

完整读取 [故事板文档结构与填充规则](references/storyboard-brief.md)，首次创建时复制 [storyboard_brief 模板](assets/storyboard_brief.template.md)，建立 Medium Lock、Style Brief、角色与场景锚点，并创建或更新唯一的 `storyboard_brief.md`。至少包含：

- 项目信息、Panel 精确时长表、Panel/板/Clip 数和唯一镜头公式。
- 故事梗概、情绪弧线、Medium Lock、Style Brief、角色表和场景表。
- 唯一 Shot 表：景别、运镜、空间关系、精确台词、声音、建议时长和锁定末态。
- Panel 映射表：每个 Panel 恰好六个 Shot，保持左上到右下的阅读顺序并写明承接关系。
- Panel QC 约束：只预先登记真正会阻断剧情、身份、可读文字、关键道具、连续性或合规的硬失败条件，同时写明可修复/可接受偏差。
- 连续性账本和确定性后期资产清单。

每个 Shot 只承担一个清晰动作或信息转折。P001 写六个新镜头；后续每个 Panel 只新增五镜。每个 Panel 默认最多 1–2 句短对白；过密时删次要信息、改画外音/后期字幕或增加时长，不静默硬塞。角色对白必须逐字记录原文、标点和语言，不得只写对白大意。

完成后检查 Panel/板/Clip 数相等、唯一镜头公式正确、每 Panel 恰好六镜、空间和道具连续、时长可执行。展示文档并请求确认；确认后才进入 STEP 2。

## STEP 2：生成角色设定图

确认故事板概要后，重新读取最新故事板，再完整读取 [角色与六镜分镜资产规范](references/creative-assets.md)，并使用其中链接的角色卡图片 Prompt 模板。每个需锁定身份的主要角色单独生成一张角色卡，角色描述逐字取自故事板，不混入剧情秘密或镜头安排。

记录平台原始路径、来源、角色锚点和目视检查结果到 `character_assets.md`。检查身份、服饰、道具数量、全身完整性、人物数量和无文字；只重做失败资产。展示并请求用户确认，确认后才进入 STEP 3。

## STEP 3：生成 2×3 六镜黑白分镜板

确认角色资产后，重新读取故事板和角色资产，再按 [角色与六镜分镜资产规范](references/creative-assets.md) 执行：

1. 按已确认映射读取当前 Panel 六个 Shot，不临时改写剧情、顺序或空间关系。
2. 一次调用图片生成模型直出一张恰好 2 行 × 3 列、六个等大格的黑白板，按左上→右下写入六个 Shot。
3. 传入当前 Panel 出场角色卡；P002 起同时传入上一张已确认分镜板，要求新板左上格承接上一板右下格的构图、人物/道具状态和动作末态。
4. 检查无并格、跨格、漏格、伪文字、彩色、精致角色卡、人物漂移或动作换序。

失败时只重做当前整板；不自动拆成六图、裁切或脚本拼板。展示完整分镜板和原始路径并请求确认，确认后才进入 STEP 4。

## STEP 4：把单 Panel 交给 h3-prompt-writing

本步骤只做跨 Skill 交接，不撰写视频提示词。对当前已确认 Panel 明确使用 `$h3-prompt-writing`，并按该 Skill 要求完整读取对应模式的官方 reference。每次只处理一个 Panel，不批量生成整集提示词。

向 `$h3-prompt-writing` 提供原始创作输入，而不是预写好的提示词草稿：

- 当前 Panel 的精确时长、画幅、Medium Lock 和 Style Brief。
- 六个有序 Shot 的构图、角色位置、动作变化、运镜意图、声音和锁定末态。
- 每句对白的说话人、原文、标点、语言、是否画外音；禁止概括、改写或遗漏对白。
- 当前 Panel 的已确认角色卡、分镜板、真实首帧/尾帧、视频或音频参考及各自用途。
- 上一 Panel 的最小可见末态和确定性后期资产要求。

H3 模式选择、正式字段、引用标签、镜头时间、对白标记、声音段落和最终措辞全部由 `$h3-prompt-writing` 决定。本 Skill 不提供第二套规则，不在输出前后追加自定义字段、说明前缀、负向词块或“优化”文本。

展示 `$h3-prompt-writing` 的原始最终输出供用户确认。需要修改时重新调用该 Skill；不得在本 Skill 内手工改写。用户确认后，才把该输出逐字交给 STEP 5。

## STEP 5：交付 LFO Runtime

完整读取 [VideoExecutionPackage 交付格式](references/execution-package.md)，生成 `execution-package.json`。`generation.prompt` 只逐字复制当前 Panel 已确认的 `$h3-prompt-writing` 最终输出；不添加标题、解释、负向词、Markdown 包裹或本 Skill 自创元数据。

每个 Clip 只引用本 Panel 所需且已确认的素材，使用 `placement: "fixed"` 与明确 `slot: "ref_image_N"`。引用顺序必须与 `$h3-prompt-writing` 输出中的 `<Picture N>`、`<Subject N>`、`<Video N>` 和 `<Audio N>` 含义一致。`dependencies` 只表达执行顺序，不等于上一 Clip 末帧自动传入。

执行包边界只交付 `lfo.video-execution.v1` 与已确认的素材语义；不要写数据库、ComfyUI 节点、模型路径、内部 ID 或绝对输出路径。LFO 统一写入 `workspace/projects/<project_id>/outputs/<run_id>/` 和 `workspace/projects/<project_id>/final/<output.directory>/`。

每个 Clip 生成后，完整读取并执行 [生成视频分级 QC 与重试止损规则](references/video-qc.md)。LFO 的技术 QC 保持硬阻断；创作侧语义 QC 必须给出 `PASS`、`PASS_WITH_REPAIR` 或 `FAIL`，不得把提示词中的每个细节偏差自动判为失败。

### 逐镜接力执行（强制）

ComfyUI 是单任务队列，多 Clip 并行只是排队。因此必须逐 Panel 接力：

1. 使用 `$h3-prompt-writing` 完成并确认 P001 的最终提示词，创建只含 P001 的执行包，依次运行 `validate`、`plan` 和经批准的 `execute`。
2. 对 P001 执行分级 QC。`PASS` 可直接继续；`PASS_WITH_REPAIR` 先完成并复核所需修复；只有 `FAIL` 才拒绝当前片段。
3. 从通过或修复后通过的最终视频提取真实末帧 PNG。若修复只影响中段或音频且尾帧已通过，可保留原始真实尾帧；若修复影响最后一秒，必须从修复成品重新提取并复核。
4. 把该末帧作为 P002 的新增真实参考，连同 P002 创作输入重新交给 `$h3-prompt-writing`。不要手工给旧提示词换编号或追加末帧说明。
5. 用户确认新的 P002 输出后，创建新 revision，写入明确的 `ref_image_0` 或与实际 H3 标签一致的固定槽位，再运行 `validate`、`plan` 和经批准的 `execute`。
6. 重复以上步骤直到最后一个 Panel。失败 run、修复源和采用产物保留并记录，不覆盖旧产物。

每 Clip 的真实末帧必须成为下一 Clip 的显式参考，禁止用文字描述“脑补”末态替代。`PASS_WITH_REPAIR` 只要修复不改变尾帧，就不阻断接力；若改变尾帧，先修复再接力。每次引用、顺序、时长或提示词发生变化都提升 revision，并重新验证、计划和请求确认。

## 失败即停规则

- 任一阶段没有直接上游用户确认：停止，不生成下游资产。
- Panel、分镜板和 Clip 数不一致，任一 Panel 不是六格，或唯一镜头公式错误：退回 STEP 1。
- 任何单段不在 4–15 秒，或台词、动作明显无法容纳：退回故事板调整内容或时长，不把超载交给提示词 Skill 猜测。
- 当前 Panel 没有由 `$h3-prompt-writing` 生成且经用户确认的最终输出：不得创建或执行 Package。
- `$h3-prompt-writing` 输出与素材标签、顺序或实际引用不一致：带正确输入重新调用该 Skill；不得由本 Skill 局部修补提示词。
- 只有 `FAIL` 级语义问题阻断尾帧链；`PASS_WITH_REPAIR` 必须优先走确定性修复，轻微偏差记录为 `PASS`，不得为了追求提示词逐字命中而无限重生成。
- 同一根因连续两次 `FAIL`：停止只换 seed 或继续堆约束，改用模式/后端调整、拆 Panel、替换素材或确定性修复；实质策略变化后仍复现时不再继续采样。
- `validate`、`plan` 任一失败，或用户未确认计划摘要：不得执行。
- 一次性并行执行所有 Clip：停止并改为逐 Panel 接力，每段成功后提取真实末帧。

## 资源导航

- 故事板结构、六镜表、节奏和连续性： [storyboard-brief.md](references/storyboard-brief.md)
- 角色卡、整板直出、连续性和运镜词典： [creative-assets.md](references/creative-assets.md)
- LFO 公共契约、执行包和外部提示词透传边界： [execution-package.md](references/execution-package.md)
- 视频技术/语义分级 QC、接力与重试止损： [video-qc.md](references/video-qc.md)
- 可复制的故事板与图片资产 Prompt： [assets/](assets/)
