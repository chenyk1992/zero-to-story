---
name: mimo-video-understanding
description: 用 MiMo 2.6 Pro 或 Flash 分析音频、歌曲和视频，支持本地文件或 URL。用于声音、音乐段落、视频动作与时序的观察和证据提取；不生成媒体，不把模型观察直接作为内容验收结论。
---

# MiMo 音频与视频观察

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。分析用户指定的音频或视频及其问题，不生成媒体。保留 `mimo-video-understanding` 名称和脚本路径以兼容既有视频调用；两种输入共用请求与结果处理。观察结论可能有误，不能称为真实标注或直接听审。

## 输入与限制

需要媒体路径或可访问 URL、明确的观察问题，以及环境变量 `MIMO_API_KEY`。密钥只从环境读取，不打印。用户已要求分析且输入可用时直接执行。

- 每次处理一个音频或一个视频，`--audio` 与 `--video` 互斥。音频格式为 MP3、WAV、FLAC、M4A、OGG；视频为 MP4、MOV、AVI、WMV。
- 本地文件自动转 Base64，编码后不超过 `50 * 1024 * 1024` 字符（原文件约 37.5 MB）。脚本把本地文件编码为 data URL：音频写入 `input_audio.data`，视频写入 `video_url.url`，不需要公开上传本地文件。远端输入接受公网 HTTP(S) URL；CLI 不直接接收已有 data URL。
- URL 方式按供应方限制：音频上限 100 MB，视频上限 300 MB。脚本不下载远端文件检查大小，不能借 URL 假定超限文件一定可用。
- 超限时说明缺口，按已有授权压缩/截取副本或使用已有可访问 URL；不改原文件。音乐分析保留需要判断的音色和声道，不默认转为低采样率单声道。
- 默认接口 `https://api.xiaomimimo.com/v1/chat/completions`；视频沿用 `MIMO_VIDEO_BASE_URL`，音频使用 `MIMO_AUDIO_BASE_URL`；`--base-url` 优先于对应环境变量，可指定 base URL/完整接口 URL。

## 执行

使用项目解释器和本 Skill 的 [scripts/mimo_video.py](scripts/mimo_video.py)。从项目根目录运行。既有视频命令保持可用：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/mimo-video-understanding/scripts/mimo_video.py --video "<video-path-or-url>" --prompt "按时间顺序简述主要动作、关键接触和最终状态，标注大致秒数；看不清的地方明确说未知。" --fps 2 --media-resolution default --max-tokens 1500 --output "<result-path>"
~~~

歌曲或其他音频使用真实音轨直接分析：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/mimo-video-understanding/scripts/mimo_video.py --audio "<audio-path-or-url>" --model mimo-v2.6-flash --prompt "依据实际音频，简述人声、主要音色、段落变化和结尾，标注近似时间；听不清的词和不能确定的判断明确保留未知。不要逐段转录全部歌词。" --max-tokens 1500 --output "<result-path>"
~~~

`--output` 可省略；保存时遵守项目产物目录规则。

| 参数 | 默认值与用途 |
| --- | --- |
| `--model` | 默认仍为 `mimo-v2.6-pro`；音频和视频均支持 `mimo-v2.6-flash`。既有 `mimo-v2-omni` 仅保留视频兼容入口；不自动换模型 |
| `--fps` | 仅视频，默认 2.0，允许 0.1–10；动作较快才提高采样 |
| `--media-resolution` | 仅视频，默认 `default`；需要辨认局部细节时可用 `max` |
| `--max-tokens` | 脚本默认 1024；短描述可用 1500，按输出需要调整 |
| `--thinking` | 默认 `disabled`；Pro 和 Flash 均支持 `enabled`。旧 Omni 不发送该参数，也不接受显式启用 |

先用短问题获取相关观察，不把整章剧本、长评分表和执行日志一起发给模型。音乐首次观察可只提供实际音频，减少原歌词和编曲说明的引导；需要核对唱词时再提供原文，区分听辨结果与参考文本。精确转写可另用已核实的 ASR 能力，转写不替代音乐观察。验收或对位任务由调用方用这次观察对照既定要求，通常不再调用 MiMo 评分；只有用户要求评分时才输出分数。

## 返回与一次复核

返回观察摘要、近似时间位置和未核实项；需要留档时提供实际结果路径，说明所用模型和媒体版本。歌曲可关注人声、可辨乐器、说唱/歌唱转换、段落反差及结尾；不把模型猜测的精确 BPM、和弦或单词当成测量结果。声音结论只能来自实际音轨或用户提供的音频证据，截图和无声输入不能推出对白、停顿或音画同步。

模型观察是辅助证据，不能称为主会话亲自听见，也不自动改写 Canvas 接受状态。关键事实仍结合实际音视频或用户听审核实。视频需要单独检查声音时，按授权提取保留原时间关系的音轨副本，并记录片段起点。

`--max-tokens` 是输出上限，不是上下文容量。媒体、提示词、推理与输出都可能影响预算；不能仅凭一次 `finish_reason=length` 断言具体原因。脚本只保存正常结束的最终正文，排除独立推理字段及混入正文的 think 标签内容；报错、空输出、非正常结束或截断不覆盖已有结果，也不能作为有效证据。有明确的长度或输入问题时，可在现有分析授权和预算内精简问题、调整输出上限，或针对有关片段复核一次；视频可按需降低采样。仍失败就报告，不连续试错或静默换模型。

## 官方依据

2026-10-01 核实：[音频理解](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/multimodal-understanding/audio-understanding)与[视频理解](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/multimodal-understanding/video-understanding)均列出 Pro 和 Flash；两者的[深度思考](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/deep-thinking)都支持 enabled/disabled。接口支持不等于已核实当前账户可用性，也不保证音乐判断准确。
