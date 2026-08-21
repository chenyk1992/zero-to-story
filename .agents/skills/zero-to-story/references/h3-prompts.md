# MiniMax H3 Panel 视频提示词规范

本文件是 H3 提示词的唯一权威来源。它规定如何把已确认的六镜故事板压缩成一个 Panel Clip 的可执行控制文本；故事板仍是 Shot ID、空间和连续性的权威来源，`execution-package.md` 是 LFO 契约的权威来源。

## 目录

- [固定边界](#1-固定边界)
- [PromptControlPlan](#2-promptcontrolplan只在推理中使用)
- [六格到执行节拍](#3-六格到执行节拍)
- [复杂度评分与三档选择](#4-复杂度评分与三档选择)
- [提示词正文结构](#5-提示词正文结构)
- [跨 Clip 连续性与 revision](#6-跨-clip-连续性与-revision)
- [图片编号与执行包映射](#7-图片编号与执行包映射)
- [video_prompt_list.md 输出格式](#8-video_prompt_listmd-输出格式)
- [交付前自检](#9-交付前自检)

## 1. 固定边界

- `1 Panel = 1 张 2×3 六镜板 = 1 条 H3 Clip`；六格是六个视觉节拍，不强制生成六次剪切。
- 提示词可以把相邻、连续、同轴的视觉节拍合成 3–6 个执行节拍，但每个节拍必须能回指六个 Shot，不能改变 Shot ID、顺序或 Panel 数。
- 单段时长必须为 4–15 秒；默认 10 秒；提示词硬上限 7000 字符。
- 最多 9 张图片参考；图片的自然语言编号从 1 开始，唯一映射为 `图片1 → ref_image_0`、`图片2 → ref_image_1`，依此类推。
- 分镜板只提供构图、空间、动作链和节奏参考；必须在主体中排除线稿、宫格、分割线、漫画页面和可读文字。
- 提示词不写模型名、文件路径、数据库字段、工作流/节点、执行日志或最终导出分辨率。
- H3 的可变能力、特殊入口和本地 backend 事实只按需读取 [h3-capabilities.md](h3-capabilities.md)，不在本文件复制易变平台说明。

## 2. PromptControlPlan（只在推理中使用）

每个 Panel 先建立一个临时 `PromptControlPlan`。它不是用户项目文件，不进入 `video_prompt_list.md` 或执行包。

```text
PromptControlPlan
├─ references_and_control_dimensions
├─ global_lock
├─ continuity_anchor
├─ execution_beats
├─ audio_plan
└─ critical_negatives
```

### 2.1 控制维度与来源优先级

同一维度只能有一个最终控制源。若两个来源冲突，停止生成并让用户复核，不用提示词自行折中。

| 控制维度 | 首选来源 | 其他来源如何使用 |
|---|---|---|
| 身份、体型、服装、道具 | 已确认角色卡 | 故事板只补当前动作与状态 |
| 精确开场状态 | 实际上一镜尾帧（若已确认加入） | 否则使用上一 Panel 末态和故事板 |
| 构图、空间、动作顺序 | 当前 2×3 分镜板与故事板 | 角色卡不改构图 |
| 动作轨迹 | 动作视频参考（若已确认加入） | 分镜板提供关键节点，不覆盖轨迹 |
| 媒介、色彩、质感 | Medium Lock / Style Brief | 参考板不得把黑白线稿带入成片 |
| 音色、节奏、配乐 | 音频参考（若已确认加入） | 故事板定义叙事声音；N/A 需要写入主体 |
| 对白 | 故事板与用户确认文本 | 音频只改变听感，不改台词 |

全局锁至少写入：主体身份、Medium Lock、画幅/构图意图、光线色调、动作节奏、原生声音原则和禁止输出项。连续性锚只写跨 Clip 的最小状态差：位置、朝向、双手、道具、未完成动作、镜头方向、音频尾音。

## 3. 六格到执行节拍

先读故事板的“与前镜关系、时长权重、必须独立”。

### 3.1 合并规则

允许合并：相邻格为同一场景、同一轴线和连续动作轨迹，没有新说话人或必须切换的视点；后格只是动作推进、反应或同一声音延续。

禁止合并：场景改变、说话人改变且需看口型、视点/轴线改变、故事板要求硬切或匹配切、J/L 对白落点需独立、首尾帧或素材约束需独立，或合并会丢失信息转折。

六个视觉节拍必须保持可追溯，不为了“看起来像分镜”而强制六次剪切；也不为了省字而合并必须独立的节拍。每个执行节拍在内部记下覆盖的 Shot ID，例如 `S002–S003`，最终提示词只输出必要的可见过程。

### 3.2 动态时序算法

为每个执行节拍选择基础最短时长：

| 节拍类型 | 基础最短时长 |
|---|---:|
| 插入 / 反应 | 0.6s |
| 简单动作 | 0.9s |
| 建立 | 1.1s |
| 复杂动作 | 1.5s |
| 情绪停留 | 1.2s |

中文台词最低时长：`字符数 / 4 + 0.3s`。取基础最短时长和对白最低时长的较大值，求所有执行节拍的最低总和。

若最低总和超过目标时长，依次执行：

1. 简化动作，删除不影响因果的次要动作；
2. 缩短台词，或改为旁白/后期字幕；
3. 合并相邻且满足合并规则的节拍；
4. 将 Panel 延长到 4–15 秒；
5. 拆分 Panel，并回到故事板阶段重新确认。

最低总和满足后，剩余时间按故事板 `时长权重` 分配，结果按 0.1 秒取整并把舍入误差回收到最后一个可延长节拍。每个节拍的时间范围必须从 0 开始、严格递增、在 Panel 时长内且不超过 Panel 总时长。不要默认六段等时。

**节拍时间落到 prompt 主体**（H3 官方格式）：动态时序算出的 `节拍起点（0.0–2.4s）/ 切点秒数` 用 H3 base 格式写在 `integrated_multimodal_description`（base 3 段）或 `detailed_description`（full-reference 6 段）主体内：

```text
[Shot 1] (no time, opening) <style + initial composition> ...
[Shot 2] At 02.400, the camera cuts to ...
[Shot 3] At 05.500, ...
```

- `[Shot 1]` 不写时间；后续 Shot 写 `At SS.SSS, the camera cuts to ...`（两位小数秒）。
- Shot 数 = 执行节拍数 = N；cut 数 = N - 1。
- **不要**在主体内写 `16:9` / `15 秒` / `0.0–2.4s` 区间字面——这些由执行包 `requirements.aspect_ratio` / `duration_ms` 字段传递。
- 6 个项目内部 Shot ID（S001–S006）的覆盖关系**不进 prompt 主体**，只写入 `source_context.shot_range` 和 `video_prompt_list.md` 的动态时序表。

## 4. 复杂度评分与三档选择

每个 Panel 计算一次分数：

| 条件 | 分值 |
|---|---:|
| 口型同步对白超过 8 字 | +2 |
| J-cut / L-cut 或跨节拍对白 | +2 |
| 两名及以上说话角色 | +1 |
| 至少 4 个引用，或有视频/音频引用 | +1 |
| 至少 2 个关键运镜 | +1 |
| 5–6 个执行节拍 | +1 |
| 精确音频/音乐/动作同步 | +1 |
| 编辑已有视频，或严格首帧/尾帧 | +2 |

按总分选择：

| 分数 | 档位 | 目标长度 | 结构 |
|---:|---|---:|---|
| 0–2 | 精简（base 3 段） | 350–800 字符 | H3 base 3 段：`integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music` |
| 3–5 | 结构化（base 3 段，默认） | 700–1500 字符 | H3 base 3 段；只写必要时间锚 |
| 6+ | 精确（full-reference 6 段） | 1200–3000 字符 | H3 full-reference 6 段：`subject_definitions` / `summary` / `retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music` |

**full-reference 强制升级**（与分数无关）：只要命中以下任一条件，**必须**升级到 full-reference 6 段，不再用 base 3 段：

- 引用图 ≥ 4 张（含角色卡 + 分镜板 + 上一镜尾帧）
- 含上一镜真实末帧（P002 起在 revision 中加入）
- 含视频或音频参考
- 含 J/L-cut 跨节拍对白

硬上限始终是 7000 字符。评分不是把无关信息塞进 prompt 的理由；越高只表示需要更明确的时间、同步和连续性控制。

## 5. 提示词正文结构

最终正文按 §4 档位自动落入 **H3 官方 3 段 base** 或 **H3 官方 6 段 full-reference**。**不再保留项目自创的"五段中文标题"**（让 H3 模型直接消费与官方一致的字段名）。原"控制源 / 创作意图 / 时间过程 / 音频 / 关键负向"五类信息被映射到 H3 官方字段：

| 旧五段 | 新 base 3 段 | 新 full-reference 6 段 |
|---|---|---|
| 控制源 | `integrated_multimodal_description` 开头引用说明 | `subject_definitions` + `summary` + `retention_analysis` |
| 创作意图 | `integrated_multimodal_description` 风格与首句 | `summary` + `detailed_description` 首句 |
| 时间过程 | `integrated_multimodal_description` 主体 `[Shot N] At SS.SSS` | `detailed_description` 主体 `[Shot N] At SS.SSS` |
| 音频 | `overall_soundscape` + `non_diegetic_music` | `overall_soundscape` + `non_diegetic_music` |
| 关键负向 | 写入 `integrated_multimodal_description` 末段（"不要 …"） | 写入 `detailed_description` 末段（"不要 …"） |

**主体内禁止出现的字段**：模型名 / 文件路径 / SQLite / workflow 节点 / LFO backend 内部 ID / 最终导出分辨率 / 绝对输出路径 / 提示词推理过程。Clip ID 与 Shot ID（S001–S006）属项目内部标签，**不进 prompt 主体**，只写在 `source_context` 与动态时序表里。

### 5.1 base 3 段（H3 精简 / 结构化档）

适用于：参考图 ≤ 3 张、且不含上一镜末帧、且不含视频/音频参考、且无 J/L-cut 跨节拍对白。

```text
integrated_multimodal_description: [Shot 1] <style, initial composition, opening action> ...
[Shot 2] At SS.SSS, the camera cuts to ...
[Shot 3] At SS.SSS, ...
（中间 Shot 4–6 按需）
（关键负向：不要 …；不要 …；不要 …）

overall_soundscape: <1–4 句英语/中文环境声、动作声、非言语人声；无 N/A 例外>

non_diegetic_music: N/A
```

- `[Shot 1]` 必须是 `integrated_multimodal_description: ` 后第一个 token；后续 Shot 序号从 2 起严格递增。
- 切点用 `At SS.SSS, the camera cuts to ...`（两位小数秒）。不要在主体内写 `16:9`、`15 秒`、`<X seconds>` 等数值字面——画幅与时长由执行包 `requirements` 字段传递。
- `non_diegetic_music: N/A` 与任何积极的 BGM/配乐要求互斥，二选一。

### 5.2 full-reference 6 段（H3 精确档，或 full-reference 强制升级）

适用条件见 §4（≥4 引用 / 含末帧 / 含视频或音频 / 跨节拍对白）。6 段顺序固定，不得调换。

```text
subject_definitions:
  <Subject 1>: <description>（attribute reference from Picture 1）
  <Subject 2>: <description>（attribute reference from Picture 2）
  <Picture 1>: <concrete frame anchored at 0.00s>（仅当用作 first/last frame 时；属性引用用纯 Picture N 内联在 <Subject N> 内，不另立 <Picture N>）
  ...

summary: [reference generation] <one-sentence core scene, ≤30 words>

retention_analysis:
  <Subject 1>: fully_preserved
  <Subject 2>: fully_preserved
  <Subject 3>: partially_preserved
  <Picture 1>: fully_preserved (or attribute_transfer if applied to a different identifiable subject)
  ...

detailed_description: [Shot 1] <style + initial composition> ...
[Shot 2] At SS.SSS, the camera cuts to ...
（关键负向：不要 …；不要 …；不要 …）

overall_soundscape: <1–4 句>

non_diegetic_music: N/A
```

`<Subject N>` 与 `<Picture N>` 用法严格遵守 H3 官方：
- `<Subject N>` 是可复用主体（人物、道具、场景、风格）。`Picture N` 内联在 `<Subject N>` 定义里表示属性来源；只有当图片用作具体帧（first/last/锁定主体）时才独立写 `<Picture N>: ...`。
- `<Picture N>` 必须对应实际图片素材；不要凭空虚构 `<Picture 5>` 而不传 `ref_image_4`。
- 同一主体用 `fully_preserved` 或 `partially_preserved`；属性应用到**不同**主体用 `attribute_transfer`（不能用来表达"同一主体保留"）。
- `summary` 段开头用 `[reference generation]` / `[reference generation + keyframe completion]` / `[reference generation + video editing]` / `[reference generation + audio reference]` 等 task-type 前缀，组合时用 ` + `。

### 5.3 对白、voiceover、声音

**对白**：每个节拍使用 `台词：角色"……"` 明确落点。中文台词估时用 `字符数 / 4 + 0.3s`（项目自创规则，不与 H3 官方冲突）。

**跨节拍对白（J-cut / L-cut）**：在 `detailed_description` 写明"上一节拍已起声 / 下一节拍继续"，并标 `J-cut` / `L-cut`。H3 官方要求跨切点用 `<scenetrans>` 标记；本项目为可读性沿用 `J-cut` / `L-cut`，二者并存但等效。

**voiceover / 旁白**（高优先级规则）：旁白一律使用 H3 官方格式 + closed-lips 声明：

```text
<Subject or speaker> (S1) says in an off-screen voiceover: <d>[zh] Exact words.</d>
The corresponding on-screen character's lips remain completely closed.
```

`(S1)` / `(S2)` 是 stable speaker ID，跨 shot 保持不变；只发给声的角色分配 ID，不发声的不要给。完整对白只出现在 `<d>` 内，其他段只描述语言/时长/角色，不要复述台词。

**声音**：`overall_soundscape` 只写模型能生成或用户确认要保留的环境声、动作声、空间声和静默。`non_diegetic_music: N/A` 与积极的 BGM/配乐要求互斥。

## 6. 跨 Clip 连续性与 revision

P002 起提示词只承接最小状态差，不重复整段角色设定。至少写出上一段末态到本段开场的可见关系；不能只写"保持连续"。

**首帧（I2V 模式）**：把当前 Panel 的第 0 秒画面作为 `首帧（绑定 0.00 秒）：<Picture 1> ...`；它置顶为 `ref_image_0`，原有属性参考顺延。

**末帧（L2V 模式 / P002 起承接上一镜）**：把上一 Clip 真实末帧作为 `末帧（绑定 SS.SSS 秒，承接上一 Clip 末态）：<Picture 1> ...`；同样置顶为 `ref_image_0`，其它引用顺延。

**两种情况都触发同样的流程**：

1. 锁定帧必须成为 `ref_image_0`；其它引用全部顺延并重写 `<Subject N>` / `<Picture N>` 编号；
2. `summary` 段开头 task-type 前缀改为 `[reference generation + keyframe completion]`，明确告知模型"首/末帧在 0.00 秒被严格对齐"；
3. `detailed_description` 在 `[Shot 1]` 之后立即描述锁定帧继承的可见状态（位置、朝向、双手、道具、未完成动作），不要从零开始；
4. revision 增加 1；
5. 重新运行 `validate` 和 `plan`；
6. 重新请求故事板/H3 提示词确认。

## 7. 图片编号与执行包映射

提示词自然语言与执行包 `ref_image_N` 槽位的映射固定，但**语法按引用类型分三种**（H3 官方）：

| 提示词语法 | 执行包槽位 | 引用类型 | 出现条件 |
|---|---|---|---|
| `首帧（绑定 0.00 秒）：<Picture 1> ...` | `ref_image_0` | **first-frame 锁定** | I2V 模式，I2V 必为首帧 |
| `末帧（绑定 SS.SSS 秒，承接上一 Clip 末态）：<Picture 1> ...` | `ref_image_0` | **last-frame 锁定** | L2V 模式，末帧置顶 |
| `图片 N`（无角括号，内联在 `<Subject N>` 内） | `ref_image_(N-1)` | **属性参考** | 角色卡 / 分镜板只锁身份与构图 |

执行包槽位规则不变（连续、从 `ref_image_0` 起）：
- 任意**锁定帧**（first-frame / last-frame）必须置顶为 `ref_image_0`，其它引用顺延；触发 `revision++`。
- 仅有属性参考时，按"角色卡 → 分镜板"顺序连续排列。
- `summary` 段开头 task-type 前缀与提示词保持一致：含锁定帧用 `[reference generation + keyframe completion]`；仅属性参考用 `[reference generation]`。

每条 `generation.references[]` 必须设置 `placement: "fixed"` 和对应 `binding.slot`。`<Picture N>` 编号必须连续、对应实际存在的图片素材；`asset_key` 必须存在于顶层 `assets[]`；必需引用不能静默省略。`<d>` 内外的台词、`<Audio N>` 引用与 `<Subject N>` 共用同一 speaker ID，不独立编号。

## 8. video_prompt_list.md 输出格式

从 [video_prompt_list.template.md](../assets/video_prompt_list.template.md) 创建主文档，每个 Panel 复制一节。只有“最终提示词”正文复制到 `generation.prompt`；档位、分值和执行节拍数可复制到 Clip 的 `source_context` 供审计与确定性长度校验，校验结果和 Markdown 标题不复制。

执行包的 `generation.prompt` 只复制“最终提示词”正文，不能复制标题、档位、score、plan、校验报告或 markdown 标记。若写入审计元数据，使用 `source_context.prompt_tier`、`source_context.complexity_score` 和 `source_context.execution_beat_count`。

## 9. 交付前自检

### 9.1 项目内通用项

- [ ] 复杂度分值、档位和长度匹配；档位落入 base 3 段或 full-reference 6 段。
- [ ] full-reference 强制升级条件判定：引用 ≥ 4 / 含末帧 / 含视频或音频 / 含 J/L-cut 任一命中时，已切到 6 段。
- [ ] 3–6 个执行节拍覆盖六个 Shot，且没有违规合并。
- [ ] 动态时间满足基础最短时长与对白估时，范围 4–15 秒。
- [ ] 图片编号与 `ref_image_N` 一一对应、连续、必需素材已声明。
- [ ] P002 起写出最小连续性锚；新增首/末帧已触发顺延、revision++、`validate` / `plan` 重跑。
- [ ] 分镜板的线稿、宫格、漫画和可读文字已在主体中排除。
- [ ] 音频无 N/A 冲突；关键负向为 3–5 条。
- [ ] 内容自检完成并经用户确认；执行包组装后运行 `validate` 和 `plan`。

### 9.2 H3 官方对齐项（24 条自检的子集，重点关注）

- [ ] base 3 段：`integrated_multimodal_description: ` 后第一个 token 是 `[Shot 1]`，中间无任何散文。
- [ ] base 3 段：主体内不出现 `16:9` / `15 秒` / `XX seconds` 等数值字面；画幅与时长由 `requirements` 字段传递。
- [ ] base 3 段：Shot 数 = N，cut 数 = N-1；切点时间严格递增、单位两位小数秒。
- [ ] full-reference 6 段：6 段顺序固定（`subject_definitions` / `summary` / `retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music`），未调换。
- [ ] full-reference 6 段：`summary` 开头是合法的 task-type 前缀（`[reference generation]` / `[reference generation + keyframe completion]` 等）。
- [ ] full-reference 6 段：每个 `<Picture N>` 对应实际图片素材；不凭空写 `<Picture 5>` 而不传 `ref_image_4`。
- [ ] full-reference 6 段：同一主体用 `fully_preserved` / `partially_preserved`；属性应用到**不同**主体才用 `attribute_transfer`。
- [ ] voiceover：每个 off-screen 旁白后立即跟 `The corresponding on-screen character's lips remain completely closed.`
- [ ] 完整对白/歌词只出现在 `<d>` 内，其他段不重复台词字面。
- [ ] `non_diegetic_music` 用 `N/A` 表示无配乐；与积极的 BGM 要求二选一。
- [ ] `<Audio N>` 引用与目标主体共享 speaker ID，不独立编号。
