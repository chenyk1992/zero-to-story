# Canvas Handoff

共享授权、Canvas 唯一入口和实际结果规则见[项目共享生产规则](../../../../guides/ai-system-prompt.md)。本文件只说明 Presenter Panel 如何交给画布。

## 分工

virtual-presenter 决定角色、环境、文案、Shot Contract、引用语义和本条验收重点；h3-prompt-writing 生成最终 H3 文本；canvas-workspace 保存节点并在授权后冻结快照。保存只是草稿，不能绕过页面确认或对话授权。

## 单 Panel 输入

每个 Shot/Panel 使用一个视频节点。保存前从最新 presenter_plan 复制：

- 稳定 panel_id、画幅和 4–15 秒时长；
- h3-prompt-writing 返回的完整提示词，逐字保存；
- 用户已确定的 provider、mode 和参数；
- 当前 Panel 必需素材及用途；同镜头续接的真实尾帧及其采用来源；
- 声音生成方案、参考用途、原音轨/字幕的后期责任；按需附采用音频版本、原音频窗与受保护尾音，已确定的成片偏移留在成片记录；
- 连续镜头编号、段界类型、本条可观察验收重点和连续性末态。

素材语义按以下槽位固定，缺项不顺延：

| Canvas 槽位 | H3 标签 | 用途 |
|---|---|---|
| ref_image_0 | <Picture 1> | 角色/身份 |
| ref_image_1 | <Picture 2> | 全景/环境源 |
| ref_image_2 | <Picture 3> | 当前方向视图 |
| ref_audio_0 | <Audio 1> | 声音参考 |
| ref_video_0 | <Video 1> | 同画幅上一条完整 ACCEPT 片 |

首条省略 ref_video_0；后续完整视频参考按用途补充，不能替代同镜头续接必需的 `first_frame`。`first_frame` 不占普通参考编号，只绑定上一条同画幅完整 ACCEPT 实际采用版本的真实尾帧。contact sheet 不代替方向视图。不要填充无用途素材或虚构路径。

`ref_audio_0` 只绑定有实际用途的声音参考；原音轨保留与声音生成责任按 [Shot Contract](presenter-plan-shot-contract.md#声音与动作按需记录) 保存。没有实际音频时省略该槽位，沿用已定 H3 声音方案。所选模式须支持必要输入，能力见 [H3 控制与后期责任](../../h3-prompt-writing/references/control-boundaries.md)。

同镜头续接按[画布指南](../../../../guides/canvas-guide.md)将真实尾帧导入并登记为来源视频的 `derived_outputs`，记录 `source_run_id`，通过 `output:<id>` 连接下一节点的 `first_frame`，连线指定该来源 run 和 `require_accept: true`。核对尾帧来自当前 review 的实际采用版本；普通上传图片或读取最近成功结果不能代替采用来源绑定。

本地 Comfy 同镜头口播可使用 `r2v + first_frame`，同时保留必要的角色、环境和声音参考。`frame_zero_video_guide` 须关闭或省略，避免视频前缀路线优先而跳过单张首帧引导；上一条完整片仍作为普通视频参考使用（有用途时）。其他已选模式/提供方须支持首帧及本条必要参考；不兼容或已确认配置冲突时暂停并报告，不静默改模式、换提供方或改成只引用视频。首帧引导不承诺像素级一致或声音自动连续。

## 交接顺序

1. 核对计划、提示词标签、Canvas 端口和素材用途；同镜头续接须核对真实尾帧、采用来源和模式兼容性。
2. 保存提示词、模式、参数、素材、音频/后期责任和本条验收重点。
3. 页面确认或对话明确授权后，Canvas 冻结快照并按已选能力提交一次；comfy 由 Canvas 服务调用 comfy-video-executor。
4. 返回实际文件后回填原节点。状态未知时核对原请求，不重提、不换提供方。
5. 按 [Presenter 最小 QC](qc-rubric.md) 检查当前实际采用文件，记录本阶段的末态、音频证据和一次判断；本段采用条件包含后期处理时，先完成该处理再审实际派生版本。

素材不可用、模式冲突、执行失败或证据不足时停止受影响 Panel。重做由调用方修改草稿并确认新快照；不建立恢复循环。

## 接力与成片

独立 Panel 可以先准备；同镜头续接须等上一条完整 ACCEPT 并绑定其真实尾帧后才可 ready 和确认生成。默认保持机位、景别、人物画面位置与大小、背景布局和光线，按计划承接姿态与动作；拆分长口播不新增切镜。只有明确计划的切镜或换场才按新镜头起点准备输入，不要求旧镜头尾帧。拒绝、INCONCLUSIVE 或执行错误的输出不能接力。

全部 Panel 接受且用户要求成片时，按 Canvas 当前 review 采用的实际版本做确定性排序、连接、音频和字幕处理；完成全部后期后按 [最小 QC](qc-rubric.md#处理) 检查最终文件。后期不触发新的生成请求。
