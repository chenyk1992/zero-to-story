# 模型职责与真实字段

来源：[Qwen3-TTS 官方 README](https://github.com/QwenLM/Qwen3-TTS#python-package-usage)、[官方 Design then Clone](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)；2026-09-17 对照本机 flybirdxx/ComfyUI-Qwen-TTS v1.0.7 的 `__init__.py`、`nodes.py` 和 `qwen_tts/inference/qwen3_tts_model.py`。本次服务离线，源码核实不等于实时 schema/生成验证。

## CustomVoice

真实节点 `FB_Qwen3TTSCustomVoice`。官方九种声音如下；Comfy 枚举大小写与官方文档有两处差异，以实时 schema 为准：

| Comfy speaker | 官方描述摘要 | 母语/口音 |
| --- | --- | --- |
| Vivian | 明亮、稍有锐度的年轻女声 | 中文 |
| Serena | 温暖柔和的年轻女声 | 中文 |
| Uncle_fu | 低沉醇厚的成熟男声 | 中文；官方写作 Uncle_Fu |
| Dylan | 清楚自然的年轻北京男声 | 北京话 |
| Eric | 活泼、略沙哑而明亮的成都男声 | 四川成都 |
| Ryan | 节奏感较强的男声 | 英语 |
| Aiden | 明朗、清晰中音区的美国男声 | 英语 |
| Ono_anna | 轻盈活泼的日本女声 | 日语；官方写作 Ono_Anna |
| Sohee | 温暖、情绪丰富的女声 | 韩语 |

语言枚举：`Auto, Chinese, English, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian`。Auto 是自动语言选择，不是第十一种语言。官方支持跨语言，母语通常更适合；不承诺每种 speaker×language 都已实测。Eric 不代表所有四川地区。

1.7B `instruct` 可描述“压低声音，带一点犹豫”“Very happy.”；将表演指令与台词分开，不依赖括号被自动消音。0.6B 不作为此次指令路线。兼容默认保留原 `eric-smoke.json` 与 `eric-api.json`。

## VoiceDesign

真实节点 `FB_Qwen3TTSVoiceDesign`，模型 `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`。输入 `text/instruct/model_choice/device/precision/language`。本机 schema 源码虽列出 0.6B，加载器明确拒绝 VoiceDesign 0.6B，本工具限定 1.7B。

描述示例：“成年女性，中低音区，温暖略带沙哑，普通话清楚，像面对熟人交谈，情绪克制。”台词选含自然停顿的一句完整话。保存描述、参数和实际音频；重新运行同一描述不等于复用同一角色。

## Base 克隆

真实节点 `FB_Qwen3TTSVoiceClone`，模型 `Qwen/Qwen3-TTS-12Hz-1.7B-Base`；台词字段是 **target_text**，参考字段是 **ref_audio/ref_text**，不是 CustomVoice 的 text/speaker。

- 常规 `x_vector_only=false`：引擎要求 `ref_text`，虽然节点界面将它标成 optional。必须是参考音频实际说的文字，不是目标新台词。
- `x_vector_only=true`：无需转写，仅提取说话人 embedding，质量可能下降；用户明确选用才切换，不能作为缺转写的静默兜底。
- 本机插件添加了 `instruct` 并传入其自带引擎；这不是官方 Base 说明中已经验证的表演能力。本工具不开放 Base instruct，后续有真实对照测试再扩展。
- `FB_Qwen3TTSVoiceClonePrompt` 可提取可复用内存 prompt，接 VoiceClone 的 `voice_clone_prompt`。便携音频+转写配置可跨进程复用但会重提取；不可称为已缓存 embedding。不要加载来源不明的 `.pt`/pickle 声音文件。

参考授权记录说明来源及允许用途。优先使用本次合成且可用于复用的虚构角色声音；不要擅自选择真实人物录音。技术检测不能证明授权或听感质量。
