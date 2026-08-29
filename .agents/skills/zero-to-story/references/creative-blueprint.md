# 创作蓝图与低成本预检

## 目的

`storyboard_brief.md` 仍是故事、视觉和连续性的人工可读唯一源文件。`creative_blueprint.json` 是从它同步编译出的机器可读索引，不是第二套剧情，也不取代故事板；两者冲突时先修故事板，再重新编译蓝图。

蓝图只做一次低成本静态预检，不生成图片、视频或音频，也不新增用户审批节点。它把最容易在成片阶段暴露、且一旦暴露就会浪费生成资源的问题前移：原文冲突、剧情覆盖遗漏、场景因果断裂、状态跳变、对白顺序错误，以及单镜头超出模型可控范围。

## 最小字段

| 区域 | 必须回答的问题 |
|---|---|
| `source` | 当前采用哪一份原文？所有冲突是否已经写明选择并标记 `resolved`？ |
| `coverage` | 这一段故事哪些事件 `must_show` / `must_explain`？每件事的原文出处、可见证据、前态和后态是什么？ |
| `scenes` | 每场的目的、转折、入场状态、离场状态和下一场义务是什么？场景切换如何桥接？ |
| `panels` | 每个 Panel 的时长、场景、镜头集合、覆盖事件和前后状态是什么？相邻 Panel 的动作归属是谁？ |
| `dialogue` | 每句对白的说话人、逐字原文、全局顺序、事件和镜头是什么？ |
| `generation.shots` | 每个 Camera Setup 只承担什么主动作？有多少关键人物、参考图、运镜和对白？开始/结束状态如何接力？ |

`must_show` 与 `must_explain` 必须且只能映射到一个生成镜头；`optional` 可以被删减，但不能在蓝图里伪装成已完成。可读文字使用 `text_strategy: "post"` 并登记确定性后期资产，不把文字正确性押给视频模型。

## 编译顺序

1. 从原文或 handoff 建立 `source.conflicts`，先解决版本、人物关系、关键道具和结尾钩子等冲突。
2. 按观众必须获得的信息建立 `coverage`，给每个事件写出可见证据和状态变化；没有可见证据的事件不能进入视频生成。
3. 按完整因果链填写 `scenes`，再拆成 `panels` 和 Camera Setup。场景切换必须有 `bridge_from_previous`；Panel 切换必须声明唯一的 `transition_to_next.ownership` 和桥接理由。
4. 按镜头顺序填写对白和生成预算。单镜头默认只保留一个主动作、少量关键人物和有限参考槽位；复杂内容拆成新的 Setup 或 Panel，不让 H3 猜测隐含顺序。
5. 在任何角色卡、分镜板或视频生成前执行预检：

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
- 生成文字策略显式选择；需要文字时必须走确定性后期资产。

脚本会一次返回全部问题，方便在一个创作编辑周期内修完；它不是对最终视频逐帧打分的 QC，也不要求为了轻微偏差重复生成。
