# 广告生产交接

只在制作/保存项目/继续成片时读取。[共同交接](../../canvas-workspace/references/creative-handoff.md)定义源协调、文字/时间和现有接口；广告ad_plan是唯一全片创作源，Canvas是运行/快照/采用来源，不新增ad_production schema。

## 限定专业委托

| 范围 | 专能与返回要求 |
| --- | --- |
| 角色/IP、产品、服装、版式 | [视觉资产](../../visual-design-creator/SKILL.md)：实际图/key/版本/用途，不规划全片 |
| 喜剧/剧情稿 | [编剧](../../short-drama-screenwriter/SKILL.md)：指定节拍/可拍稿，不接管广告 |
| MG/产品功能动效 | [MG](../../mg-voiceover-animation-generator/SKILL.md)：指定文案与镜头事实，多镜不套Presenter单机位 |
| 连续数字人口播 | [Presenter](../../virtual-presenter/SKILL.md)：指定口播/角色/声音，保持其4～15秒、同镜续段真实尾帧条件 |
| 逐字稿副镜头 | [B-roll](../../transcript-broll-planner/SKILL.md)：当前语义窗口，保留其专业约束 |
| 歌词/歌曲/器乐 | [音乐](../../music-video-creator/SKILL.md)：实际采用音频与窗口/来源，不新建整片MV |
| 参考/替换分析 | [分析](../../video-deconstruct-analyzer/SKILL.md)：对象/窗口/保留与变化证据，不改广告策略 |

传主源/版本、单元、锁定项、允许变化、素材、授权、位置、完成条件；返回该单元实际成果与未知，由广告整合。歌曲可单独有音乐成果文件，不能同时维护一份可改全片的MV计划。

## Panel、模式与参数

每Panel是独立生成段，无六Beat要求。交给[H3](../../h3-prompt-writing/SKILL.md)的事实包括目的、Shot/切点、动作/起止状态、身份/产品、逐字对白/说话人/语言、文字表、声音/静默窗、素材用途、规格、后期与关键验收。时装动态涉及衣料响应时，在该Shot动作描述中区分资料支持的材质事实与已采用的运动意图；不要求精确布料仿真。

真实素材→实际端口→解析零基槽位→H3一基标签依次核对。商品不固定Picture1，规划九格不自动传入，related只资料。t2v无媒体；i2v仅first_frame；fl2v实际首尾图；r2v至少一种参考、可另首帧、无尾帧、最多9图/3视频/3音频。普通r2v frame_zero_video_guide关闭/省略，不能把源片默认作为前缀。

本地H3当前0.2～15秒、24fps，短插镜按可读性/实际能力；影视4秒下限不套广告。provider/model/mode、duration/aspect_ratio/megapixels及options里的sampler_profile/steps按当前capability与已选规格继承，vdn_turbo的8步等条件不猜。不切镜30秒/仅尾帧等冲突说明缺口，不自行拆分、改模式/提供方。

依赖同镜末态用固定ACCEPT源run与真实尾帧；独立镜头不等待全片资产。目标海报为r2v参考不保证精确末帧，主格全屏开场不能用整板冒充第0帧。

## 音乐广告

委托音乐时保留原专业流程的用途与许可约束；广告统筹不等于获得歌曲、音色、素材或模型的商用许可。当前YuE2权重为CC BY-NC 4.0，采用该分支用于广告前须按实际商业用途核实许可；不因已有非商用试听或技术成功而推定可商用，不自动换提供方。

先取得实际采用歌、摘要与所需音乐窗口。可见演唱/说唱用本地r2v、同窗口真实reference_audio、实际槽位及演员映射；歌曲只背景/背影动作则不强加音频槽。嘴部冻结与同步歌唱冲突在定稿前解决，不能擅改VO或重排歌。

生成声、参考音频、最终主歌分别安排；参考不保证口型，最终保留主歌需实际后期与同步检查。广告不强制整曲预览或独立MV六阶段；明确启用graph.workspace.mv_production时必须完整满足[现行检查](../../music-video-creator/references/production-checks.md)，不能半填。只检查图片的字段不替代音频语义/窗口核对。

## 保存、确认与执行

已有项目主源按配置media_root/projects/<canvas_id>/ad_plan.md，document.content投影、source_path实际路径，媒体content当前事实/位置/版本；定稿保存data.prompt。计划换版核对差异，只同步受影响草稿，不覆盖用户新编辑/冻结快照。

读取最新Canvas保存参数和连线，readiness只技术齐全，不检查广告语义。保存不是授权；已有明确授权覆盖精确输入时确认一次，request_id幂等。本地Comfy queued由worker单次执行，pending_agent才由真实工具会话claim execution_snapshot；unknown/失败核实原任务，不重提/换后端。技术failed/unknown是原请求状态，不是内容修正或新运行授权；已成功媒体的画面问题按[后期与验收](finishing-and-review.md)处理。缺工具说明具体阶段。

全部生成段组成时总预算等于Panel合计；含旧素材/授权后期插段时用逐段编辑清单记录实际采用窗口与成片位置。不多生成裁切凑长、不自动变速；24fps帧对齐差异按实际交付条件检查。
