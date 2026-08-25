# VideoExecutionPackage 交付格式

## 目录

- [公共边界](#公共边界)
- [外部提示词边界](#外部提示词边界)
- [最小示例](#最小示例)
- [Panel 与 Clip](#panel-与-clip)
- [参考素材与槽位](#参考素材与槽位)
- [验证与执行闸门](#验证与执行闸门)

## 公共边界

Skill 交付给 LFO 的唯一执行文件是 `execution-package.json`，契约为 `lfo.video-execution.v1`。只写用户已经确认的创作信息；LFO 负责导入素材、计算哈希、选择后端、运行工作流、标准化、QC 和导出。

不要在执行包中写 SQLite ID、ComfyUI 节点、模型文件路径、内部素材 ID、绝对输出路径或任何 Skill 的推理过程。

`project.project_id` 是 LFO 的稳定项目目录键，只能是一个安全路径组件。LFO 将中间产物写入 `workspace/projects/<project_id>/outputs/<run_id>/`，最终文件写入 `workspace/projects/<project_id>/final/<output.directory>/`；`output.directory` 只是发布目录名。

生成画布只写 `generation.requirements.aspect_ratio` 和 `megapixels`。`output.width/height` 是交付分辨率，不要再写进 generation。

## 外部提示词边界

`zero-to-story` 不生成视频提示词。执行包中的 `generation.prompt` 是一个不透明的外部输入，只能逐字复制由 `$h3-prompt-writing` 生成、已经展示给用户且明确获批的最终输出。

- 不在复制前后添加标题、解释、前缀、后缀、Markdown 代码围栏或负向词块。
- 不创建 `video_prompt_list.md`、提示词档位、复杂度分值、执行节拍数或 PromptControlPlan。
- 不在 `source_context` 伪造提示词分析结果。
- 不写 `generation.negative_prompt`。若确需改变视频提示词，带更新后的 Panel 输入重新调用 `$h3-prompt-writing`，再提升 package revision。
- H3 模式、正式字段、引用标签、镜头时间和对白语法均以 `$h3-prompt-writing` 的输出为准；本文档不维护第二份规则。

## 最小示例

以下示例只展示透传边界。`generation.prompt` 的占位内容在真实 Package 中必须替换为 `$h3-prompt-writing` 的完整已确认输出。

```json
{
  "schema": "lfo.video-execution.v1",
  "package_id": "project-p001-r001",
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
        "prompt": "[逐字复制 h3-prompt-writing 的完整已确认输出]",
        "requirements": {"aspect_ratio": "9:16", "megapixels": 0.4, "fps": 24, "native_audio": "allowed"},
        "references": [
          {
            "reference_id": "hero-reference",
            "asset_key": "character.hero",
            "semantic_usage": "subject.identity",
            "binding": {"required": true, "priority": 100, "placement": "fixed", "slot": "ref_image_0", "on_unsupported": "fail"}
          },
          {
            "reference_id": "p001-board-reference",
            "asset_key": "storyboard.p001",
            "semantic_usage": "composition.motion.sequence",
            "binding": {"required": true, "priority": 90, "placement": "fixed", "slot": "ref_image_1", "on_unsupported": "fail"}
          }
        ]
      },
      "audio": {"native_audio": "preserve"},
      "subtitles": {"cues": []},
      "source_context": {
        "creative_skill": "zero-to-story",
        "prompt_skill": "h3-prompt-writing",
        "creative_unit": "panel",
        "panel": "P001",
        "shot_range": [1, 6]
      }
    }
  ],
  "output": {"width": 1080, "height": 1920, "fps": 24, "subtitles_mode": "both"},
  "approval": {"approved_by": "user", "approved_at": "2026-08-13T00:00:00Z"}
}
```

## Panel 与 Clip

- `1 Panel = 1 张 2×3 分镜板 = 6 个有序 Shot = 1 Clip`。
- P001 的 `shot_range` 为 `[1, 6]`；P002 为 `[6, 11]`；重叠 Shot 是连续性承接。
- 默认 `duration_ms: 10000`。自定义单段时长保持 4–15 秒，Clip 时长之和等于用户确认总时长。
- `dependencies` 只表达执行顺序，不会自动把上一 Clip 末帧传给下一 Clip；真实末帧必须作为新 revision 的明确素材引用。
- 每个 Clip 是可独立重做的最小执行单位。修改已批准的故事、素材、时长、引用或外部提示词时提升 revision，保留旧产物。
- 字幕 cue 的 `start_ms` / `end_ms` 是当前 Clip 本地时间，从 0 开始，`end_ms <= duration_ms` 且 `end_ms > start_ms`。

## 参考素材与槽位

- 每个引用使用 `placement: "fixed"` 和明确 `binding.slot`，不要依赖隐式数组顺序。
- Package 中图片、视频和音频的实际顺序、语义用途，必须与交给 `$h3-prompt-writing` 的输入顺序以及最终输出中的引用标签完全一致。
- 只传当前 Panel 真正需要的已确认素材，不静默丢弃必需引用，也不加入未交给 `$h3-prompt-writing` 的额外素材。
- 新增上一 Clip 的真实末帧后，重新确定全部素材顺序，把完整新输入再次交给 `$h3-prompt-writing`，提升 revision；禁止只修改 Package 槽位而沿用旧提示词。
- 以 `lfo plan` 的 `resolved_references` 为最终执行核对依据。

## 验证与执行闸门

先运行：

```powershell
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
```

逐 Clip 核对：

- Clip 数 = Panel 数 = 2×3 分镜板数；每个 Panel 六个 Shot ID 仍可追溯。
- 每个 `source.uri` 指向实际存在且已获用户确认的文件。
- `generation.prompt` 与 `$h3-prompt-writing` 的已确认输出逐字一致。
- 素材顺序、槽位、asset key、语义用途、H3 引用标签和 `resolved_references` 一致。
- 时长满足 4–15 秒，字幕 cue 未越界，后端与引用能力无警告。
- 不存在非空 `generation.negative_prompt`，也没有本 Skill 添加的提示词字段或元数据。

任何执行包结构、素材顺序、时长或外部提示词变化都先提升 revision，并重新运行 `validate`、`plan`。只有两者通过且用户确认计划摘要后，才能执行。
