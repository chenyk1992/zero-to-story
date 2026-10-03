---
name: comfy-upscale-executor
description: 由 Canvas worker 调用本地 SeedVR2 3B INT8 视频超分，负责帧范围校验、Comfy 工作流单次执行和实际视频回填；不从对话直接提交。
---

# 本地 SeedVR2 视频超分执行

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。仅由 Canvas worker 调用 `scripts/execute.py`，执行已确认的冻结快照。通过画布持有的官方 Comfy MCP 会话上传、预检、单次提交、查询原任务与取回视频，和其他本地 Comfy 生成共用 `VideoSubmissionGuard`。

## 输入与执行

- `video` 节点选择 `comfy-upscale`、`seedvr2-3b-int8`、`upscale`，必须且只能连接一条 `reference_video`。
- `start_frame` 从 0 开始；`frame_count` 省略时处理起始帧后的剩余画面。提交前用 ffprobe 核实帧率、总帧数和范围；要求恒定帧率，越界或选区超过 15 秒时停止。15 秒是单次选区上限，不是内部窗口长度。
- 当前能力只开放 1920×1066，输入须保持相同画幅比例；其他比例会被拒绝。需要 1920×1080 时另做已授权的居中补边，不拉伸人物或构图。
- 使用既有 `seedvr2_3b_int8_convrot.safetensors`、`seedvr2_ema_vae_fp16.safetensors` 和项目提供的 `CanvasSeedVR2BoundedUpscale` 节点。缺失时在提交前停止，不自动安装或下载。模型、节点和缓存由 ComfyUI 管理，项目工作区只保存媒体与运行产物。
- 自动分窗在 Comfy 工作流内部完成：每窗保留 16 帧，两侧各至多 4 帧上下文；处理后写临时片段并释放像素张量，最后合并完整选区与音轨。Canvas 只绑定源视频、范围与参数，不在提交前拆分素材。诊断显存、时间戳或窗口接缝时读[有界工作流细节](references/bounded-workflow.md)，不要替换为整段浮点帧拼接。
- `chunk_mode` 默认为 `auto`；手动模式只允许 9 个像素帧。参数以当前 capability 与冻结快照为准，执行者不临时改写输入。

## 失败与回填

遇到 CUDA 或主机内存错误时，依据原任务的明确终态与日志定位。未知任务保持锁并核实原编号；后续运行须有针对错误的修正、当前用户授权和新的 Canvas 冻结输入，不盲目重复。对话 Agent 不单独启动脚本或建立上传/提交入口。

记录实际帧范围、输出规格、哈希及音轨情况；检查窗口接缝、人物细节和画面清晰度。窗口化限制活跃像素内存，不能据此保证任何环境下都不 OOM；技术成功与视觉接受分别记录，不将单次运行统计写成其他项目的性能保证。
