---
name: comfy-singing-executor
description: 由 Canvas worker 执行已确认的本地 MelBandRoFormer 人声与伴奏分离，回填实际 FLAC。用于分离执行适配和诊断；不编排歌曲，不从对话另行提交。
---

# 本地人声与伴奏分离

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。`audio` 节点选择 `comfy-singing` / `melband-seedvc-44k` / `separate`，由画布 worker 启动 `scripts/execute.py`。使用官方本地 Comfy MCP、共享资源与机器锁，按冻结输入单次执行并回填真实人声、伴奏 FLAC；失败或未知不自动重提。

`melband-seedvc-44k` 是兼容已有分离节点的历史模型标识，当前只执行 MelBandRoFormer。一份实际歌曲接 `reference_audios`，描述写入 `prompt`；可选 `separator_model` 选择已安装分离权重，默认 `MelBandRoformer_fp16.safetensors`。adapter 预检模型，不下载或替换依赖。

输出角色按真实输出节点或提供方文件来源核对，不依赖下载后的文件顺序。检查 FLAC 可解码、有效时长与原曲相符，保留哈希及 `INCONCLUSIVE` 听审状态。分离结果可能有串音，技术通过不等于可以自然替换人声。

原有 Seed-VC、RVC、SoulX-Singer-SVC 和 DiffSinger 试验入口已撤下；历史节点与媒体保留，但这些模式不可再次执行，不能静默改成分离。多人音乐由 [music-video-creator 的多人轮唱流程](../music-video-creator/references/multi-singer-workflow.md)规划，翻唱使用 [YuE2 执行器](../comfy-yue2-executor/SKILL.md)。
