---
name: title-sequence-creator
description: 设计影视片头、片名揭示、开场卡司和标题序列，交付视觉母题、字体与文字事件、镜头声音方案及H3/Canvas交接。独立请求止于片头；完整影视、广告、MV仍由原主责统筹，不用于普通字幕、片尾滚动名单或完整预告片。
---

# 片头与标题序列

遵守[共享生产规则](../../../guides/ai-system-prompt.md)。片头用画面、文字与声音建立作品身份，不预设人物、双语、片长、镜数或效果密度。只写方案时止于文本；媒体仅经 Canvas 已授权请求生产。

## 范围与创作源

独立任务用[片头计划](assets/title_plan.template.md)维护当前范围。受影视、广告或MV委托时，原主计划持有全片事实；本Skill交指定片头的专业成果与版本，由主责整合，不重建全片计划。完整预告的事件/人物选择交影视或广告主责，片尾长名单不套本流程；普通字幕与讲解MG保留原入口。

只要对话方案时不初始化项目或强制落盘；用户要求保存或准备制作时，再按模板保存当前源。已有资料与采用决定直接复用。

沿用已有作品定位、准确片名/署名、语言、风格、参考用途和允许变化。用户只给灵感并授权创作时可提出原创标题与人物设计，标明提案，不虚构真实卡司或作品资料；已定内容直接使用，不重新发散或逐关确认。

## 设计与交付

1. 从作品希望观众带走的感受出发，读[片头导演](references/title-direction.md)，让人物行动、材料、空间、编辑或抽象关系形成母题。先明确文字和画面怎样共同发展，再选拍法。
2. 在现有计划记录准确文字、字形/材料、载体、阅读与变化窗口，区分生成和后期。没有卡司就不补姓名；允许无字铺陈、静点和稳定读字，不要求全程运动。
3. 按完整动作、阅读和声音的自然结束点安排 Shot/Panel。总长、画幅、原生规格依共享规则确定；一个Panel可含多个Shot，长片头可跨Panel，不把15秒当全片固定上限。用户要求连续一镜且超过所选能力时说明缺口，不静默拆镜。
4. 准备提示词或Canvas交接时读[生产与验收](references/production-and-review.md)，把已定单Panel事实交[H3](../h3-prompt-writing/SKILL.md)，完整文本与实际素材交[Canvas](../canvas-workspace/SKILL.md)。资料链接不替代输入，独立后期须有真实工具。
5. 实际媒体返回后，按共享规则一次检查所选表达、准确文字与必要接缝；只对影响当前用途的项目判断，技术成功不代表片头表现成立。

## 按需协作

| 当前问题 | 读取或委托 |
| --- | --- |
| 字体角色、主体与图形共演 | [构图与字体](../mg-voiceover-animation-generator/references/composition-and-typography.md)，只复用视觉方法，不继承口播流程 |
| 具体选字、排字与包装材料 | [字形选型](../visual-design-creator/references/type-and-layout-choices.md)、[包装方向](../visual-design-creator/references/packaging-style-directions.md)，沿作品身份深化，不强制辅助字或高密度 |
| 先声后形、材料回答、延迟或留白 | [声音互动](../music-video-creator/references/sound-image-interaction.md)，保留已有音轨/无声选择，时间与跨段关系回原计划 |
| 摄影世界与复杂图形共同主导 | [实拍动态图形](references/live-action-graphics-direction.md)，保留原片与重建式生成分别处理 |
| 微缩、抽象或异常材料规则 | [构造世界](references/constructed-world-direction.md)，选规则、尺度和有用途的反馈 |
| 角色、物件、场景或准确字图 | [视觉资产](../visual-design-creator/SKILL.md)，交实际用途与版本；不为每个文字事件机械重做资产 |
| 原片分析、受控复刻 | [参考变更](../video-deconstruct-analyzer/references/recreation-change-plan.md)，保留锁定事实和允许变化 |
| 已锁画面的配乐 | [锁定画面配乐](../music-video-creator/references/music-direction.md#锁定画面配乐)，片头仍持有画面、文字与时点 |
| 跨Panel文字、声音或状态 | [共同边界交接](../canvas-workspace/references/creative-handoff.md#跨panel文字声音与状态)，不增加独立状态机 |

返回当前方案、完整的所需交接或实际成果及缺口；不自动生成、不要求用户选择Skill。来源取舍见[方法说明](references/source-notes.md)。
