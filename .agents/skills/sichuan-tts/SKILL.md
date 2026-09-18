---
name: sichuan-tts
description: 准备和验证 ComfyUI 中的四川话语音合成，使用 Qwen3-TTS 的 Eric 预置成都男声。用于四川话短句试听与工作流准备；本期不处理音色克隆、训练或视频生成。
---

# 四川话语音合成

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。本 Skill 提供可复用的预检和试听工作流；直接 ComfyUI 技术试听已成功生成音频，尚未接通 Canvas 音频执行能力，不能宣称已能从项目画布生成语音。

## 最小目标

将一段用户确认的短台词生成可试听、可保存的四川话音频。默认使用 `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`、`Eric`、`Chinese`、`bf16`、`sdpa`，风格指令先留空。Eric 是官方标注的成都男声，不代表所有四川地区的方言。

用户已有台词时保留原文；需要改成自然四川话时，先展示改写。未提供台词的首次试用可使用[试听配置](assets/eric-smoke.json)中的示例。时长由实际输出测量，不承诺固定秒数。

## 默认语速

按本项目用户偏好，交付音频默认为原始合成音频的 **1.2 倍语速**，保留音高；用户为本次指定其他倍率时覆盖默认值，指定 `1.0` 则保留原速。此倍率用于合成后的音频处理，不是未经核实的 Qwen 节点参数，也不通过重复添加“快速说话”指令叠加加速。

获取真实原始音频后，用已安装的 FFmpeg 执行一次 `atempo=1.2`，保留原文件并另存无损派生文件。例如在当前项目 outputs 子目录内：

```powershell
ffmpeg -hide_banner -loglevel error -n -i "<原始音频.flac>" -map 0:a:0 -af "atempo=1.2" -c:a flac "<交付音频_speed1.2.flac>"
ffprobe -v error -show_entries format=duration:stream=sample_rate,channels -of json "<交付音频_speed1.2.flac>"
```

试听、交付及下游视频音频参考均使用变速后的实际文件；记录原始路径、派生路径、倍率和两者实测时长。未处理或工具缺失时明确说明，不能将原速文件标为1.2倍速。每次从原始音频派生，避免对已变速文件再次加速。变速后时长约为原时长除以1.2，最终以探测结果为准。

为视频准备台词时，按变速后的真实发声时长加必要表演及句尾余量安排镜头。不要为迁就旧镜头时长擅自将该音频再放慢；本默认值不追溯修改已有采用音轨或成片。[试听配置](assets/eric-smoke.json)的 `postprocess` 是本地后期配置，不传给 Comfy 节点；[API 工作流](assets/eric-api.json)仍只生成原始音频。

## 预检和准备

运行[只读预检脚本](scripts/preflight.py)：

```powershell
./.venv/Scripts/python.exe .agents/skills/sichuan-tts/scripts/preflight.py --comfy-root <实际ComfyUI目录>
```

服务地址可用 `--base-url` 或 `LFO_COMFY_BASE_URL` 指定。脚本只读取 `/system_stats`、`/object_info` 及显式提供的模型目录，不安装、下载、加载模型或提交任务。目录检查只是线索，不证明权重完整；额外模型目录可重复传 `--model-root`。

目标插件为 [flybirdxx/ComfyUI-Qwen-TTS](https://github.com/flybirdxx/ComfyUI-Qwen-TTS)，真实类名为 `FB_Qwen3TTSCustomVoice`，不是 Python 类名 `CustomVoiceNode`。确认实时节点存在，支持 Eric 和所需参数，且输出类型为 AUDIO。保存节点按实时 schema 选择，优先保存无损格式。

安装或兼容问题时读取[部署与验证参考](references/setup.md)。缺少依赖时先给出具体变更清单并核对既有安装授权；生成授权本身不包含外部 ComfyUI 的安装与模型下载。

## 执行边界

项目正式生产须由 Canvas 已接入的音频能力冻结输入并执行；当前 Comfy 视频能力不能代替音频能力，不伪造 capability.json 或把音频登记为视频。

如果用户明确批准脱离 Canvas 的一次 ComfyUI 技术试听，可按其范围验证插件；否则完成准备并说明音频入口缺口。试听配置是参数草稿；[API 工作流](assets/eric-api.json)提供 CustomVoice 到 SaveAudio 的实际连接。执行前依据本次 `/object_info` 检查字段、枚举和保存节点，不能因模板存在就自动提交。

获授权执行后保留单次任务 ID，使用原任务历史核实完成并取得实际音频；状态未知时不盲目重提。产物归入该项目的 outputs 目录，不写 workspace 根目录。

## 验证与交付

技术检查确认文件可读、包含音频、时长大于零，记录实际采样率、时长、模型与参数。试听检查针对最终变速文件，关注错漏字、四川话发音与语调、加速后的清晰度及句尾是否完整。无法实际听审时标记待用户试听，不用 ASR 或音色名称代替听审结论。

交付实际音频与简短结果；一次试听未验证的能力不写成 Skill 的成功经验。用户以后明确要求克隆时再扩展 Qwen3-TTS Base 路线，不自动下载 Base 或 VoiceDesign 模型，也不路由到 MiniMax 克隆。
