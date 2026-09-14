---
name: mimo-video-understanding
description: 用 MiMo 分析视频中的内容、动作和时间顺序，支持本地文件或视频 URL。用于视频观察和证据提取；模型描述不直接作为内容验收结论。
---

# MiMo 视频观察

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。只分析用户指定的视频和问题，不生成视频。观察结论可能有误，不能称为真实标注或保证无幻觉。

## 输入与限制

需要视频路径或可访问 URL、明确的观察问题，以及环境变量 `MIMO_API_KEY`。密钥只从环境读取，不打印。用户已要求分析且输入可用时直接执行。

- 每次处理一个视频；格式为 MP4、MOV、AVI、WMV。
- 本地文件自动转 Base64，编码后不超过 `50 * 1024 * 1024` 字符（原文件约 37.5 MB）。URL 方式按当前供应方限制，文档上限 300 MB；不能借 URL 方式假定超限视频一定可用。
- 超限时说明缺口，按已有授权压缩/截取副本或使用已有可访问 URL；不改原文件、不擅自公开上传。
- 默认接口 `https://api.xiaomimimo.com/v1/chat/completions`；可由 `MIMO_VIDEO_BASE_URL` 或 `--base-url` 指定 base URL/完整接口 URL。

## 执行

使用项目解释器和本 Skill 的 [scripts/mimo_video.py](scripts/mimo_video.py)。从项目根目录运行：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/mimo-video-understanding/scripts/mimo_video.py --video "<video-path-or-url>" --prompt "按时间顺序简述主要动作、关键接触和最终状态，标注大致秒数；看不清的地方明确说未知。" --fps 2 --media-resolution default --max-tokens 1500 --output "<result-path>"
~~~

`--output` 可省略；保存时遵守项目产物目录规则。

| 参数 | 默认值与用途 |
| --- | --- |
| `--model` | `mimo-v2.5`；也支持 `mimo-v2-omni`，沿用用户选择 |
| `--fps` | 2.0，允许 0.1–10；动作较快才提高采样 |
| `--media-resolution` | `default`；需要辨认局部细节时可用 `max` |
| `--max-tokens` | 脚本默认 1024；短描述可用 1500，按输出需要调整 |
| `--thinking` | `disabled`；只有 `mimo-v2.5` 支持 `enabled` |

先用短问题获取相关观察，不把整章剧本、长评分表和执行日志一起发给模型。验收或对位任务由调用方用这次观察对照既定要求，通常不再调用 MiMo 评分；只有用户要求评分时才输出分数。

## 返回与一次复核

返回观察摘要、时间位置和看不清的事实；需要留档时提供实际结果路径。声音结论只能来自实际音频或用户提供的音频证据，截图和无声输入不能推出对白、停顿或音画同步。模型描述可辅助定位，关键事实仍要结合实际视频核实。

`--max-tokens` 是输出上限，不是上下文容量。视频、提示词、推理与输出都可能影响预算；不能仅凭一次 `finish_reason=length` 断言具体原因。报错、空输出或截断不能作为有效证据。有明确的长度或输入问题时，可在现有分析授权和预算内精简问题、降低采样或调整输出上限，复核一次；仍失败就报告，不连续试错或静默换模型。
