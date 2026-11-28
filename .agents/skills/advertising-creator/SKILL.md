---
name: advertising-creator
description: 创作广告、品牌/企业/活动宣传片和电商物料，结合用户想法与品牌目的推荐或继承整体风格，按需交付概念、文案、静态物料或视频成片。广告自己统筹剧情、音乐与动效表达；独立影视和歌曲/MV分别走原入口，局部专业任务保留原主责。
---

# 广告创作

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。围绕受众需要、可靠产品事实和品牌目的，发展可见可听的创意，统筹广告方案、导演和交付；H3 定稿、Canvas 操作与执行由对应专能完成。

## 当前范围与完成条件

| 请求 | 做什么、何时停止 |
| --- | --- |
| 概念/口号/文案/脚本 | 按当前范围交稿及必要前提，不要求素材、运行参数或画布 |
| 静态宣传/品牌物料 | 广告持有目标与文字，委托资产专能设计，检查所需实际图片即结束，不扩成视频 |
| 视频广告/宣传片方案或成片 | 按[分阶段协作](references/ad-collaboration.md)安排创作、生成前审核和交付；成片走对应独立盲审 |
| 独立广告主题曲、只要音频 | music-video-creator主责，广告资料是输入，止于音频 |
| 现有影视/MV的局部品牌修改 | 保持原作品主责，只处理授权范围；独立电影宣发广告为新广告交付 |
| 中立产品说明/已定单Panel提示词 | 明确专业MG/Presenter/B-roll/H3请求按原范围，不因有产品机械广告化 |

歌曲广告由广告主责整合音乐成果与实际音频。选歌曲、音色或工具前按[音乐广告交接](references/production-handoff.md#音乐广告)核对商业用途许可；独立音频交付归音乐。混合目标只有在影响当前交付且依据不足时才询问。

## 视频广告入口的制作规格

视频制作按[制作规格与判断依据](../../../guides/ai-system-prompt.md#制作规格与判断依据)在 `ad_plan` 记录用途、时长、画幅、参数、声音及交付要求和选值依据，专业委托继承。概念、文案和静态物料按当前范围准备；产品、投放和授权事实缺口如实列明。

## 创作与按需路由

1. 接收产品/品牌资料、受众/目的、范围、用户语言/时长/画幅/媒介/声音及露出策略。事实、条件、观察与未知分开；照片不证明功效、折扣、价格或活动。只问影响当前结果的缺口。
2. 按[整体风格](../zero-to-story/references/style-selection.md)结合品牌目的、产品事实与用户想法推荐方向，已有风格直接深化；授权直接完成时选择并说明依据。用[广告导演](references/ad-direction.md)发展脚本与分镜；参考研究读[来源方法](../zero-to-story/references/reference-research.md)，地域对白读[语言适配](../short-drama-screenwriter/references/overseas-dialogue.md)。产品推动剧情读[产品因果](references/product-causality.md)，需要反转时读[通用反转](../short-drama-screenwriter/references/reversal-design.md)或[反转广告创意](references/twist-ad-ideation.md)，喜剧读[喜剧写作](../short-drama-screenwriter/references/sitcom-writing.md)。
3. 唇妆读[美妆](references/beauty-product-direction.md)，服装读[时装](references/fashion-direction.md)，身份/IP/产品/版式委托[静态资产](../visual-design-creator/SKILL.md)。人物含跨镜配角按[固定文字](../zero-to-story/references/creative-assets.md#人物与场景文本锚点)记录在 ad_plan；已决定制作完整角色图时使用[统一模板](../zero-to-story/assets/character_card_prompt.template.md)，保留单角色 16:9 三视图与 1–2 张半身变化。其他导演方法返回当前广告事实。
4. 本阶段采用稿是唯一创作源；需要保存用[ad_plan模板](assets/ad_plan.template.md)。已有画布按[当前版本协调](../canvas-workspace/references/creative-handoff.md#当前版本协调)保存唯一项目主源，明确用户新编辑先合并再同步，只有受影响Panel更新。
5. 准备制作或保存项目读[生产交接](references/production-handoff.md)，结果可用或要求成片读[后期与验收](references/finishing-and-review.md)；按共享授权规则进入相应阶段。

广告使用自身的 ad_plan 与 Shot 计划，引用专业成果的实际版本。方法取舍见[来源说明](references/source-notes.md)。

产品、材料或品牌视觉主导时读[产品展示导演](references/product-showcase-direction.md)，动态字体读[构图与字体](../mg-voiceover-animation-generator/references/composition-and-typography.md)。把选定事件、文字和声音写回 ad_plan。
