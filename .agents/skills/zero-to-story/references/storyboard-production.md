# GPT-6 适配变更说明

2026-09-07：从入口移入导演、Camera Setup、六 Beat、operation 与 R2V 可变网格决策，按需读取；保持现有故事板、蓝图和视觉资产规范的领域契约。

# 故事板与导演工作台

本参考只在需要创建或修改故事板、Camera Setup、创作蓝图或分镜板时读取。文档字段的完整模板和填充顺序仍以 [故事板结构与填充规则](storyboard-brief.md) 为准；视觉资产的提示词和用途规则仍以 [角色与视觉控制资产规范](creative-assets.md) 为准。

## 导演职责

主 Agent 兼任章节导演，先决定观众在这一章应理解和感受什么，再选择可实现的拍法。导演统一维护叙事视点、表演动机、空间调度、视觉语言、节奏和最终呈现；不把运镜数量或“电影感”当作质量标准。具体取舍写入故事板，不另建导演报告或新的审批节点。

导演、提示词作者和执行器的边界如下：

- 主 Agent 决定故事、镜头意图、连续性、operation 和素材计划。
- `$h3-prompt-writing` 只把已经确认的单 Panel 镜头事实写成 H3 提示词，不重新设计故事或镜头。
- LFO 只消费公共执行包与素材，不理解故事板语义，不作导演决策。
- 调用方负责逐段 ACCEPT/REJECT 和最终视听检查。

重要的视点、调度或节奏争议仍未解决时，可以委派一次独立导演审阅；只传原文、已确认规格、当前故事板和必要资产。审阅返回具体问题和最小建议，由主 Agent 决定是否采纳；不另建故事板、不代替用户批准、不直接改执行包或生成视频。

## 故事板唯一来源与六 Beat

- `storyboard_brief.md` 是故事、视觉和连续性的唯一人工源文件；`creative_blueprint.json` 是从它编译的索引和静态预检输入，不是第二套剧情。
- 新项目使用 `zero-to-story.creative-blueprint.v2`。创建角色图、视觉控制图或视频前，运行蓝图预检并要求 `CREATIVE PREFLIGHT: PASS`。
- 一个 Panel 对应一个 Clip。六个 Beat 是有序语义时刻，不是六格图像，也不是六个镜头；真实 H3 `[Shot N]` 只来自 Camera Setup 的变化。
- P002 起，第一个 Beat 是上一 Panel 已完成末态的零时长边界锚点，后五个 Beat 才是当前 Panel 的新内容。共享边界动作只归前段或后段，保持唯一 transition ownership。
- 每个 Panel 都在故事板里记录精确时长、Camera Setup、六 Beat 映射、operation、首尾帧关系、运行时素材和规划素材；从最新故事板同步编译蓝图后再做最低限度静态检查。
- 故事板同时记录故事梗概、情绪弧线、Medium Lock、Style Brief、角色与场景文本锚点、全章节奏图、逐字对白、统一字幕策略和必要的确定性后期资产；台词字幕与场景内文字分别指定制作责任。

## Camera Setup 表

Camera Setup 是镜头的实现事实来源。每个真正的镜头 Setup 至少写明：景别、机位、轴线侧、人物朝向、目标或视线、屏幕运动、运镜及其起止动机、动作及完成依据、声音和锁定末态。把同一 Setup 内的动作写入 Beat 映射；只有镜头实现事实发生变化时才新增 Setup。

先按场景因果和每 Panel 4–15 秒估算 Panel 数，再把语义 Beat 映射到 Setup；不要用六格或固定切镜数量倒推时长。镜头表需要让后续提示词作者能够直接判断：镜头从哪里开始、主体怎样移动、观众看到什么变化、动作何时完成、最后画面停在哪里，以及下一个 Panel 从哪个真实状态接入。

## operation 与分镜板

先按首帧、尾帧和参考关系选 operation，再决定素材。分镜板存在本身不能触发 R2V：

- 连续场景优先 I2VA，下一 Panel 的 `first_frame` 使用上一段 ACCEPT 成片提取的真实尾帧。
- 同时硬锁首尾才用 FL2VA，并提供 `first_frame` 与 `last_frame`。
- 需要分镜板承载强一致性控制或明确硬切时才用 R2V。
- 无视觉引用且由模型从文字完成时用 T2V。

R2V 的 `storyboard_board` 是一张自包含的黑白分镜板，必须在 STEP 1 先锁定 `rowsxcolumns` 布局，格数为 2–6（例如 `1x2`、`2x2`、`2x3`）。每格只承担其在故事板中被选定的 Beat、Setup 和独有视觉信息，阅读顺序固定为从左到右、从上到下。STEP 3 只做一次图片生成，直接输出准确网格的整张板：

- 不先生成独立分镜帧。
- 不把格子拆成并行任务。
- 不把格子后期拼接成板。
- 不为板内格子另造或重复传入独立图片。
- H3 默认把整张板作为一个 fixed reference；需要时再加入用途明确、不可替代的角色卡或场景关键帧。

人物可以用火柴人式简化表达，但保留少量能维持身份和动作关系的特征，例如发型或帽形、体型、服装轮廓和关键道具；不以“纯火柴人”或肖像级还原作为硬门槛。网格规格、格数、阅读顺序、主体关系、空间、道具和动作状态足以误导视频时才阻断；线条、阴影或环境细节差异只作为后续提示词诊断。

## STEP 0–3 的产出顺序

1. **分析输入。** 读取小说、剧本、参考图、视频或 handoff，提取角色、场景因果、情绪、目标总时长、画幅、媒介和声音要求。信息足够时直接写入故事板；只在关键事实无法安全推断时合并列出缺口。
2. **建立故事板与蓝图。** 首次创建复制 [故事板模板](../assets/storyboard_brief.template.md)，完成导演检查、节奏图、Camera Setup、六 Beat、operation 和资产计划；运行 `python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json`。
3. **生成角色设定图。** 蓝图预检通过后读取 [角色与视觉控制资产规范](creative-assets.md)，每个需要稳定身份的主要角色生成一张角色卡；只做一次身份、服饰/道具、全身视图和画风的功能检查，并把原始路径记入 `character_assets.md`。
4. **生成必要视觉控制资产。** 按 `generation.panel_plans` 只物化运行时必要资产：`none`、`storyboard_board`、`scene_keyframe` 或 `last_frame`。先满足依赖，再按当前工具额度有限并行互不引用的资产；同一分镜板始终一次生成。已有可用资产复用，`planning_only` 默认不生成。

角色图、场景关键帧或尾帧不可用到足以阻断当前用途时停止并报告具体缺口；可承担用途的轻微风格差异直接接受，并在后续提示词或参考组合中修正，不用同一提示词盲目重试。

## 交付文件

创作阶段维护 `storyboard_brief.md`、`creative_blueprint.json`、`character_assets.md` 以及按需的 `panels/<panel>/storyboard_board.png`、`scene_keyframe.png`、`last_frame.png`。执行包放在同一个 `workspace/projects/<project_id>/` 项目根目录，每个 Panel 一个唯一文件名，assembly 另一个唯一文件名；运行时目录和数据边界见项目 [AGENTS.md](../../../../AGENTS.md)。
