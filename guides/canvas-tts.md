# Canvas 语音生成

使用画布“语音”节点生成本地 Qwen3-TTS。保存只是编辑草稿；确认后服务冻结台词、参数和连接的参考音频，排队并回填实际文件。所有试听也经此入口执行。创作侧入口为 [qwen3-tts](../.agents/skills/qwen3-tts/SKILL.md)，执行责任为 [comfy-tts-executor](../.agents/skills/comfy-tts-executor/SKILL.md)。

## 选择模式

| 模式 | 权重 | 页面输入 |
| --- | --- | --- |
| 预置音色 `tts` | 1.7B CustomVoice | 逐字台词、speaker、language；默认 Eric 成都男声 |
| 声音设计 `design` | 1.7B VoiceDesign | 逐字台词、非空声音描述 instruct、language |
| 音色克隆 `clone` | 1.7B Base | 新台词、一个真实参考音频、来源与授权、已核对参考转写及听审确认 |

Canvas 仍使用原来的 `comfy-qwen-tts` 后端和 `qwen3-tts-1.7b-customvoice` 模型 ID，以保留已保存的预置音色节点；执行器按模式选择对应 1.7B 权重。模式变更后，清除页面提示的旧模式专属参数和不适用的输入连线，再确认执行。

## 操作

1. 新建语音卡，在提示词栏填写需要逐字说出的台词；选择本地 Qwen3-TTS 与模式。声音设计填写声音描述，不把描述混入台词。
2. 克隆时从已生成的语音卡或音频素材卡连接到新语音卡的“声音参考”。只接一个音频；填写参考来源、允许用途和这份音频实际说出的文字。先听实际参考并核对转写，才勾选听审确认。只有明确选择 `x_vector_only` 时可省略转写；该模式不免除来源授权和听审。
3. 确认执行并等待本次运行结果。完成后播放 `speech.flac` 交付版本，核查台词、发音、声音和句尾。继续复用角色时使用这份实际交付文件作下一次参考。
4. 要作为 H3 声音参考时，把语音输出连接到视频卡的“音频参考”。它是生成参考，不是固定时间轴配音。

## 参数与结果

`tempo` 默认 1.2，范围 0.5–2，由 FFmpeg 对原始音频做一次保留音高的变速；设为 1 则保持原速。`seed` 未填时执行器生成并记录。`max_new_tokens` 默认 2048；较长台词须实际听审是否完整。CustomVoice 可选表演指令；VoiceDesign 必须填写声音描述。Base 不开放未验证的表演指令。三模式固定 CUDA、bf16、SDPA、top_p 1、top_k 50、repetition_penalty 1.05，生成后卸载模型。

提交前通过 MCP 核对本机实时节点及对应权重文件名清单，包括每套模型内的 `speech_tokenizer/` 和独立 `Qwen3-TTS-Tokenizer-12Hz` 文件名；不直接检查 Tokenizer 文件大小，文件名存在也不等于生成验收通过。缺失时停止，避免插件隐式下载。克隆参考在确认时冻结，以 MCP 上传成功回执及源文件未变化作为提交条件，不读回服务端比较 SHA-256。图片、视频与 TTS 共用机器锁和持久回执；状态未知时依据原任务证据核实，不重提。

每次运行在项目 `outputs/<run_id>/` 保留 `workflow.json`、`conditions.json`、原始 `original.flac`、交付 `speech.flac` 和 `speech.flac.json`。交付记录绑定实际文件哈希、任务 ID、语速和时长，内容听审初始为 `INCONCLUSIVE`。技术成功不表示台词和音色已被接受；声音复用方法见 [Skill 工具参考](../.agents/skills/qwen3-tts/references/tools.md)。
