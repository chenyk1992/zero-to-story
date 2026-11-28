---
name: aistudio-image-executor
description: 由 Canvas worker 通过本机 AIStudio2API 执行 Google AI Studio Nano Banana 文生图、多图参考生成与图片编辑（最多 14 张参考图），单次提交并回填校验后的 PNG；不从对话重复提交。
---

# AI Studio Nano Banana 图片执行

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)与[画布指南](../../../guides/canvas-guide.md)。本 Skill 只负责执行适配与故障诊断；不改写用户定稿提示词，不由对话 Agent 绕过画布直接重复提交。

## 能力与输入边界

- 提供方标识：`aistudio-image`（`execution: "script"`，独立资源键 `aistudio-image`，默认并发上限受 `LFO_IMAGE_CONCURRENCY` 约束）。
- 模型：`gemini-nano-banana-2.1`、`gemini-3-pro-image` 及其 `-search` 联网增强变体。
- 模式：
  - `create`：文生图（未显式设置画幅时默认 `1:1`）。
  - `reference`：图片参考生成（连接 1～14 张静态参考图，未设置画幅时默认 `1:1`）。
  - `edit`：图片编辑（连接 1～14 张静态参考图，未设置画幅时保留源图比例）。
- 输出分辨率：`1K`、`2K`（默认）、`4K`；产物经 `ffprobe` 校验并统一落盘为无损 `image.png`。

## 本机端点与安全边界

- 仅允许连接本机回环 HTTP 服务（默认自动读取 `~/.local/share/magpie-ai-studio/config.json` 或 `~/.config/magpie/plugin-auth.json`，也可经 `LFO_AISTUDIO_BASE_URL` / `LFO_AISTUDIO_API_KEY` 显式覆盖）。
- 禁止跟随任何 HTTP 重定向，禁止把密钥写入 URL 查询串、`conditions.json` 或错误回执。
- 消耗的是本机 `AIStudio2API` 登录账户在 Google AI Studio 网页端的配额，不等同于 Google Flow 的 25,000 点数池。
