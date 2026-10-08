---
name: comfy-yue2-executor
description: 由 Canvas worker 执行已确认的本地 YuE2 旋律翻唱快照，通过 SheetSage2 提取旋律并回填真实 FLAC。用于执行适配和诊断，不编写歌词，不从对话另行提交。
---

# 本地 YuE2 旋律翻唱

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。`audio` 节点选择 `comfy-yue2-music` / `yue2-3b` / `cover`，由画布 worker 启动 `scripts/execute.py`。使用官方本地 Comfy MCP、共享资源与机器锁，冻结输入后单次提交，监控原任务并回填 FLAC；失败或未知不自动重提。

一份参考歌曲接 `reference_audios`，音乐风格放 `prompt`，实际匹配歌词放 `options["comfy-yue2-music"].lyrics`。最长时长是生成上限；不得把角色名或编曲说明当作歌词。模型须预先准备：`checkpoints/yue2_3b_int8_convrot.safetensors` 和 `audio_encoders/sheetsage2_bf16.safetensors`。adapter 不下载安装或替换模型。

本能力按本机原生 Music Cover 工作流执行：参考音频 → SheetSage2 melody ABC → YuE2GenerateMusic → 音频扩散与解码。参考传递的是自动识别的旋律，参考歌手音色和原伴奏不会直接传递。ABC 的识别错误会影响翻唱，生成后的原任务预览可用于核对乐谱。

风格中的独唱、合唱或女团描述是软条件，不支持固定歌手身份、音色克隆、指定人数的独立干声、精确长度或逐词对齐保证。实际结果保留 `INCONCLUSIVE` 听审状态；不能用技术成功证明五人可辨或口型同步。后续 MV 必须从实际采用音频重新建立时间轴。

当前 Comfy-Org YuE2 权重采用 CC BY-NC 4.0；本地非商用试听应符合用户已确认的用途，商用需另行核实许可。原生参考：[Comfy-Org YuE2](https://huggingface.co/Comfy-Org/YuE2)、[官方翻唱说明](https://github.com/multimodal-art-projection/YuE/blob/main/docs/covers.md)。

多人项目的完整候选与轮唱混音由 [music-video-creator](../music-video-creator/references/multi-singer-workflow.md)规划：每份完整翻唱保留独立真实 run，不用短片拼成伪完整翻唱。执行器不绑定角色或保证 N 人；来源中选用的乐句与最终混剪分别听审，后期沿用原曲伴奏和时间轴。
