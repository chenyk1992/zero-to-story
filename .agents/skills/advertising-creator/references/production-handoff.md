# 广告生产交接

处理字形/排字、包装材料或声画关系时，按[具体交接](../../canvas-workspace/references/creative-handoff.md#字形包装与声音互动的具体交接)从 ad_plan 提取当前 Shot 的准确内容、可见过程、素材版本和制作责任，并写入完整 prompt、真实参考或后期清单。

用于保存项目、制作或继续成片。[共同交接](../../canvas-workspace/references/creative-handoff.md)定义源协调、文字/时间和接口；ad_plan 持有广告创作事实，Canvas 持有运行、快照与采用记录。

按[共同风格交接](../../canvas-workspace/references/creative-handoff.md#整体风格的继承与分镜方法)从 ad_plan 继承整体媒介、美术、品牌气质及局部变化，并传给受托专能。将当前 Shot 的具体视觉特征写入 H3 正文和对应参考；同时沿用已核实的产品事实与准确文案。

## 限定专业委托

| 范围 | 专能与返回要求 |
| --- | --- |
| 角色/IP、产品、服装、版式 | [视觉资产](../../visual-design-creator/SKILL.md)：实际图/key/版本/用途，不规划全片 |
| 喜剧/剧情稿 | [编剧](../../short-drama-screenwriter/SKILL.md)：指定节拍/可拍稿，不接管广告 |
| MG/产品功能动效 | [MG](../../mg-voiceover-animation-generator/SKILL.md)：指定文案与镜头事实，多镜不套Presenter单机位 |
| 连续数字人口播 | [Presenter](../../virtual-presenter/SKILL.md)：指定口播/角色/声音，保持其4～15秒、同镜续段真实尾帧条件 |
| 逐字稿副镜头 | [B-roll](../../transcript-broll-planner/SKILL.md)：当前语义窗口，保留其专业约束 |
| 歌词/歌曲/器乐 | [音乐](../../music-video-creator/SKILL.md)：实际采用音频、窗口和来源；可见演唱时带回逐句时序与声源依据，不新建整片MV |
| 参考/替换分析 | [分析](../../video-deconstruct-analyzer/SKILL.md)：对象/窗口/保留与变化证据，不改广告策略 |
| 开场片名/卡司专业序列 | [标题序列](../../title-sequence-creator/SKILL.md)：限定文字与镜头/声音事实及实际成果，广告保留总长、主张与主源 |

每项委托引用 ad_plan 版本和单元范围，说明锁定事实、可调整内容、所需素材、授权与完成条件；专能返回实际成果和待核项，由广告主责整合。歌曲可作为独立音乐成果交付，广告计划继续维护全片内容。

## Panel、模式与参数

品牌展示或动态字体已选定时，将其具体视觉事件写回 ad_plan 对应 Shot：商品状态怎样变化、观众何时看见主张所依赖的细节、文字怎样参与构图、声音怎样回应动作。向 H3 和后期交接时保留这一过程及各自责任，不缩成风格标签，也不把身份参考当作功能或结构的事实证明。

每Panel是独立生成段，无六Beat要求。交给[H3](../../h3-prompt-writing/SKILL.md)的事实包括目的、Shot/切点、动作/起止状态、身份/产品、逐字对白/说话人/语言、文字表、声音/静默窗、素材用途、规格、后期与关键验收。时装动态涉及衣料响应时，在该Shot动作描述中区分资料支持的材质事实与已采用的运动意图；不要求精确布料仿真。

真实素材→实际端口→解析零基槽位→H3一基标签依次核对。商品不固定Picture1，规划九格不自动传入，related只资料。本地H3（provider=comfy）中t2v无媒体；i2v仅first_frame；fl2v实际首尾图；r2v至少一种参考、可另首帧、无尾帧、最多9图/3视频/3音频。普通本地r2v frame_zero_video_guide关闭/省略，不能把源片默认作为前缀。用户选择其他已接入提供方时，模式和参考容量按其当前capability核对，不套用上述本地数值。

本地 H3 当前支持 0.2～15 秒、24fps；短插镜按可读性与实际能力安排，影视的 4 秒下限不套用广告。provider/model/mode、duration/aspect_ratio/megapixels 及 options 中的 sampler_profile/steps 沿用广告主责按[共享规格规则](../../../../guides/ai-system-prompt.md#制作规格与判断依据)记录的值与依据，并按当前 capability 核对组合。若用户目标与可用模式或长度不匹配，回主责确定可执行的拍法。

多人互动、产品交接和跨机位使用按需复用[复杂调度](../../zero-to-story/references/blocking-direction.md)，将空间、遮挡、接触与商品状态写回 ad_plan 当前 Shot；不建立影视蓝图。解释性文案可委托[narration-writer](../../narration-writer/SKILL.md)处理限定稿件，产品事实与主张仍由广告持有，不因委托变成中立科普。

依赖同镜末态用固定ACCEPT源run与真实尾帧；独立镜头不等待全片资产。目标海报为r2v参考不保证精确末帧，主格全屏开场不能用整板冒充第0帧。

## 音乐广告

委托音乐时保留原专业流程的用途与许可约束；广告统筹不等于获得歌曲、音色、素材或模型的商用许可。当前YuE2权重为CC BY-NC 4.0，采用该分支用于广告前须按实际商业用途核实许可；不因已有非商用试听或技术成功而推定可商用，不自动换提供方。

先取得实际采用歌、摘要与所需音乐窗口。涉及可见演唱时，在 ad_plan 的可见演唱交接保留实际逐句窗口、唱词、起口与停顿、声源和出镜人。有现成[轮唱表](../../music-video-creator/assets/group_vocals.template.md)可引用当前版本，广告主责核对出镜映射与相关 Shot。可见演唱/说唱用本地r2v、同窗口真实reference_audio、实际槽位及演员映射；歌曲只背景/背影动作则不强加音频槽。嘴部冻结与同步歌唱冲突在定稿前解决，不能擅改VO或重排歌。

生成声、参考音频、最终主歌分别安排；参考不保证口型，最终保留主歌需实际后期与同步检查。广告不强制整曲预览或独立MV六阶段；明确启用graph.workspace.mv_production时必须完整满足[现行检查](../../music-video-creator/references/production-checks.md)，不能半填。只检查图片的字段不替代音频语义/窗口核对。

## 保存、确认与执行

已有项目主源按配置media_root/projects/<canvas_id>/ad_plan.md，document.content投影、source_path实际路径，媒体content当前事实/位置/版本；定稿保存data.prompt。计划换版核对差异，只同步受影响草稿，不覆盖用户新编辑/冻结快照。

读取最新 Canvas 的参数与素材连线，按[生成前审核](ad-collaboration.md#广告与宣传片的分阶段协作)核对当前 Panel 的完整实际输入，处理关键冲突并确认 readiness，再按[共享规则](../../../../guides/ai-system-prompt.md#唯一执行入口)在已有授权范围内创建请求。本地 Comfy 的 queued 请求由 worker 执行，pending_agent 请求由具备真实工具的会话领取；保留 request_id 与 execution_snapshot。执行状态未明时按共享规则核对原请求；成功媒体的内容修订和成片检查见[后期与验收](finishing-and-review.md)。缺少工具时说明受影响的制作环节。

全部生成段时长与 Panel 合计、目标片长对应；旧素材或后期插段用编辑清单记录实际采用窗口和成片位置。按锁定时长设计每个 Panel 的动作与结构；确需调整时长、增加生成段或变速时，回广告主责确定后更新计划。按交付要求核对 24fps 帧对齐差异。
