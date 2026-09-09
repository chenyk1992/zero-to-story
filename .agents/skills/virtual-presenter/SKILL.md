---
name: virtual-presenter
description: 规划数字人或虚拟实拍的连续口播视频，处理角色、360° 环境、自然表演、文案、声音参考、H3 提示词和 LFO 包。用于明确的数字人口播、虚拟实拍口播或 virtual presenter 请求；纯 MG 动画、B-roll 副镜头和普通文案不触发本 Skill。
---

# 虚拟实拍口播

先遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。主会话负责角色、文案和创意决定；执行子代理使用用户在当前宿主配置的子代理模型与推理档位完成一个冻结 Panel 工作单元，不复制主会话设置或写死型号，不建立监控代理。

把口播拆成可审阅的 Shot/Panel 规划。项目中的 `presenter_plan.md` 是创作侧唯一中枢；执行侧遵循“一次一个 Panel、一个 Panel 一个 Clip”的公共流程。

画布任务按 [canvas-workspace](../canvas-workspace/SKILL.md) 交付固定输入和实际结果；不创建执行包或增加包 hash、assembly 包门槛。只有用户明确选择 LFO package CLI 时，才使用本 Skill 的包适配器和 hash 规则。两条入口共用当前 Panel 的创作事实、素材语义与内容验收要求。

## 阶段范围

- 用户只要求输入规格、口语化文案、Shot Plan、H3 提示词、执行包或某个 Panel 时，只完成该阶段及必要检查，不自动继续环境 Pack、视频生成或最终组装。
- 只有当前正在执行的阶段确实需要 360°空间方向/站位时，才准备 Environment Pack；没有该空间依赖时不为完整模板补做环境包。进入后续阶段时按同样条件决定，完整生成请求且依赖满足时才按后续步骤继续。

## 边界与启动

- 只负责口播的创作规划、资产绑定、必要的方案确认和执行交接；不写 LFO 数据库、ComfyUI 节点、内部素材 ID 或平台缓存。
- 按当前阶段需要读取本项目现有 `presenter_plan.md`、角色/声音/环境素材和已接受片的结果；续作时从用户要求范围内第一个 `待确认` 或 `需重审` 阶段继续。用户修改上游字段时，受影响阶段及下游回到 `需重审`。
- 首轮整理角色、目标受众、语言、声音参考、目标画幅、总时长、口播目的、情绪和环境来源。若当前指令或已有计划已确定方向与区域/站位，直接沿用；只有缺少会改变成品的关键输入时才询问，未决时不进入生成。
- 进入需要具体 360°空间方向/站位的 Shot Plan 或生成阶段时，才运行 `scripts/build_environment_pack.py`，并把 `manifest.json` 和四张方向视图登记到计划；当前阶段不需要该空间依赖时不运行。已进入该阶段但没有可用 `ffprobe`/`ffmpeg` 或 equirectangular 比例不合格时暂停受影响阶段，不猜测空间。
- 一次交付选择一个目标画幅。确需另一画幅时，按同一规则另行建立完整的 Panel 执行序列；不同画幅不共用 `ref_video_0`，也不把两个画幅塞进同一生成包。
- 创作计划与项目产物写入 `workspace/projects/<project_id>/`；画布自身的快照与请求由画布服务管理。使用 package CLI 时，每个 Panel 包和 assembly 包直接位于项目根目录，文件名唯一，素材使用包内相对 URI。不要重复创建独立 QC、失败候选或恢复日志，也不在 workspace 根部放临时文件。

## 固定工作流（完整交付或用户要求该阶段时）

完整交付或用户要求创建计划时，首次创建计划复制 [presenter_plan 模板](assets/presenter_plan.template.md)，只维护一个 `presenter_plan.md`。每阶段完成后展示本阶段摘要，并在计划里记录确认依据。

1. **输入规格**：明确角色锚点、声音、环境、区域/站位、一个目标画幅、目标时长和发布限制；复用当前指令或计划中的方向和区域，只有关键事实缺失时才停下来补问。
2. **环境 Pack**：检查 2:1 equirectangular；登记 yaw `0/90/180/-90`、pitch `0`、FOV `90°` 的四张 `1024×1024` 视图、contact sheet 和 manifest。所有方向名称及相机朝向写入 Shot Contract。
3. **口语化文案**：把书面稿改成可说的话；一段只承载一个信息意图，记录停顿、重音、发音和声音尾音，按画面时长复核而不是静默加速。
4. **Shot Plan**：每段严格 `4–15 秒`，一个段落一个明确动作/信息转折，给每段分配三级动作预算（L0 静态、L1 轻微交流、L2 单一复杂意图），并写清起止姿态、镜头、区域、连续性和引用槽位。呼吸、眨眼、轻微视线与重心变化是所有等级的自然底层；每片最多 1–2 次语言强调动作、最多一种主运镜，整条计划只在一个已选 Shot 安排一次小范围语义走位。需要详细字段时读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)。
5. **H3 提示词与执行输入**：按 [H3 Presenter Prompt](references/h3-presenter-prompt.md) 生成每段最终提示词。画布任务把当前 Panel 的提示词、素材、参数、音频/后期责任与验收要求交给 `canvas-workspace`，固定快照后领取。package CLI 任务才按 [LFO handoff](references/lfo-handoff.md) 构建单 Clip 包，逐包 `validate`，核对完整文件 SHA-256 的明确批准或适用持续授权。
6. **逐 Panel 执行**：每个 Panel 是一个独立的短生命周期执行单元；视频提交保持串行，独立 Panel 可以先准备。存在连续性依赖时才等待上一 Panel 的实际 `ACCEPT`。执行适配层提交一次，不传入与当前 Panel 无关的历史；画布请求未知时按原请求核对结果，不通过新包或再次提交绕过。
7. **最小接受判断**：执行单元查看实际输出，记录实际末态（位置、姿态、手势、手持物和动作完成状态）与实际音频证据（声音、对白、停顿、同步和可懂度；无音频时明确记录），再作出 `ACCEPT`、`REJECT` 或证据不足时的 `INCONCLUSIVE`。下一条 Presenter Panel 使用当前完整 `ACCEPT` 视频作为普通连续性参考；只有下游 operation 明确需要精确首帧时，才提取真实末帧并绑定。执行失败、`REJECT` 或 `INCONCLUSIVE` 都暂停受影响的接力；执行状态与内容判断分开记录，不自动重试。
8. **最终组装**：全部 Panel `ACCEPT` 后按所选入口处理已接受片段、音频和字幕。只有 package CLI 使用 `build_assembly_package` 的全 `video.passthrough` 包，独立 `validate`、核对 hash 授权并执行一次。两条入口都检查实际最终文件的可播放性、顺序、接缝、声音、字幕和同步。

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

## package CLI 的运行与暂停规则

- 每次构建包前重新读取最新 `presenter_plan.md`，确认直接上游状态为 `已确认`；该状态可以由当前指令或已有有效确认形成，不为相同内容重复追问。适配器返回的 package 是交给 LFO 的唯一边界。
- `build_shot_package` 和 `build_assembly_package` 只负责构建包；不要绕过它们直接访问 ComfyUI。Panel 包和 assembly 包都必须独立 `validate` 和 hash 核对；`plan` 不属于必经链路。
- 每个 Panel 的执行输入只保留 `panel_id`、package 路径、批准 hash、可选的上一条完整 `ACCEPT` 视频 URI 和输出位置。执行器负责同步等待 CLI；执行单元负责实际末态、实际音频证据与一次 ACCEPT/REJECT/INCONCLUSIVE；校验或执行失败记为 ERROR。
- ComfyUI、素材、hash、证据不足、最小 QC 或组装任一失败即停止。需要重做时，由调用方明确创建新的当前 Panel 执行包并重新核对授权；不在 Skill 内自动重试、修改提示词或维护恢复状态。包内容未变且已有有效 hash 批准时可复用，不把泛化的生成意图当作未来包的批准。
- 读取 [Presenter Plan 与 Shot Contract](references/presenter-plan-shot-contract.md)、[H3 Presenter Prompt](references/h3-presenter-prompt.md)、[QC rubric](references/qc-rubric.md)、[LFO handoff](references/lfo-handoff.md) 只在对应阶段需要时进行，避免把重复规则塞入单次执行输入。

## 交付前检查

对本轮实际执行的阶段做对应检查：输入规格、文案和 Shot Plan 检查字段与时长；H3 提示词检查槽位与空间依赖。画布核对当前快照、实际结果与回填；package CLI 才检查 `validate`、hash 和 assembly 包。只有 Panel 已执行才记录实际输出、内容验收和按需尾帧。不要为未执行阶段声称已完成检查，也不要维护重复的 QC 报告。


