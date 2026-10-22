---
name: visual-design-creator
description: 设计角色/IP、产品/服装视觉资料、海报与静态网格资产及用途交接。独立资产请求止于资产；完整影视、MV和广告仍由对应主入口统筹，不规划整片视频。
---

# 静态视觉资产设计

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。先区分独立资产交付与主计划中的限定委托。商业海报策略归advertising-creator，本Skill只落实设计。

受故事、MV或广告委托时，从当前主源继承已采用的整体媒介、美术、气质与局部例外，在人物/产品/场景及文字资产中落实，不独立改选全片风格或重复确认。独立资产仍在自身范围设计；源图与选定风格有实质冲突时回主责协调，不让下游生成猜测。具体传递沿[共同风格交接](../canvas-workspace/references/creative-handoff.md#整体风格的继承与分镜方法)。

1. 读当前来源、采用资产、用途与锁定项；按[资产规划](references/asset-planning.md)保持身份、版本、消费者，只选必要资产。
2. 按需读[身份设计](references/character-identity-design.md)、[品牌IP模块](references/brand-ip-package.md)、[产品/服装资产](references/product-fashion-assets.md)、[海报/网格版式](references/poster-grid-layout.md)。字形仍不具体时读[字形选型与排字](references/type-and-layout-choices.md)，需要材料/排字形成包装身份时读[包装风格](references/packaging-style-directions.md)，只落实本次选中关系。海报/最终网格进入视频时再读[布局动效交接](references/layout-motion-handoff.md)；资产侧只提供实际版式、状态和运动相关证据。
3. 按用途选模板，说明各参考贡献；只有交付需要角色图时才制作或复用[完整角色设定图](references/character-identity-design.md#最小有用资产)，确定该交付后不删三视图/半身变化。登记新角色或仅用固定文字控制的配角不自动生图。只要方案就交文字；其他资产不默认候选数、全套视图或先行黑白草图。
4. 按[生产交接](references/production-handoff.md)保存/生成并做一次实际用途检查；缺工具、未知结构或精确生产文件要求如实报告。
5. 返回实际资产、版本、用途证据、允许变化与消费者。视频主责按需读[布局动效](references/layout-motion-handoff.md)；商业广告的镜头与服装场景规划仍由 `advertising-creator` 维护，本Skill不另建视频计划。

独立保存用[资产计划模板](assets/asset_plan.template.md)；受托记录在调用方计划并引用本成果，不复制整片事实。取舍见[来源说明](references/source-notes.md)。

有较大美术探索空间时，按[互补资产设计](references/asset-planning.md#让图片分别回答设计问题)选择身份、环境、材料或关键状态，已有素材足够就复用。品牌场景的完整事件由广告主责按[产品展示方法](../advertising-creator/references/product-showcase-direction.md)确定，本 Skill 返回适用的静态设计，不另编视频。
