> **GPT-6 适配变更说明**  复用当前指令或已有计划中的创作授权，不为同一方案重复确认。只在关键事实、真实素材/授权或执行包完整文件 hash 缺失时暂停；单 Panel、串行、失败即停和不盲目重试规则继续由根 `AGENTS.md` 统一约束。

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

在构建执行包前，由当前指令或已确定的创作方案显式选择 `generation_operation`。参考数量只用于核对，不用于自动推断 operation：

| 已确认意图 | H3/执行包路由 |
|---|---|
| 无视觉参考 | T2V：`video.text_to_video` |
| 单张图片被明确批准为精确首帧 | I2V：`video.image_to_video`，绑定 `placement="first"` |
| 两张图片被明确批准为精确首帧和尾帧 | FL2V：`video.first_last_frame` |
| 普通身份/构图/风格参考，或视频参考 | R2V：`video.reference_to_video`，使用类型匹配的 fixed slot |

每个视觉参考都要写清 `semantic_usage`、保真要求、与 Clip 的 binding、review 状态和 provenance。产品图由 Skill 生成时同样如此；生成产品图不等于已经生成最终动画。外部口播音频通过 audio track 绑定到 Clip，不伪装成视觉 reference。

## 3. 执行包组装

方案确定后调用 `lfo.skill_adapter.mg_voiceover.build_package(..., generation_operation="已确定的 operation")`：

- 默认一个连续生成 Clip，Clip 时长覆盖整条 MG 动画；不要把时间线段落误建成多个生成 Clip。生成结果 `ACCEPT` 后必须再由 `lfo.skill_adapter.mg_voiceover.build_assembly_package` 构建一个单 Clip passthrough 组装包，用于落实最终音频和输出策略。
- `pixel_ratio` 只写到 `GenerationRequirements.megapixels`；未指定时保持空值，不推断默认像素预算。例如用户明确选择 `0.4` 时写成 `megapixels: 0.4`；同时需要 `1080x1920` 时把它放在 `OutputPolicy`，不要再向 generation requirements 写 width/height。
- 有外部口播音频时在生成包中登记音频 asset/track，并由最终 passthrough assembly 实际替换音频；无外部口播时 assembly 保留 H3 原生音频。音频来源必须在提示词和包中一致。
- 普通字幕默认 `subtitles_mode: "none"`。MG 动态字、UI 标签、标题和数据标签不是字幕。
- 记录当前指令或已有计划的创作授权；方案未确定前不调用 adapter，不把未确定包交给运行时。包已构建后仍须 `validate` 并取得该完整文件字节 hash 的明确批准。

## 4. LFO CLI 交付顺序

每个 Panel 包和最终 assembly 包都直接写入 `workspace/projects/<project_id>/` 项目根目录，并使用唯一文件名（如 `panel-P001.execution-package.json`、`assembly.execution-package.json`）；不要为每个 Panel 建子目录，否则 `outputs/<run_id>/...` 无法用包内相对 URI 稳定引用。每个 Panel 都是独立执行包，调用方先运行 `validate`，使用其返回的完整文件字节 `package_sha256`；若同一未变更包尚无明确批准，则取得一次精确 hash 批准，随后使用实际 CLI：

```text
python -m lfo.cli.main validate panel-P001.execution-package.json
python -m lfo.cli.main execute panel-P001.execution-package.json --approved-sha256 <PACKAGE_SHA256>
```

当前 Panel 必须按 `validate → 核对/取得其 package_sha256 批准 → execute --approved-sha256` 严格串行执行；包内容变化后必须重新 `validate` 和批准。`plan` 仅为可选诊断，不是生产必经步骤。`execute` 同步调用官方 `comfy-cli`，等待完成并返回生成文件路径。调用方对返回 Clip 做最小语义判断，输出 `ACCEPT` 或 `REJECT`；REJECT 或任一执行失败即停止，需要重做时显式生成/确认新的执行包。泛化的生成请求不代替尚不存在包的 hash 批准。

`status`、`retry`、`review`、`export` 不属于本 Skill 的生产交接协议。真实末帧只在下一 Panel 的批准 `operation` 需要精确首帧时从已接受的实际输出提取并绑定；R2V 可按已确定的连续性计划使用完整 `ACCEPT` 视频作为普通参考，不把普通参考冒充精确首帧；T2V/硬切无需尾帧。全部 Panel 接受后调用 `build_assembly_package(generation_package, accepted_clip_uri, ...)`，对返回的单 Clip `video.passthrough` package 独立执行 `validate`、hash 批准和一次 `execute`，应用最终口播音频和输出策略。不要把执行拆成额外的审批、监控或恢复步骤。
