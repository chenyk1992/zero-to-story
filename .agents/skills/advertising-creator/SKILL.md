---
name: advertising-creator
description: 创作广告、品牌传播和电商宣传，按需交付概念、文案、静态物料或视频成片。广告自己统筹剧情、音乐与动效表达；独立影视和歌曲/MV分别走原入口，局部专业任务保留原主责。
---

# 广告创作

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。本Skill负责广告目标、事实、创意、导演、主计划与广告验收；H3定稿、Canvas操作、实际执行仍各守原契约。电商属于广告，反转只是可选表现方法，没有独立反转广告入口。

## 当前范围与完成条件

| 请求 | 做什么、何时停止 |
| --- | --- |
| 概念/口号/文案/脚本 | 按当前范围交稿及必要前提，不要求素材、运行参数或画布 |
| 静态宣传/品牌物料 | 广告持有目标与文字，委托资产专能设计，检查所需实际图片即结束，不扩成视频 |
| 视频制作方案/成片 | 自己安排Panel/Shot与时间预算，直接交H3/Canvas，检查实际采用与最终文件 |
| 独立广告主题曲、只要音频 | music-video-creator主责，广告资料是输入，止于音频 |
| 现有影视/MV的局部品牌修改 | 保持原作品主责，只处理授权范围；独立电影宣发广告为新广告交付 |
| 中立产品说明/已定单Panel提示词 | 明确专业MG/Presenter/B-roll/H3请求按原范围，不因有产品机械广告化 |

广告采用歌曲时只委托音乐创作并接收实际采用音频，整支广告主责不转MV。影视配乐同理归影视统筹。混合目标确实影响当前交付且未明确时，只问归属缺口。

## 视频广告入口的制作规格

视频制作任务先在本入口询问投放平台、目标时长、画幅、原生生成规格、声音与交付要求，用户可以自定义。本地 H3 需明确选择 `megapixels`、`sampler_profile`（`vdn_turbo` / `native`）与 `steps`；其他提供方按实际能力给出选项。推荐可说明速度与画质取舍，但不能自动采用模板、历史广告或推荐的参数。只有创意自主权时，仍需确认制作规格；用户明确委托决定制作规格时，记录授权和实际选值。

当前请求已有明确值时只补缺口；同一广告后续 Panel 继承本次确认，不逐镜重问。把值、用户确认依据和适用范围写入 `ad_plan`，分开记录原生生成与最终导出规格。已有参数缺少确认依据时先核对，尚未选择或委托的规格不提交生成；后续变更只同步受影响草稿，旧快照保留。概念、文案、脚本和静态物料按原交付范围，不收集无关的视频执行参数。

## 创作与按需路由

1. 接收产品/品牌资料、受众/目的、范围、用户语言/时长/画幅/媒介/声音及露出策略。事实、条件、观察与未知分开；照片不证明功效、折扣、价格或活动。只问影响当前结果的缺口。
2. 按[广告导演](references/ad-direction.md)选适合目的的表达。用户仍在开放构思且没有定路线/场景时，才按需提出少量不同方向；已有故事、脚本或明确方向时沿用，不重复发散。产品驱动剧情读[产品因果](references/product-causality.md)，反转读[通用方法](../short-drama-screenwriter/references/reversal-design.md)，喜剧按需读[喜剧写作](../short-drama-screenwriter/references/sitcom-writing.md)，不强制反转/人物/CTA/音乐。
3. 唇妆读[美妆](references/beauty-product-direction.md)，服装读[时装](references/fashion-direction.md)；身份/IP/产品/版式委托[静态资产](../visual-design-creator/SKILL.md)。人物按[固定文字与跨模式规则](../zero-to-story/references/creative-assets.md#人物与场景文本锚点)记录在ad_plan，含跨镜配角；确需完整角色图时才用[统一设定图模板](../zero-to-story/assets/character_card_prompt.template.md)，从ad_plan逐字复制描述，保留单角色16:9三视图与1–2张半身变化，不建立影视故事板。微表演、时间效果、对称风格、海报/网格动效由导演参考返回事实，不转交全片主责。
4. 本阶段采用稿是唯一创作源；需要保存用[ad_plan模板](assets/ad_plan.template.md)。已有画布按[当前版本协调](../canvas-workspace/references/creative-handoff.md#当前版本协调)保存唯一项目主源，明确用户新编辑先合并再同步，只有受影响Panel更新。
5. 准备制作/保存项目读[生产交接](references/production-handoff.md)，实际结果可用/要求成片读[后期与验收](references/finishing-and-review.md)。文本阶段不提前加载执行资料。没有画布生成授权不生成，创作采用不等于生成授权。

不要求影视六Beat/故事蓝图或独立MV六阶段；专业成果引用实际版本，不另写第二份全片计划。方法取舍见[来源说明](references/source-notes.md)。
