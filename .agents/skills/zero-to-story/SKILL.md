---
name: zero-to-story
description: 从灵感或小说完成故事设计、故事板概要、角色设定图、黑白分镜、经用户确认的 Panel 级视频提示词，并交付给 LFO Runtime 执行视频生成。适用于从零分镜、故事分镜创建、短剧创作、小说改视频；已有剧本也可从故事板阶段开始。触发词包括：从零分镜、从零创建分镜、故事分镜创建、从零开始做分镜、零基础分镜、帮我做个分镜、创建故事分镜。
---

# 从零创作并交付视频执行包

将创作与执行分离：本 Skill 负责故事、画面设计、提示词和用户确认；LFO Runtime 负责素材导入、视频生成、字幕、混音和导出。不要直接调用视频 Agent 生成最终片段。

## 工作原则

- 以用户可见、可编辑的 `storyboard_brief.md` 为信息中枢；画布文档存在时同步更新。
- 所有图像由当前平台可用的图像 Skill/Agent 或用户提供素材生成；不固定图片模型或平台。
- 一个黑白分镜板通常可对应一个 Panel，但这是创作策略，不是 LFO 的执行限制。
- 默认无 BGM；只设计对白、环境、动作和空间声。用户明确要求后才添加音乐意图或音乐素材。
- 用户每次编辑故事板或视频提示词后，重新读取最新版本再继续。
- 绝不向 LFO 写入 SQLite、ComfyUI 节点、模型路径或内部素材 ID；只交付文件路径、素材语义和明确绑定规则。

## 阶段 0：理解输入

读取用户的小说、剧本、参考图或视频，提取：故事核心、角色、场景、情绪推进、目标时长、比例和视觉风格。

没有剧本时，一次性询问故事类型、角色、场景、一句话故事、时长和视觉风格；不要逐题阻塞。然后给出结构化摘要供用户修订。

## 阶段 1：故事板概要

创建或更新 `storyboard_brief.md`，至少包含：

- 项目信息：类型、时长、比例、风格。
- 故事梗概、情绪弧线、Medium Lock、Style Brief。
- 角色表：完整外貌、服饰、标志动作、关键道具。
- 场景表：空间结构、时间、光线、色调和氛围。
- 分镜表：每个镜头的景别、画面、角色台词和声音设计。

每个画面描述必须写明前中远景、人物左右/深度位置、朝向、关键环境元素和相对距离。每个镜头只承担一个清晰动作或信息转折。

向用户展示故事板概要，并等待确认后才生成视觉资产。

## 阶段 2：角色设定图

用户确认故事板后，每个角色单独生成一张设定图。保持同一角色的正、侧、背视图，包含少量表情/动作变化、标志动作和关键道具；默认没有图片内文字。

读取 [角色与黑白分镜提示词](references/creative-assets.md) 后使用其中的质量约束与提示词结构。记录每张图片的实际输出路径，绝不重命名或移动平台生成的文件。

展示资产清单并等待用户确认。

## 阶段 3：黑白分镜板

确认角色设定后，按故事节奏生成黑白灰的动作预览分镜。默认使用 2×4 网格；后续板第一格复用上一板最后一个动作关键帧，以保持动作连续性。黑白板只表达构图、空间和动作链，不复制角色服装、面部或成片材质。

如目标时长需要更多镜头，先扩写 `storyboard_brief.md`，再生成分镜板。读取 [角色与黑白分镜提示词](references/creative-assets.md) 后使用完整的版式、连续性和负面约束。

展示所有角色图和黑白板路径，等待确认。

## 阶段 4：视频提示词确认

只维护一个 `video_prompt_list.md`。每个 Panel 写一个自然段，而非逐镜头机械拼接，按此顺序组织：

1. 本 Panel 出现角色的统一形象要点。
2. 对应黑白分镜板及其“只参考构图、动作和运动”的用途。
3. 连续的故事动作、情绪推进和自然嵌入的台词。
4. 声音设计：明确 `NO background music`，列出环境、动作、空间声和必要静默。

用户可修改提示词、片段时长、比例、分辨率、声音和输出要求。展示主文档并明确请求确认；确认前绝不执行视频生成。

## 阶段 5：交付给 LFO Runtime

用户确认视频提示词和参数后，读取 [VideoExecutionPackage 交付格式](references/execution-package.md)，将创作结果写为项目目录中的 `execution-package.json`。

每个 Clip 必须包含：

- 已确认的完整视频提示词和时长。
- 实际存在的角色设定图、黑白分镜板、用户素材或音频路径。
- 对每个参考图的 `semantic_usage`、`instruction` 和 `binding`；构图参考通常为 `placement: "last"`。
- 已定时字幕 cue 或外部字幕素材（如有）。
- 输出规格和创作审批信息。

先执行：

```powershell
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
```

将验证错误或计划中的后端/素材警告返回给用户修正。验证和计划无误后，明确展示计划摘要（Clip 数、时长、素材、输出）并再次请求最终执行确认。

得到最终确认后执行：

```powershell
python -m lfo.cli.main execute execution-package.json --approve
```

随后通过以下命令查看、处理和导出：

```powershell
python -m lfo.cli.main status <run_id>
python -m lfo.cli.main retry <run_id> --clip-id <clip_id>
python -m lfo.cli.main review <run_id> <target> approved
python -m lfo.cli.main export <run_id>
```

向用户报告 LFO 返回的 Run ID、每段状态和最终输出路径。需要修改时，修改创作文档或执行包并生成新 revision，不覆盖已批准版本。

## 质量闸门

- 故事板确认后才生成角色设定图。
- 角色设定确认后才生成黑白分镜板。
- `video_prompt_list.md` 确认后才构造执行包。
- `validate` 与 `plan` 无阻塞问题、用户最终确认后才执行。
- 任一素材路径、提示词、时长或绑定关系改变后，重新验证和计划。

## 参考资料

- 需要生成角色图或黑白分镜板时，读取 [角色与黑白分镜提示词](references/creative-assets.md)。
- 需要写入或审阅 `execution-package.json` 时，读取 [VideoExecutionPackage 交付格式](references/execution-package.md)。
