# 部署与试听参考

## 来源与适用版本

准备参数依据 2026-09-14 读取的上游源码；运行时以安装版本和 `/object_info` 为准。

- [Qwen3-TTS 官方模型和音色说明](https://github.com/QwenLM/Qwen3-TTS)：Eric 为四川方言成都男声；1.7B CustomVoice 支持指令控制。
- [插件说明](https://github.com/flybirdxx/ComfyUI-Qwen-TTS)：安装、模型搜索和 attention 选项。
- [节点实现](https://github.com/flybirdxx/ComfyUI-Qwen-TTS/blob/main/nodes.py)及[节点注册](https://github.com/flybirdxx/ComfyUI-Qwen-TTS/blob/main/__init__.py)：核对真实字段与类名。

## 获准安装后的最小范围

1. 确认运行中 ComfyUI 对应的安装目录与 Python，记录依赖版本。项目 `.venv` 与 ComfyUI 的 Python 可能不同。
2. 仅添加 `ComfyUI-Qwen-TTS` 插件，记录取得的 commit。检查 requirements 与当前环境差异后再安装缺失依赖，不直接覆盖 Torch/CUDA。上游 README 指明 transformers 4.57.3 或具有其兼容补丁的 5.x；不能只依据 requirements 中较宽的下限认定兼容。
3. 仅准备 `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` 与其所需 `Qwen/Qwen3-TTS-Tokenizer-12Hz`。先确认仓库布局和实际文件大小，避免一键下载全部模型。插件可能在加载时自动联网下载，启动前核对下载授权。
4. 本次 v1.0.7 源码的加载器只遍历模型根的直接子目录，使用 `models/qwen-tts/<模型名>/`。README 中带 `Qwen/` 的嵌套示例不能直接套用；Tokenizer 检查也使用不带该层的目录。其他版本按其实际加载器核实，不能凭目录名认定已加载。
5. 确认现有任务状态，在可重启时重启 ComfyUI，然后重新检查节点；有目录但无节点时检查导入日志。

Python 兼容性和显存占用由实际导入、加载及短句生成验证。模型文件大小不等于显存需求。首次优先 sdpa，不为加速额外安装 Flash Attention。

## 最小验证

使用 Skill 的 eric-smoke.json 作为参数输入；eric-api.json 是已按实时 schema 检查过的 API 工作流，连接 CustomVoice AUDIO 输出到 SaveAudio，输出 FLAC。SaveAudio 在 ComfyUI 0.35.1 中已标记 deprecated 但仍可用，后续迁移到 SaveAudioAdvanced 时须核实其动态 format 字段。API 工作流不包含 Canvas 冻结运行或提交授权。

先做一段短句，记录生成结果后再决定是否调整指令。单独区分技术成功与四川话听审；无音频时不判断口音质量。正式 Canvas 集成还需要音频节点/能力契约和执行回填支持，不在安装插件时顺手改视频能力。

## 已验证的代表场景

2026-09-14，在用户明确允许直接 ComfyUI 技术试听后，使用上述 API 工作流完成一次生成：Eric、1.7B CustomVoice、Chinese、bf16、sdpa、空 instruct、seed 42。得到 8.24 秒、24kHz、单声道 FLAC；包含初次加载的 ComfyUI 任务耗时约 36.5 秒。此记录只证明该环境的技术链路成功，口音自然度与台词准确性仍待用户听审；不据此承诺其他机器的时长或性能。

当次环境为 RTX 5080 16GB、ComfyUI 0.35.1、Python 3.13.12、Torch 2.12.1+cu130、Transformers 5.14.1，插件自报 v1.0.7。这是 ComfyUI 自有环境；项目脚本仍用项目 Python 3.12。保留现有 onnxruntime-gpu 即可导入，不为 requirements 中的 OpenVINO 变体覆盖它。SoX 可执行文件缺失及未安装 flash-attn 的警告未阻止本次 12Hz CustomVoice + SDPA 路线，不代表其他功能也不需要它们。

本次固定的模型版本为 CustomVoice `0c0e3051f131929182e2c023b9537f8b1c68adfe`、Tokenizer `7dd38ad4e9bad454aae9cd937d0cd577604fe229`。Hugging Face Xet 下载未及时落盘时，终止该次下载进程后，使用同一来源和版本的普通 HTTP 下载完成；没有更换模型。
