# Canvas Music 3

画布的音频节点可选择 `comfy-minimax-music` / `minimax-music-3`。歌曲模式填写音乐描述和独立多行歌词；纯器乐模式只填写音乐描述。最长生成时长是上限，模型可能提前结束。种子、采样步数与模型文件名按当前能力设置；确认前服务仍会核对本机模型与节点。

保存字段按[画布操作接口](../.agents/skills/canvas-workspace/references/operations.md)和[音乐能力](../.agents/skills/comfy-music-executor/capability.json)填写：节点 `type=audio`，`data.provider=comfy-minimax-music`、`data.model=minimax-music-3`、`data.mode=song|instrumental`。声音设计 caption 写入 `data.prompt`；歌词写入 `data.options["comfy-minimax-music"].lyrics`，冻结后位于快照 `parameters.lyrics`，不混进 caption。歌曲模式需要非空歌词；器乐模式清空歌词，其他采样选项位于同一提供方 options 中。

当前两种模式均不接受参考音视频输入。锁定画面配乐由创作者把已观察的画面节奏转成音乐要求，不能声称 Music 3 直接观看原视频或复用了歌曲声线。目标 BPM、精确时长或转折位置均须检查实际输出；`max_duration` 不是精确长度保证。

先保存草稿，确认执行时画布冻结输入并创建一次请求。服务 worker 使用已有 Comfy MCP 和机器锁提交；对话 Agent 不运行适配脚本。失败或未知时核实原任务，不自动重提。生成成功会回填实际 FLAC、时长、哈希和任务编号；只有真实听审后才把它用作采用歌曲。已有歌曲可作为音频素材导入，不必经过 Music 3。

只要歌词时不创建音乐请求；只要歌曲或器乐时交付真实音频与听审结论后停止。需要 MV 或锁定画面配乐时，再按对应计划交接。正式后期使用当前 review 采用的实际文件与哈希；导入素材沿用真实来源与采用证据，具体见[音乐后期交接](../.agents/skills/music-video-creator/references/finishing-and-review.md#采用版本与后期交接)。

MV 规划从采用的实际音频建立时间轴，不从提示词 BPM、歌词行数或最长生成时长推算成片切点。歌曲音轨可从音频节点连到支持参考音频的视频模式；最终主音轨仍使用已采用文件，是否有镜内同步须看实际结果。
