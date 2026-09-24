---
name: qwen3-tts
description: 通过项目 Canvas 生成 Qwen3-TTS 预置多语言语音、VoiceDesign 角色声音或 Base 授权音色克隆，并准备台词、参考转写与听审。用于语音配音、声音设计和复用；Eric 成都男声仍是预置音色入口。
---

# Qwen3-TTS 语音与角色音色

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。本 Skill 负责台词、模式选择、参考来源和听审准备；所有生成由 Canvas 的 `audio` 节点确认，使用 `comfy-qwen-tts` 能力和 [comfy-tts-executor](../comfy-tts-executor/SKILL.md)。实际操作见 [Canvas TTS 指南](../../../guides/canvas-tts.md)。

## 模式选择

| 需求 | Canvas 模式 | 1.7B 模型 | 必要输入 |
| --- | --- | --- | --- |
| 预置音色读台词，包括 Eric 成都男声 | `tts` | CustomVoice | 原文、speaker、language；instruct 可选 |
| 根据描述设计角色声音 | `design` | VoiceDesign | 原文、非空 instruct 声音描述、language |
| 参考已授权声音说新台词 | `clone` | Base | 新台词、一个实际音频、来源与授权、实际参考转写和听审确认 |

当前 Canvas 为兼容既有节点继续使用模型 ID `qwen3-tts-1.7b-customvoice`；实际加载的权重由模式决定。三模式均固定 1.7B、CUDA、bf16、sdpa。更多真实节点字段和约束见[模式参考](references/modes.md)。

用户已有台词时保留原文；要改成四川话时先展示改写。未提供台词的 Eric 首次试听可参考[示例配置](assets/eric-smoke.json)。VoiceDesign 可从[声音设计草稿](assets/voice-design.json)开始；[克隆草稿](assets/voice-clone.json)故意缺少参考授权和转写，不能直接执行。

## 准备与执行

1. 先运行[只读预检](scripts/preflight.py)：`./.venv/Scripts/python.exe .agents/skills/qwen3-tts/scripts/preflight.py --mode all --comfy-root <实际ComfyUI目录>`。脚本中的 `custom` 对应 Canvas 的 `tts`；预检不下载、不加载或提交模型。模型存在不等于已完成实际生成验收。部署差异见[安装参考](references/setup.md)。
2. 在 Canvas 新建语音节点，选择本地 Qwen3-TTS 和模式，将需要逐字说出的文字放入提示词。表演指令与声音描述另填。默认语速为原始合成的 1.2 倍，使用 FFmpeg 单次变速并保留音高；本次指定 1.0 则保留原速。不得在 Qwen 指令中重复要求“快速说话”叠加速度。
3. 克隆时，把已核对的真实音频接到 `reference_audio`。记录来源与用途授权；听实际文件并核对逐字转写后，才设置“已听审参考并核对转写”。常规模式填写 `ref_text`；明确选用 `x_vector_only` 才可省略转写。不得把目标新台词填作参考转写，或仅凭输入文本、ASR、元数据宣称已听审。
4. 通过画布确认一次，由服务冻结输入并排队执行。状态未知时核实原任务 ID，不自行调用 `/prompt`、Comfy CLI 或重复提交。运行时会核对对应权重、独立 Tokenizer、实时节点和上传参考的 SHA-256，然后保存原始 `original.flac` 与交付 `speech.flac`。

## 角色复用与验收

VoiceDesign 先产生真实交付文件，再听审台词、声音和句尾。认可后，保存该文件、实际逐字转写、来源运行、授权和 SHA-256；Base 新节点连接此文件并说新台词。仅有文字描述或种子不代表已锁定角色声音。便携配置是音频引用，不是持久 embedding 缓存。辅助草稿与音频工具见[工具用法](references/tools.md)。

试听和下游引用使用实际交付文件。记录原始与交付的时长、采样率、倍率和来源任务；内容听审针对交付版本，检查错漏字、发音、情绪、音色和句尾。技术生成成功不自动成为内容 ACCEPT。无法实际听审时提供文件供用户试听，并将内容状态留为 INCONCLUSIVE。
