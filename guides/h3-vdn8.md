# MiniMax H3 采样模式与 VDN8 工作流

VDN8 是 Canvas 本地 H3 视频的 8 步加速采样配置。当前 `comfy-video-executor` capability 要求画布快照显式保存 `sampler_profile` 和 `steps`：

- `vdn_turbo` 只接受 8 步，使用 Skill 的 `h3_standard_fl2va.json` 或 `h3_standard_r2v.json`；
- `native` 接受至少 8 步，使用 `h3_native_fl2va.json` 或 `h3_native_r2v.json`。

模式与步数由用户在项目制作规格中确定，后续 Panel 显式继承。不是所有 8 步都代表 VDN；adapter 不根据步数猜 profile，也不在失败后从一种 profile 回退到另一种。

## 当前质量证据

当前完成质量对照并接受的范围是：

- I2V：使用图像首帧和 `euler` / `simple` / 8 steps；
- R2V：使用图像引用和 `euler` / `simple` / 8 steps。

这只说明已有 I2V 和图像 R2V 对照达到了当时的质量门槛。T2V、FL2V、视频引用、音频引用和混合引用已有结构兼容路径，但不能据此宣称画面质量已经验证。结构兼容不足以新增运行时拒绝规则，实际产物仍需逐次验收。

## VDN8 固定结构

`vdn_turbo` 模板的 `KSamplerSelect` 使用 `euler`，`BasicScheduler` 使用 `simple`，`steps=8`，`denoise=1.0`。VDN 节点保持：

- `vdn_checkpoint=stage-dmd-step-250`
- `apply_turbo_adapter=true`
- `strength=1.0`
- `lora_mode=merge`
- `branch_weights=stream`
- `retain_buffers=off`
- `verbose=true`
- `attention_backend=grouped`

`MiniMaxH3SigmaShift` 使用 `shift_video=12.0`、`shift_audio=3.0`。seed、时长、FPS、分辨率、提示词和引用顺序来自当前冻结的 Canvas snapshot。

`native` 使用原生 H3 基座，不接入 `ApplyVDNH3` 或 `MiniMaxH3SigmaShift`，采样器为 `res_multistep` / `simple`，步数来自当前 snapshot。选择 native 不代表每种步数都已有画面质量证据。

### 插件开关不等于采样模式

以下含义核对自本机 ComfyUI-VDN-H3 1.4.0 的固定提交 `b49130c26a70d12c542601c5bc4f7ee0f112ee2e`：

- 关闭 `apply_turbo_adapter` 只移除 turbo adapter，VDN 注意力分支和 default adapter 仍在；它不是原生 H3。
- `lora_mode=bypass` 是 LoRA 注入方式，不等于禁用 LoRA。
- Advanced 节点降低 adapter 强度但保留 VDN 注意力，也不等于原生。
- 旁路整个 VDN 加速分支时应选择 `native`。

保留 VDN 注意力但禁用 adapter 的组合不能冒充 `native`，当前也不把它暴露为第三个公共模式。

## 当前环境与限制

已验证的节点环境为 ComfyUI 0.34.x 和 ComfyUI-VDN-H3 1.4.0。VDN bundle 位于 ComfyUI 模型根目录的 `vdn/stage-dmd-step-250/`，包含 linear branch、default/turbo adapters 及配置和元数据。adapter 在本次提交前通过 `/object_info` 检查节点、模型和枚举；不能只复制一个权重文件，或用旧检查记录代替当前预检。

本机 VDN merge/stream 路径配合裁剪 H3 基座时，会跳过 51 个完整宽度的 turbo AdaLN delta 张量。这可能影响细节或时序稳定性，不能解释为所有 turbo 权重都已合并。

在同一 RTX 5080、5 秒、768×1344、24 fps、相同 seed/提示词/参考图的 R2V 历史对照中，曾记录：原生 20 步约 723.940 秒，VDN8 约 295.139 秒，PDD8 约 309.264 秒。VDN8 相对原生约快 59.23%，相对 PDD8 快约 14.125 秒。该记录包含同一 ComfyUI 会话的 warm-cache 影响，只是特定场景证据，不是性能承诺或纯推理基准。

## 验证口径

2026-09-07 的安装记录确认本地 `ComfyUI-VDN-H3` 1.4.0 与完整 bundle 已复制并逐文件核对；插件归档 SHA-256 为 `c7d40bc497aac152c9acd2d0e3a07e620060bcaf1642df905bff712ceefa32b2`，bundle 共 8 个文件、5,464,957,032 字节。随后运行中的 `/object_info` 能识别 `ApplyVDNH3` 和 `stage-dmd-step-250`。这些记录证明当时的安装和结构兼容，不替代当前 Canvas adapter 预检或实际生成验收。

每个已确认 Canvas run 仍只提交一次。验收至少检查人物身份和脸部、手部与动作、参考一致性、动作连续性、背景稳定性、视频时长与分辨率、有效音轨和实际耗时。接受 VDN8 只表示当前实际结果满足要求，不会抹掉原生或其他方案的历史证据。
