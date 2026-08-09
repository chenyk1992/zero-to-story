# VideoExecutionPackage 交付格式

Skill 交付给 LFO 的唯一公共文件是 `execution-package.json`。使用 `lfo.video-execution.v1`，只写创作层已确认的信息。LFO 会导入素材、计算哈希、分配内部版本、选择后端和执行工作流。

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
      "source": {"uri": "assets/hero.png"},
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
      "duration_ms": 15000,
      "generation": {
        "operation": "video.reference_to_video",
        "prompt": "用户确认后的完整 Panel 视频提示词",
        "requirements": {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 24},
        "references": [
          {
            "reference_id": "hero-identity",
            "asset_key": "character.hero",
            "semantic_usage": "subject.identity",
            "instruction": "保持主体身份、服装和关键道具一致",
            "binding": {"required": true, "priority": 100, "placement": "any", "on_unsupported": "fail"}
          },
          {
            "reference_id": "panel-composition",
            "asset_key": "storyboard.panel-001",
            "semantic_usage": "composition.motion",
            "instruction": "只参考构图、动作链与运动，不采用线稿画风",
            "binding": {"required": true, "priority": 90, "placement": "last", "on_unsupported": "fail"}
          }
        ]
      },
      "audio": {"native_audio": "preserve"},
      "subtitles": {"cues": []}
    }
  ],
  "output": {"width": 1080, "height": 1920, "fps": 24, "subtitles_mode": "both"},
  "approval": {"approved_by": "user", "approved_at": "2026-08-09T00:00:00Z"}
}
```

规则：

- `asset_key` 在同一包内唯一，所有 reference/audio/subtitle 资产都必须已在 `assets` 中声明。
- `source.uri` 必须是实际存在、允许导入的本地素材路径；不要写内部数据库 ID、ComfyUI 路径或模型名。
- `semantic_usage` 是开放字符串，例如 `subject.identity`、`composition.motion`、`product.visual`；不要将角色、场景、产品类别写进 LFO 固定枚举。
- `binding` 明确必需性、优先级、槽位位置和不支持时行为，LFO 不从创作语义猜测。
- 每个 Clip 是可独立重新生成的最小单位，可依 `dependencies` 表达前后关系。
- 任何审批后修改均提升 `revision` 并重新运行 `validate` 和 `plan`。
