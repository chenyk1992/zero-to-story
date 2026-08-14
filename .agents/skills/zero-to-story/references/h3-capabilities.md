# H3 能力核验记录

本文件只记录易变的能力、入口和本地运行时事实。它不是提示词写作规则；只有使用特殊入口或遇到能力冲突时按需读取。所有条目都必须带来源和最后核验日期，不把推测写成保证。

最后核验日期：2026-08-13（Asia/Shanghai）。

## 本地 LFO backend

| 能力/事实 | 当前核验结果 | 来源 | 最后核验 |
|---|---|---|---|
| prompt 传递 | `generation.prompt` 被映射到本地 H3 工作流 | `src/lfo/backends/comfy_h3.py` 的工作流参数映射 | 2026-08-13 |
| negative prompt | 当前 backend 不消费 `generation.negative_prompt`；不能依赖它控制画面 | 同上，检索 generation 参数映射；`references/execution-package.md` 说明 | 2026-08-13 |
| 参考图槽位 | 执行包使用固定 `ref_image_N` 槽位，Prompt 的图片编号从 1 映射到 N-1 | `references/execution-package.md` 与 LFO package 契约 | 2026-08-13 |
| 单段时长 | 本 Skill 的交付策略要求 4–15 秒；实际工作流可能在帧网格上对齐 | `references/h3-prompts.md`、`references/execution-package.md`；本地 workflow 适配 | 2026-08-13 |

## 特殊模式按需核对

当用户明确使用以下模式时，先核对当前 backend/工作流 manifest 和真实运行结果，再决定 PromptControlPlan 的引用语义：

- 纯文生视频：没有图片引用，必须把主体、空间、动作和媒介写具体。
- 图生视频：明确引用是首帧、尾帧或单一状态参考；两张首尾帧不自动等于一次硬切。
- 混合多模态：逐项说明图片、视频、音频参考控制的维度；不要仅按上传顺序猜用途。
- 已有视频编辑、严格首帧/尾帧：把它计入复杂度分数，并确认当前工作流真的消费该输入。
- 音频或 TTS：确认当前入口的音频字段、语言和时长支持后再写入，不把历史手册的语言列表当作永久能力。

## 更新规则

1. 能力变更时更新表格中的来源、结果和最后核验日期。
2. 若本地代码没有消费某字段，不在执行包、workflow 或节点中虚构该能力。
3. 稳定的创作规则留在 `h3-prompts.md`；本文件只保留会随 backend、模型或入口变化的事实。
4. 能力未知时降低假设、加入校验或停止执行，不能用“官方支持”作为替代证据。
