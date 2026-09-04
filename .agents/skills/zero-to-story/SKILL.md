---
name: zero-to-story
description: 从灵感、小说、剧本或 short-drama handoff 开始完成故事板、角色与必要视觉控制资产，并把已确认的单 Panel 输入交给 h3-prompt-writing 和 LFO。执行阶段每个 Panel 使用一份用户批准的 VideoExecutionPackage 精确文件字节 SHA-256 作为锁，并以相互隔离的执行单元串行调用 ComfyUI 官方 comfy-cli；不负责撰写 H3 视频提示词。
---

# 从零开始创作并交付短片

## 目标与边界

本 Skill 负责故事、视觉设计、角色资产、分镜、连续性和执行包准备：

~~~text
输入分析 → 故事板与 Camera Setup → 必要视觉资产 → 单 Panel H3 提示词 →
逐 Panel execution package → 每包 validate 与精确文件 SHA-256 核对 → 隔离串行生成 → 真实尾帧接力 → 一次最终组装检查
~~~

它不撰写、优化或改写 H3 提示词，也不操作 LFO 数据库、ComfyUI 节点、模型文件或内部素材 ID。需要视频提示词时必须使用 $h3-prompt-writing；LFO 执行器只消费已经确认的执行包和素材文件。

本流程面向当前新流程，不为旧包、旧状态表或旧锁格式提供兼容分支。已有素材可以按语义复用，但必须重新纳入当前故事板和批准执行包。

## 不可变工作契约

- storyboard_brief.md 是故事、视觉和连续性的唯一人工源文件；creative_blueprint.json 是从它编译的索引和静态预检输入，不是第二套剧情。
- 新项目只使用 zero-to-story.creative-blueprint.v2。在生成角色图、视觉控制图或视频前，预检必须通过。
- 1 Panel = 1 Clip。六个 Beat 是有序语义时刻，不是六格图像或六个镜头；真正的 H3 [Shot N] 只来自 Camera Setup 的变化。
- 先按首帧、尾帧和参考关系选择 operation，再决定是否需要 storyboard_board、scene_keyframe 或 last_frame。R2V 必须在 STEP 1 同时锁定 `storyboard_layout`；分镜板存在本身不是 R2V 理由。
- 同场连续接力优先 I2VA；下一 Panel 使用上一段已接受成片提取的真实尾帧作为唯一精确首帧。只有同时硬锁首尾才用 FL2VA；需要分镜板承载强一致性控制或明确硬切时才用 R2V。
- 每个 Panel 都有一份独立的 execution package，且每份只包含当前 Panel 的一个 Clip；它是该 Panel 的唯一执行输入。所有 Panel 包和最后的 assembly 包都直接放在同一个 `workspace/projects/<project_id>/` 项目根目录，使用互不重复的文件名（例如 `panel-P001.execution-package.json`、`panel-P002.execution-package.json`、`assembly.execution-package.json`），不要把包放进每 Panel 子目录，否则前一 Run 的 `outputs/<run_id>/...` 无法稳定地用包内相对 `source.uri` 引用。先运行 `validate`，再让用户确认其返回的精确文件字节 `package_sha256`，并把这个值作为该 Panel 的唯一执行锁；执行前 Runtime 再次计算，哈希不一致就停止。不要把所有 Panel 或依赖关系塞进一个生产包，也不要创建独立 production lock、prompt manifest 或重复锁文件。
- 每个 Panel 是一个独立的短生命周期执行单元，严格按 P001、P002……顺序运行。每次执行只处理被指定的 Panel，不能并行、改写创作计划或自行换模式。
- 执行器直接同步调用 ComfyUI 官方 comfy-cli 完成当前生成并返回结果；不建设 provider 状态机、租约、心跳、自动重试、失败候选或恢复记录。
- 每个 Panel 只有一次 ACCEPT / REJECT 判断：确认文件可播放、主要内容符合计划，并在连续接力时确认当前开头能从上一段末态自然继续。轻微、不影响故事的差异不升级为复杂 QC。
- 只有 ACCEPT 的成片才能在下游需要时提取真实末帧并交给下一 Panel；没有下游用途时不做多余提取。REJECT 或生成错误立即停止，由调用方或用户决定是否重新发起一次新的 Panel 任务。
- 全部 Panel ACCEPT 后才组装；最终只做一次可播放性、顺序和基本音视频存在检查。
## 项目产物

在用户指定的项目目录维护以下文件和必要素材：

~~~text
storyboard_brief.md
creative_blueprint.json
character_assets.md
（可选）panels/<panel>/storyboard_board.png（R2V 一张，布局在 STEP 1 锁定）
（可选）panels/<panel>/scene_keyframe.png
（可选）panels/<panel>/last_frame.png
项目根目录下每个 Panel 一份独立 execution package（每份只含一个 Clip），另有根目录下的 assembly package
~~~

不创建 video_prompt_list.md、prompt-manifests/、独立 production lock、评分型 QC 报告、失败候选清单或恢复日志。提示词是当前 Panel 的已确认文本，直接保存在执行包的 generation.prompt 中。

素材保留平台原始路径和语义用途；不要为了目录整齐重命名、移动或复制平台返回文件。执行包使用稳定的 project.project_id 和包内相对素材 URI，不写绝对输出路径、ComfyUI 节点、模型路径或内部 ID。
## 流程状态与确认

只保留能帮助恢复创作的最小状态：

| 项目 | 状态 |
|---|---|
| 故事板/蓝图 | 草稿 / 已确认 |
| 角色与视觉资产 | 未生成 / 待确认 / 已确认 |
| 当前 Panel execution package | 未批准 / 已批准（记录该包精确文件 SHA-256） |
| Panel | 待生成 / ACCEPT / REJECT |

用户修改故事板、时长、画幅、角色锚点、引用、operation 或 H3 提示词时，为受影响的执行包设置新的正整数 `revision` 并重新取得一次哈希批准；不维护独立 prompt revision 或下游失效表。每次继续前读取最新文件，不从旧对话补写已变更内容。
## STEP 0：分析输入并确认规格

读取小说、剧本、参考图、视频或 handoff，提取角色、场景、故事因果、情绪推进、目标总时长、画幅、媒介和声音要求。信息不足时一次合并询问，不逐题阻塞。按场景因果和每 Panel 4–15 秒估算 Panel 数，不按六格或固定切镜倒推时长。

展示简短结构化摘要，并在故事板中记录用户确认的目标总时长、画幅、媒介和声音原则。
## STEP 1：建立故事板和创作蓝图

完整读取 [故事板结构与填充规则](references/storyboard-brief.md)，首次创建时复制 [storyboard_brief 模板](assets/storyboard_brief.template.md)。故事板至少包含：

- 故事梗概、情绪弧线、Medium Lock、Style Brief、角色和场景文本锚点；
- Panel 精确时长表、Panel/Clip 数、全章节奏图；
- Camera Setup 表：景别、机位、轴线侧、人物朝向、目标/视线、屏幕运动、运镜、声音和锁定末态；
- 每个 Panel 的六个有序 Beat 映射。P002 起第一个 Beat 是上一 Panel 已完成末态的零时长锚点，后五个 Beat 是当前新内容；共享边界动作只归前段或后段；
- 每个 Panel 的 operation、视觉资产策略、R2V `storyboard_layout`、首尾帧来源、运行时素材和规划素材；
- 逐字对白和必要的确定性后期资产。

从最新故事板同步编译 creative_blueprint.json，使用 [创作蓝图规范](references/creative-blueprint.md) 和 v2 模板。只做最低限度的静态检查：结构完整、Panel/Clip 对应、时长可用、对白和事件有落点、相邻状态能接上、operation 与引用关系一致。

执行：

~~~powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
~~~

只有 CREATIVE PREFLIGHT: PASS 才能进入资产或视频阶段。失败时一次性修正文档和蓝图，不消耗生成额度；这项预检不是最终视频逐帧评分。

展示故事板、蓝图摘要和资产数量，取得对创作计划的确认后进入 STEP 2。
## STEP 2：生成角色设定图

确认故事板和蓝图后，重新读取最新文件，完整读取 [角色与视觉控制资产规范](references/creative-assets.md)，并使用其中链接的角色卡模板。每个需要稳定身份的主要角色生成一张角色卡；角色描述逐字取自故事板，不混入剧情秘密或镜头安排。

只做一次简洁目视确认：角色身份、服饰/关键道具、全身视图和画风是否可用。记录原始路径到 character_assets.md。需要修正时只重新生成当前角色卡；不创建失败候选历史。所有需要的角色资产确认后进入 STEP 3。
## STEP 3：生成必要视觉控制资产

优化顺序固定为：选择性生成 → 按用途二元检查 → 对剩余任务做依赖感知并行。并行不能成为补生无用资产或放宽功能错误的理由。

先按蓝图中的 generation.panel_plans 汇总当前章节清单：

- none：不调用图片模型，用于 T2V 或等待上一 Panel 真实尾帧的连续 I2V；
- storyboard_board：只为 R2V 生成或复用一张黑白分镜板；在 STEP 1 已按需要锁定 `1x2`、`2x2`、`2x3` 等 2–6 格布局，STEP 3 用一次图片生成直接得到整张板，不先生成独立帧，也不后期拼接；
- scene_keyframe：生成或复用一张成片画幅的场景/首帧关键图；
- last_frame：生成一张成片画幅的目标尾帧，供 FL2V 使用。

先列出每项资产依赖的已确认角色卡、场景关键帧或其他视觉资产；同一依赖层中互不引用的不同 Panel 分镜板或其他资产，可以在当前工具并发额度内有限并行，依赖尚未确认资产的任务必须等待。一张分镜板始终作为一次原子生成，不把格子拆成并行任务。只物化计划中的运行时必要资产，`planning_only` 默认不生成；已有可用资产直接复用。

视觉资产检查与后续视频检查按用途分开，但都只给一次二元结论，不打分。分镜板先检查网格规格、格数、阅读顺序及关键主体、空间、人物关系、道具和动作状态；缺失或错误到足以误导视频时才阻断。“不够纯火柴人”、环境较细、线条或阴影差异只作为非阻断的提示词诊断。资产仍能承担用途时直接接受，并修正后续提示词或参考组合，不用同一提示词反复重试。

展示“计划生成 / 复用 / 不生成”的短清单，确认后进入 STEP 4。
## STEP 4：逐 Panel 交给 h3-prompt-writing

每次只处理一个 Panel，并完整读取 $h3-prompt-writing 对应模式的官方 reference。提供创作事实，不提供自写提示词草稿：

- 当前 Panel 时长、画幅、Medium Lock、Style Brief 和节奏意图；
- 六个 Beat 到 Camera Setup 的映射；
- 每个 Setup 的构图、机位、轴线、人物朝向、目标/视线、屏幕运动、动作、声音和锁定末态；
- 逐字对白、说话人、语言和画外音状态；
- 推荐 operation、精确首/尾帧要求、连续/硬切关系；
- 当前 Panel 的最小 runtime_input_keys 及每个素材用途；R2V 同时提供已锁定的 `storyboard_layout`、按从左到右/从上到下排列的格子到 Beat/Setup 映射；
- P002 起的零时长边界锚点和唯一 transition ownership。

$h3-prompt-writing 负责选择对应 H3 字段、标签、镜头时间、对白语法和最终英文措辞。它不得静默换 operation、丢弃必需素材、重排对白或改变已批准时长。R2V 分镜板作为一张图片和一个 fixed reference 处理；在提示词中补充分格阅读顺序与内容，不附加并不存在的独立格子图片。分镜板的存在不能单独触发 R2V。

展示该 Panel 的完整最终提示词。需要修改时重新调用 $h3-prompt-writing；不得在本 Skill 内手工修补。用户确认创作/执行计划后，逐字复制提示词到执行包，不创建 prompt manifest。
## STEP 5：创建并批准逐 Panel 执行包

完整读取 [VideoExecutionPackage 交付格式](references/execution-package.md)，为当前 Panel 生成一份独立的 execution-package.json，且只包含当前 Panel 的一个 Clip；不要把所有 Panel、跨 Panel dependencies 或最终 assembly 塞进这份包。每份 Panel 包使用独立 `package_id`；适配器缺省采用 `<project_id>-<panel_id>`。Clip 的 generation.prompt 只逐字复制当前 Panel 已确认的 H3 输出，不加标题、解释、负向词或自创字段。

执行包至少写清：

- 当前 Panel 的稳定项目 ID、Panel/Clip 标识、精确时长、画幅、FPS 和用户明确选择的生成规格；
- 当前 Panel 的 operation 及最小素材引用。I2VA 只用 first_frame，FL2VA 只用 first_frame + last_frame，R2V 把整张 `storyboard_board.<panel>` 放入一个明确的 typed fixed slot，T2V 不带视觉引用；不会把板内格子作为额外图片重复传入，其他参考仅在不可替代且用途明确时加入；
- 当前 Panel 的字幕、音频和输出策略；跨 Panel 串行关系由主流程保持，不写成单包内的生产依赖；
- approval 中的用户批准信息；锁值是当前 execution-package.json 的精确文件字节 SHA-256，由 runtime 的 `--approved-sha256 <hash>` 参数核对。

当前 Panel 提交前执行一次最小链路：

~~~powershell
python -m lfo.cli.main validate <panel-execution-package.json>
python -m lfo.cli.main execute <panel-execution-package.json> --approved-sha256 <hash>
~~~

其中 `<hash>` 是 `validate` 成功结果中的 `package_sha256`；每个 Panel 都必须独立 validate、取得用户批准，并由 execute 再次核对 hash。`plan` 不是必经步骤，只可作为需要时的诊断；不生成额外锁文件。

## STEP 6：逐 Panel 隔离执行

对每个 Panel 建立一个独立的短生命周期执行单元并严格串行。具体运行机制由宿主工具决定，不属于 Skill 契约。每次只提供下列最小输入，不传完整故事或前序执行日志；当前执行完成并返回后才可开始下一个。

~~~text
validate current Panel package and show package_sha256 for approval
  → exact file-byte SHA-256 approved
  → start one isolated Panel execution
  → execute current package --approved-sha256 <hash>
  → synchronous comfy-cli generation
  → one ACCEPT / REJECT
  → ACCEPT: extract real tail frame when needed downstream
  → start next Panel execution
~~~

调用方启动的 Panel 执行单元输入保持最小（其中 `tail_frame_output_path` 只是调用方提取辅助参数，不是 LFO CLI/runtime 参数，也不写入 package）：

~~~text
panel_id
package_path
approved_package_sha256
machine_id（有已保存机器配置时）
tail_frame_output_path（仅下游需要真实尾帧时；调用方的 ffmpeg 提取目标）
~~~

执行器只读取当前 Panel 的 Package；上一 Panel 的尾帧若是当前生成输入，必须先在 `ACCEPT` 后由调用方使用现有 ffmpeg 从实际接受视频提取到项目 Run 输出目录，再把该确切 PNG 作为下一 Panel package 的相对素材 URI 和 `first_frame` 引用写入包，并在下一次 `validate` 前完成。尾帧文件路径不通过 LFO `execute` 参数传递，也不能用文字描述或虚构路径替代。执行器调用 runtime 的 `execute ... --approved-sha256 <hash>`；ComfyUI 由该执行路径同步调用官方 comfy-cli。若调用方提供 `tail_frame_output_path`，它只是调用方当前 Panel 的提取目标；尾帧登记完成后才可准备下一包。回传：

~~~text
panel_id
ACCEPT | REJECT | ERROR
video_path
tail_frame_path（ACCEPT 且下游需要时）
一句结果或错误说明
~~~

不把完整故事历史、旧日志、内部状态或所有素材塞进单次执行输入。ComfyUI 是单队列，禁止并行提交。CLI 错误或 REJECT 都立即停止，不自动重试、不保留失败候选、不写恢复记录；如需再做，由调用方或用户明确发起一个新的当前 Panel 任务。

对 P001 做一次成片可播放和内容可用检查。P002 起，在同一次检查里顺带观看上一段末态到当前开头的短连接，确认没有明显回卷、重置或跳变。接受后只有下一 Panel 的 I2VA/FL2VA 计划需要时才把真实末帧作为 first_frame。

## STEP 7：一次最终组装

所有 Panel 都 ACCEPT 后才交给 LFO 组装。按执行包顺序连接 Clip；当前最终转场使用 cut，match-cut 只是创作关系，不新增转场类型。只做一次基本检查：最终文件可播放、Clip 顺序正确、音视频轨道和字幕策略符合执行包。

## 资源导航

- 故事板结构与 Camera Setup：[storyboard-brief.md](references/storyboard-brief.md)
- 创作蓝图与最小预检：[creative-blueprint.md](references/creative-blueprint.md)
- 角色卡、选择性视觉资产与连续性：[creative-assets.md](references/creative-assets.md)
- 执行包、批准哈希与 Panel 接力：[execution-package.md](references/execution-package.md)
- 一次 ACCEPT/REJECT 与最终检查：[video-qc.md](references/video-qc.md)
- 可复制的图片 Prompt：[assets/](assets/)
