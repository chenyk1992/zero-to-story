# MG Skill 参考与执行路由

本文件是参考资料和 LFO 交付的轻量索引。只读取当前任务会影响决策的资料。

## 1. 创作资料路由

先读 `h3-mg-prompt-template.md`，再按语义选择：

| 当前需求 | 读取 |
|---|---|
| 所有 MG 口播任务 | `h3-mg-prompt-template.md` |
| 风格、版式、色彩、层级、信息密度 | `visual-style-layout-library.md` |
| 卡片、图标、线条、镜头、转场、桥接 | `element-motion-transition-library.md` |
| 标题、关键词、输入框、动态字形 | `kinetic-typography-motion-library.md` |
| 抽象概念、对比、分流、聚合、波形 | `mg-motion-pattern-library.md` |
| 数字、百分比、增长、排名、KPI、进度 | `data-visualization-motion-library.md` |

不存在的语义映射、桥接或 UI 专用资料不应被引用；用现有资料的语义映射和元素动效规则完成判断。历史 Seedance 资料仅在明确的兼容迁移需求下读取，不能替换当前 H3/LFO 流程。

## 2. 视觉参考路由

在构建执行包前统计视觉参考文件（图片或视频，不含口播音频）：

| 参考输入 | H3/执行包路由 |
|---|---|
| 0 个 | T2V：`video.text_to_video` |
| 1 个图片 | I2V：`video.image_to_video` |
| 1 个视频，或 2 个及以上视觉参考 | R2V：`video.reference_to_video` |

每个视觉参考都要写清 `semantic_usage`、保真要求、与 Clip 的 binding、review 状态和 provenance。产品图由 Skill 生成时同样如此；生成产品图不等于已经生成最终动画。外部口播音频通过 audio track 绑定到 Clip，不伪装成视觉 reference。

## 3. 执行包组装

确认后调用 `lfo.skill_adapter.mg_voiceover.build_package`：

- 默认一个连续 Clip，Clip 时长覆盖整条 MG 动画；不要把时间线段落误建成多个 Clip。
- `pixel_ratio` 只写到 `GenerationRequirements.megapixels`。例如 `0.4` 写成 `megapixels: 0.4`；同时需要 `1080x1920` 时把它放在 `OutputPolicy`，不要再向 generation requirements 写 width/height。
- 有外部口播音频时绑定音频 asset/track，并让输出使用外部音频；无外部口播时允许 H3 原生音频。音频来源必须在提示词和包中一致。
- 普通字幕默认 `subtitles_mode: "none"`。MG 动态字、UI 标签、标题和数据标签不是字幕。
- 记录用户确认信息；确认前不调用 adapter，不把未批准包交给运行时。

## 4. LFO CLI 交付顺序

执行包固定写入 `workspace/projects/<project_id>/execution-package.json`；创建项目前先按仓库 `workspace/README.md` 确认布局。随后使用实际 CLI：

```text
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
python -m lfo.cli.main execute execution-package.json --approve
python -m lfo.cli.main status RUN_ID
python -m lfo.cli.main retry RUN_ID
python -m lfo.cli.main export RUN_ID
```

通常顺序是 `validate -> plan -> execute --approve -> status -> export`；仅在失败且需要重试时使用 `retry`。`status`、`retry`、`export` 需要真实的 `RUN_ID`。

`preflight` 仅用于机器、后端和工作流检查；它不是执行包导入、审批或运行子命令。不要把这些动作拆成额外的 CLI 子命令，唯一的执行审批形式是上方的 `execute --approve`。
