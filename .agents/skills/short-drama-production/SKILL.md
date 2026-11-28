---
name: short-drama-production
description: 短剧四阶段端到端制作：从题材与分集大纲/剧本（含出海改编），到角色定妆与状态递进参考、空间四视图场景参考、关键道具与状态参考，再到防跳切分镜规划、片段提示词与单集成片合成。适用于微短剧快速建项与全流程推进；深度多集编剧可协同 short-drama-screenwriter，复杂导演与节点生成经 zero-to-story、h3-prompt-writing 和 canvas-workspace 执行。
---

# 短剧四阶段制作

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)与[项目数据边界](../../../AGENTS.md)。

本 Skill 提供从「大纲与剧本 → 角色/场景/道具三类含状态递进的视觉参考 → 防跳切分镜与连续片段提示词 → 视频生成与单集成片合成」的紧凑四阶段短剧制作流程。用户只要求其中某一阶段（如只要大纲剧本、只要角色/场景/道具参考规划或只要分镜提示词）时，完成该阶段即停，不擅自启动未授权的媒体生成。

## 与项目现有短剧/影视链的协同

- **与编剧、资产、导演 Skill 的分工与互用**：
  - 用户需要紧凑的四阶段短剧全流程推进，或需要建立**角色受伤/换装等状态递进参考**、**同一空间 2×2 四视图空场景参考**、**关键道具及状态参考**和**跨生成段防同角度跳切分镜**时，使用本 Skill（相关设定规范也可供 [visual-design-creator](../visual-design-creator/SKILL.md) 与 [zero-to-story](../zero-to-story/SKILL.md) 复用）。
  - 需要深度多集连载开发、独立情景喜剧创作或 `.short-drama/{drama_title}/` 完整编剧工程时，可协同 [short-drama-screenwriter](../short-drama-screenwriter/SKILL.md)；需要复杂镜头调度或分阶段成片盲审时，可协同 [zero-to-story](../zero-to-story/SKILL.md)。
- **唯一画布生产入口与数据边界**：
  - 阶段 2 的角色/场景/道具参考图、阶段 3–4 的视频片段与配乐/语音生成，均遵守项目三项关键硬门（生成模式选择、跨段同镜连续的 `ACCEPT` 真实尾帧绑定、声音/对白方案），通过项目唯一生产入口 [canvas-workspace](../canvas-workspace/SKILL.md) 保存节点并在页面确认或对话明确授权后执行（单 Panel H3 提示词可协同 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) 定稿）。
  - 文本剧本按需保存在 `.short-drama/<剧名>/` 或 `workspace/projects/<project_id>/`，运行产物与合成后的单集成片保存在 `workspace/projects/<project_id>/final/`。

## 阶段 1：剧本

1. 参考 [短剧题材参考](references/short-drama-genres.md) 将用户设定与合适的参考结合，出海短剧再读取其中的「出海改编」小节（多语对白细节也可按需参考 [语言适配](../short-drama-screenwriter/references/overseas-dialogue.md)）。
2. 直接给出创作大纲，包括但不限于：剧名、一句话故事、主要转折、结局方向，多集时含分集大纲。
3. 依据大纲，参考 [短剧剧本参考](references/short-drama-script.md) 制作场景级剧本。

## 阶段 2：角色、场景与道具参考

- 按 [角色参考](references/character-reference.md) 为露脸的主要角色建立通用定妆图（默认 16:9 横版，含正面、侧面、背面全身三视图及面部近景）；外观随剧情持续变化（如不同受伤等级、换装、湿透脏污、年龄跨度）时，以通用定妆图为基础为每个状态另做状态参考并标注适用场次。
- 按 [场景参考](references/scene-reference.md) 为跨镜头复用的地点建立空间参考（多方向复用时可采用同一空间的 2×2 四视图干净空场景，以固定物锚定方位）。
- 按 [道具参考](references/prop-reference.md) 为跨镜头复用、有特写或会发生状态变化（如碎裂、染血、打开前后）的剧情关键道具建立道具参考与状态参考。
- 需要生成参考图时，将提示词与参数写入 [canvas-workspace](../canvas-workspace/SKILL.md) 图片节点，经确认授权后生成并核验一致性。

## 阶段 3：分镜与片段提示词

- 按 [分镜规划与片段提示词](references/storyboard-planning.md) 制作分镜表；跨生成段的上一段末镜与下一段首镜避免同一人物同角度直切，用有剧情依据的听者反应、道具特写或场景全景过渡。
- 按其中「片段提示词」模板，为每个生成单元带入角色、场景与道具参考（写明各自提供角色外观/当前状态、空间陈设或道具状态，不把多视图排版带入画面），台词逐字沿用剧本。
- 提示词可直接写入当前画布（[canvas-workspace](../canvas-workspace/SKILL.md)）视频节点草稿或协同 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) 定稿，不另建冗余的独立提示词文档。

## 阶段 4：视频生成与合成

- 在画布节点确认或用户明确授权后执行视频片段生成；按实际采用（`ACCEPT`）的视频片段及分镜表顺序合成为单集成片（输出至 `workspace/projects/<project_id>/final/`）。
- 粗剪审片遇到重要角色的小脸影响身份辨认或表情阅读时，执行 Agent 按[局部修脸交接](../canvas-workspace/references/creative-handoff.md#粗剪审片中的局部修脸)使用本批明确授权，支持单人（`solo`）与双人（`duet`）及长镜头同镜窗偏移，审过候选后再纳入剪辑。
- 片段生成阶段只保留角色对白、环境声、动作声和拟音；用户需要配乐或字幕时，可通过 `python -m lfo.media.story_edit` 使用 `lfo.story.preview.v1` 做有声故事板预演，或使用 `lfo.story.edit.v1` 按实测时长节奏完成原声接缝过渡、J/L-cut、混音避让、响度对齐与字幕烧录，输出最终成片。

## 能力边界

如有不属于本 Skill 的其他需求（如独立品牌广告、独立歌曲 MV、热点采集与抖音发布），按 [Skill 路由](../../../guides/ai-skill-routing.md) 选择对应主责 Skill。
