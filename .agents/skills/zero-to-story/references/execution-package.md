# VideoExecutionPackage 交付格式

## 目录

- [公共边界](#公共边界)
- [最小示例](#最小示例)
- [参考图编号与槽位](#参考图编号与槽位)
- [Panel 与 Clip 规则](#panel-与-clip-规则)
- [验证与执行闸门](#验证与执行闸门)

## 公共边界

Skill 交付给 LFO 的唯一执行文件是 `execution-package.json`。使用 `lfo.video-execution.v1`，只写用户已经确认的创作信息。LFO 负责导入素材、计算哈希、分配内部版本、选择后端和运行工作流。

不要在执行包中写 SQLite ID、ComfyUI 节点、模型文件路径或猜测的内部素材 ID。

## 最小示例

以下示例表示：图片1为角色卡，图片2为 P001 的 2×3 六镜分镜板；提示词必须使用同一编号。

```json
{
  "schema": "lfo.video-execution.v1",
  "package_id": "project-revision-001",
  "revision": 1,
  "project": {"title": "项目名称", "locale": "zh-CN"},
  "assets": [
    {
      "asset_key": "character.hero",
      "media_type": "image",
      "source": {"uri": "characters/hero.png"},
      "provenance": {
        "source_type": "external_skill",
        "producer": "imagegen",
        "operation": "image.generate"
      },
      "review": {"required": true}
    },
    {
      "asset_key": "storyboard.p001",
      "media_type": "image",
      "source": {"uri": "panels/P001/board.png"},
      "provenance": {
        "source_type": "external_skill",
        "producer": "imagegen",
        "operation": "image.generate"
      },
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
        "prompt": "用户确认后的完整 H3 Panel 视频提示词（紧凑档 ≤ 900 中文字符，或成片档 1.5–3KB，按 video_prompt_list.md 用户确认版本原样填入）；其中图片1=角色卡，图片2=分镜板",
        "negative_prompt": "split screen, storyboard grid, monochrome line art, identity drift, prop duplication, random text",
        "requirements": {
          "aspect_ratio": "9:16",
          "width": 1080,
          "height": 1920,
          "fps": 24,
          "native_audio": "allowed"
        },
        "references": [
          {
            "reference_id": "picture-01-hero",
            "asset_key": "character.hero",
            "semantic_usage": "subject.identity",
            "instruction": "图片1：保持角色身份、发型、体型、服饰和关键道具一致",
            "binding": {
              "required": true,
              "priority": 100,
              "placement": "fixed",
              "slot": "ref_image_0",
              "on_unsupported": "fail"
            }
          },
          {
            "reference_id": "picture-02-p001-board",
            "asset_key": "storyboard.p001",
            "semantic_usage": "composition.motion.sequence",
            "instruction": "图片2：左上到右下对应 Shot 1-6；只参考六镜顺序、构图、空间、动作和切镜，不复制格线或线稿",
            "binding": {
              "required": true,
              "priority": 90,
              "placement": "fixed",
              "slot": "ref_image_1",
              "on_unsupported": "fail"
            }
          }
        ]
      },
      "audio": {"native_audio": "preserve"},
      "subtitles": {"cues": []},
      "source_context": {
        "creative_unit": "panel",
        "panel": "P001",
        "shot_range": [1, 6]
      }
    }
  ],
  "output": {
    "width": 1080,
    "height": 1920,
    "fps": 24,
    "subtitles_mode": "both"
  },
  "approval": {
    "approved_by": "user",
    "approved_at": "2026-08-11T00:00:00Z"
  }
}
```

## 参考图编号与槽位

- `ref_image_0` 对应提示词“图片1”，`ref_image_1` 对应“图片2”，依此类推。
- 对所有提示词中有编号的图片使用 `placement: "fixed"`，并写出 `slot`。不要混用 `any`/`last` 后再假设 JSON 数组顺序不变。
- 默认先放本 Panel 出场角色卡，再放当前 2×3 分镜板。只传需要身份锁定的出场角色，不把画外音角色或背景路人加入。
- H3 最多接收 9 张参考图。角色卡加分镜板超过 9 张时，先回到 Panel 设计减少需锁定角色或拆分，不静默丢弃必需引用。
- H3 参考图宽高比保持在 0.4–2.5；整板直出时就选择符合范围的图片模型原生画幅。超出范围时重新生成当前整板，不引入拆图或拼板流程。
- 若后续 revision 加入上一 Clip 的实际末帧，把它放到新的 `ref_image_0`，顺延并改写所有图片编号；重新确认提示词并运行 `validate`/`plan`。
- `semantic_usage` 和 `instruction` 说明素材用途，但 H3 真正观察到的是槽位顺序；必须以 `lfo plan` 的 `resolved_references` 为最终核对依据。

## Panel 与 Clip 规则

- `1 Panel = 1 张 2×3 分镜板 = 6 个镜头 = 1 Clip`。
- P001 的 `source_context.shot_range` 为 `[1, 6]`；P002 为 `[6, 11]`；后续同理。重叠镜头是连续性承接。
- 每个 Clip 的提示词必须是 `video_prompt_list.md` 中用户确认的完整文本，不做摘要、翻译或散文化改写。提示词支持两档（紧凑档 ≤ 900 中文字符 / 成片档 1.5–3KB），均由用户确认后原样填入 `generation.prompt`；LFO 不做长度调整或档位判断。
- 默认 `duration_ms: 10000`。H3 工作流会把时长对齐到 `17k+5 @ 24fps` 的帧网格，10 秒请求约为 10.1 秒；不要手工写帧数。
- 自定义单段时长保持 4–15 秒。所有 Clip 请求时长之和等于用户确认的目标时长。
- `dependencies` 只控制执行顺序，不会自动把上一 Clip 末帧传给下一 Clip。首轮批量连续性依靠重叠分镜和提示词末态；实际末帧只能在生成后作为新 revision 素材加入。
- 每个 Clip 是可独立重做的最小执行单位。修改一个 Panel 时只提升 revision 并重做受影响 Clip，不覆盖已批准文件。
- 生成式画面中的手机、招牌和屏幕保持空白或抽象；可读文字/UI 使用确定性素材或后期叠加。
- 字幕 cue 的 `start_ms`/`end_ms` 是当前 Clip 本地时间，从 0 开始，`end_ms <= duration_ms` 且 `end_ms > start_ms`。
- `output.subtitles_mode` 可为 `sidecar`、`burnin` 或 `both`。
- 可选 `seed` 用于最佳努力复现；可选 `reference_image_size` 为 `match` 或 `max`。

## 验证与执行闸门

先运行：

```powershell
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
```

逐 Clip 核对：

- Clip 数 = Panel 数 = 2×3 分镜板数。
- 每个 `source.uri` 指向实际存在且已获用户确认的文件。
- 每个提示词图片编号与 `resolved_references` 的槽位、asset key、角色/分镜用途一致。
- 时长与项目规格一致，提示词完整覆盖当前分镜六格动作链；字幕 cue 未越界。
- `negative_prompt` 不与正向提示词矛盾。
- 后端为预期 H3 路径，没有素材数、画幅或能力警告。

任何错误、警告或顺序变化都先修正并重新验证。只有 `validate`、`plan` 通过且用户确认计划摘要后，才能运行：

```powershell
python -m lfo.cli.main execute execution-package.json --approve
```
