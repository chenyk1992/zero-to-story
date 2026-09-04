---
name: virtual-presenter
description: 规划自然、可信的数字人口播与虚拟实拍连续镜头，包含角色、360°环境、口语化文案、声音参考、H3 提示词和 LFO 执行包。用户说“口播”“数字人口播”“虚拟实拍口播”或“virtual presenter”，或要求把角色、环境和演讲文案做成连续口播视频时使用。
---

# 虚拟实拍口播

把口播拆成可审阅的 Shot/Panel 规划。项目中的 `presenter_plan.md` 是创作侧唯一中枢；执行侧遵循“一次一个 Panel、一个 Panel 一个 Clip”的公共流程。

## 边界与启动

- 只负责口播的创作规划、资产绑定、用户确认和执行包；不写 LFO 数据库、ComfyUI 节点、内部素材 ID 或平台缓存。
- 先读取现有 `presenter_plan.md`、角色/声音/环境素材和已接受片的结果；从第一个 `待确认` 或 `需重审` 阶段继续。用户修改上游字段时，受影响阶段及下游回到 `需重审`。
- 首轮整理角色、目标受众、语言、声音参考、目标画幅、总时长、口播目的、情绪和环境来源，请用户确认方向与区域/站位。没有明确确认时不进入生成。
- 360°环境来源应先运行 `scripts/build_environment_pack.py`，并把 `manifest.json` 和四张方向视图登记到计划；没有可用 `ffprobe`/`ffmpeg` 或 equirectangular 比例不合格时暂停，不猜测空间。
- 一次交付选择一个目标画幅。确需另一画幅时，按同一规则另行建立完整的 Panel 执行序列；不同画幅不共用 `ref_video_0`，也不把两个画幅塞进同一生成包。
- 项目只写入 `workspace/projects/<project_id>/`。每个 Panel 包和最终 assembly 包都直接位于该项目根目录，使用唯一文件名（如 `panel-P001.execution-package.json`、`assembly.execution-package.json`），不要为每个包建立子目录；`presenter_plan.md` 与创作素材只能放在项目内已经存在、用途明确且能被 package-relative URI 引用的位置。不要自行新建 `inputs/`、`environment-pack/`、`packages/`、独立 `qc/`、失败候选、恢复日志或 workspace 根部临时目录。

## 固定工作流

首次创建计划时复制 [presenter_plan 模板](assets/presenter_plan.template.md)，只维护一个 `presenter_plan.md`。每阶段完成后展示本阶段摘要，并在计划里记录确认依据。

1. **输入规格**：明确角色锚点、声音、环境、区域/站位、一个目标画幅、目标时长和发布限制；确认方向和区域后再往下走。
2. **环境 Pack**：检查 2:1 equirectangular；登记 yaw `0/90/180/-90`、pitch `0`、FOV `90°` 的四张 `1024×1024` 视图、contact sheet 和 manifest。所有方向名称及相机朝向写入 Shot Contract。
3. **口语化文案**：把书面稿改成可说的话；一段只承载一个信息意图，记录停顿、重音、发音和声音尾音，按画面时长复核而不是静默加速。
4. **Shot Plan**：每段严格 `4–15 秒`，一个段落一个明确动作/信息转折，给每段分配三级动作预算（L0 静态、L1 轻微交流、L2 单一复杂意图），并写清起止姿态、镜头、区域、连续性和引用槽位。呼吸、眨眼、轻微视线与重心变化是所有等级的自然底层；每片最多 1–2 次语言强调动作、最多一种主运镜，整条计划只在一个已选 Shot 安排一次小范围语义走位。需要详细字段时读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)。
5. **H3 提示词与执行包**：按 [H3 Presenter Prompt](references/h3-presenter-prompt.md) 生成每段最终提示词，按 [LFO handoff](references/lfo-handoff.md) 调用适配器。每个 Shot/Panel 构建一份只含当前 Clip 的执行包；逐包 `validate`，计算并记录完整文件字节 SHA-256，`plan` 仅在需要查看诊断信息时使用。
6. **逐 Panel 执行**：每个 Panel 是一个独立的短生命周期执行单元，严格按顺序串行运行。执行器同步调用官方 ComfyUI `comfy-cli`，等待当前 Clip 完成后返回结果；不并行，也不传入与当前 Panel 无关的历史。
7. **最小 ACCEPT/REJECT**：调用方只检查输出可播放、没有明显生成错误、且在有前序片时开头能接上上一片末态；QC 决策只有 `ACCEPT` 或 `REJECT`，校验或执行失败记为 `ERROR`。下一条 Presenter Panel 使用当前完整 `ACCEPT` 视频作为 `ref_video_0` 普通连续性参考；只有其他下游 operation 明确需要精确首帧时，才从实际输出提取真实末帧并绑定。任何 `ERROR` 或 `REJECT` 立即停止，不自动重试、不保留失败候选、不写复杂恢复记录。
8. **最终组装**：全部 Panel `ACCEPT` 后调用 `build_assembly_package`，只使用已接受 Clip 和 `video.passthrough`；组装包独立 `validate`、独立计算完整文件字节 SHA-256，再 `execute --approved-sha256` 一次。只做最终文件可播放、顺序和基本音视频存在检查。

## 不可变引用槽位

对每个 Shot/Panel 固定使用以下语义，不因缺少某项而把其他素材前移：

| 槽位 | 含义 |
|---|---|
| `ref_image_0` | 角色图/身份锚点；提示词写 `<Picture 1>` |
| `ref_image_1` | 360°环境全景或环境 Pack 的全景源；提示词写 `<Picture 2>` |
| `ref_image_2` | 当前方向视图（yaw/pitch/FOV 已登记）；提示词写 `<Picture 3>` |
| `ref_audio_0` | 声音参考；提示词写 `<Audio 1>` |
| `ref_video_0` | 上一条已接受片；提示词写 `<Video 1>`；首片没有时省略 |

槽位编号从 0 开始，H3 提示词标签从 1 开始；不得混写或把 contact sheet 当作方向视图。上一条失败或被拒绝的输出不能成为下一 Panel 的引用。`ref_video_0` 指上一条完整 ACCEPT 视频的普通连续性参考，不等于精确首帧尾帧锁；若确需精确首帧，必须由上游改选可消费真实尾帧的 I2V/FL2V operation。每个执行包只表达当前 Panel；跨 Panel 接力由调用方根据已接受的真实输出保持。

## 运行与暂停规则（当前 breaking 协议）

- 每次构建包前重新读取最新 `presenter_plan.md`，确认直接上游状态为 `已确认`。适配器返回的 package 是交给 LFO 的唯一边界。
- `build_shot_package` 和 `build_assembly_package` 只负责构建包；不要绕过它们直接访问 ComfyUI。Panel 包和 assembly 包都必须独立 `validate` 和 hash 核对；`plan` 不属于必经链路。
- 每个 Panel 的执行输入只保留 `panel_id`、package 路径、批准 hash、可选的上一条完整 `ACCEPT` 视频 URI 和输出位置。执行器负责同步等待 CLI，调用方负责最小 QC 与 ACCEPT/REJECT；校验或执行失败记为 ERROR。
- ComfyUI、素材、hash、最小 QC 或组装任一失败即停止。需要重做时，由调用方明确创建/确认新的当前 Panel 执行包并重新取得 hash；不在 Skill 内自动重试、修改提示词或维护恢复状态。
- 读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)、[H3 Presenter Prompt](references/h3-presenter-prompt.md)、[QC rubric](references/qc-rubric.md)、[LFO handoff](references/lfo-handoff.md) 只在对应阶段需要时进行，避免把重复规则塞入单次执行输入。

## 交付前检查

确认 `presenter_plan.md` 中每段为 `4–15 秒`、动作预算未超载、引用槽位未漂移、当前 Panel 已明确批准且 package 已 `validate`/hash；每个 ACCEPT 都有实际输出路径，只有下游明确需要精确首帧时才登记真实末帧。最终组装只使用 `video.passthrough`，并独立 `validate`/hash/execute 一次。不要维护重做次数、PASS/REVIEW 分级或复杂 QC 报告。




