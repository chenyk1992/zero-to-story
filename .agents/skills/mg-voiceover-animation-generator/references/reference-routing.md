# MG 参考与交接路由

poster-motion-generator的五层分析与八类运动、ip-toy-grid-motion的最终六格方法统一在[布局动效](../../visual-design-creator/references/layout-motion-handoff.md)维护，取舍见[来源说明](../../visual-design-creator/references/source-notes.md)。不移植矛盾单次/分段、固定BGM/模板套件或平台执行链。

海报/最终网格按需读[布局动效](../../visual-design-creator/references/layout-motion-handoff.md)，静态状态交资产专能。最终网格不是六Shot。受广告委托返回限定成果，源/文字/后期按[共同交接](../../canvas-workspace/references/creative-handoff.md)，不接管全片。

共享授权、停止和结果规则见[项目共享生产规则](../../../../guides/ai-system-prompt.md)。只读取会改变当前 MG 决策的参考。

## 创作参考

所有 MG 任务先读本路由；只有准备 H3 交接或用户要求提示词文档时才读 [h3-mg-prompt-template.md](h3-mg-prompt-template.md)，再按问题选择：

| 问题 | 参考 |
|---|---|
| 风格、版式、色彩、信息密度 | visual-style-layout-library.md |
| 卡片、图标、线条、镜头和转场 | element-motion-transition-library.md |
| 标题、关键词、输入框、动态字 | kinetic-typography-motion-library.md |
| 抽象概念、对比、分流、聚合、波形 | mg-motion-pattern-library.md |
| 数字、百分比、增长、排名、KPI | data-visualization-motion-library.md |
| 明确要求 Seedance 兼容创作 | seedance-omni-reference-prompt.md（legacy，仅写作） |

不用为形式完整读取未命中的库。库中的建议要翻译成当前画面动作，不写“参考知识库”代替方案。

## 视觉参考模式

模式由已确认的素材用途决定，不能按素材数量猜：

| 已确认用途 | Canvas 模式 |
|---|---|
| 无视觉参考 | T2V，不绑定媒体 |
| 一张明确的精确首帧 | I2V，绑定唯一 first_frame |
| 明确的首帧和尾帧 | FL2V，绑定 first_frame / last_frame |
| 普通身份、构图、风格图或视频参考 | R2V，绑定对应参考端口 |

每项参考记录来源、语义用途、保真要求和当前 Panel；没有用途就不绑定。外部口播是音频输入或后期责任，不是视觉参考。产品图即使由 Skill 生成，也先审阅再交接。

原片与接续参考按[素材用途与编号](../../video-deconstruct-analyzer/references/recreation-change-plan.md#素材用途与编号)分开：用户上传原片可作普通视频参考，保留其选定来源/版本和运动、构图等用途，不要求或伪造生成 ACCEPT；前段生成结果用于连续性时必须是已 ACCEPT 的实际采用版本。精确续接尾帧从该采用版本提取，独立绑定 `first_frame`，不占普通视频参考编号。只有原片或只有前段时均可为 `<Video 1>`；两者都需要时按真实紧凑输入列表映射槽位/标签，不预留空槽、不补无用素材。普通 R2V 关闭或省略 `frame_zero_video_guide`，不能把第一条原片意外设为时序前缀。

## Canvas 交接

方案确定后：

1. 把当前 Panel 的事实交给 [h3-prompt-writing](../../h3-prompt-writing/SKILL.md)，取得完整 H3 文本；
2. 把提示词、已确认模式、素材、参数、音频/后期责任和验收重点交给 [canvas-workspace](../../canvas-workspace/SKILL.md)；
3. 保存草稿，等页面确认或对话明确授权后由 Canvas 冻结快照并提交一次。comfy 由 Canvas 服务调用 [comfy-video-executor](../../comfy-video-executor/SKILL.md)。

只有旧输入明确把 pixel_ratio 当作同一 MP 像素预算时，才将该值映射为 Canvas parameters.megapixels；不要把画幅或像素宽高比当作 MP，未指定不猜。交付分辨率由后期处理负责。默认一条 Panel Clip，Clip 可含已批准的多个 Shot/切点，受控复刻不改为单连续镜；只有用户要多条成片或能力时长限制要求拆分才建多个 Panel。

## 结果

实际输出回填原节点后，按共享规则记录任务相关末态和音频证据，并做一次 ACCEPT、REJECT 或 INCONCLUSIVE。请求状态未知时核对同一请求，不重提、不换能力。需要连续性时，接续来源和精确尾帧使用已接受的实际采用版本；这不限制上文用户上传原片的普通参考用途。后期影响采用时走[后期与采用状态](../../zero-to-story/references/video-qc.md#后期与采用状态)，不能用旧结论覆盖新文件。全部 Panel 接受且用户要求成片时，只对已接受输出做确定性连接、音频、字幕和可播放性/同步检查。
