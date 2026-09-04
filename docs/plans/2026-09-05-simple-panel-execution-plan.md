# LFO 极简单 Panel 执行计划

**状态：当前实施基线**
**日期：2026-09-05**
**性质：breaking redesign，不兼容历史执行入口**

本文是当前 LFO 实施与文档的唯一执行计划。旧的运行时设计、恢复方案和分级 QC 方案不再作为实施依据；它们只保留文件名以避免历史链接失效，内容均应以本文为准。

## 1. 目标

LFO 只负责把上游创作 Skill 已确认的一个 Panel 可靠地生成成一个 Clip。调用方负责最小语义 QC、真实尾帧接力和在全部 Panel 完成后的最终组装。

- 创作 Skill 负责故事、分镜、角色/场景素材、H3 提示词和用户确认。
- LFO 负责执行包校验、素材读取、后端选择和同步调用 ComfyUI；不在 `execute` 中伪造 `ACCEPT` 或自动提取尾帧。
- 一次生成执行只处理一个 Panel/Clip；全部 Panel 接受后，另用一份全 `video.passthrough` 的组装包做一次最终组装。组装包可以只有一个 Clip。
- 调用方把每个 Panel 作为独立的短生命周期执行单元，只传当前 Panel 的最小执行参数。当前 Panel 完成后才开始下一个；执行单元严格串行，不共享无关历史，也不并行提交 ComfyUI。具体运行机制由宿主工具自行决定，不属于项目契约。

## 2. 明确不做

本次 breaking 实施不保留下列能力或兼容层：

- 不在新公开流程中兼容旧 `shots[]`、旧 Panel-only CLI、旧创作入口和旧数据库运行语义；底层既有 Run/Task/Attempt 记录不作为 Panel 交接合同的一部分；
- 不在公开流程中使用整集长寿命执行器、后台 Worker、租约、心跳和复杂状态机；
- 不在公开流程中提供自动重试、失败候选片、Attempt 历史、UNKNOWN 对账和自动恢复；调用方不读取或维护恢复记录；
- `PASS_WITH_REPAIR`、分级评分、接触表、长篇 QC 报告和重复审批；
- Prompt revision、复杂生产锁扩展和多份重复的 lock/manifest 审计文件；
- LFO 在运行阶段修改故事、时长、镜头、operation、引用或提示词。

ComfyUI/comfy-cli 负责其自身的生成执行。LFO 对每个已声明的工作流只提交一次并同步等待结果：H3 生成一次；如 package 显式开启可选 SeedVR2 放大，再单独提交一次已启用自适应时域分块的放大工作流。任一步失败、超时或输出不可用时立即返回失败，不在 LFO 内自动重新提交。发生等待超时时，LFO 只向当前本地 ComfyUI 发出一次尽力而为的中断请求，避免超时任务继续占用串行队列；中断失败不会触发第二次提交或恢复流程。用户若要重做，显式重新运行对应 Panel。

comfy-cli 的结构化结果必须明确指向唯一视频。LFO 可复制 CLI 返回的可信本地路径，或按其 `/view` 元数据从同一 ComfyUI 服务下载；不按文件时间猜候选，不把图片当视频，也不接受越过已配置输出根目录的路径。CLI 同时受事件静默超时和带少量退出余量的进程级硬超时约束，避免单次执行无限占用。

## 3. 唯一流程

```text
上游创作确认
    ↓
生成一个只含当前 Panel 的 execution-package.json
    ↓
运行 validate 并取得 package_sha256（plan 仅在需要时诊断）
    ↓
用户确认 package 完整文件字节 SHA-256（exact file SHA-256）
    ↓
启动当前 Panel 的隔离执行单元
    ↓
execute（同步提交并等待 ComfyUI）
    ↓
调用方做最小 QC：可播放 + 无明显内容/连续性错误
    ├─ REJECT/ERROR：立即停止，等待人工决定是否重新生成
    └─ ACCEPT：调用方登记 Clip，按下游需求提取真实末帧
                    ↓
          作为下一 Panel 的真实首帧（仅 I2V/FL2V 需要时绑定）
                    ↓
              串行处理下一个 Panel
                    ↓
        所有 Panel ACCEPT 后执行一次最终 assembly
```

任何 Panel 未 `ACCEPT`，都不能启动下一个依赖它尾帧的 Panel，也不能执行最终组装。

## 4. 输入与锁

每个 Panel 交给 LFO 的生成执行包仍使用 `lfo.video-execution.v1` 公共字段，但必须只表达当前 Panel 的一个非 passthrough Clip。最终组装包则包含一个或多个 `video.passthrough` Clip。生成包至少包含：

- 稳定的 `project.project_id`、当前 Panel 独有的 `package_id` 和正整数 `revision`；
- 当前 Clip 的时长、operation、最终确认的 H3 prompt、generation requirements；
- 当前 Clip 实际需要的素材引用及其 operation 对应的槽位；
- 输出策略和必要的字幕/音频信息；
- 可选的上游用户确认信息；真正阻断执行的批准门禁只有完整 package 文件字节 SHA-256。

已命名的契约对象拒绝未知字段，避免拼写错误被静默忽略；仅 `metadata`、`source_context` 和开放命名空间内容允许自由键。当前内置 `extensions.upscale` 也严格限制为 `enabled`、`scale_multiplier`、可选 `seed`，不提供 `segment_seconds`。它只允许用于单 Panel 生成包；纯 passthrough assembly 开启 upscale 会在 validate 阶段失败。

`validate` 计算当前 package 文件的完整文件字节 SHA-256（exact file SHA-256）并作为 `package_sha256` 返回，用户批准该值。每个 Panel package 和最终 assembly package 都直接位于同一 `workspace/projects/<project_id>/` 项目根目录，使用唯一文件名；不要放入 Panel 子目录，否则 `outputs/<run_id>/...` 无法用包内相对 URI 稳定引用。`execute` 开始前重新计算并比对批准 hash；文件中的素材引用或声明 hash、提示词、时长、operation、输出设置或任何执行字段发生变化，直接停止并要求重新 validate 与确认，不接受局部悄悄修补。锁是一个简单的 package 文件 hash，不再叠加生产锁、提示词 revision 或审批状态机。需要把素材内容也纳入批准边界时，在 package 中填写该素材的 `source.sha256`；Runtime 导入时会核对实际内容。

Package 中的相对素材路径只用于读取。LFO 可将素材导入内容寻址存储，但不修改、移动或删除源文件；运行产物写入项目既有的 RunArtifactLayout。`ACCEPT` 后的真实尾帧由调用方使用 ffmpeg 提取到 `outputs/<run_id>/...`，再作为下一包的相对素材 URI；提取目标是调用方辅助参数，不是 LFO CLI `execute` 参数。

## 5. CLI 契约

当前公开 CLI 只有单 Panel 主流程：

```powershell
python -m lfo.cli.main validate <execution-package.json>
python -m lfo.cli.main execute <execution-package.json> --approved-sha256 <hash>
```

- `validate`：只检查 JSON、路径、operation、引用和基本规格，不生成媒体；成功时返回供用户确认的 `package_sha256`。
- `execute`：校验批准 hash，导入当前 Panel 所需素材，对 H3 生成工作流提交一次并收集输出；只有 package 显式开启放大时才再提交一次 SeedVR2。它只返回生成结果或错误；调用方负责最小 QC，并决定 `ACCEPT` 或 `REJECT`。

`plan` 是只读的可选诊断命令，只在需要查看后端、工作流、引用或产物位置时使用；它直接解析源素材并校验声明 hash，但不导入 CAS、不记录素材 revision、不参与批准，也不是 `execute` 的前置条件。

在使用已保存 machine profile 的机器上，`validate`、`plan`、`execute` 统一追加 `--machine-id <id>`。Runtime 必须把该 profile 中的 ComfyUI 地址、`comfy` 可执行文件和可选输出根目录传给实际执行器；显式指定不存在的 profile 时立即失败。未配置输出根目录时，ComfyUI `/view` 元数据下载仍是有效路径。

`setup --machine-id <id>` 只负责发现并保存 machine profile；不创建 `workspace/` 项目目录、SQLite/旧数据库 schema、环境快照，也不提交视频或 smoke 任务。当前公开入口不依赖 `--smoke-level`；工具和 ComfyUI 可达性由 `doctor`/`preflight` 默认检查 `comfy`、`ffmpeg`、`ffprobe` 和服务连通性。

`retry`、`prompt-revision`、`review` 和自动恢复不属于当前单 Panel 执行入口。若底层保留 `status`、`cancel`、`export` 等 Run 运维入口，它们不属于 Panel 交接协议，也不用于推进下一 Panel；失败后由调用方重新准备并明确执行对应 Panel。

## 6. 最小 QC

QC 只保留真正阻断交付的判断：

1. LFO 技术 QC：文件存在、可读取、包含视频流，且探测到的时长和分辨率为正；
2. 调用方语义 QC：视频可播放，主要主体/动作没有明显生成错误；
3. 调用方连续性 QC：有前序片时检查末尾与当前开头，没有明显倒带、重复收尾或状态跳变；
4. 最终组装后只确认顺序正确、文件可播放，音频/字幕按已确认的输出策略存在。

调用方的结果只有 `ACCEPT` 或 `REJECT`。LFO 不检测黑帧、人物/文字质量或镜头连续性，不自动修改提示词、不评分，也不触发重试。语义判断和接受决定属于创作侧/用户；调用方只在下游需要时于 `ACCEPT` 后提取真实末帧。

## 7. 真实尾帧接力

当下一 Panel 或边界检查需要连续性输入时，调用方必须从当前 `ACCEPT` Clip 的实际输出中提取真实末帧 PNG，并将它作为当前 Panel 的产物记录；没有下游用途时不做多余提取。下一 Panel：

- I2V：将上一段真实末帧作为唯一精确 `first_frame`；
- FL2V：按已确认计划使用真实 `first_frame` 和 `last_frame`；
- T2V 或硬切 R2V：真实末帧只用于人工连续性检查，不伪装成模型首帧引用；
- 不得用文字描述或“脑补”上一段末态替代真实帧。

尾帧 hash 变化时，所有依赖该尾帧的后续 Panel 必须重新准备；不复用陈旧尾帧。尾帧和 Clip 都是执行证据，但不生成失败候选列表或复杂 lineage 报告。

## 8. 最终组装

所有 Panel 依次 `ACCEPT` 后，由调用方构造一份只含 `video.passthrough` Clip 的 assembly package，按 Panel 顺序直接 `cut`，使用已接受的 Clip 和已确认的字幕/音频设置。这份包可以只有一个 Clip；单 Panel 项目仍通过它应用最终配音、字幕和输出策略。assembly package 同样先 `validate`、确认完整文件字节 SHA-256，再执行一次。最终输出写入项目的 `final/<output.directory>/`，只做一次可播放检查。没有通过的 Panel、缺少输入或 package hash 不一致时，组装立即停止。

## 9. 实施顺序与验收

1. 将 CLI 和 Runtime 收敛为单 Panel、同步执行路径；execute 只负责生成结果，不伪造 ACCEPT 或尾帧。
2. 用批准 package 完整文件字节 SHA-256（exact file SHA-256）作为唯一执行锁。
3. 从公开执行流程移除自动重试、恢复、候选片、复杂 Review/QC 和 Prompt revision 分支；不要求删除底层 Run/Task/Attempt 基础设施。
4. 保留真实尾帧提取、串行依赖和最小 ACCEPT/REJECT 门禁。
5. 保留一次性的最终组装与可播放检查。
6. 更新 Skill/适配器交付格式和全部运行文档。

最小验收集：

- 缺少 `--approved-sha256` 或 hash 不匹配时不提交 ComfyUI；
- 一个执行包只生成当前 Panel，不启动并行 Clip；
- ComfyUI 返回失败时命令立即失败且不自动再次提交；
- 调用方在 `ACCEPT` 后能得到真实尾帧，下一 Panel 能按 operation 使用；
- `REJECT/ERROR` 时不会生成下一 Panel 或最终 assembly；
- 所有 Panel `ACCEPT` 后只组装一次并得到可播放最终文件。
