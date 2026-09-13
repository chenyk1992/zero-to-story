# Canvas Handoff

共享授权、Canvas 唯一入口和实际结果规则见[项目共享生产规则](../../../../docs/ai-system-prompt.md)。本文件只说明 Presenter Panel 如何交给画布。

## 分工

virtual-presenter 决定角色、环境、文案、Shot Contract、引用语义和本条验收重点；h3-prompt-writing 生成最终 H3 文本；canvas-workspace 保存节点并在授权后冻结快照。保存只是草稿，不能绕过页面确认或对话授权。

## 单 Panel 输入

每个 Shot/Panel 使用一个视频节点。保存前从最新 presenter_plan 复制：

- 稳定 panel_id、画幅和 4–15 秒时长；
- h3-prompt-writing 返回的完整提示词，逐字保存；
- 用户已确定的 provider、mode 和参数；
- 当前 Panel 必需素材及用途；
- 外部音频、字幕和确定性后期责任；
- 本条可观察验收重点和连续性末态。

素材语义按以下槽位固定，缺项不顺延：

| Canvas 槽位 | H3 标签 | 用途 |
|---|---|---|
| ref_image_0 | <Picture 1> | 角色/身份 |
| ref_image_1 | <Picture 2> | 全景/环境源 |
| ref_image_2 | <Picture 3> | 当前方向视图 |
| ref_audio_0 | <Audio 1> | 声音参考 |
| ref_video_0 | <Video 1> | 同画幅上一条完整 ACCEPT 片 |

首条省略 ref_video_0；contact sheet 不代替方向视图。普通视频参考不等于精确首帧，精确首帧只绑定已接受实际输出的真实尾帧。不要填充无用途素材或虚构路径。

## 交接顺序

1. 核对计划、提示词标签、Canvas 端口和素材用途。
2. 保存提示词、模式、参数、素材、音频/后期责任和本条验收重点。
3. 页面确认或对话明确授权后，Canvas 冻结快照并按已选能力提交一次；comfy 由 Canvas 服务调用 comfy-video-executor。
4. 返回实际文件后回填原节点。状态未知时核对原请求，不重提、不换提供方。
5. 对故事媒体查看实际输出，记录任务相关末态和音频证据，做一次 ACCEPT、REJECT 或 INCONCLUSIVE。

素材不可用、模式冲突、执行失败或证据不足时停止受影响 Panel。重做由调用方修改草稿并确认新快照；不建立恢复循环。

## 接力与成片

独立 Panel 可以先准备；存在连续性依赖时才等上一条完整 ACCEPT。下一条使用普通 ref_video_0，或在已确认模式要求精确首帧时使用真实尾帧。拒绝、INCONCLUSIVE 或执行错误的输出不能接力。

全部 Panel 接受且用户要求成片时，只对已接受输出做确定性排序、连接、音频和字幕处理，并检查实际文件的可播放性、顺序、接缝以及计划需要的音画同步。后期不触发新的生成请求。
