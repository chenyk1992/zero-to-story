---
name: comfy-music-executor
description: 由 Canvas worker 单次执行已确认的本地 MiniMax Music 3 音乐快照，预检模型并回填实际 FLAC。用于音乐执行适配与诊断；不创作歌词、不由对话直接提交。
---

# 本地 Music 3 执行

消费 Canvas 已冻结的 `audio` 节点快照，`provider=comfy-minimax-music`、`model=minimax-music-3`。`prompt` 是音乐 caption，`parameters.lyrics` 是独立歌词字段；纯器乐模式没有歌词。执行仅由画布 worker 使用本 Skill 的内部脚本，遵守[共享生产规则](../../../guides/ai-system-prompt.md)。

适配器预检实际模型文件和 Comfy 节点，使用已有 Comfy MCP、机器锁与持久任务回执单次提交，保留原任务编号并取回唯一可解码 FLAC。记录实际时长、哈希与参数；Music 3 可以提前结束。音频听审状态在真实听审前保持 `INCONCLUSIVE`。

诊断可只读检查模型与任务状态；不得从对话运行内部脚本、改动冻结输入或因连接中断重提。
