---
name: voice-clone
description: |
  本地 MiniMax 音色克隆助手。将参考音频上传到 MiniMax 文件接口，
  调用 /v1/voice_clone 生成可用于后续 TTS 的 voice_id；包含授权确认、
  音频校验、可选预处理、试听和风险提示。仅适用于用户明确要求声音/音色克隆。
allowed-tools: [read, exec_command]
---

# 本地 MiniMax 音色克隆

本技能在本地执行 MiniMax 官方的两段式音色复刻流程：

1. `POST /v1/files/upload`，以 `multipart/form-data` 上传参考音频，字段为 `purpose=voice_clone` 和 `file`，取得 `file_id`。
2. `POST /v1/voice_clone`，以 JSON 传入 `file_id`、唯一的 `voice_id`，以及可选的试听和音频处理参数。

实现脚本位于 `scripts/minimax_voice_clone.py`，只使用 Python 标准库；它不会把 API key 写入文件，也不会调用 Hub 的 `hub_voice_prepare`。接口字段和限制见 [references/minimax-api.md](references/minimax-api.md)。

始终使用用户当前语言交互。当前技能只处理音频到 voice_id 的执行，不负责故事、脚本或视频创作。

## 1. 必须先取得授权确认

在任何 `ffprobe`、`ffmpeg`、上传或克隆请求之前，必须向用户展示下面的原文并等待明确确认。不要改写、概括或替用户默认确认：

```yaml
question: "音色克隆需要您确认以下声明，请确认后继续:"
options:
  - label: "确认并继续"
    description: "我确认并保证: 1）我拥有该音频的合法使用权并已获得音频中说话人的授权，从而有权继续进行音色克隆操作；2）克隆生成的结果仅用于合法用途"
  - label: "取消"
    description: "我不确定是否有授权，取消操作"
```

用户取消、拒绝或表达不确定时，立即停止，不读取、预处理、上传或克隆音频。

## 2. 本地前置检查

确认后再检查：

- 文件存在且扩展名为 `.mp3`、`.m4a` 或 `.wav`。
- 文件不超过 20 MB。
- 主参考音频时长不少于 10 秒且不超过 5 分钟。
- 可选 `prompt_audio` 必须小于 8 秒且不超过 20 MB；它用于增强稳定性，不能替代主参考音频。

使用本地 `ffprobe` 检查时长；不要修改用户原始文件。脚本会再次校验这些条件。

若音频不符合限制，使用本地临时目录通过 `ffmpeg` 生成准备文件：

- 少于 10 秒：循环至至少 10 秒，并输出为 mp3。
- 超过 5 分钟：优先在 300 秒前最后一个静音点裁切；没有合适静音点时，在 295 秒开始 5 秒淡出并裁切到 300 秒。
- 超过 20 MB：重新编码为合理码率的 mp3。

准备文件只放在系统临时目录，测试结束后清理；不要写入 `workspace/`、skill 目录或 CAS。

## 3. 确认试听和请求参数

在发起真实请求前确认以下信息：

- `voice_id`：用户提供时验证其长度为 8–256、首字符为英文字母、只含字母/数字/`-`/`_`，且末字符不能为 `-` 或 `_`；用户未提供时由脚本生成唯一 ID。
- 试听文本：若要试听，确认文本后通过 `--text` 传入，最多 1000 字符。MiniMax 会按 TTS 规则计费；不需要试听时使用 `--no-demo`。
- 模型：默认 `speech-2.8-hd`。
- `need_noise_reduction` 和 `need_volume_normalization`：只有用户选择需要时才打开。
- 已知参考音频逐字稿时，可通过 `--text-validation` 传入，最多 200 字符，并使用 `--accuracy`（默认 0.7）做 ASR 相似度校验；不要猜测逐字稿。
- 已提供独立的短示例音频和对应逐字稿时，才使用 `--prompt-audio` 与 `--prompt-text`。
- 已知语言时可传 `--language-boost`，例如 `Chinese`、`Chinese,Yue` 或 `auto`；未知时不要擅自标注语言。

## 4. 执行本地适配器

只通过技能内脚本执行真实 API 请求。API key 必须来自环境变量 `MINIMAX_API_KEY`；可用 `MINIMAX_API_BASE_URL` 覆盖默认的 `https://api.minimaxi.com`。不要在命令行参数、日志或回复中打印 key。

有试听时：

```powershell
python "<skill_dir>\scripts\minimax_voice_clone.py" `
  --audio "<prepared_audio>" `
  --text "<confirmed_demo_text>" `
  --model speech-2.8-hd `
  --legal-confirmed
```

无试听时：

```powershell
python "<skill_dir>\scripts\minimax_voice_clone.py" `
  --audio "<prepared_audio>" `
  --no-demo `
  --legal-confirmed
```

需要降噪或归一化时分别追加 `--need-noise-reduction`、`--need-volume-normalization`。脚本先上传主文件并取得 `file_id`，再调用 `/v1/voice_clone`；失败时不要盲目重复克隆同一音频，先根据错误修正参数。

## 5. 处理响应和安全结果

向用户返回：

- `voice_id`、主文件 `file_id`、模型和音频检查结果。
- `demo_audio` 链接（如果请求了试听）。试听链接为空不代表克隆失败，应查看 `base_resp`。
- `input_sensitive_type` 非零时，明确告知风险标记，不要把该音色当作正常结果继续使用；等待用户决定。
- 说明 MiniMax 快速复刻音色若 7 天内没有正式用于 TTS，可能会被删除；需要长期使用时及时调用正式语音合成接口。

不要自动把 voice_id 写入记忆、数据库或 `workspace/`。只有用户另行明确要求保存时，才使用用户指定的存储方式，并避免保存原始音频副本。

## 6. 本地验证模式

修改技能或排查配置时，可在取得授权后使用 `--dry-run`，它只做本地音频校验和请求计划输出，不上传文件：

```powershell
python "<skill_dir>\scripts\minimax_voice_clone.py" `
  --audio "<audio>" `
  --text "<confirmed_demo_text>" `
  --dry-run `
  --legal-confirmed
```

不要用 `--dry-run` 冒充真实克隆测试；真实测试必须检查上传和 `/v1/voice_clone` 的返回结果。

## 反面模式

- 不得跳过或代替用户完成授权确认。
- 不得把本地路径直接当作 MiniMax 的 `file_id`；必须先走文件上传接口。
- 不得把小于 10 秒、超过 5 分钟或超过 20 MB 的主音频直接上传。
- 不得把试听文本或 `text-validation` 当作参考音频的逐字稿来猜测。
- 不得在命令行、日志、skill 文件或结果文件中暴露 `MINIMAX_API_KEY`。
- 不得因网络错误、参数错误或敏感标记自动重复克隆同一音频。
