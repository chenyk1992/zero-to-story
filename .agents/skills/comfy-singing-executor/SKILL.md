---
name: comfy-singing-executor
description: 由 Canvas worker 执行已确认的本地 MelBandRoFormer 音轨分离或 Seed-VC 44.1k 歌声转换，回填实际 FLAC。用于已授权参考声音的翻唱；不编排歌曲，不从对话另行提交。
---

# 本地歌声转换执行

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。仅由画布 worker 调用 scripts/execute.py。执行冻结输入，经过共享 Comfy MCP 上传、实时节点预检、单次提交、原任务查询与取回，并共用机器锁。

separate 模式接一份 reference_audio，输出 vocals.flac 和 instruments.flac。convert 模式按边顺序接两份 reference_audio：先原演唱，后目标人物声音。明确记录已有授权，使用预下载的 44.1k 歌声模型，禁止执行时自动补下载。模型、缓存与节点在现有 ComfyUI 内，项目工作空间只保存制作媒体和运行产物。

每份实际音轨记录时长与哈希；转换保持 length_adjust=1，默认不自动迁移音高。八度调整须在已确认参数内。未知任务核实原编号，不重提。技术成功不代表音色、唱词或歌曲听审通过。

## 可选参考观察

[scripts/transcribe_reference.py](scripts/transcribe_reference.py) 是只读本地 ASR 辅助工具，可用 `--audio`、本地 `--model-dir`、`--start`/`--duration` 和新 `--output` JSON 定位候选乐句。它需要已准备的 librosa、PyTorch、Transformers 与本地 ASR 模型，不属于 Canvas 生成执行器，也不自动安装依赖。输出保留源片起点与近似时间；用于定位后再听审，不作为准确歌词、音色或内容接受的证明。
