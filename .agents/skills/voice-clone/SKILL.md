---
name: voice-clone
description: 使用本地脚本调用 MiniMax 音色克隆，将已授权参考音频转成 voice_id，并按需试听。仅用于用户明确要求声音或音色克隆。
allowed-tools: [read, exec_command]
---

# MiniMax 音色克隆

遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。本 Skill 处理音频到 `voice_id`，不扩展到故事、TTS 视频或自动保存音色库。用用户当前语言交互。

## 输入与授权

需要主参考音频、有效的 `MINIMAX_API_KEY`，以及同一音频/说话人的授权说明：操作者拥有合法使用权、说话人授权克隆、用途合法。已有明确说明直接复用；缺失时只补问该缺口，不从笼统的“克隆这个声音”推断权利。

用户提供音频并要求处理后，可先做本地只读检查。上传和克隆前授权必须清楚；取消则停止，不把本地检查当成克隆授权。密钥只从环境读取，不写命令参数、日志或回复。

## 操作步骤

1. **本地检查。** 用 ffprobe 确认主音频为 MP3/M4A/WAV、10 秒至 5 分钟、不超过 20 MB。可选 `prompt_audio` 小于 8 秒且不超过 20 MB。脚本会执行相同输入校验，无需另写检查程序。
2. **按需准备副本。** 保留原音频，必要转换只在系统临时目录：短于 10 秒可循环至下限；超过 5 分钟在 300 秒前的合适静音处裁切，无合适位置则在 295 秒起淡出至 300 秒；超大小则降低 MP3 码率。说明实际做了什么，循环不代表新增了说话内容。
3. **确定请求参数。** 复用已有选择。未指定 `voice_id` 时让脚本生成唯一 ID；默认模型 `speech-2.8-hd`。只有用户要求试听且已给出/确认文本时传 `--text`，否则用 `--no-demo`。降噪和归一化只在用户选择时打开。
4. **执行一次。** 用 [scripts/minimax_voice_clone.py](scripts/minimax_voice_clone.py) 上传参考，再调用克隆；本地路径不是 `file_id`。请求失败先核实原响应，不盲目重复克隆。
5. **返回真实结果。** 提供 `voice_id`、`file_id`、所用模型和必要检查摘要；请求试听时附实际 `demo_audio`。试听为空不直接代表克隆失败，应看 `base_resp`。

从项目根运行，无试听示例：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/voice-clone/scripts/minimax_voice_clone.py --audio "<prepared-audio>" --no-demo --legal-confirmed
~~~

`--legal-confirmed` 只在已有明确授权时传入。有试听时把 `--no-demo` 替换为 `--text "<confirmed-demo-text>"`；文本上限 1000 字符。接口默认 `https://api.minimaxi.com`，可由现有 `MINIMAX_API_BASE_URL` 覆盖。

## 条件参数与结果处理

需要自定义 ID、语言、ASR 对照或短示例时，才读[接口参数](references/minimax-api.md)：

- 自定义 `voice_id` 为 8–256 字符，字母开头，只含字母/数字/`-`/`_`，末尾不能为 `-` 或 `_`。
- 降噪/归一化用 `--need-noise-reduction` / `--need-volume-normalization`。
- 已知主参考逐字稿才传 `--text-validation`（最多 200 字符）和 `--accuracy`（默认 0.7）。
- 已有独立短音频及其逐字稿才传 `--prompt-audio` / `--prompt-text`。语言已知才传 `--language-boost`，不猜逐字稿或语言。

`input_sensitive_type` 非零时说明实际风险标记，停止后续使用并等待用户决定，不自动重试。告知用户：快速克隆音色若 7 天内未正式用于 TTS，可能被删除；不要因此自动发起 TTS。只有用户要求保存时才写到指定位置，默认不复制原音频或写数据库。

维护或排查时，可在已授权的本地检查范围内加 `--dry-run`，只校验并输出计划，不上传。它不能证明真实 API 已成功，也不能冒充克隆授权。
