> **GPT-6 适配变更说明**  当前指令或已有 Presenter Plan 授权可直接进入包构建，不重复确认同一创作方案。LFO 运行前仍必须核对并取得当前执行包完整文件 SHA-256 的明确批准；笼统生成请求不代替尚不存在包的 hash 批准。单 Panel、串行、真实尾帧、失败即停和不盲目重试规则继续由根 `AGENTS.md` 统一约束。

# LFO Handoff

## 边界

Skill 只交付公共执行包和已确定素材语义。LFO Runtime 负责素材读取、后端选择和同步调用官方 ComfyUI/comfy-cli；调用方负责最小语义 QC、上一条完整 `ACCEPT` 视频接力和最终组装，只有其他下游 operation 明确需要精确首帧时才提取真实尾帧。Skill 不写数据库、ComfyUI 节点、模型路径、内部素材 ID 或平台缓存路径。

适配器入口固定为：

- lfo.skill_adapter.virtual_presenter.build_shot_package
- lfo.skill_adapter.virtual_presenter.build_assembly_package

这两个函数负责把当前指令或已有授权确定的 Presenter Plan/Shot Contract 转成 LFO 可校验的执行包。若运行环境尚未提供模块或函数，立即停止并报告缺失接口；不要在 Skill 目录里复制一个“伪适配器”。

## Shot/Panel package 约定

每个 Shot/Panel 单独调用 `build_shot_package`。Shot Contract、H3 最终提示词、素材语义映射、项目标识和输出策略先写入已确定的 `plan`；函数只额外接收目标 `shot_id`、可选的上一条完整 ACCEPT 视频 URI 和 package revision。每个生成包只含当前 Panel 的一个 Clip；不要把多个 Panel、跨 Panel dependencies 或最终组装塞进同一生成包。
每个 Panel package 和最终 assembly package 都直接写在 `workspace/projects/<project_id>/` 项目根目录，使用唯一文件名（如 `panel-P001.execution-package.json`、`assembly.execution-package.json`），不要把它们分散到 Panel 子目录；这样 `accepted_clips` 中的 `outputs/<run_id>/...` URI 对所有包都保持可解析。
当前仓库适配器公开的命名入口为：

    build_shot_package(plan, shot_id, *, previous_clip_uri=None, package_revision=1)
    build_assembly_package(plan, accepted_clips, *, package_revision=1)

shot plan 至少提供 project、inputs、output、shots 和 approval；当前 shot 提供 shot_id、sequence、duration_ms、prompt、environment_view_uri；组装使用已接受片段的 shot_id、sequence、duration_ms 和 package-relative uri。若仓库接口发生变化，先读取实现和测试再更新本 Skill，不把这些字段猜写到 LFO 内部。

素材语义映射固定如下，不能因为缺失一项而移动编号：

| package 槽位 | 语义 | H3 提示词标签 |
|---|---|---|
| ref_image_0 | 角色图/身份锚点 | `<Picture 1>` |
| ref_image_1 | 360°全景或环境源 | `<Picture 2>` |
| ref_image_2 | 当前 yaw、pitch 0°、FOV 90°方向视图 | `<Picture 3>` |
| ref_audio_0 | 声音参考 | `<Audio 1>` |
| ref_video_0 | 同画幅上一条已接受片 | `<Video 1>` |

首片没有上一条接受片时省略 `ref_video_0`，绝不拿 contact sheet 或其他图片填补。后续 Panel 只使用同画幅上一条完整 `ACCEPT` 视频；`ref_video_0` 是普通连续性参考，不等于精确 `first_frame` 尾帧锁。上一条的路径和素材语义保持可追溯，不能把失败或被拒绝的输出当作连续性输入。需要另一画幅或精确首帧 operation 时由上游另行建立对应序列，不在 virtual-presenter 适配器内猜测切换。

存在 `ref_video_0` 时默认不再附加 `ref_audio_0`，让 Presenter 继承上一片视频的配对音轨；只有当前 Shot Contract 明确要求独立声音参考时，才设置 `include_voice_reference: true`，让适配器同时映射 `ref_audio_0`。

每个包至少通过现有公共字段记录 `project.project_id`、`package_id`、Clip `operation`、`source_context.shot`、画幅、duration、prompt、references 和 output 语义；不要添加不存在的 `package kind` 字段。包内的 duration 必须与 Shot Contract 相同且在 4–15 秒；包发生修改时重新构建并重新取得文件 hash，不维护额外的 lock/manifest 或重做记录。

## validate → execute

每个 Shot/Panel package 生成后独立执行：

1. 读取 resolved references，核对 `ref_image_0/1/2`、`ref_audio_0`、需要时的 `ref_video_0` 与 `<Picture 1/2/3>`、`<Audio 1>`、`<Video 1>`；
2. 运行 `python -m lfo.cli.main validate <panel-execution-package.json>`，取得结果中的 `package_sha256`；
3. 若该完整文件 hash 尚无明确批准，由用户批准该 exact file SHA-256；同一未变更包可复用既有批准；
4. `plan` 只在需要查看后端、工作流或引用诊断时运行，不是执行前置条件；
5. 启动当前 Panel 的隔离执行单元，运行 `python -m lfo.cli.main execute <panel-execution-package.json> --approved-sha256 <package_sha256>`，同步等待官方 ComfyUI `comfy-cli` 完成。

每个 Panel 都必须独立 `validate`，使用其返回的 `package_sha256` 完成或核对批准，并由 `execute` 重新核对自己的文件 hash；不使用跨 Panel 的预检或锁文件。执行包未获用户批准、hash 不一致或引用不完整时立即停止。

## Panel 串行执行

Presenter Plan 获得当前指令或已有确认授权后，按 Shot/Panel 顺序逐个构建、validate、取得并核对 `package_sha256` 批准、执行。每个 Panel 建立一个独立的短生命周期执行单元；前一个同步完成并返回结果后，才启动下一个。执行输入只包含当前 Panel 的 package 路径、批准 hash、输出位置和可选的上一条完整 `ACCEPT` 视频 URI；具体运行机制由宿主工具自行决定。

调用方对当前输出只做最小可播放与明显内容错误检查，QC 决策只有 `ACCEPT` 或 `REJECT`；校验或执行失败记为 `ERROR`。下一条 Presenter Panel 将当前完整 `ACCEPT` 视频作为普通 `ref_video_0` 连续性参考。只有其他下游 operation 明确需要精确首帧时，才从实际输出提取真实末帧并绑定。`ERROR` 或 `REJECT` 立即停止，不自动重试、不把失败输出加入 accepted 列表；需要重做时重新构建当前 Panel package 并重新批准其 hash。

## Assembly package

全部 Panel 都 `ACCEPT` 后才调用 `build_assembly_package(plan, accepted_clips, *, package_revision=1)`。目标画幅、输出策略、字幕和 `project_id` 已写在 `plan` 中；`accepted_clips` 只提供已接受片段的 `shot_id`、`sequence`、`duration_ms`、package-relative `uri` 及可选字幕覆盖。不要让组装器重新生成语义镜头，也不要把未接受或被拒绝的片段混入清单。

最终视频后端固定为 `video.passthrough`：片段顺序、每段时长、音频/字幕时间线和输出目录交给 LFO Runtime 的公共契约。Assembly package 也要独立运行 `validate`，取得其返回的 `package_sha256`，若该 hash 尚无明确批准则由用户批准该完整文件字节 SHA-256；同一未变更包可复用既有批准。随后再运行 `python -m lfo.cli.main execute <assembly-package.json> --approved-sha256 <package_sha256>` 一次。其 accepted video URI、音频和字幕 URI 都相对同一项目根目录下的 assembly 文件；最终输出必须遵守 LFO 的项目 Run artifact layout；Skill 不在 workspace 根目录创建 runs 或 exports。

## 接口假设与故障处理

当前 Skill 使用上述两个入口：生成入口从已确认 `plan` 读取 Shot Contract、提示词、引用语义、project 和 output；assembly 入口从同一 `plan` 与全部已接受片段列表构建 `video.passthrough` 包。具体字段名、包文件位置、字幕字段和项目路径以仓库适配器/公共契约为准。

若 validate、hash、适配器导入、引用解析、comfy-cli 执行或最小 QC 失败：

- 立即停止当前 Panel，不执行下一 Panel 或最终组装；
- 不把失败输出作为 accepted，也不自动重试、自动修改提示词或维护恢复记录；
- 需要重做时，由调用方明确重新构建当前 Panel package，并重新取得用户批准的文件 hash。


