# H3 视频提示词清单 — [项目标题]

> 每个 Panel 复制一节。规则和档位判定以 `references/h3-prompts.md` 为准。
> 正文按 §4 档位落入 base 3 段或 full-reference 6 段；不再使用旧的"控制源 / 创作意图 / 时间过程 / 音频 / 关键负向"五段结构。

## P001｜[标题]

- duration: 10.0s
- tier: concise / structured / precise
- prompt format: base-3 | full-reference-6
- complexity score: [0+]
- execution beats: [3–6]
- reference mapping:
  - 图片1 / 首帧 / 末帧 → ref_image_0（[用途：属性参考 / first-frame 锁定 / last-frame 锁定]）
  - 图片2 → ref_image_1（[用途]）
  - 图片N → ref_image_(N-1)（[用途]）

### 最终提示词

> 按所选档位格式书写：
>
> **base 3 段**（精简 / 结构化档）：
> ```text
> integrated_multimodal_description: [Shot 1] ...
> [Shot 2] At SS.SSS, the camera cuts to ...
> （关键负向：不要 …；不要 …）
>
> overall_soundscape: ...
>
> non_diegetic_music: N/A
> ```
>
> **full-reference 6 段**（精确档，或满足 §4 升级条件）：
> ```text
> subject_definitions:
>   <Subject 1>: ...（attribute reference from Picture 1）
>   <Subject 2>: ...（attribute reference from Picture 2）
>
> summary: [reference generation] <one-sentence core scene>
>
> retention_analysis:
>   <Subject 1>: fully_preserved
>   <Subject 2>: fully_preserved
>
> detailed_description: [Shot 1] ...
> [Shot 2] At SS.SSS, the camera cuts to ...
> （关键负向：不要 …；不要 …）
>
> overall_soundscape: ...
>
> non_diegetic_music: N/A
> ```

[只写交给视频生成后端的最终正文。不复制评分、推理、节拍时长表或文件路径。]

### 审批记录

- 内容自检：[待审/已完成]
- 用户审批：[待确认/用户确认摘要]
