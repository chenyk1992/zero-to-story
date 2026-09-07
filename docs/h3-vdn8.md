# MiniMax H3 VDN8 工作流迁移

VDN8 是当前本地 H3 视频生产的 8 步加速工作流。它直接替换标准 FL2VA/R2V
registry JSON 中的采样路径，不增加 LFO 公共执行包字段，也不在运行时提供
4 步、额外选择器或失败后的隐式回退。原模板已有的 operation 映射、T2V/
FL2V 映射和视频、音频、混合引用绑定继续保留。

当前完成质量对照并接受的范围是：

- `video.image_to_video`：使用图像首帧和 `euler` / `simple` / 8 steps；
- `video.reference_to_video`：使用图像引用，使用 `euler` / `simple` /
  8 steps。

这表示已有图像 I2V 和图像 R2V 对照达到了当前质量门槛，不代表其它映射
已经完成质量验证。T2V、FL2V、视频引用、音频引用和混合引用仍按原模板
的结构绑定保留，可以正常进入既有流程；它们目前只有结构兼容证据，缺少
本轮 VDN8 的画面质量对照记录，因此不能据此宣称画质已验证，也不应新增
一条运行时拒绝规则。`video.virtual_presenter` 仍使用独立的原生 20 步
工作流。

## 采样约定

VDN8 registry JSON 是采样参数的唯一来源：`KSamplerSelect` 使用 `euler`，
`BasicScheduler` 使用 `simple`，`steps` 固定为 `8`，`denoise` 为 `1.0`。
VDN 节点的完整配置保持为：`vdn_checkpoint=stage-dmd-step-250`、
`apply_turbo_adapter=true`、`strength=1.0`、`lora_mode=merge`、
`branch_weights=stream`、`retain_buffers=off`、`verbose=true`、
`attention_backend=grouped`。`MiniMaxH3SigmaShift` 使用
`shift_video=12.0`、`shift_audio=3.0`。seed、时长、FPS、分辨率、提示词、
引用顺序和音频策略仍由当前 Panel 的执行包及 LFO 输入绑定提供。不要把步数改成 4
来换取额外速度；当前质量底线是 8 步。

## 当前已知限制

已验证的节点环境为 ComfyUI 0.34.0 和 ComfyUI-VDN-H3 1.4.0
（插件提交 `b49130c26a70d12c542601c5bc4f7ee0f112ee2e`）。VDN bundle 位于
ComfyUI 模型根目录的 `vdn/stage-dmd-step-250/`，包含 linear branch、
default/turbo adapters 及其配置和元数据；必需文件逐项声明在
`src/lfo/core/workflow_registry.py`。不能只复制一个权重文件就视为安装完成。

本机 VDN merge/stream 路径使用裁剪后的 H3 基座时，会跳过 51 个完整宽度
的 turbo AdaLN delta 张量。这是当前加速路径的明确边界，不能被解释为
“所有 turbo 权重都已合并”。它可能影响某些镜头的细节或时序稳定性，所以
每次迁移仍要做人物、动作、背景、音频和可播放性检查；如果肉眼质量达不到
当前原生结果，停止迁移并保留证据。

在同一 RTX 5080、5 秒、768×1344、24fps、相同 seed/提示词/参考图的 R2V
对照中，曾记录：原生 20 步约 723.940 秒，VDN8 约 295.139 秒，PDD8
约 309.264 秒。VDN8 相对原生约快 59.23%，相对同为 8 步的 PDD 约快
14.125 秒。这个结果是当前测试场景的证据，不是所有镜头的性能承诺。
这轮是在同一 ComfyUI 会话中顺序运行，后运行的方案受已加载模型、编码器、
VAE、图片和条件缓存的 warm-cache 优势影响；因此这些是当前端到端运行记录，
不是独立冷启动基准，也不能直接解释为纯采样或纯推理时间。若比较冷启动，
应另行记录启动、模型加载和缓存建立时间。

## 验证口径

2026-09-07：使用已安装的隔离实验环境检查了两份标准 VDN8 图和独立
presenter 图的真实 `/object_info`，节点及配置检查通过，队列为空，未提交
新的视频生成；服务在检查后关闭。这是环境兼容检查，不是新版 LFO 的
端到端生成验收。当前 `local-windows` 生产配置仍需补齐可发现的 comfy-cli、
FFmpeg、FFprobe 和运行中的目标 ComfyUI，才能完成正式环境的 doctor/preflight。

保持原 registry 文件名和 LFO 的标题绑定，替换 JSON 中的 VDN 参数；现有
workflow hash 和 `validate` → `execute --approved-sha256` 契约照常生效。
对新镜头记录单 Panel 串行执行的耗时和输出媒体信息，确认有效音轨后，由
调用方给出 `ACCEPT` 或 `REJECT`。

验收至少检查：人物身份和脸部、手部与动作细节、参考图一致性、动作连续性、
背景稳定性、视频时长/分辨率、有效音轨和生成耗时。接受 VDN8 只表示当前
对照满足质量门槛；它不会把原生 20 步和 PDD8 的结果从历史证据中抹掉。
