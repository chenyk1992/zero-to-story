---
name: zero-to-story
description: 将灵感、小说、剧本或短剧交接转成影视故事板、角色与必要视觉资产，结合内容推荐或继承整体风格，再按Panel交给H3和Canvas。用于影视剧、叙事短片及其局部导演任务；完整广告交advertising-creator，独立歌曲/MV交music-video-creator。
---

# 故事到分镜与视频交接

遵守[项目共享生产规则](../../../guides/ai-system-prompt.md)。把本次范围写成观众能经历的故事，再设计镜头、准备资产并交接生产；交付到用户要求的阶段。

## 先判断当前任务

影视故事的多阶段任务先读[分阶段协作](references/story-collaboration.md)：在当前同一宿主内按主做、审核、监督、代理分工，阶段执行者只接收所需材料。按当前阶段选用[导演与审核提示词](references/story-collaboration-prompts.md)，不一次加载所有角色。单次局部咨询、研究或措辞修改不启动整套生产协作。

读取已有创作源和用户规格：剧情、目标时长、画幅、画风、对白/声音、交付阶段。复用已有决定；只在关键事实缺失或冲突时集中说明缺口。主会话负责导演选择，下游按确定的事实写提示词和执行。

新故事或全片方案先按[整体风格推荐与继承](references/style-selection.md)提出适合内容与观看目标的方向，已有风格直接深化。题材/世界、媒介美术与气质组合成作品方向，反转、表演、时间效果和运镜在具体场面落实。局部任务继承当前作品决定。

视频制作按[制作规格与判断依据](../../../guides/ai-system-prompt.md#制作规格与判断依据)在故事板与蓝图 `user_constraints` 记录目标时长、画幅、生成参数、声音、导出要求及选值依据，H3 和 Canvas 继承；文本任务完成相应创作范围。

有人物连续性时，拆 Panel 前按[固定人物文字](references/creative-assets.md#人物与场景文本锚点)识别整场出场主体，覆盖跨镜配角、旁观者和背影，补齐必要设计并沿用 ID/造型。文字锚点与角色图按实际控制用途选择。

| 当前交付 | 读取时机与资源 |
| --- | --- |
| 影视中的身份设计/必要资产 | 委托[视觉资产](../visual-design-creator/SKILL.md)，按[身份适配](references/character-identity-design.md)沿用cast ID/阶段；独立资产请求止于专能 |
| 情景喜剧分镜 | 读[喜剧导演](references/sitcom-direction.md)；缺剧本时由编剧层确定因果 |
| 影视片头、片名揭示或开场卡司 | 委托[标题序列](../title-sequence-creator/SKILL.md)限定片头，回本故事主源；完整预告仍由本入口统筹 |
| RPG/游戏电影化、探索/战斗/跑酷与HUD状态 | 按需读[游戏导演](references/game-cinematic-direction.md)，仅补创作与状态交接；宣传广告回广告，歌曲驱动回MV |
| 完整广告或独立宣发广告 | 交[advertising-creator](../advertising-creator/SKILL.md)主责；广告复用本目录导演方法 |
| 反转、身份揭示或误判的导演信息安排 | 按需读[通用反转](../short-drama-screenwriter/references/reversal-design.md)，保留导演真相和观众获知窗口 |
| 慢动作、冻结、子弹时间或 bullet-time-slow-motion-video 项目方法 | 读[时间效果导演](references/time-effects-direction.md)，写回现有 Setup、状态和声音字段 |
| 对称复古童话式短片或风格图 | 读[对称童话风格](references/symmetric-storybook-style.md)，保留用户画幅、媒介与颜色 |
| 参考片改编/受控复刻 | 接收[变更交接](../video-deconstruct-analyzer/references/recreation-change-plan.md)，采用用户方式并记入当前简报 |
| 参考作品研究、选题或改编依据 | 按需读[参考研究](references/reference-research.md)，研究成果返回当前主源 |
| 历史、科普或知识解说稿 | 委托[narration-writer](../narration-writer/SKILL.md)完成事实与旁白；影视重现由本入口统筹，MG/B-roll/Presenter 保留专业范围 |
| 剧本、改编与叙事声音 | 读[剧本与改编层](references/script-adaptation.md)；已选旁白与对白混合时按需读[混合叙事](references/mixed-narration-direction.md)，再进入故事板设计 |
| 故事板与导演设计 | 读[故事板与导演工作台](references/storyboard-production.md)，需要把事件发展成具体拍法时读[镜头表现示例](references/expressive-direction.md)，填字段时查[故事板结构](references/storyboard-brief.md) |
| 只修改某个 Panel 的拍法 | 读[局部改拍](references/storyboard-production.md#局部改拍)，依据当前创作源修改，保留未受影响的剧情、对白和 ID |
| 下一集复用人物，或角色有别名、年龄与服装变化 | 读[角色身份与造型复用](references/creative-assets.md#角色身份与造型复用)，先匹配故事身份，再选择本镜适用的资产 |
| 宫崎骏／吉卜力启发的手绘动画，或未来科幻短片与参考图 | 按需读[视觉风格参考](references/visual-style-profiles.md)的对应分支，将具体美术规则写回风格与资产字段；项目采用方法涵盖 miyazaki-inspired-animation / future-sci-fi-cinematic-generator |
| 都市赛璐璐 / City Pop 或中式仙宫空间的风格设计 | 读同一[风格参考](references/visual-style-profiles.md)的对应分支，落实运动、空间和声音；按当前作品范围交付 |
| 风格化3D、国漫块面或带绘画表面的3D | 读同一参考的[3D分支](references/visual-style-profiles.md#风格化3d与混合叙事)，声音分工另按混合叙事 |
| 细化当前镜头的动作或表演 | 仅按需要读[动作导演参考](references/action-direction.md)或[表演导演参考](references/performance-direction.md)，再写回已有的 Setup、状态与转场字段 |
| 多人、反打、出入口、遮挡或复杂走位 | 读[复杂场面调度](references/blocking-direction.md)，稳定场景位置后再转为各机位画面关系 |
| 为已锁定画面制作配乐 | 保持本故事流程，只复用[音乐方向的锁定画面分支](../music-video-creator/references/music-direction.md#锁定画面配乐)，保留画面、对白与动作时点 |
| 完整故事生产的结构化蓝图 | 从故事板编译时读[创作蓝图](references/creative-blueprint.md) |
| 角色图、分镜板、关键帧 | 只在准备相应资产时读[视觉资产](references/creative-assets.md) |
| 单 Panel 提示词和生成交接 | 输入准备好后读[Panel 交接](references/panel-execution.md)，调用 [h3-prompt-writing](../h3-prompt-writing/SKILL.md) |
| 实际结果验收或成片 | 结果可用后读[视频验收](references/video-qc.md) |

## 创作与交付步骤

1. **先写成立的戏，再设计镜头。** 小说或梗概先按[场景剧本](references/script-adaptation.md#从故事到场景剧本)发展观看价值、人物目标、阻力、选择和后果，完成当前范围的场景稿与一次针对性修订。已有可拍剧本直接继承；局部改拍从采用稿取事实。按[交流、停顿与呼吸](references/performance-direction.md#交流停顿与呼吸)安排接话与反应，按[连续场景分段](references/storyboard-production.md#连续场景的分段)保护完整动作、对白、句尾和声音关系。
2. **记录可执行计划。** 使用[故事板模板](assets/storyboard_brief.template.md)保存创作正文；`creative_blueprint.json` 按 [v2 规范](references/creative-blueprint.md)编译结构化索引。局部交付使用相应范围。
3. **准备必要资产。** 完整蓝图先做静态预检，按报错修正后复核。按[角色图用途](references/creative-assets.md#角色设定图)决定复用、新建或仅用固定文字；已决定制作[完整设定图](assets/character_card_prompt.template.md)时保留三视图与半身变化规格。分镜板和关键帧按当前 Panel 控制需要准备，`planning_only` 保持规划用途。实际资产做一次用途检查。
4. **写提示词并交接。** 将已确定的单 Panel 事实交给 H3 Skill，把返回提示词与素材、参数原样交给 [canvas-workspace](../canvas-workspace/SKILL.md)。每个 Panel 对应一个视频节点。已有授权覆盖时按共享规则执行；只要草稿时停在保存。
5. **处理实际结果。** 按视频验收做一次结论。下游需要精确首帧时，才从已接受视频提取真实尾帧。用户要求完整成片或先做有声故事板预演时，可使用 `python -m lfo.media.story_edit`（`lfo.story.preview.v1` Animatic 或 `lfo.story.edit.v1` 确定性后期，支持接缝过渡、J/L-cut、混音避让、响度对齐与字幕/净版输出）完成确定性后期和一次最终视听检查。

各引用中的 "STEP 1 / STEP 3" 即上述第 1 步（先写成立的戏再设计镜头，含 operation、布局与资产计划锁定）与第 3 步（准备必要资产）。[创作蓝图](references/creative-blueprint.md)的"编译顺序"是第 1–2 步内部的子流程，编号独立，不与上述步骤对应。

完整故事生产的静态预检命令：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/zero-to-story/scripts/validate_creative_blueprint.py <creative_blueprint.json>
~~~

预检 `FAIL` 先修硬错误，`NEEDS_REVIEW` 由主责判断 warning 的影响，`PASS` 表示静态无发现；JSON `ok` 和退出码只区分是否有 error。完整解释见[编译顺序](references/creative-blueprint.md#编译顺序)，输入变化后检查受影响部分。

## 容易混淆的契约

- 一个 Panel 是一条 4–15 秒 Clip；六个 Beat 是语义时刻，Camera Setup 才对应真实摄影镜头和 H3 Shot。不要为六个 Beat 凑六次动作或切镜。
- 目标总时长等于 Panel 时长合计，Canvas 时长与该 Panel 一致。不采用生成余量后裁切或自动变速凑时长；实际帧对齐微差如实核对交付条件，不擅自修整。
- 继续创作先按[当前版本协调](references/storyboard-brief.md#当前版本协调)核对最新源、Canvas 草稿和冻结快照；“人工源”不表示旧文件覆盖明确的用户新编辑。
- 按[控制方式](references/storyboard-production.md#选择控制方式)选择模式，再按[资产路由](references/creative-assets.md#逐-panel-视觉资产路由)落实布局与素材。
- 生成参数的选值、依据与范围统一按[共享规格规则](../../../guides/ai-system-prompt.md#制作规格与判断依据)记录，交接端继承。
- 当前 Panel 输入齐全即可推进；只有真实依赖前段状态时才等它 `ACCEPT`。准备可并行，视频提交仍串行。
- 连续场景跨 Panel 时，区分同机位续演、换机位与换场；静态角色/场景参考不等于继承实际末态。不得为提前生成而取消真实依赖。相邻片段按[画面与声音接缝](references/video-qc.md#画面与声音接缝)一起检查，单片通过不代表接缝成立。
- 失败与未知按[共享执行规则](../../../guides/ai-system-prompt.md#唯一执行入口)核实原请求，只停止受影响单元及依赖。

## 返回结果

影视中的商品仍可作道具，品牌露出不自动转广告；现有作品局部改动保持原主责。参考[共同交接](../canvas-workspace/references/creative-handoff.md)协调源、文字/时间和采用版本。

交付用户所需的故事板、蓝图、`character_assets.md` 或实际资产路径，并说明尚缺的决定或依赖。文件位置遵守 [AGENTS.md](../../../AGENTS.md)。生产状态以 Canvas 为准；保留原快照与历史媒体，替换片段时只核对受影响的[接缝](references/video-qc.md#替换片段后的接缝)。
