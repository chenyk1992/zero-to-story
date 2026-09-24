---
name: comfy-tts-executor
description: 由 Canvas 服务执行已确认的本地 Qwen3-TTS CustomVoice、VoiceDesign 或 Base 音频快照，回填实际 FLAC。用于执行适配与故障诊断；不改写台词，不由 Agent 另行提交生成。
---

# 本地 Qwen3-TTS 执行

仅处理 Canvas 冻结的 `audio` 请求。`comfy-qwen-tts` 能力由服务内部 worker 领取 `queued` 并调用本 Skill 的内部 adapter；不提供对话或独立脚本的生成入口。所有试听也须先保存音频节点，再经画布确认执行。

使用方法和参数见 [Canvas TTS 指南](../../../guides/canvas-tts.md)，共同规则见[共享生产规则](../../../guides/ai-system-prompt.md)。

- 逐字使用 `prompt` 台词；`instruct` 单独控制表演，不添加隐藏文案或改写台词。
- 按冻结模式选用 1.7B CustomVoice、VoiceDesign 或 Base；Base 只接收一个已授权、已听审并核对转写的参考音频。上传后从 Comfy `/view` 校验相同 SHA-256，再提交生成。
- 提交前核对实时节点、`/models/qwen-tts` 中对应模式的完整模型清单（含 `speech_tokenizer/`），以及官方 `comfy env` 所指安装中的独立 Tokenizer 文件；CLI 配置须与运行中服务为同一安装。缺失时停止，不触发插件下载。文件检查不代表生成质量通过。
- 服务复用共享连接、官方 comfy-cli、`video` 资源键及 `VideoSubmissionGuard`，一次提交并等待；未知回执不解除、不重提。
- 原始 `original.flac` 完整解码后保留；从原始文件按所选 `tempo` 确定性变速，`speech.flac` 是唯一节点输出。倍率 1 保持原速，不叠加处理。
- `workflow.json`、`conditions.json`、`speech.flac.json` 与音频保存在当前 run 目录。记录任务 ID、实际文件哈希、时长、采样率、声道、种子和语速；失败不把候选文件回填为成功。
- 技术成功不代表台词、口音和语气验收。需要内容采用时试听实际交付文件，不用 ASR 或音色标签代替听审。
