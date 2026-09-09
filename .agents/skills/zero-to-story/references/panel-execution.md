# Panel 交接与执行

共同的角色、Panel ready、单工作单元、实际末态/音频验收和授权规则见[项目共享生产规则](../../../../docs/ai-system-prompt.md)。STEP 4 提供两条入口共用的 H3 创作事实；STEP 5 起只适用于明确选择的 package CLI，画布执行改读 [canvas-workspace](../../canvas-workspace/SKILL.md)。

本参考只在 Panel 已有确认的故事板、operation、素材关系，需要写 H3 handoff、创建执行包或执行/组装时读取。执行包字段以 [VideoExecutionPackage 交付格式](execution-package.md) 为准；实际内容与最终检查以 [最小视频接受检查](video-qc.md) 为准。

## STEP 4：交给 H3 提示词作者

每次只处理一个 Panel，并读取 `$h3-prompt-writing` 对应模式的官方 reference。提供已经确认的创作事实，不自写 H3 提示词草稿：

- Panel 时长、画幅、Medium Lock、Style Brief 和节奏意图。
- 六 Beat 到 Camera Setup 的映射；每个 Setup 的构图、机位、轴线、朝向、目标/视线、屏幕运动、运镜动机及起止、动作完成依据、声音和锁定末态。
- 逐字对白、说话人、语言、画外音状态，以及台词字幕和场景文字的制作责任。
- 推荐 operation、精确首/尾帧要求、连续或硬切关系。
- 最小 `runtime_input_keys` 与素材用途；R2V 的已锁定 `storyboard_layout` 和按阅读顺序排列的格子到 Beat/Setup 映射。
- P002 起的零时长边界锚点和唯一 transition ownership。

H3 skill 负责字段、标签、镜头时间、对白语法和最终英文措辞。它不能静默换 operation、丢弃必需素材、重排对白或改变已批准时长。R2V 分镜板作为一张图片和一个 fixed reference 处理；提示词中说明阅读顺序与内容，但不附加不存在的独立格子图片。需要修改时重新交给 H3 skill，不在本 Skill 内手工修补。最终提示词符合已确认的创作事实和用户指定的审核阶段后，逐字交给画布的提示词输入或 package 的 `generation.prompt`，不创建 prompt manifest。

## STEP 5：每个 Panel 创建并批准一个包

每个 Panel 单独创建一份 `execution-package.json`，只含当前 Panel 的一个非 `video.passthrough` Clip；不要把所有 Panel、跨 Panel dependencies 或 assembly 放进生产包。包至少包含稳定 `project_id`、Panel/Clip 标识、精确时长、画幅、FPS、operation、最小素材引用、字幕/音频/输出策略，以及当前已确认的提示词。

从故事板和蓝图 `user_constraints` 继承用户已选的 `megapixels`、`sampler_profile`、`steps`，显式写入当前 Clip 的 `generation.requirements`。遵循 [一次选择与继承规则](execution-package.md#项目级生成参数选择一次逐-panel-继承)：后续 Panel 不重复询问、不临时改步数或混用模式；用户明确变更后，更新项目规格及受影响包，再校验与批准。采样参数属于执行配置，不塞进 H3 提示词。

Panel 包和最终 assembly 包都直接放在同一项目根目录，文件名互不重复。包内使用 project-relative 素材 URI，不写绝对输出路径、ComfyUI 节点、模型路径或内部素材 ID。I2VA 只用 `first_frame`；FL2VA 用 `first_frame` 与 `last_frame`；R2V 按资产计划使用整张 `storyboard_board.<panel>` 或明确用途的 `reference_assets` typed fixed slot；T2V 不带视觉引用。

包还要保留当前 Panel 的稳定项目 ID、Panel/Clip 标识、精确时长、画幅、FPS、字幕/音频/输出策略和 `approval` 信息。跨 Panel 的串行关系由主流程保持，不写成单包内的生产依赖；ComfyUI 输出复制到项目 Run 目录后才登记为 LFO artifact。

## 最小状态与版本

### 修订包持续授权

用户明确要求“这种修订包默认批准 / 不再逐次确认”时，记录其原话、项目和修订范围到现有故事板，不另建审批清单或锁文件。该授权覆盖范围内的常规提示词、动作因果及连续性修正；不默认覆盖扩大制作范围、改变已选生成参数、增加收费/外部服务或未授权的数据操作。每次先形成新 revision、validate、核对差异仍在授权内，再把当前精确文件 hash 交给 execute。简短告知修订与执行即可，无需用户再次回复。

本文及相邻引用中的“重新批准 / 取得新 hash 批准”包括调用方依据明确持续授权绑定新 hash，不等于必须人工再次确认。授权记录应如实写“依据用户持续授权”，不能伪称用户亲自审阅了每份新包。单纯“继续”、沉默或等待超时不建立这种授权。

此规则不绕过 validate、哈希一致性、串行生成和 QC。失败后先停止该执行链；只有存在具体原因与有依据的修订、且新任务仍在授权内时才能形成新包，不能原样重投或无限尝试；同一关键问题经一次定点修订仍失败则报告并停止。

只保留有助于继续创作的状态：故事板/蓝图为草稿或已确认，角色与视觉资产为未生成、待确认或已确认，当前 Panel 包为未批准或已批准（记录该包的精确 SHA-256）；实际内容判断为 `ACCEPT`、`REJECT` 或 `INCONCLUSIVE`，尚未检查时留空，执行错误另记。用户修改故事板、时长、画幅、角色锚点、引用、operation 或 H3 提示词时，为受影响包设置新的正整数 `revision` 并重新核对授权；不维护独立 prompt revision 或下游失效表。每次继续前读取最新文件，不从旧对话补写已变更内容。

提交前执行：

```powershell
python -m lfo.cli.main validate <panel-execution-package.json>
python -m lfo.cli.main execute <panel-execution-package.json> --approved-sha256 <hash>
```

`<hash>` 必须是本次 `validate` 成功返回的当前包完整文件字节 `package_sha256`。批准对象是该文件、该字节和该范围；同一包未变更且已有可验证批准时复用，不重复打断。包字节变化后先重新校验，再核对已有持续授权是否覆盖：覆盖则直接绑定新 hash；不覆盖才询问。hash 不匹配时停止，不能沿用旧值执行。执行期间不修改包，不创建独立 production lock 或重复锁文件。

## STEP 6：逐 Panel 隔离串行

每个 Panel 使用一个短生命周期、相互隔离的执行单元，视频提交保持串行；只传当前包路径、批准 hash 和必要机器参数，不传完整故事、前序日志或内部状态。只有当前 Panel 依赖上一 Panel 的真实状态时才等待前段 `ACCEPT`。调用方的最小交接形态是：

```text
validate current package → exact file-byte SHA-256 approval
→ isolated execute current package --approved-sha256 <hash>
→ synchronous official comfy-cli generation
→ ACCEPT / REJECT / INCONCLUSIVE
→ ACCEPT: extract actual tail only when the next Panel needs it
```

LFO 直接同步调用官方 ComfyUI/comfy-cli。生成提交严格串行；可以并行做资料读取、提示词准备、独立资产准备和普通代码工作，但不能并行提交生成 Clip。下一 operation 需要精确首帧时，由调用方在上一 Panel `ACCEPT` 后从实际接受视频提取尾帧到项目 Run 输出目录，再作为下一包的确切相对素材 URI 和 `first_frame`；不能用文字描述或虚构路径代替真实尾帧。没有下游用途时不做多余提取。

调用方的最小输入是 `panel_id`、`package_path`、`approved_package_sha256` 和已有机器配置时的 `machine_id`；`tail_frame_output_path` 仅是调用方提取真实尾帧的辅助参数，不是 LFO CLI/runtime 参数，也不写入 package。执行单元只读取当前 Panel 包，不接收完整故事、前序日志或内部状态。

执行单元按 [最小视频接受检查](video-qc.md) 查看实际文件，对关键身份、动作因果、实际完成状态、实际末态、实际音频证据和相邻衔接作出 `ACCEPT`、`REJECT` 或证据不足时的 `INCONCLUSIVE`。执行技术成功不等于内容 ACCEPT；片段级后期也纳入这次检查。拒绝、证据不足、生成错误、超时、hash 不符或素材不可用时暂停受影响任务，不盲目重试、不把失败候选登记为正式产物，也不另写恢复侧车。

## STEP 7：一次最终组装

全部 Panel `ACCEPT` 后，才用一个独立且已批准的 assembly 包做一次最终组装。assembly 包可以包含一个或多个全 `video.passthrough` Clip，不调用生成模型；按包顺序连接，当前最终转场用 cut。字幕、音频、后期和实际交付文件按 [最终组装检查](video-qc.md#最终组装) 核对。发现具体问题时修正并显式决定是否重新执行受影响包；未完成的观看或听审项目如实报告，不以轨道存在代替通过。

## 停止与继续

故事板、蓝图或执行包草案的可逆问题，在当前授权范围内按具体报错定点修复和复核；同一问题无新依据不重复修复。生成错误、硬件/素材功能错误、引用模式不兼容、批准缺失或不匹配、REJECT 和最小 QC 失败是硬停止；停止当前 Panel 并报告实际原因与受影响路径。只有用户新指令、修正后的输入或新的精确批准包满足继续条件后，才重新发起受影响 Panel。
