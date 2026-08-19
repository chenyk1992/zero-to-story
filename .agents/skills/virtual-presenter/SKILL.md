---
name: virtual-presenter
description: 规划自然、可信的数字人口播与虚拟实拍连续镜头，包含角色、360°环境、口语化文案、声音参考、H3 提示词和 LFO 执行包。用户说“口播”“数字人口播”“虚拟实拍口播”或“virtual presenter”，或要求把角色、环境和演讲文案做成连续口播视频时使用。
---

# 虚拟实拍口播

把一次口播当作可审阅、可恢复的拍摄计划，而不是一条孤立提示词。唯一中枢是项目中的 `presenter_plan.md`：所有输入、环境视图、文案、Shot Contract、H3 提示词、首片基线、QC 和 LFO handoff 都写回这一份文件。

## 边界与启动

- 只负责口播的创作规划、资产绑定、用户确认和执行包；不写 LFO 数据库、ComfyUI 节点、内部素材 ID 或平台缓存。
- 先读取现有 `presenter_plan.md`、角色/声音/环境素材和上一轮 QC；从第一个 `待确认` 或 `需重审` 阶段继续。用户修改上游字段时，受影响阶段及下游全部回到 `需重审`。
- 首轮把角色、目标受众、语言、声音参考、两个目标画幅（若只需一个则明确记录）、总时长、口播目的、情绪和环境来源整理成输入规格，请用户确认“方向”和“区域/站位”。沉默、素材存在或模型返回不算确认。
- 360°环境来源应先运行 `scripts/build_environment_pack.py`，并把 `manifest.json` 和四张方向视图登记到计划；没有可用 `ffprobe`/`ffmpeg` 或 equirectangular 比例不合格时暂停，不猜测空间。
- 项目只写入 `workspace/projects/<project_id>/`：`presenter_plan.md` 是唯一状态中枢，原始素材保真副本放 `inputs/`，环境派生物放 `environment-pack/`，逐 Shot 历史包和组装包放 `packages/`，语义 QC 放 `qc/`，当前待执行包固定为 `execution-package.json`。不要在 `workspace/` 根部创建临时目录。

## 固定工作流

首次创建计划时复制 [presenter_plan 模板](assets/presenter_plan.template.md)，只维护一个 `presenter_plan.md`。每阶段完成后展示本阶段摘要，并在计划里记录确认依据。

1. **输入规格**：明确角色锚点、声音、环境、区域/站位、两个画幅、目标时长和发布限制；确认方向和区域后再往下走。
2. **环境 Pack**：检查 2:1 equirectangular；登记 yaw `0/90/180/-90`、pitch `0`、FOV `90°` 的四张 `1024×1024` 视图、contact sheet 和 manifest。所有方向名称及相机朝向写入 Shot Contract。
3. **口语化文案**：把书面稿改成可说的话；一段只承载一个信息意图，记录停顿、重音、发音和声音尾音，按画面时长复核而不是静默加速。
4. **Shot Plan**：每段严格 `4–15 秒`，一个段落一个明确动作/信息转折，给每段分配三级动作预算（L0 静态、L1 轻微交流、L2 单一复杂意图），并写清起止姿态、镜头、区域、连续性和引用槽位。呼吸、眨眼、轻微视线与重心变化是所有等级的自然底层；每片最多 1–2 次语言强调动作、最多一种主运镜，整条计划只在一个已选 Shot 安排一次小范围语义走位。需要详细字段时读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)。
5. **H3 提示词 / LFO 计划**：按 [H3 Presenter Prompt](references/h3-presenter-prompt.md) 生成每段的最终提示词，按 [LFO handoff](references/lfo-handoff.md) 调用适配器。每个包都先 `validate`、再 `plan`；计划未获用户明确确认不得执行。
6. **首片基线**：完整计划确认后，每个目标画幅只生成第一段。分别展示并请求用户确认两个画幅的首片；任一画幅未确认，不生成其余段。把确认版的身份、光线、镜头速度、声音和表演强度写为 baseline。
7. **剩余生成**：两个目标画幅的首片都明确确认后，按 Shot Plan 顺序自动推进；`ref_video_0` 只传上一条已接受片。后续片默认只继承该视频的配对音轨；只有 Scene D 对比证明“上一片视频 + 独立声音参考”的声音评分不下降且连续性不降低，才为该 Shot 设置 `include_voice_reference: true` 并同时传 `ref_audio_0`。每片自动 QC。语义失败最多重做 2 次，仍失败就暂停并请求决策，不无限重试。按 [QC rubric](references/qc-rubric.md) 记录结果。
8. **最终组装**：所有段及两种画幅均通过 QC（或用户明确接受 REVIEW）后，调用 `build_assembly_package`，让最终视频使用 `video.passthrough`；再次 `validate`、`plan`。若没有改变已确认计划或首片 baseline，则沿用自动推进授权完成组装；需要改变方案时才暂停请求确认。

## 不可变引用槽位

对每个 shot 固定使用以下语义，不因缺少某项而把其他素材前移：

| 槽位 | 含义 |
|---|---|
| `ref_image_0` | 角色图/身份锚点；提示词写 `<Picture 1>` |
| `ref_image_1` | 360°环境全景或环境 Pack 的全景源；提示词写 `<Picture 2>` |
| `ref_image_2` | 当前方向视图（yaw/pitch/FOV 已登记）；提示词写 `<Picture 3>` |
| `ref_audio_0` | 声音参考；提示词写 `<Audio 1>` |
| `ref_video_0` | 上一条已接受片；提示词写 `<Video 1>`；首片没有时省略 |

槽位编号从 0 开始，H3 提示词标签从 1 开始；不得混写或把 contact sheet 当作方向视图。每次改动提示词、引用、时长、画幅或连续性都提升 revision，并重新 `validate`、`plan`；实质改变已确认方案时才重新请求确认。

## 运行与暂停规则

- 每次向适配器提交前重新读取最新 `presenter_plan.md`，确认直接上游状态为 `已确认`。适配器返回的 package 是唯一交付给 LFO 的边界。
- `build_shot_package` 和 `build_assembly_package` 只负责构建包；不要绕过它们直接访问 ComfyUI。完整计划确认授权两个画幅的首片；两个首片确认后授权未改变方案的剩余生成、QC 与组装。任何超出该范围的修改都暂停并重新请求授权。
- MiMo 可用时用于语义和连续性 QC；不可用、超时或结果无法解析时仅重试一次，仍不可用就暂停并保留可恢复状态。不要把解析失败默认为通过。
- 读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)、[H3 Presenter Prompt](references/h3-presenter-prompt.md)、[QC rubric](references/qc-rubric.md)、[LFO handoff](references/lfo-handoff.md) 只在对应阶段需要时进行，避免重复复制规则。

## 交付前检查

确认 `presenter_plan.md` 中每段为 `4–15 秒`、动作预算未超载、两个首片确认记录齐全、引用槽位未漂移、每片重做次数不超过 2、QC 结果可追溯，且 package 已分别 `validate`/`plan`。最终组装只使用 `video.passthrough`，并且没有越过已记录的自动推进授权范围。




