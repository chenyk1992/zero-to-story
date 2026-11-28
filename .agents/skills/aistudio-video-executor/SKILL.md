---
name: aistudio-video-executor
description: 由 Canvas worker 通过本机 AIStudio2API 执行 Google AI Studio Gemini Omni 文生视频、首帧图生视频与多参考图生视频（3～15 秒），单次提交并按原任务 ID 轮询回填 MP4；不从对话重复提交。
---

# AI Studio Gemini Omni 视频执行

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)与[画布指南](../../../guides/canvas-guide.md)。本 Skill 只负责执行适配与故障诊断；不编写提示词，不由对话 Agent 另行提交生成。

## 能力与输入边界

- 提供方标识：`aistudio-video`（`execution: "script"`，使用独立串行资源 `aistudio-video`，不阻塞本机 Comfy GPU 队列）。
- 模型：
  - `gemini-omni-1.2-flash`：支持 3～15 秒、`16:9` / `9:16`、`360p`～`4k`（默认 `1080p`）。
  - `gemini-omni-1.1-flash`：支持 3～10 秒。
- 模式：
  - `t2v`：文生视频。
  - `i2v`：首帧图生视频（必填 1 张静态 `first_frame`）。
  - `r2v`：多参考图生视频（必填 1～6 张静态 `reference_images`，不支持同时连接 `first_frame`）。
- 已知协议边界：AI Studio 的 Omni 视频接口不接受尾帧（`last_frame` / `fl2v`）、参考音频及独立反向提示词；需要首尾帧控制或消费 Google Flow 25,000 点数池时，不能用本通道静默替代。

## 单次提交与异常恢复

- 经 `POST /v1beta/models/{model}:predictLongRunning` 单次创建任务后立即持久化 `provider_task_id`（`omni-...`），随后仅轮询 `GET /v1/videos/{id}` 并下载 `GET /v1/videos/{id}/content`，不在轮询或下载异常时重新提交。
- 轮询超时、中途断连、轮询返回 `HTTP 404` 或 `AIStudio2API` 在生成完成前重启丢失记录（`video_not_found`）均遵守“历史缺失不证明远端失败”原则，保持 `status: "unknown"` 与原 `provider_task_id`，仅明确的上游生成失败（`video_generation_failed`）记为 `failed`。
