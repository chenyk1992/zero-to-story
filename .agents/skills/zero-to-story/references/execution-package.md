# VideoExecutionPackage 交付格式

## 目录

- [公共边界](#公共边界)
- [最小示例](#最小示例)
- [Panel、Clip 与三档提示词](#panelclip-与三档提示词)
- [参考图编号与槽位](#参考图编号与槽位)
- [负向控制边界](#负向控制边界)
- [验证与执行闸门](#验证与执行闸门)

## 公共边界

Skill 交付给 LFO 的唯一执行文件是 `execution-package.json`，契约为 `lfo.video-execution.v1`。只写用户已经确认的创作信息；LFO 负责导入素材、计算哈希、选择后端、运行工作流、标准化、QC 和导出。

不要在执行包中写 SQLite ID、ComfyUI 节点、模型文件路径、内部素材 ID、绝对输出路径或提示词推理过程。

`project.project_id` 是 LFO 的稳定项目目录键，只能是一个安全路径组件。LFO 将中间产物写入 `workspace/projects/<project_id>/outputs/<run_id>/`，最终文件写入 `workspace/projects/<project_id>/final/<output.directory>/`；`output.directory` 只是发布目录名。

H3 生成画布只写 `generation.requirements.aspect_ratio` 和 `megapixels`（默认竖屏 `9:16` / `0.4`，也可写 `16:9` / `0.6` 或 `16:9` / `1`）。`output.width/height` 是交付分辨率（例如 `1080x1920`），不要再写进 generation。

## 最小示例

以下示例表示：图片1为角色卡，图片2为 P001 的 2×3 六镜板。注意：最终提示词正文包含关键负向；不使用 `generation.negative_prompt`。

```json
{
  "schema": "lfo.video-execution.v1",
  "package_id": "project-revision-001",
  "revision": 1,
  "project": {"project_id": "my-project", "title": "项目名称", "locale": "zh-CN"},
  "assets": [
    {
      "asset_key": "character.hero",
      "media_type": "image",
      "source": {"uri": "characters/hero.png"},
      "provenance": {"source_type": "external_skill", "producer": "imagegen", "operation": "image.generate"},
      "review": {"required": true}
    },
    {
      "asset_key": "storyboard.p001",
      "media_type": "image",
      "source": {"uri": "panels/P001/board.png"},
      "provenance": {"source_type": "external_skill", "producer": "imagegen", "operation": "image.generate"},
      "review": {"required": true}
    }
  ],
  "clips": [
    {
      "clip_id": "panel-001",
      "sequence": 1,
      "duration_ms": 10000,
      "generation": {
        "operation": "video.reference_to_video",
        "prompt": "图片1仅锁定主角身份、服装与手中钥匙；图片2仅控制 P001 六格的构图、空间、动作顺序和节奏，不采用黑白线稿，不输出宫格、分割线或漫画页面。写实低饱和夜巷中，主角从画面左侧中景快步走到门前，短暂停顿后用右手举起钥匙，镜头由 wide shot 平稳 dolly in 到手部 close-up，结尾保持人物面向门、钥匙停在锁孔前。音频：近处脚步、衣料摩擦、远处风声；非叙事性音乐：N/A。关键负向：不要六宫格或分割线、不要黑白线稿或漫画页面、不要身份漂移、不要道具复制、不要可读文字。",
        "requirements": {"aspect_ratio": "9:16", "megapixels": 0.4, "fps": 24, "native_audio": "allowed"},
        "references": [
          {
            "reference_id": "picture-01-hero",
            "asset_key": "character.hero",
            "semantic_usage": "subject.identity",
            "instruction": "图片1：保持角色身份、发型、体型、服饰和关键道具一致",
            "binding": {"required": true, "priority": 100, "placement": "fixed", "slot": "ref_image_0", "on_unsupported": "fail"}
          },
          {
            "reference_id": "picture-02-p001-board",
            "asset_key": "storyboard.p001",
            "semantic_usage": "composition.motion.sequence",
            "instruction": "图片2：左上到右下对应六个 Shot；只参考构图、空间、动作和节奏",
            "binding": {"required": true, "priority": 90, "placement": "fixed", "slot": "ref_image_1", "on_unsupported": "fail"}
          }
        ]
      },
      "audio": {"native_audio": "preserve"},
      "subtitles": {"cues": []},
      "source_context": {
        "skill": "zero-to-story",
        "creative_unit": "panel",
        "panel": "P001",
        "shot_range": [1, 6],
        "prompt_tier": "structured",
        "complexity_score": 4,
        "execution_beat_count": 4
      }
    }
  ],
  "output": {"width": 1080, "height": 1920, "fps": 24, "subtitles_mode": "both"},
  "approval": {"approved_by": "user", "approved_at": "2026-08-13T00:00:00Z"}
}
```

## Panel、Clip 与三档提示词

- `1 Panel = 1 张 2×3 分镜板 = 6 个 Shot = 1 Clip`。H3 提示词可把相邻连续 Shot 合并成 3–6 个执行节拍，但 `source_context.shot_range` 和六个 Shot ID 不改变。
- P001 的 `shot_range` 为 `[1, 6]`；P002 为 `[6, 11]`；重叠 Shot 是连续性承接。
- `generation.prompt` 只复制 `video_prompt_list.md` 的“最终提示词”正文，不复制档位、score、执行节拍表、审批记录或 Markdown 标题。将 `prompt_tier`、`complexity_score`、`execution_beat_count` 放在 `source_context`，供执行计划审阅。
- 提示词档位由 H3 规范决定：0–2 精简 350–800 字符，3–5 结构化 700–1500 字符，6+ 精确 1200–3000 字符；任何档位硬上限 7000 字符。LFO 不替提示词选档或改写长度。
- 默认 `duration_ms: 10000`。工作流可能把时长对齐到帧网格；不要在执行包手工写帧数。自定义单段时长保持 4–15 秒，Clip 时长之和等于用户确认总时长。
- `dependencies` 只表达执行顺序，不会自动把上一 Clip 末帧传给下一 Clip；实际末帧必须作为新 revision 的明确引用。
- 每个 Clip 是可独立重做的最小执行单位。修改已批准内容时提升 revision，保留旧产物。
- 字幕 cue 的 `start_ms` / `end_ms` 是当前 Clip 本地时间，从 0 开始，`end_ms <= duration_ms` 且 `end_ms > start_ms`。

## 参考图编号与槽位

唯一映射为：`图片1 → ref_image_0`、`图片2 → ref_image_1`、`图片N → ref_image_(N-1)`。

- 每个有编号的引用使用 `placement: "fixed"` 和明确 `binding.slot`；不要混用 `any`/`last` 后假设 JSON 数组顺序。
- 默认先放本 Panel 出场角色卡，再放当前 2×3 分镜板；只传需锁定身份的角色。
- 最多 9 张图片参考；超过时回到 Panel 设计减少必需角色或拆分，不静默丢弃必需引用。
- 如果 revision 加入上一 Clip 的真实末帧，把它放到新的 `ref_image_0`，顺延全部引用，提升 revision，并重新运行 `validate`、`plan` 和用户确认。
- 以 `lfo plan` 的 `resolved_references` 为最终核对依据：它必须和提示词中图片编号、asset key、角色/分镜用途一致。

## 负向控制边界

当前本地 H3 ComfyUI backend 只把 generation 的 `prompt`、时长和输出前缀等已支持字段映射进工作流，不消费 `generation.negative_prompt`。这不是模型能力宣称，而是本地代码的可验证事实；来源和最后核验日期见 [h3-capabilities.md](h3-capabilities.md)。

因此：

- 关键负向必须写进 `generation.prompt` 主体，通常保留 3–5 条最可能失败的排除项。
- 不把 `negative_prompt` 当作有效控制字段；新包不得写非空 `generation.negative_prompt`。已有包发现该字段时移入主体，并提升 revision。
- 不为“支持负向”虚构 ComfyUI 节点、workflow 字段或 manifest 能力。
- 交付前人工检查非空 `negative_prompt`；即使主体已有负向，也必须删除该字段后再交付。

## 验证与执行闸门

先运行：

```powershell
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
```

逐 Clip 核对：

- Clip 数 = Panel 数 = 2×3 分镜板数；每个 Panel 六个 Shot ID 仍可追溯。
- 每个 `source.uri` 指向实际存在且已获用户确认的文件。
- 图片编号、槽位、asset key、用途和 `resolved_references` 一致，必需引用已声明。
- 时长满足 4–15 秒，提示词覆盖当前 Panel 动作链，动态时间与对白不越界。
- 关键负向位于 prompt 主体，不存在非空 `negative_prompt`。
- 字幕 cue 未越界，后端与引用能力无警告。

任何执行包结构、素材顺序或时长变化都先修正并重新运行 `validate`、`plan`。只有两者通过，且用户确认计划摘要后，才能运行：

```powershell
python -m lfo.cli.main execute execution-package.json --approve
```
