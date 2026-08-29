# Panel 跨段连续性与影视生产完整实施计划

## 1. 目标

本方案解决的不是单个视频的“重复镜头”，而是所有 `1 Panel = 1 Clip` 影视生产中的跨段时间连续性问题。最终目标是：

- 上一 Panel 的真实尾帧与下一 Panel 的实际首帧形成可验证的电影连续性。
- 已经完成的动作、台词、黑场、定格或转场只在时间线上出现一次。
- 黑白分镜继续承担导演规划，但不再被误当成真实视频首帧或时间轴。
- H3 的 I2VA、FL2VA 与 Ref2VA/R2V 按真实能力选用，不把普通参考图冒充硬首帧锁。
- LFO 能执行裁切、硬切、匹配切、有限叠化、音频桥接和字幕重定时，而不是只能完整片段硬拼。
- 下一 Panel 只有通过“上一尾 2 秒 + 下一头 3 秒”的联合边界 QC，才允许成为后续接力源。
- 历史片段、失败版本、修复版本和真实尾帧全部可追溯，不覆盖用户资产。

## 2. 核心判断

自然过渡不等于所有边界都做叠化，也不等于所有下一首帧都必须与上一尾帧像素相同。

电影上应根据叙事关系选择：

1. **同一镜头继续运动**：上一真实尾帧必须成为下一视频的真实首帧，使用 I2VA。
2. **同场景切景别或切视点**：使用切动作、视线切或匹配切；下一首帧应是新的有效画面，不能再次表演上一动作。
3. **明确换场或换时空**：转场由剪辑层唯一持有，使用一次硬切、叠化或淡出淡入；不能在两个生成片段中各做一半。
4. **单镜连续且已有批准终帧**：使用 FL2VA，从真实首帧沿可见运动路径到批准终帧。

默认优先级：

```text
真实首帧连续 > 切动作/匹配切 > 普通硬切 > 短叠化 > 黑场
```

禁止用长叠化掩盖人物、道具或动作不连续。几何状态不一致时应裁切、换切点或重生成；只有色温/曝光轻微差异才允许短暂确定性过渡修复。

## 3. 新的端到端生产链

```text
故事与导演节拍
    ↓
唯一 Shot + Panel 边界计划（谁拥有这段时间）
    ↓
角色卡 + 2×3 黑白分镜板（规划锚点，不是播放时长）
    ↓
P001 H3 提示词与生成
    ↓
P001 单片 QC → 提取真实尾帧与尾部 2 秒
    ↓
判定 P001→P002 边界类型
    ├─ 同镜连续：真实尾帧直接作为 P002 I2VA first_frame
    ├─ 匹配/切动作：批准 P002 新首帧或用 R2V 直接进入新镜头
    └─ 换场：生成两侧正常画面，转场交给 LFO
    ↓
P002 H3 提示词与生成
    ↓
联合边界 QC：P001 尾 2 秒 + P002 头 3 秒
    ├─ PASS：接受 P002，提取 P002 真实尾帧，继续 P003
    ├─ PASS_WITH_REPAIR：裁切/颜色/音频/字幕修复后复核
    └─ FAIL：修改边界策略或 H3 模式，再生成 P002
    ↓
全部 Panel 通过
    ↓
带 source-in/source-out、转场和音频桥接的最终时间线
    ↓
全片视频理解 + 技术 QC + 音频/字幕 QC
    ↓
最终导出
```

## 4. 创作层：修正黑白分镜与时间语义

### 4.1 保留 2×3 六格，但拆开“视觉锚点”和“播放镜头”

继续遵守：

- `1 Panel = 1 张 2×3 六镜板 = 1 条生成 Clip`。
- P001 使用 S001–S006；P002 使用 S006–S011；后一 Panel 左上格复用上一 Panel 右下格。

新增硬规则：

- P002 起左上格是 `boundary_anchor`，只保存上一 Shot 的可见末态，播放时长为 0。
- 左上格不能出现“复现走近、复现起身、再次落笔、继续说完整上一句”等动作文本。
- 当前 Panel 的有效播放时间只由后五个新增 Shot 分配。
- H3 视频的第 0 帧可以使用该锚点，但新动作必须在第 2–6 帧内开始，不得保持 1–4 秒再继续。

故事板模板需要把现有“六镜时长合计等于 Panel 时长”改为：

```text
P001：六个新增 Shot 的时长合计 = Panel 独占屏幕时间。
P002+：五个新增 Shot 的时长合计 = Panel 独占屏幕时间；boundary_anchor = 0ms。
```

### 4.2 增加 Panel 边界计划表

在 `storyboard_brief.md` 增加：

| 字段 | 说明 |
| --- | --- |
| boundary_id | 如 `P001__P002` |
| continuity_mode | `same_take` / `cut_on_action` / `match_cut` / `hard_cut` / `scene_transition` |
| previous_owner | 上一段拥有的最后动作、台词或转场 |
| inherited_state | 人物、双手、道具、位置、朝向、灯光、轴线的真实末态 |
| first_new_shot | 下一段第一个新增 Shot ID |
| first_new_action | 下一段必须立即出现的新动作或新信息 |
| forbidden_replay | 不得重复的动作、对白、位移或停留 |
| planned_head_relation | `identical_frame` / `motion_match` / `composition_match` / `new_view` |
| edit_transition | `cut` / `dissolve` / `fade_black`，及其唯一所有者 |
| audio_bridge | `none` / `J-cut` / `L-cut` / `room-tone-crossfade` |
| boundary_qc | 当前边界的硬失败条件 |

示例：

```yaml
boundary_id: P001__P002
continuity_mode: same_take
previous_owner: P001 owns the complete cangue approach
inherited_state: 木枷已经停在苏轼肩前半步，差役双脚已停
first_new_shot: S007
first_new_action: 两名差役立即垂直抬枷至肩颈高度
forbidden_replay:
  - 差役再次从远处走近
  - 木枷先远离苏轼再靠近
  - 再次脱下官袍
planned_head_relation: identical_frame
edit_transition: cut
audio_bridge: room-tone-crossfade
```

### 4.3 黑白分镜板的职责

黑白分镜板继续用于：

- 镜头顺序、构图、轴线、景别、人物与道具状态。
- 下一板左上格目视承接上一板右下格。

但它不再承担：

- 像素级视频首帧。
- 精确色彩、材质和人物面部连续。
- 下一 Panel 的首镜播放时长。

分镜 Prompt 中的“左上格复现上一板右下格”应改为：

```text
左上格只画上一板右下格的静态锁定末态，作为零时长连续性锚点；
不新增动作、不表现动作再次发生；上中格开始才是当前 Panel 的第一个新增动作。
```

## 5. 生产层：建立“计划锚点—真实尾帧—实际首帧”三层资产

黑白板生成完成后，只得到 `planned_anchor`。实际生产中再增加：

1. `planned_anchor`：黑白分镜中的导演计划末态。
2. `resolved_tail_frame`：上一通过视频提取的真实尾帧 PNG，带源视频哈希和时间戳。
3. `actual_head_frame`：下一候选视频的真实第一帧。

对于切动作或匹配切，可增加：

4. `approved_head_keyframe`：生成前已批准的下一首帧，用于 I2VA；它不要求与上一尾帧相同，但必须满足轴线、视线、动作方向和道具状态。

所有真实帧与 QC 资产进入 `RunArtifactLayout`，例如：

```text
workspace/projects/<project_id>/outputs/<run_id>/clips/<clip_id>/
  head-frame.png
  tail-frame.png
  tail-2s.mp4

workspace/projects/<project_id>/outputs/<run_id>/global/boundaries/P001__P002/
  preview-5s.mp4
  contact-sheet-4fps.jpg
  metrics.json
  review.json
```

不手工复制到 CAS，不直接修改数据库；由 LFO 任务产生并记录 artifact。

## 6. H3 模式选择与提示词规则

### 6.1 模式矩阵

| 边界类型 | 下一首帧 | H3 operation | 适用方式 |
| --- | --- | --- | --- |
| `same_take` | 上一真实尾帧，必须是 frame 0 | `video.image_to_video` | I2VA；人物和关键道具已在尾帧中 |
| `cut_on_action` | 批准的新机位首帧，或 R2V 直接新镜头 | 优先 I2VA；多参考不可缺时 R2V | 硬切发生在动作峰值，不回放动作起点 |
| `match_cut` | 构图/手势/形状匹配的新首帧 | I2VA 或 R2V | 编辑上是硬切，语义上保持动作与构图关系 |
| `hard_cut` | 完全新的有效画面 | `video.reference_to_video` | 第 0 秒直接提供新信息；上一尾帧不是首帧锁 |
| `scene_transition` | 新场景正常首帧 | I2VA 或 R2V | 叠化/淡黑由 LFO 后期执行一次 |
| 单镜首尾锁定 | 上一尾帧 + 批准终帧 | `video.first_last_frame` | FL2VA；优先单镜连续路径，不承载频繁六切 |

### 6.2 I2VA 强制规则

- 上一真实尾帧使用 `placement: "first"`、`slot: "first_frame"`。
- H3 提示词必须使用 I2VA 的正式首帧对齐指令。
- 不写 `reproduce Picture 1 exactly for 1.5 seconds`。
- 第一句动作应描述第 0 帧以后发生什么；第 0.083–0.250 秒应看到新运动趋势。
- 对可测状态写单调约束，例如：
  - 木枷与肩膀距离只能缩小，不能先增大。
  - 起身人物的头部高度只能上升，不能回到坐姿。
  - 囚车沿道路纵深只能继续变小。
  - 笔尖已触纸时不得再次从高处下降。
- 上一段对白由上一段拥有。下一段只允许其尾音作为明确 L-cut，不重新发音完整词句。

### 6.3 R2V 强制规则

- `ref_image_N` 只能称为参考素材，不能称为“硬首帧锁”。
- 若下一段需要多角色卡和整板参考而必须使用 R2V，边界应设计为新的切镜，而非伪装成同一镜头连续。
- `[Shot 1]` 从 0.000 秒直接进入第一个新增 Shot，不分配时间重建上一末态。
- 上一尾帧可以提供角色、道具或轴线参考，但不得要求模型再次表演上一动作。

### 6.4 FL2VA 强制规则

- 第一张图片必须绑定 `first_frame`，第二张绑定 `last_frame`。
- 只用于一条连续运动路径或极少切镜。
- 如果 Panel 需要多角色身份参考、复杂场景参考和多次切镜，不为了“首尾都锁”强行选择 FL2VA。

### 6.5 后端能力必须按 operation 校验

当前 H3 能力被聚合声明为可接收多种媒体和最多 15 个引用，但实际：

- FL2VA/I2VA 工作流只消费 `first_frame` / `last_frame`，不消费普通参考图。
- R2V 消费多参考图/视频/音频，但没有硬首尾帧输入。

实施时需要增加 operation-specific constraints：

```yaml
video.image_to_video:
  required_slots: [first_frame]
  allowed_placements: [first]
  ordinary_reference_images: false

video.first_last_frame:
  required_slots: [first_frame, last_frame]
  allowed_placements: [first, last]
  ordinary_reference_images: false

video.reference_to_video:
  allowed_slots: [ref_image_N, ref_video_N, ref_audio_N]
  hard_first_frame: false
  hard_last_frame: false
```

若 `semantic_usage=continuity.exact_previous_last_frame` 却绑定到 R2V 的 `ref_image_0`，`validate/plan` 必须报错，不再允许带着误导性“exact lock”执行。

## 7. LFO 公共契约与时间线修改

### 7.1 使用已存在但尚未真正执行的 `timeline` 字段

为 `lfo.video-execution.v1` 增加向后兼容的可选 typed timeline：

```json
{
  "timeline": {
    "version": "lfo.timeline.v1",
    "segments": [
      {
        "clip_id": "panel-001",
        "source_in_ms": 0,
        "source_out_ms": 12271
      },
      {
        "clip_id": "panel-002",
        "source_in_ms": 1420,
        "source_out_ms": 15104
      }
    ],
    "boundaries": [
      {
        "from_clip_id": "panel-001",
        "to_clip_id": "panel-002",
        "edit": "cut",
        "duration_ms": 0,
        "audio": {
          "mode": "room_tone_crossfade",
          "duration_ms": 160
        }
      }
    ]
  }
}
```

`source_in_ms/source_out_ms` 属于最终剪辑包，不要求在生成前猜测。生成包只描述源 Clip；所有 Panel 通过后，导演根据真实帧创建新的 assembly revision。

### 7.2 时间线运行时

扩展 `ClipSegment`：

- `source_in_ms`
- `source_out_ms`
- `transition_in`
- `transition_duration_ms`
- `audio_transition`

FFmpeg 实施：

- 有裁切时对视频使用 `trim,setpts`，音频使用 `atrim,asetpts`。
- 普通切、切动作和匹配切在媒体层均为 `cut`，不额外叠化。
- 场景转换才使用 `xfade`；声音用独立的 `acrossfade` 或 J/L-cut。
- 只有无裁切、无转场且编码完全兼容时才能走 concat stream-copy 快路径。
- 时间线总长根据实际裁切后时长和转场重叠计算，不能继续相加原始 Clip 时长。

### 7.3 字幕与音频

- 字幕全局时间应使用真实 timeline layout：`global = segment_start + local - source_in`。
- 被 head trim 完全裁掉的字幕 cue 删除；跨裁切点的 cue 必须裁短或重新审核。
- J/L-cut 的对白只保留一个音频所有者，不能把两个生成片段中的同一句同时混入。
- 环境底噪允许 80–250ms 等功率交叉淡化，避免房间声在画面硬切处突然断裂。
- 最终检查对白重复、音量跳变、音画同步和字幕同步。

### 7.4 物化、哈希与失效

- typed timeline 必须进入 `MaterializedRun` 和 materialization hash。
- 改变 `source_in/source_out`、转场或音频桥接时，只重建 timeline、字幕和 export，不重生成已通过的 Panel。
- 改变 P(n) 的尾帧时，失效 P(n)→P(n+1) 边界审查、P(n+1) 的首帧依赖和其后接力链；P001…P(n-1) 不失效。
- 继续保留历史 run、修复源和最终采用版本。

## 8. 跨边界 QC 体系

### 8.1 两阶段视频理解

每个边界使用：

1. 视频理解模型只做客观描述：人物、道具、位置、动作顺序、台词和转场。
2. 导演代理按 `boundary_contract` 判分，不让模型自行决定 PASS/FAIL。

如果视频理解接口返回空内容、截断或错误：

- 自动生成 4 fps 接触表；高运动边界提高到 8–12 fps。
- 结合首尾帧、黑场/定格检测、音频波形或 ASR 继续审查。
- 模型失败不得静默记为 PASS。

### 8.2 自动证据

LFO 只生成技术证据，不理解故事语义：

- 尾帧与首帧的 SSIM/pHash/亮度差。
- 边界前后黑场和静帧持续时间。
- 片段真实时长、帧率、关键帧和音轨信息。
- 重复音频指纹/ASR 文本候选。
- 5 秒边界预览与 4 fps 接触表。

故事动作是否倒带、人物是否回到更早状态，由上游导演代理结合故事板判断。

### 8.3 分类型通过条件

**same_take**：

- 下一实际首帧与上一尾帧高度一致；建议归一化后 SSIM ≥ 0.98，或经目视确认仅有编码差异。
- 动作方向不反转，关键道具状态不回退。
- 0.4 秒内出现新运动或新信息。
- 不重复完整台词。

**cut_on_action / match_cut**：

- 运动方向、轴线、视线、手部和道具归属成立。
- 切后直接显示动作的下一阶段或新的反应，不回到动作起点。
- 不以短叠化掩盖几何错误。

**hard_cut / scene_transition**：

- 新首帧立即建立新信息。
- 转场只有一个所有者，时长与故事板一致。
- 两段共同持有的黑场或定格为 0；需要长黑场时也只由一侧或剪辑层完整持有。

### 8.4 通用硬失败

- 完成动作明显回退后再次执行。
- 同一句可辨对白跨边界完整出现两次。
- 未登记的静态重复超过 0.8 秒。
- 同一黑场/定格由两边重复持有。
- 下一段错误地改变人物身份、人数、道具所有者或动作方向。
- I2VA 第一帧未真正使用批准的 `first_frame`。
- R2V 被错误标记为精确首帧锁。

## 9. 修复与重试策略

按成本和观感从低到高：

1. **选切点**：从下一片段找到第一个真正的新动作，设置 `source_in_ms`。
2. **音频/字幕重定时**：删除重复尾音、平滑环境声、同步字幕。
3. **颜色与曝光修复**：仅修正小幅色温或亮度跳变。
4. **改边界类型**：同镜连续失败时，改为专业的切动作或匹配切。
5. **改 H3 模式**：R2V 伪连续失败时改 I2VA；复杂多参考不适合 I2VA 时改成明确硬切。
6. **重生成下一 Panel**：只重做发生问题的后一段。
7. **重构 Panel 节拍**：两次同根因失败后，将完整动作归给一侧或重新拆分 4–15 秒 Panel。

禁止只换 seed 反复碰运气，也禁止用长黑场/长叠化掩盖失败。

## 10. 代码与文档实施包

### WP1：创作契约和 Skill

修改：

- `.agents/skills/zero-to-story/SKILL.md`
- `.agents/skills/zero-to-story/references/storyboard-brief.md`
- `.agents/skills/zero-to-story/references/creative-assets.md`
- `.agents/skills/zero-to-story/references/execution-package.md`
- `.agents/skills/zero-to-story/references/video-qc.md`
- `.agents/skills/zero-to-story/assets/storyboard_brief.template.md`
- `.agents/skills/zero-to-story/assets/storyboard_board_prompt.template.md`
- `.agents/skills/h3-prompt-writing/SKILL.md`

完成条件：模板不再出现有时长的“复现上一动作”；边界表、模式矩阵、零时长锚点和联合 QC 成为强制流程。

### WP2：公共契约与验证

修改：

- `src/lfo/contracts/timeline.py`
- `src/lfo/contracts/package.py`
- `src/lfo/contracts/builder.py`
- `src/lfo/contracts/schemas/video-execution-v1.schema.json`
- `src/lfo/contracts/validation.py`
- `src/lfo/skill_adapter/zero_to_story.py`
- 对应 `tests/contracts/`、`tests/skill_adapter/`

完成条件：timeline 可 round-trip、可校验、进入哈希；错误的 operation/placement/slot 组合在 plan 前失败。

### WP3：H3 operation-specific capability

修改：

- `src/lfo/backends/capabilities.py`
- `src/lfo/backends/selector.py`
- `src/lfo/backends/comfy_h3.py`
- H3 capability/manifest 文件
- `tests/backends/test_comfy_h3.py`
- `tests/execution/test_materializer.py`

完成条件：I2VA/FL2VA 不再静默忽略额外普通参考；R2V 不能被声明为硬首帧；本地 H3 单段上限按实际 15 秒校验。

### WP4：尾帧、边界证据与时间线

新增或修改：

- 帧提取媒体模块与任务 handler。
- `src/lfo/execution/dag.py`
- `src/lfo/media/timeline.py`
- `src/lfo/media/handlers.py`
- `src/lfo/media/subtitles.py`
- 对应 media、DAG 和真实 FFmpeg acceptance tests。

完成条件：生成 head/tail/boundary artifacts；支持 source trim、cut、有限 dissolve、音频桥接；字幕使用真实布局重定时。

### WP5：跨边界导演 QC

修改 Skill QC 流程并提供复用脚本，输出：

- 5 秒边界预览。
- 4 fps 接触表。
- 技术 metrics JSON。
- 两阶段视频理解描述和导演判定。

完成条件：未通过边界 QC 的下一 Panel 不能成为后续 tail source。

### WP6：迁移与回归

使用《一蓑烟雨》作为首个回归项目：

1. 先通过 `source_in_ms` 对现有 P002–P012 做 frame-accurate 去重剪辑。
2. 对裁切仍不能自然衔接的边界重生成，优先：
   - P001→P002：I2VA 真实首帧，木枷立即垂直抬升。
   - P002→P003：I2VA 继续冲势，或切到枪杆交叉的新镜头。
   - P006→P007：黑场只由时间线或一侧持有。
   - P010→P011：删除二次起身，优先握手到毛笔的匹配切。
   - P011→P012：从笔尖已经触纸后的新动作进入。
3. 新旧版制作全部 11 个边界的 A/B 预览。
4. 完整观看 9:16、0.4MP、100+ 秒最终片，复核音画和字幕。

## 11. 测试计划

### 单元测试

- 零时长 anchor 不进入 Panel 独占时长。
- I2VA 必须有且只有合法 first-frame binding。
- FL2VA 必须有 first/last，额外 required 普通参考会失败。
- R2V 遇到 `exact_previous_last_frame + fixed/ref_image_0` 会失败并给出修复提示。
- timeline segment trim、边界邻接、转场时长和源范围校验。
- materialization hash 随 trim/transition 变化。

### 媒体测试

- 使用色条、移动方块和测试音生成两个小视频。
- 验证 source-in/source-out 后首尾帧准确到 1 帧。
- 验证 cut 不重复帧，dissolve 只执行一次。
- 验证音频交叉淡化时长和最终总长。
- 验证字幕在裁切和转场后偏移正确。

### Live E2E

- Comfy H3 I2VA：上一尾帧确实进入 `first_frame` 节点。
- Comfy H3 R2V：多参考正常，但不声称精确首帧。
- P001→P002 小型连续动作案例无位移回退。
- 生成、技术 QC、边界 QC、修复、时间线和导出全链路可恢复。

## 12. 最终验收标准

系统上线必须同时满足：

- 所有边界都有明确 `continuity_mode`、首帧关系和时间所有者。
- P002 起共享左上格不占播放时长、不包含新动作。
- 每个实际 tail/head 均有路径、哈希和审查证据。
- 所有 I2VA/FL2VA/R2V 引用与工作流真实能力一致，没有静默忽略。
- 最终时间线支持 frame-accurate trim，字幕和音频随之重定时。
- 联合边界 QC 覆盖所有相邻 Panel；模型失败时不会自动放行。
- 回归成片不存在动作倒带、完整对白重复或双重黑场。
- 《一蓑烟雨》修复版仍保持 100+ 秒、9:16、0.4MP 与写实电影质感。
- 相关目标测试与全量测试通过；ComfyUI 改动完成 doctor/preflight 和 live E2E。

## 13. 推荐实施顺序

严格按以下顺序推进：

```text
WP1 创作契约
  → WP2 公共契约
  → WP3 H3 能力校验
  → WP4 时间线与边界资产
  → WP5 联合 QC
  → WP6 一蓑烟雨试点
  → 全量回归与正式启用
```

不应先批量重生成《一蓑烟雨》。先让时间语义、模式校验、裁切和边界 QC 成为系统能力，再用当前项目验证，才能保证后续其他影视生产不会复现同一问题。
