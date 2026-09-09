# 创作蓝图与低成本预检

共同的角色、Panel ready、实际验收和授权规则见[项目共享生产规则](../../../../docs/ai-system-prompt.md)。本文只规定蓝图字段和静态预检，不把预检当作成片验收。

## 目的

storyboard_brief.md 是故事、视觉和连续性的人工源文件。creative_blueprint.json 是从它同步编译的机器可读索引，用于一次低成本静态预检；它不是第二套剧情，也不是视频成片评分器。两者冲突时修正故事板，再重新编译蓝图。

新流程只使用 zero-to-story.creative-blueprint.v2，不读取旧 schema，不做迁移兼容。蓝图在任何角色图、视觉控制资产或视频生成前通过一次即可。

## 必须回答的问题

| 区域 | 内容 |
|---|---|
| source | 当前原文、已经解决的冲突和采用版本 |
| user_constraints | 用户选择的生成像素预算、采样模式和步数；视频生产前补齐，后续 Panel 继承 |
| coverage | 观众必须看到/理解的事件、原文出处、可见证据和前后状态 |
| scenes | 每场目的、转折、入场/离场状态、下一场义务和必要桥接 |
| panels | Panel 顺序、4–15 秒时长、场景、六 Beat、状态和边界归属 |
| dialogue | 按原文顺序的逐字对白、说话人、语言和所属 Setup |
| generation.panel_plans | 每个 Panel 的 operation、可选视觉资产、首尾帧来源和最小运行时引用 |
| generation.shots | 每个 Camera Setup 的镜头边界、动作、人物、参考和状态 |

must_show 和 must_explain 事件必须有唯一的镜头落点；optional 事件可以在创作阶段删减。场景内文字要么写进已确认 H3 提示词，要么在故事板中明确标记确定性后期；台词字幕单独沿用逐字对白和执行包字幕策略，不要求生成模型烧录。导演决策复用已有 purpose、visible_proof、状态、运镜和 reason 等字段，不为审美判断增加 Schema 字段或静态评分。

## 编译顺序

1. 从原文建立 source.conflicts，先解决人物、版本、道具和结尾等歧义。
2. 列出观众必须获得的信息，给每个 coverage 事件写可见证据、before_state 和 after_state。
3. 先按因果链填写 scenes，再拆 panels 和 Camera Setup；Panel 边界写唯一的 transition ownership。
4. 根据真实首帧/尾帧和参考控制需要选择 operation，再选择 visual_asset_policy；分镜板不能反向决定 R2V。
5. 按镜头顺序填写对白、动作和状态。每个 Setup 只承担一个清晰主动作；先简化不必要的动作耦合，再按叙事理由拆 Setup 或 Panel，不把一个动作的表演发展机械拆成多个任务。
6. 运行一次预检；发现可逆的文档或输入错误时，在当前授权范围内按具体报错修正后复核一次：

~~~powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
~~~

只有 CREATIVE PREFLIGHT: PASS 才能进入角色卡、视觉资产和视频提示词阶段。失败时按具体报错修正文档并复核；没有新依据或缺关键事实时报告阻塞，不消耗视频生成资源，也不重复同一无效修复。

## 最小预检范围

预检只阻断会让执行包无法运行或破坏 Panel 接力的错误：

- JSON 结构、ID、顺序和跨区域引用完整。
- 每个 Panel 为 4–15 秒，目标总时长等于 Panel 时长之和。
- `must_show` / `must_explain` 事件都有唯一镜头落点，镜头有来源、证据和前后状态。
- 同场相邻 Panel 的状态链相接；换场有明确桥接，不能无解释跳转。
- 对白顺序、Setup 归属和已确认的文字策略可执行。
- 每个 Panel 恰好一条 `generation.panel_plans`；operation、首尾帧和引用槽位相互一致。
- I2VA 只有一个首帧，FL2VA 按首帧/尾帧顺序提供两个帧，T2VA 不带视觉参考；R2V 在创作阶段明确选择分镜板或有明确用途的普通参考素材，不能声明精确首尾帧。

预检不做最终视频评分，不计算对白关键路径、不要求形容词计数，也不生成候选片、恢复记录或独立锁文件。

## `generation.panel_plans`

每个 Panel 使用一个最小计划：

```json
{
  "panel_id": "P002",
  "operation": "video.image_to_video",
  "visual_asset_policy": "none",
  "storyboard_layout": null,
  "first_frame_source": "boundary.P001.last_frame",
  "last_frame_source": null,
  "runtime_input_keys": ["boundary.P001.last_frame"],
  "planning_only_asset_keys": [],
  "reason": "同场连续，使用上一 Panel 接受后的真实尾帧锁定起点。"
}
```

`operation` 只能是 `video.text_to_video`、`video.image_to_video`、`video.first_last_frame` 或 `video.reference_to_video`。`visual_asset_policy` 只能是 `none`、`storyboard_board`、`reference_assets`、`scene_keyframe` 或 `last_frame`。帧来源只能引用实际 asset key；`runtime_input_keys` 是当前 Panel 的最小引用集，不能混入只供审阅的规划资产。

`storyboard_board` 是 R2V 的分镜板策略，使用时必须在 STEP 1 写入规范的 `storyboard_layout: "rowsxcolumns"`，例如 `1x2`、`2x2` 或 `2x3`，且行数乘列数为 2–6；其他策略的该字段必须为 `null` 或省略。STEP 3 按此布局一次生成或复用一张 `storyboard_board.<panel>`，不能生成 `storyboard_frame.*` 独立格子，也不能在事后拼板。

`reference_assets` 用于已明确选择普通参考图的 R2V，例如开场构图图加人物正面角色图。每张图有独立用途并列入 `runtime_input_keys`，Setup引用的有序并集必须相同；不强制新增分镜板，不允许空引用或混入分镜板key。`first_frame_source`、`last_frame_source`、`storyboard_layout` 均为 `null`；开始画面只作为构图/状态参考，不承诺像素级首帧锁。包用明确的 `ref_image_N` fixed槽位，实际数量与能力仍由LFO检查。

`storyboard_board.<panel>` 在 `runtime_input_keys` 中只出现一次，并等于一个 H3 fixed image reference；同一 Panel 所有 Setup 需要使用它时，在各自 `reference_keys` 中复用同一 key。有明确且不可替代用途的声音或其他参考仍可加入，但生成分镜板时使用的角色卡、场景图和板内格子不会自动继续传给 H3。`generation.limits.reference_slots` 统计最终实际输入数，执行包 `validate` 仍负责确认后端能力。

### Panel ready

Panel 的自身事实、时长、operation、提示词输入、必要资产、采样参数、音频或对白要求、后期责任、输出位置和授权齐全后即可 ready。独立 Panel 可以先准备；只有依赖上一 Panel 的首尾状态时才等待上一段实际 `ACCEPT` 和真实尾帧。视频提交仍保持全局串行。

## 接力与执行包

项目级生成选择存入顶层 `user_constraints.megapixels`、`user_constraints.sampler_profile` 和 `user_constraints.steps`，与故事板一致。模式/步数的支持范围和一次选择规则见 [执行包格式](execution-package.md#项目级生成参数选择一次逐-panel-继承)。编译当前 Panel 时继承到 `generation.requirements`；适配器拒绝与项目模式或步数不同的 Panel 覆盖，不根据数字猜测模式，也不在执行时切换。故事规划可先于参数选择完成，但不能把尚未选择的值写成用户已批准。

视频提交保持全局串行；当前 Panel 只有在它实际依赖上一 Panel 时才等待上一 Panel 已 `ACCEPT`。下一 Panel 的 I2VA/FL2VA 计划需要时，调用方使用现有 ffmpeg 从已接受视频提取真实尾帧作为精确首帧。明确切镜或换场按已批准的 operation 和引用执行，不能用文字描述代替真实尾帧。

每个 Panel 编译一份只含一个 Clip 的独立 `execution-package.json`。每份包的锁值是该文件的精确文件字节 SHA-256，并通过运行时的 `--approved-sha256 <hash>` 传入；不再维护 prompt manifest 或独立 production lock。包内容变化都必须重新计算 hash，并核对现有授权是否覆盖；无覆盖时才需要新的明确授权。

## 输出

通过预检后，按本文件和故事板编译一次执行包。视频阶段只保留每个 Panel 的一次 `ACCEPT/REJECT` 结果和已接受媒体路径；执行单元必须查看实际文件，记录实际末态和实际音频证据，不能以技术成功或静态预检通过替代成片检查。`REJECT` 或执行错误即停止，是否重新开始由用户或调用方明确决定。片段接受、替换后的相邻接缝和实际交付文件的一次完整视听检查，统一遵守 [最小视频接受检查](video-qc.md)。
