> GPT-6 适配变更说明：前置故事板、蓝图和执行包草案在用户已授权范围内可直接准备与定点修正；不要把这些可逆检查变成逐阶段确认门槛。生成错误、缺少或不匹配的精确文件字节 SHA-256 批准、hash 变化、REJECT 和 QC 失败仍是硬停止，不能盲目重试。

# VideoExecutionPackage 交付格式

## 公共边界

Skill 为每个 Panel 交付一份独立的 `execution-package.json`，契约为 `lfo.video-execution.v1`；每份包只包含一个 Clip。它只包含用户已经确认的创作信息、素材引用和生成参数；LFO 负责导入当前素材、选择后端、同步生成当前 Clip 并做最小技术检查。全部 Panel 接受后，调用方另行提交纯 `video.passthrough` 包完成一次最终组装。

所有 Panel 包和 assembly 包都直接放在同一个 `workspace/projects/<project_id>/` 项目根目录，使用唯一文件名（如 `panel-P001.execution-package.json`、`panel-P002.execution-package.json`、`assembly.execution-package.json`），不要为每个包建立子目录。包内相对 `source.uri` 因而可以直接引用同一项目的 `outputs/<run_id>/...` 下的已接受视频或真实尾帧；命令按实际文件名传入 package 路径。

不要在执行包中写 SQLite ID、ComfyUI 节点、模型文件路径、内部素材 ID、绝对输出路径或 Skill 的推理过程。素材使用包内相对 URI，`project.project_id` 使用稳定且安全的项目键。每个 Panel 包必须有独立 `package_id`；未显式提供时 zero-to-story 适配器使用 `<project_id>-<panel_id>`，避免多个 Panel 共用同一 `(package_id, revision)`。

`generation.requirements` 只写已确认的画幅、像素预算、FPS 和音频要求；`output` 写最终交付分辨率、FPS、字幕策略和目录名。像素预算必须来自用户明确选择，不能从输出尺寸或外部服务档位推导。

## 外部提示词边界

`generation.operation` 必须与故事板和蓝图中已确认的当前 Panel 计划一致。执行包阶段不根据参考数量临时换模式，也不补写或重排 H3 镜头。

`generation.prompt` 是由 `$h3-prompt-writing` 按当前创作授权定稿的单 Panel 完整输出，只能逐字复制；随最终执行包一起接受精确 hash 批准，不另加一次提示词审批：

- 不添加标题、解释、前缀、后缀、Markdown 围栏或负向词块。
- 不写 `generation.negative_prompt`，不增加 PromptControlPlan、提示词分级、复杂度分值或执行节拍数。
- H3 字段、引用标签、镜头时间和对白语法以 `$h3-prompt-writing` 输出为准；本文件不维护第二份提示词规则。
- 若提示词或创作事实改变，重新读取最新规格并生成执行包；若包字节改变，重新取得该包精确文件字节 SHA-256 批准；不能在运行时静默修补。

## 最小示例

下面示例只展示一个 Panel 包的公共边界；`megapixels` 代表用户已明确选择的值。真实包中的 `generation.prompt` 必须替换为当前 Panel 的完整已确认 H3 输出。其他 Panel 使用各自独立的包。

```json
{
  "schema": "lfo.video-execution.v1",
  "package_id": "project-p001",
  "revision": 1,
  "project": {"project_id": "my-project", "title": "项目名称", "locale": "zh-CN"},
  "assets": [
    {
      "asset_key": "storyboard_board.P001",
      "media_type": "image",
      "source": {"uri": "panels/P001/storyboard_board.png"},
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
            "reference_id": "storyboard-board",
            "asset_key": "storyboard_board.P001",
            "semantic_usage": "storyboard.consistency_grid",
            "binding": {"required": true, "priority": 100, "placement": "fixed", "slot": "ref_image_0", "on_unsupported": "fail"}
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
        "beat_range": [1, 6],
        "setup_range": [1, 3]
      }
    }
  ],
  "output": {"width": 1080, "height": 1920, "fps": 24, "subtitles_mode": "both", "directory": "final"}
}
```

`approval` 可以记录用户、时间和审批说明；真正的执行锁不是包内另一个对象，而是批准后当前 Panel `execution-package.json` 的精确文件字节 SHA-256。

## Panel 与 Clip

- `1 Panel = 6 个有序语义 Beat = 1 Clip`；实际 H3 `[Shot N]` 数量由 Camera Setup 决定。六个 Beat 不等于固定六格；R2V 在 STEP 1 选择 2–6 格的 `storyboard_layout`，STEP 3 一次生成一张自包含分镜板。
- P001 的 `beat_range` 为 `[1, 6]`；P002 起 Beat 1 是上一段的零时长边界锚点，其余五个 Beat 是当前 Panel 的新内容。共享边界动作只能归前一个或后一个 Panel。
- 当前包只有一个 Clip，其时长为当前 Panel 的 4–15 秒；全片总时长只在故事板/蓝图中由所有 Panel 时长求和确认，Beat 1 零时长锚点不额外占用当前 Clip 时长。
- Panel 包不承载全片 `dependencies`。主流程负责按 P001、P002……串行启动；上一段 ACCEPT 后，调用方用现有 ffmpeg 从已接受视频提取真实尾帧，写入项目 Run 输出目录，再由下一 Panel 包用相对 `source.uri` 注册这一个确切 PNG，并声明为 `first_frame` 来源。下一包必须重新 `validate`，并且只有在该包当前完整文件字节的 hash 已有可验证批准后才能交给 `execute`；批准已存在且包未变更时不重复请求。缺少批准、hash 变化或不匹配就停止。不能把提取目标路径当作 LFO 运行参数，也不能用文字或虚构路径替代实际文件。调用方可以把提取目标作为自己的执行单元辅助参数，但它不进入 package 或 LFO CLI。
- 当前最终组装只使用 `cut`。`match-cut` 是故事板中的创作关系，不新增输出转场类型。
- 运行阶段把每个 Panel 作为独立的短生命周期执行单元，严格按 P001、P002……串行；每个 Panel 只做一次 ACCEPT/REJECT。REJECT 或错误立即停止，不自动重试、不保留失败候选、不写恢复记录。

## 参考素材与槽位

- R2V 引用使用 `placement: "fixed"` 和 `ref_image_N`、`ref_video_N` 或 `ref_audio_N` typed slot；I2VA/FL2VA 则分别使用 `placement: "first"` / `"last"` 和明确的 `first_frame` / `last_frame` 绑定。
- I2VA 只使用一个精确首帧；FL2VA 按首帧、尾帧顺序使用两个精确帧；T2VA 不使用视觉引用；R2V 只把普通参考图用于身份、构图、风格或多参考控制，不能声称它是视频首帧锁。
- 只传当前 Panel 已确认的最小素材集，不静默丢弃必需引用，也不加入未交给 `$h3-prompt-writing` 的素材。R2V 的 `storyboard_board.<panel>` 是一张图片，只占一个 typed fixed slot，并与一个 H3 `<Picture N>` 映射；板内格子不会成为独立 asset、slot 或额外图片引用。
- 生成分镜板时使用的角色卡、场景图或连续性锚点只作为上游合成输入，不自动重复传入视频模型。确有分镜板无法承载的声音或其他不可替代参考时，才在故事板中写明独立用途并加入执行包。
- 真实尾帧作为下一 Panel 首帧后，若 H3 提示词需要引用标签变化，回到 `$h3-prompt-writing` 重新生成该 Panel 的完整提示词；不能只改槽位却沿用不匹配的文字。
- 任何 Panel 只保留当前已接受媒体和必要尾帧。不要生成 prompt manifest、生产锁、候选片或恢复侧车。

## 验证与执行

每个 Panel 在提交视频前都做一次最小预检；预检通过后只使用该包当前完整文件字节的已批准 hash：

```powershell
python -m lfo.cli.main validate <panel-execution-package.json>
```

预检确认当前 Panel 包可读、素材存在、引用与 operation 匹配、时长/画幅完整且只含一个 Clip。通过时返回值中的 `package_sha256` 就是该包的精确文件字节 SHA-256；将它交给批准通道，执行时作为 `--approved-sha256` 传入；批准已存在且包未变更时不重复确认。每个 Panel 独立重复这一步。

运行时使用批准哈希作为唯一锁：

```powershell
python -m lfo.cli.main execute <panel-execution-package.json> --approved-sha256 <hash>
```

`plan` 不是必经步骤，只在需要时作为诊断；它不承担批准或锁定职责。任何包字节变化都使批准失效，必须重新取得批准并重新计算 SHA-256。不创建 prompt manifest 或其他锁文件；执行器不负责猜测或兼容旧包格式。

### 执行后的最小检查

LFO 返回技术执行结果后，由调用方按 [最小视频接受检查](video-qc.md) 完成当前实际片段的身份、动作因果、声音、片段后期和相邻衔接判断；技术成功不直接等于 ACCEPT。检查标准只在该参考文档维护，不增加执行包字段或运行时导演逻辑。

ACCEPT 后才按下游需要提取真实尾帧并进入下一 Panel。替换片段时核对相邻接缝和后段实际使用的首帧引用；包有变化仍须重新批准其精确文件 SHA-256。全部 Panel ACCEPT 后组装，调用方按同一参考文档对字幕及后期完成后的实际交付文件做一次完整视听检查。
