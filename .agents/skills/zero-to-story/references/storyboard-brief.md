# 故事板文档结构与填充规则

## 目录

- [固定契约](#固定契约)
- [项目模板](#项目模板)
- [创作蓝图与低成本预检](#创作蓝图与低成本预检)
- [节奏图与 Camera Setup](#节奏图与-camera-setup)
- [Panel 映射](#panel-映射)
- [Panel 接受检查](#panel-接受检查)
- [节奏与时长](#节奏与时长)
- [连续性与确认检查](#连续性与确认检查)

## 固定契约

`storyboard_brief.md` 是故事、视觉设计和连续性的唯一信息中枢。保持：

- `1 Panel = 1 条 Clip`。每个 Panel 都在文档中保留 Beat 1–6 六个有序语义时刻；它们不是固定六格图像。R2V 分镜板只选其中有控制价值的 2–6 个时刻，并在 STEP 1 单独锁定网格布局。
- P001 的六个 Beat 都是有效内容；P002 起 Beat 1 复用上一 Panel 最后一个 Beat 的已完成状态，只作为零时长边界锚点，Beat 2–6 是当前 Panel 的新内容。
- Camera Setup 才是实际摄影镜头和 H3 `[Shot N]` 的来源。相邻 Beat 可以属于同一个 Setup；只有 Setup 改变才产生 cut。Panel 和 Clip 数相等；R2V 的分镜板布局以及其他关键帧由逐 Panel 资产计划决定。
- 先根据精确首尾帧和参考控制需求锁定 operation，再决定 STEP 3 资产。R2V 必须同时选择一张分镜板的 `storyboard_layout`；分镜板的存在不是 R2V 的选择依据，也不能传入 I2V 或 FL2V。
- Beat 记录创作意图；Setup 记录实际机位和剪辑边界；两者都不在本文档内预写 H3 字段或引用标签。

### 跨 Panel 边界契约

- 每个边界登记唯一的 `transition ownership`：共享动作只能由前一个或后一个 Panel 完成；另一段只承接完成后的状态。
- 后一个 Panel 的首个有效动作必须从边界锚点立即推进，禁止倒带、重置、回到动作起点或复演上一段收尾。
- 同场连续接力优先 I2VA + 上一段真实尾帧首帧锁；同时硬锁首尾才用 FL2VA；需要分镜板承载强一致性控制或明确硬切时才用 R2V。R2V 只使用 `placement: "fixed"` 与明确的 `ref_image_N`、`ref_video_N` 或 `ref_audio_N` 槽位，参考图不等于精确首帧锁。
- 每个 Panel 只做一次 `ACCEPT` / `REJECT`。只有已接受视频才由调用方用现有 ffmpeg 提取真实尾帧，供下一 Panel 的 I2VA/FL2VA 使用。
- 当前 LFO final assembly 只落地 `cut`；`match-cut` 是剪辑关系，也以一次 cut 实现。不要在 `output.transitions` 写 `dissolve`、`fade` 或音频桥接；淡化、黑场和声音桥接须由单个 Clip 完整持有，或先制作并确认派生素材。

## 项目模板

从 [storyboard_brief.template.md](../assets/storyboard_brief.template.md) 创建项目文件。模板是可复制的成品骨架；本 reference 只解释字段语义、节奏和检查规则，不再维护第二份模板正文。

## 创作蓝图与低成本预检

在故事板概要阶段同步编译 [创作蓝图规范](creative-blueprint.md) 中的 `creative_blueprint.json`。故事板是人工可读的唯一源文件，蓝图是它的结构化索引，用来在任何图片或视频生成前一次性检查完整性；它不是额外审批或成片 QC。

蓝图必须先解决原文冲突，再覆盖所有 `must_show` / `must_explain` 事件，并为每个事件登记可见证据、前态、后态、Scene、Panel 和 Camera Setup。每场要有入场状态、转折、离场状态和下一场义务；相邻同场镜头的状态必须完全交接，换场必须写桥接。对白按原文顺序锁定，单个 Setup 的主动作、人物、参考槽位、运镜和对白行数不得超过预算。

执行以下静态预检即可发现这类问题，不需要调用任何生成模型：

```powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
```

预检失败只退回 STEP 1 修正文档和蓝图；预检通过后沿用现有角色卡、已确认视觉资产和单 Panel 交接流程。v2 必须在 `generation.panel_plans` 中为每个 Panel 锁定 operation、资产策略、首尾帧来源、运行时引用与仅规划资产。不要把脚本扩展成对最终画面逐帧打分，也不要因为轻微视觉偏差触发重复生成。

## 节奏图与 Camera Setup

### 全章节奏图

在拆 Panel 前，先按完整故事建立节奏图和故事覆盖矩阵。由导演 AI 决定每段的戏剧目标、压力变化、长镜头/切镜策略、声音和时长；Panel 只是随后执行的 4–15 秒技术容器。不能只保留“好看的画面”，必须让每个必需事件落到可见动作或可听信息上。

| 段落 | 戏剧目标 | 压力曲线 | 建议时长 | 主导拍法 | 预计 Setup 数 | 声音策略 |
|---|---|---|---:|---|---:|---|
| [段落] | [观众此处应获得什么] | 上升/保持/释放/停顿 | [秒] | 长镜头/少切/快速切换 | [范围] | [环境声/对白/静默/声桥] |

不要默认平均分配镜头时长。只有出现新的信息、空间、视点、时间或人物反应时才切镜；否则合并为同一 Setup。

### Camera Setup 表

每个 Setup 是一个实际摄影镜头，也是 H3 中一个 `[Shot N]` 的来源。相邻 Beat 使用同一 Setup ID 时表示同镜继续，不产生 cut。

| Setup | Panel | 时间范围 | 覆盖 Beat | 与前 Setup | 机位/景别 | 轴线侧 | 人物朝向 | 目标/视线 | 屏幕运动 | 运镜 | 声音与锁定末态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C001 | P001 | [0–x s] | B001、B002 | 开场 | [内容] | [左/右/N/A] | [内容] | [对象/N/A] | [左→右/N/A] | [词典词] | [内容] |

涉及追逐、对话、交接、主观视角或前后景关系时，机位、轴线侧、人物朝向、目标/视线和屏幕运动不得省略。空镜和纯物件特写可明确写 `N/A`。

每行 Beat 仍只表达一个可见变化或表演时刻。`锁定末态` 只写动作完成后的可见状态，不写无法拍摄的抽象情绪。`运镜` 使用 [creative-assets.md 的运镜词典](creative-assets.md#运镜词汇与摄影动作词典)。

对白列必须记录说话人、语言、逐字原文、原始标点，以及是否画外音。不要只写对白大意，不要翻译或顺手润色。Setup 建议时长由表演和信息量决定；P002 起 Beat 1 边界锚点仍为 0 秒，其余有效 Setup 的独占时间合计为 Panel 时长。

### Panel 生成与视觉资产计划

每个 Panel 写一行生成控制意图，由导演 AI 在完成节奏和 Camera Setup 后确定。决策顺序固定为：先判断是否需要精确首帧/尾帧或多参考，再选 operation，最后选择性物化视觉资产。

| Panel | Operation | STEP 3 资产策略 | R2V 分镜布局 | 精确首帧来源 | 精确尾帧来源 | Runtime inputs | Planning only | 连续/硬切 | 选择理由 |
|---|---|---|---|---|---|---|---|---|---|
| P001 | `video.text_to_video` / `video.image_to_video` / `video.first_last_frame` / `video.reference_to_video` | `none` / `storyboard_board` / `scene_keyframe` / `last_frame` | [`1x2` / `2x2` / `2x3` 等；非 R2V 为无] | [asset key / 无] | [asset key / 无] | [真正传入视频模型的 key] | [仅用于审阅、不传入的 key] | [连续/硬切] | [一句话] |

`visual_asset_policy` 只描述 STEP 3 需要补齐的资产：

- `none`：不调用图片模型；用于 T2V，或等待上一 Clip 通过版真实尾帧的连续 I2V。
- `storyboard_board`：R2V 在 STEP 1 先确定 `rowsxcolumns` 布局，格数为 2–6；STEP 3 一次生成或复用一张完整黑白分镜板，不逐格生成，不后期拼接。
- `scene_keyframe`：生成或复用一张彩色场景/首帧关键帧，用于新场景 I2V。
- `last_frame`：为 FL2V 生成一张精确目标尾帧；首帧通常来自上一 Clip 的通过版真实尾帧。

模式只按控制需求选择，不按题材标签选择：

- `T2V`：没有精确帧或不可替代的身份参考，适合空镜、氛围、一次性环境和弱身份远景；必须使用需要的角色/场景文本锚点。
- `I2V`：需要从上一真实尾帧或批准彩色关键帧准确起步；首帧应已包含必须一致的主要人物和场景。
- `FL2V`：首尾状态都必须准确，且主体是单条连续运动路径。
- `R2V`：强一致性、多状态参考或明确进入新机位的硬切；必须预先锁定一张自包含黑白分镜板的布局，普通参考不能声称是精确首帧。

蓝图中 `runtime_input_keys` 必须等于该 Panel 所有 Setup `reference_keys` 的有序并集，且与 `planning_only_asset_keys` 不重叠。I2V 只能有唯一 `first_frame_source`；FL2V 只能依次有 `first_frame_source` 和 `last_frame_source`；T2V 不带视觉引用；R2V 必须恰有一个当前 Panel 的 `storyboard_board.<panel>` 分镜板 key，作为一张图片和一个 fixed reference。生成分镜板时使用的角色卡、场景图和板内格子不自动再次加入 H3；只有另有不可替代用途的非分镜参考才可显式追加。若模式与素材能力冲突，退回故事板修正，不让提示词阶段静默换模式或丢弃参考。

## Panel 映射

每个 Panel 恰好映射 Beat 1–6 六个有序语义时刻，并为每个 Beat 标注所属 Camera Setup。这是文档内的导演映射，不代表分镜板必须有六格。R2V 只从中选取与已批准 `storyboard_layout` 格数相等的代表时刻，按从左到右、从上到下填入同一张板；一格可以覆盖同 Setup 的多个 Beat。映射表记录每个 Beat 的功能、初态来源、末态去向、Setup ID 和转场/承接说明；接收 Panel 的 Beat 1 明确标注“零时长边界锚点”，不为任何视频模型预先编写字段、引用标签或执行语法。

发生人物、道具或动作交接时，确保上一 Beat 的锁定末态可以成为下一 Beat 的初态。场景改变、说话人改变且需要看口型、视点或轴线改变、明确硬切、匹配切或声音跨切，都应在“转场 / 承接说明”中直接写明。

## Panel 接受检查

每个 Panel 只登记一次结果：文件能打开并播放、时长和输出规格基本可用、主要主体和动作符合计划，且 P002 起的开头能从上一段已接受尾帧自然继续。满足即 `ACCEPT`；否则 `REJECT` 并停止串行流程。轻微且不影响故事的差异不升级为额外评分或自动重试。

详细执行约束见 [最小视频接受检查](video-qc.md)。检查按视觉资产、Panel 内容、连续接力和最终组装的用途拆开，但不维护分数、多个通过等级、失败候选、恢复记录或独立锁文件。

## 节奏与时长

先为完整故事建立节奏图，再确定每个 Panel 总时长和 Camera Setup。Setup 时长由表演和信息量决定；P002 起 Beat 1 锚点固定为 0 秒，其余有效 Setup 的独占时间合计为 Panel 时长。建立镜头、复杂动作和完整对白应获得足够时间；插入、反应和简单状态变化可以更短，但不能短到动作或信息无法被观众辨认。

对白必须按正常语速完整容纳。若 Beat、Setup 的动作和对白明显超过 Panel 时长，按顺序处理：简化次要动作 → 缩短或删除次要台词 → 合并为同一 Setup → 改为画外音或确定性后期 → 延长 Panel 到 4–15 秒 → 拆分 Panel。不得把超载留给下游模型猜测。

## 连续性与确认检查

- [ ] Panel = Clip；每 Panel 恰好六个有序语义 Beat，Beat 到 Camera Setup 的映射完整；每个 R2V Panel 已在 STEP 1 锁定 `storyboard_layout`，且只有一张对应分镜板。
- [ ] 每个 Beat 有可见时刻、空间、动作、逐字对白、声音、所属 Setup 和末态；每个 Setup 有机位、轴线侧、人物朝向、目标/视线、屏幕运动、运镜和前镜关系。
- [ ] P002 起 Beat 1 边界锚点为 0 秒，其余有效 Setup 的独占时间合计等于 Panel 时长；所有 Panel 时长合计等于目标总时长。
- [ ] 每次 cut 都有新的信息、空间、视点、时间或反应理由；没有因 Beat 推进而机械增加切镜或平均分配时长。
- [ ] 场景、轴线、人物、道具、双手和灯光连续；跨 Panel 只携带最小可见状态差。
- [ ] 每个边界已登记 transition ownership；没有相邻 Panel 重复动作、回卷或首个有效镜头停留在锚点。
- [ ] 每个已生成 Panel 只做一次 ACCEPT/REJECT；接受后才提取真实尾帧，下一 Panel 需要时作为精确首帧。
- [ ] final assembly 的 `output.transitions` 只使用 cut；match-cut 不写成额外转场，dissolve/fade/音频桥接已归属单个 Clip 或已确认派生素材。
- [ ] 需要独立表达的切镜、对白、素材或首尾帧已在故事板中明确。
- [ ] 原文冲突已解决；所有 `must_show` / `must_explain` 事件均有唯一镜头落点、原文出处、可见证据和前后状态。
- [ ] 每场的入场/转折/离场/下一场义务已写明；同场状态逐镜交接，换场有因果、时间、空间或声音桥接。
- [ ] `creative_blueprint.json` 已由最新故事板同步编译并通过低成本静态预检；没有把超载动作、对白或参考图留给 H3 猜测。
- [ ] `generation.panel_plans` 与 Panel 一一对应且顺序相同；operation 先于资产选择，R2V 的 `storyboard_layout`、唯一 `storyboard_board.<panel>` 与格子映射完整，I2V/FL2V 不引用分镜板，`planning_only_asset_keys` 不进入模型。
- [ ] 需要出现的可读文字、号码、地址、聊天内容和复杂 UI 已登记为 H3 提示词中的逐字内容；不把后期补字留给运行时猜测。
- [ ] Medium Lock、Style Brief、角色锚点和场景锚点无冲突。

向用户展示故事板时指出为适配目标时长所做的删减、节奏或旁白取舍。只有用户明确确认，才将“故事板概要”状态改为 `已确认`。
