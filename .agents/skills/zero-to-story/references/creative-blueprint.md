# 创作蓝图与低成本预检

## 目的

`storyboard_brief.md` 仍是故事、视觉和连续性的人工可读唯一源文件。`creative_blueprint.json` 是从它同步编译出的机器可读索引，不是第二套剧情，也不取代故事板；两者冲突时先修故事板，再重新编译蓝图。

蓝图只做一次低成本静态预检，不生成图片、视频或音频，也不新增用户审批节点。它把最容易在成片阶段暴露、且一旦暴露就会浪费生成资源的问题前移：原文冲突、剧情覆盖遗漏、场景因果断裂、状态跳变、对白顺序错误，以及单镜头超出模型可控范围。

新项目使用 `zero-to-story.creative-blueprint.v2`。v1 仍可读取以兼容历史项目，但只有 v2 的生产准备度通过并生成生产锁后，才进入严格 LFO 执行。

## 最小字段

| 区域 | 必须回答的问题 |
|---|---|
| `source` | 当前采用哪一份原文？所有冲突是否已经写明选择并标记 `resolved`？ |
| `coverage` | 这一段故事哪些事件 `must_show` / `must_explain`？每件事的原文出处、可见证据、前态和后态是什么？ |
| `scenes` | 每场的目的、转折、入场状态、离场状态和下一场义务是什么？场景切换如何桥接？ |
| `panels` | 每个 Panel 的时长、场景、镜头集合、覆盖事件和前后状态是什么？相邻 Panel 的动作归属是谁？ |
| `dialogue` | 每句对白的说话人、逐字原文、全局顺序、事件和镜头是什么？ |
| `generation.panel_plans`（v2） | 每个 Panel 使用什么 operation？STEP 3 是不生成图、生成六格板、场景关键帧还是目标尾帧？哪些素材真正进入视频模型？ |
| `generation.shots` | 每个 Camera Setup 只承担什么主动作？有多少关键人物、参考图、运镜和对白？开始/结束状态如何接力？ |
| `production`（v2） | 每个说话人是谁？对白和动作在什么时窗发生？头尾保护区与安全余量是否足够？ |

`must_show` 与 `must_explain` 必须且只能映射到一个生成镜头；`optional` 可以被删减，但不能在蓝图里伪装成已完成。无后期项目的可读文字使用 `text_strategy: "prompt"`，在已确认的 H3 提示词中逐字写明；只有明确具备确定性后期链路时才允许 `text_strategy: "post"`。

## 编译顺序

1. 从原文或 handoff 建立 `source.conflicts`，先解决版本、人物关系、关键道具和结尾钩子等冲突。
2. 按观众必须获得的信息建立 `coverage`，给每个事件写出可见证据和状态变化；没有可见证据的事件不能进入视频生成。
3. 按完整因果链填写 `scenes`，再拆成 `panels` 和 Camera Setup。场景切换必须有 `bridge_from_previous`；Panel 切换必须声明唯一的 `transition_to_next.ownership` 和桥接理由。
4. 先按每个 Panel 的精确首尾帧与多参考需求选择 operation，再填写 `generation.panel_plans`。不得根据分镜板是否已存在反向选择 R2V。
5. 按镜头顺序填写对白和生成预算。单镜头默认只保留一个主动作、少量关键人物和有限参考槽位；复杂内容拆成新的 Setup 或 Panel，不让 H3 猜测隐含顺序。
6. 在任何角色卡、视觉控制资产或视频生成前执行预检：

```powershell
python .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py creative_blueprint.json
```

只有 `CREATIVE PREFLIGHT: PASS` 才能进入下游生成。失败时回到 `storyboard_brief.md` 修复，然后同步蓝图；不消耗视频生成额度来验证一个本可静态发现的问题。

## 预检覆盖范围

- 目标总时长等于所有 Panel 时长之和，且每个 Panel 在 4–15 秒范围内。
- 场景、Panel、coverage、对白和 Camera Setup 的 ID/顺序连续且相互回指。
- 所有必需剧情事件都有唯一镜头落点；没有无来源、无证据或被重复覆盖的关键事件。
- 同场相邻 Panel、Setup 和 Beat 的 `after_state → before_state` 完全相等；换场必须有明确桥接，不允许无解释硬跳。
- 对白全局顺序唯一，并与事件和镜头一致；同一镜头内不回退顺序。
- 参考槽位、关键人物数、主动作数、运镜数和对白行数不超过预算。
- v2 中每个 Panel 恰好有一条 `generation.panel_plans`，顺序与 Panel 一致；运行时引用等于当前 Panel 各 Setup 参考的有序并集，且与仅规划资产不重叠。
- I2V 只接受一个精确首帧来源；FL2V 只按首帧、尾帧顺序接受两个来源；T2V 不接受视觉参考；`board.*` 只能出现在 R2V 的运行时引用中。
- 生成文字策略显式选择（`none` / `prompt` / `post`）；本项目若 `postproduction: "none"`，不得登记 `text_strategy: "post"`，需要出现的真实文字必须用 `prompt` 并在已确认的 H3 提示词中逐字写清，LFO 不负责补字或替换。

## v2 生产准备度闸门

### `generation.panel_plans` 字段

每个 Panel 的记录使用以下结构：

```json
{
  "panel_id": "P002",
  "operation": "video.image_to_video",
  "visual_asset_policy": "none",
  "first_frame_source": "boundary.P001.last_frame",
  "last_frame_source": null,
  "runtime_input_keys": ["boundary.P001.last_frame"],
  "planning_only_asset_keys": ["board.P002"],
  "reason": "同场连续，使用上一 Clip 通过版真实尾帧即可锁定起点。"
}
```

- `operation` 只能是 `video.text_to_video`、`video.image_to_video`、`video.first_last_frame` 或 `video.reference_to_video`。
- `visual_asset_policy` 只能是 `none`、`board`、`scene_keyframe` 或 `last_frame`，表示 STEP 3 需要物化的资产，不是 operation 别名。
- `first_frame_source` / `last_frame_source` 只填精确帧来源的 asset key；不适用时必须为 `null`。
- `runtime_input_keys` 是 Clip 级最小引用集，必须与该 Panel 的 Setup `reference_keys` 有序并集完全一致，并不超过 `generation.limits.reference_slots`。
- `planning_only_asset_keys` 用于保留既有分镜板或审阅资产；这些 key 不得同时出现在 `runtime_input_keys` 或 Setup `reference_keys` 中。
- `reason` 说明为什么该 operation 和资产策略是最小且充分的控制集；“已经有分镜板”不是有效理由。

`production.profile` 的默认目标是无后期、逐字对白：

- `speech_units_per_second` 与 `punctuation_pause_ms` 用于没有录音时的保守时长估算；已有配音则填写 `measured_duration_ms`。
- `head_guard_ms`、`tail_guard_ms` 为进出镜和尾帧接力保留安全空间；`turn_gap_ms` 防止相邻说话人抢拍。
- `safety_margin_ratio` 对对白、串行动作和必要停顿的关键路径整体加余量。
- `production.speakers` 为每个实际发声角色登记稳定 `id`、`character_id`、声线性别和年龄段。
- 每句 `dialogue` 增加 `speaker_id`、`planned_start_ms`、`planned_end_ms`、`allow_overlap`，每个 Setup 增加 `start_ms`、`end_ms` 和 `action_schedule`。校验器还会检查对白时窗是否容纳测量/估算时长、是否越过 Setup 保护区、是否出现未声明的说话人或动作。

关键路径计算为：

```text
required = (Σ对白时长 + Σ说话人间隔 + 串行主动作时长 + 并行动作最长时长)
           × (1 + safety_margin_ratio)
           + head_guard_ms + tail_guard_ms
```

`required > Setup 可用时长` 就在前置阶段失败。它是一次性规划错误，不应等 H3 或 LFO 生成后才发现；进入生产锁后不再回退重排。

脚本会一次返回全部问题，方便在一个创作编辑周期内修完；它不是对最终视频逐帧打分的 QC，也不要求为了轻微偏差重复生成。
