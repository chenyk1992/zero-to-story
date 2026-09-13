---
name: comfy-video-executor
description: 由 Canvas 服务执行已确认的本地 Comfy H3 视频快照，提交一次并回填实际视频。用于执行适配和故障诊断；不写提示词、规划故事或从对话另行启动生成。
---

# 本地 Comfy 视频执行

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。这是 Canvas 服务调用的脚本适配器；对话 Agent 不领取或重复运行它。创意、模式、素材和参数须在确认前决定，adapter 保持提示词原文与冻结输入。

## 正常生产路线

1. Canvas 页面或对话确认当前节点，服务冻结快照并创建 `queued` 请求。
2. 服务 worker 原子领取，注入该 run 的 `request_id`，启动 [scripts/execute.py](scripts/execute.py)。
3. adapter 校验输入、通过本地 HTTP 上传必要素材和读取 `/object_info`，用官方 `comfy run --wait --json` 同步提交一次。
4. 收回唯一视频，做必要技术校验，复制到服务指定的 run 输出目录并回填原运行。内容验收由调用方按共享规则处理。

## 输入与能力

准备 Canvas 视频配置时读 [capability.json](capability.json)，以当前能力为准，模板中的值只是示例。

| 模式 | 冻结输入 |
| --- | --- |
| `t2v` | 不带媒体 |
| `i2v` | 一张 `first_frame` |
| `fl2v` | `first_frame` 和 `last_frame` |
| `r2v` | 至少一个 typed reference，保留原槽位 |

H3 必填 `duration`、`aspect_ratio`、`megapixels`，Comfy 还需 `sampler_profile` 与 `steps`。`native` 至少 8 步，`vdn_turbo` 恰为 8 步。缺值或重复配置冲突要报告，不能从 workflow 模板补成用户选择。

## 失败处理与诊断

`VideoSubmissionGuard` 的机器级互斥覆盖提交和整个等待过程，持久回执保留未知提交；不要绕过或另建提交记录。超时、无效媒体、缺素材或状态未知都停止原单元，不自动重试或切换提供方。可读取原任务证据核实状态。

正常操作不需阅读实现说明。维护 adapter、诊断参数或回收结果时，按需读[输入与执行协议](references/execution.md)，其中保留快照格式、配置优先级、命令、事件和结果校验细节。文档中的内部命令不授予手工启动权限，也不替代 Canvas 回填。
