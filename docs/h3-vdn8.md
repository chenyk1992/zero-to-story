# MiniMax H3 采样模式与 VDN8 工作流

VDN8 是本地 H3 视频生产的 8 步加速工作流。自 2026-09-08 起，公共执行包
通过 `generation.requirements.sampler_profile` 与 `steps` 成对选择
`vdn_turbo` 或 `native`；标准 FL2VA/R2V 分别保留独立的 VDN 和原生 registry
图，不在运行时拆改 VDN 节点来伪装原生，也不在失败后隐式回退。
原模板已有的 operation 映射、T2V/FL2V 映射和视频、音频、混合引用绑定继续保留。

当前完成质量对照并接受的范围是：

- `video.image_to_video`：使用图像首帧和 `euler` / `simple` / 8 steps；
- `video.reference_to_video`：使用图像引用，使用 `euler` / `simple` /
  8 steps。

这表示已有图像 I2V 和图像 R2V 对照达到了当前质量门槛，不代表其它映射
已经完成质量验证。T2V、FL2V、视频引用、音频引用和混合引用仍按原模板
的结构绑定保留，可以正常进入既有流程；它们目前只有结构兼容证据，缺少
本轮 VDN8 的画面质量对照记录，因此不能据此宣称画质已验证，也不应新增
一条运行时拒绝规则。`video.virtual_presenter` 仍只使用独立原生工作流，
缺省 20 步；显式选择 `native` 时可传入符合下述范围的步数。

## 采样约定

模式与步数由用户在项目生产前选择一次，后续 Panel 显式继承；字段、校验和
批准边界见 [公共执行包说明](package-v1-reference.md#采样模式与动态步数)。
`vdn_turbo` 只接受 8 步，`native` 接受至少 8 的整数步数，常用 16 / 20，
也可明确选原生 8 或其他值。不是所有 8 步都代表 VDN。

`vdn_turbo` registry 图的 `KSamplerSelect` 使用 `euler`，
`BasicScheduler` 使用 `simple`，`steps` 为 `8`，`denoise` 为 `1.0`。
VDN 节点的完整配置保持为：`vdn_checkpoint=stage-dmd-step-250`、
`apply_turbo_adapter=true`、`strength=1.0`、`lora_mode=merge`、
`branch_weights=stream`、`retain_buffers=off`、`verbose=true`、
`attention_backend=grouped`。`MiniMaxH3SigmaShift` 使用
`shift_video=12.0`、`shift_audio=3.0`。seed、时长、FPS、分辨率、提示词、
引用顺序和音频策略仍由当前 Panel 的执行包及 LFO 输入绑定提供。

`native` 使用原生 H3 基座，不接入 `ApplyVDNH3` 或 `MiniMaxH3SigmaShift`，
采样器为 `res_multistep` / `simple`，步数来自当前包。它不需要 VDN 插件或
bundle；新加的步数选择已接入执行并不等于每种步数的画面质量都已完成验证。
成对省略模式/步数的已有包保留原缺省：标准 H3 为 VDN8，presenter 为原生20。
新制作流程显式传递用户选择，不靠这个缺省推断授权。

### 插件开关不等于公共采样模式

以下含义核对自本机安装的 ComfyUI-VDN-H3 1.4.0（下述固定提交）的
`vdn_h3/nodes.py` 及 [插件文档](https://github.com/Saganaki22/ComfyUI-VDN-H3/blob/b49130c26a70d12c542601c5bc4f7ee0f112ee2e/README.md)：

- 关闭 `apply_turbo_adapter` 只去掉 turbo adapter；VDN 注意力分支和 default
  adapter 仍在。文档把它描述为蒸馏前的 50 步 VDN 模型，不是原生 H3。
- `lora_mode=bypass` 指运行时注入 LoRA 的方式，与 merge 相对，不是禁用 LoRA。
- Advanced 节点可单独调低 adapter 强度，但保留 VDN 注意力仍不等于原生。
- 如果“非 LoRA / 原生”指旁路整个 VDN 加速分支，当前公共模式应为 `native`。

保留 VDN 注意力但禁用 adapter 的组合不冒充 `native`，也不把它当作已支持的
第三个公共模式。当前任务不扩展非 turbo 的 50 步 VDN 工作流。

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
端到端生成验收。当时 `local-windows` 生产配置尚未完成 comfy-cli、FFmpeg、
FFprobe 和目标 ComfyUI 的正式环境检查。

2026-09-07（本地生产安装）：经用户明确授权，将同一版本的
ComfyUI-VDN-H3 1.4.0 安装到当前本地 ComfyUI 的
`custom_nodes/ComfyUI-VDN-H3/`，并将完整 bundle 安装到
`models/vdn/stage-dmd-step-250/`。插件归档 SHA-256 为
`c7d40bc497aac152c9acd2d0e3a07e620060bcaf1642df905bff712ceefa32b2`；
bundle 共 8 个文件、5,464,957,032 字节，复制前后逐文件 SHA-256 均与
已验证副本一致。插件无新增 Python 依赖。

重启配置指向的空闲服务后，启动日志确认 ComfyUI 0.34.5，真实
`/object_info` 已识别 `ApplyVDNH3` 和 `stage-dmd-step-250`；标准 R2V、
FL2VA 的 doctor 工作流兼容检查均通过，阻断项为 0。全局 comfy-cli、
FFmpeg 和 FFprobe 检查通过，机器路径仍由 `local-windows` profile 管理。
doctor 自动版本检测仍提示无法确定版本，版本值由启动日志核实。
上述结果证明安装及工作流环境兼容，不替代实际生成和画面、声音验收。

保持原 registry 文件名和 LFO 的标题绑定，替换 JSON 中的 VDN 参数；现有
workflow hash 和 `validate` → `execute --approved-sha256` 契约照常生效。
对新镜头记录单 Panel 串行执行的耗时和输出媒体信息，确认有效音轨后，由
调用方给出 `ACCEPT` 或 `REJECT`。

验收至少检查：人物身份和脸部、手部与动作细节、参考图一致性、动作连续性、
背景稳定性、视频时长/分辨率、有效音轨和生成耗时。接受 VDN8 只表示当前
对照满足质量门槛；它不会把原生 20 步和 PDD8 的结果从历史证据中抹掉。
