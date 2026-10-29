# Skill 路由

所有 Skill 先遵守[项目共享生产规则](ai-system-prompt.md)。本文只说明职责边界和选择入口；不要把 Skill 的示例、外部工具列表或历史文档当成当前宿主能力。一次请求只选与交付物直接相关的主 Skill，必要时读取它引用的资源。

故事、MV和广告由各自主入口按[整体风格推荐与继承](../.agents/skills/zero-to-story/references/style-selection.md)结合用户内容主动推荐，已有风格直接沿用；用户不必先挑Skill。题材/世界、媒介美术与整体气质组合成作品方向，反转、微表情、子弹时间和运镜等叙事/拍摄方法在剧本与分镜中按需落实，不作为互斥风格菜单，也不改变全片主责。

| 用户目标 | 主 Skill | 交付边界 |
| --- | --- | --- |
| 独立角色/IP、产品/服装、海报/网格静态资产 | `visual-design-creator` | 主身份/造型/产品/场景分开，只补必要资产；不是第四个视频主入口 |
| 细腻表演；micro-expression-video-generator 方法 | 当前影视/广告/MV或Presenter，复用表演参考 | 同一主动作内发展，保留对白、机位和口播预算 |
| 情景喜剧；sitcom-story-video 方法 | 编剧用 `short-drama-screenwriter`，导演用 `zero-to-story` | 因果、反应与回扣，不强加付费/恋爱/预告 |
| 对称复古童话；wes-anderson-style-short-film-generator 方法 | 当前影视/广告/MV，复用风格参考 | 不强加画幅、粉彩、旁白或音乐 |
| 参考复刻；reference-video-recreation-workflow 方法 | `video-deconstruct-analyzer`，再交原主 Skill | 对话/Skill 选择自由改编、受控复刻、只读分析并记简报；不改 Canvas 页面，不代表生成授权 |
| 微短剧、独立情景喜剧及其角色/分集剧本 | `short-drama-screenwriter` | 剧情、人物、对白和分集文本；普通小说或其他剧本不强套短剧规则，不直接执行视频 |
| 参考作品研究、对标或选题采风 | 当前创作主责复用[参考研究](../.agents/skills/zero-to-story/references/reference-research.md) | 交来源、实际观察、推断与迁移决定；视频观察由分析专能负责，不自动生产 |
| 只要公开热点数据、榜单或快照，不要求选题判断 | [hot-collect](../.agents/skills/hot-collect/SKILL.md) | 采集与来源状态；已有符合需求的快照直接复用，不默认运行采集＋打分整链 |
| 从已有热点快照挑选题、比较趋势或生成候选卡 | [topic-scout](../.agents/skills/topic-scout/SKILL.md) | 读取 hot-collect 数据；已有数据请求不自动补采，缺数据说明缺口 |
| AI 知识分享、工具实测、vibe coding 账号的热点、升温线索、对标、选题与脚本复盘 | [ai-creator-radar](../.agents/skills/ai-creator-radar/SKILL.md) | 免费来源与可追溯采样；不承诺爆款、不自动发布或调用付费 API，成片交原有制作入口 |
| 从选题/资料撰写历史、科普、人物或知识解说稿 | `narration-writer` | 事实、解释与旁白文本；制作按视觉目标交影视/MG/B-roll/Presenter，不新增完整作品生产链 |
| 海外对白、多语互动与地域语言 | 当前主责复用[语言适配](../.agents/skills/short-drama-screenwriter/references/overseas-dialogue.md) | 保留语言证据、人物知情与当前版本；文本、音色、字幕和口型分别验证 |
| 多人、反打、产品交接或复杂走位 | 当前影视/MV/广告/专业主责复用[复杂调度](../.agents/skills/zero-to-story/references/blocking-direction.md) | 场景位置与各机位画面关系写回现有 Shot/Setup，不建第二份全片计划 |
| 广告、品牌传播、电商宣传；含反转、美妆、时装和海报/IP动效 | `advertising-creator` | 独立广告策略、ad_plan、静态/视频制作与验收；反转可选，文本不自动生成 |
| 卖点直接造成一次可见状态倒置的剧情广告 | `advertising-creator` 的[反转广告创意路线](../.agents/skills/advertising-creator/references/twist-ad-ideation.md) | 只补创意搜索与自筛；反转机制与商品因果仍在通用反转与产品因果，不新增入口或广告 schema |
| 影视、广告或有叙事需要的MV中的反转、误判、身份揭示 | 当前写作/导演主 Skill，复用[通用反转](../.agents/skills/short-drama-screenwriter/references/reversal-design.md) | 反转是叙事机制，不自动归入喜剧，也不强制进入短剧或广告流程 |
| 慢动作、冻结与子弹时间；bullet-time-slow-motion-video 项目方法 | 当前制作主 Skill，复用[时间效果导演](../.agents/skills/zero-to-story/references/time-effects-direction.md) | 效果窗口、冻结/运动对象、环绕与恢复；不新增控制接口。已有视频确定性变速先核实工具 |
| 影视剧、短剧、叙事短片及其分镜/Panel交接 | `zero-to-story` | 影视故事板/蓝图与必要资产；广告不用影视全片契约，H3另定稿 |
| 宫崎骏／吉卜力启发的手绘动画、未来科幻短片，或其人物/环境参考图；点名 miyazaki-inspired-animation / future-sci-fi-cinematic-generator 的项目方法 | `zero-to-story` 的视觉风格分支 | 可先从内容推荐方向，按制作需要用实际参考图核实美术并交接；只要参考图就止于图片。歌曲驱动 MV 仍由 `music-video-creator` 主导 |
| 都市赛璐璐 / City Pop、中式仙宫的美术与空间表现 | 当前作品主责按需读[风格分支](../.agents/skills/zero-to-story/references/visual-style-profiles.md) | 只复用视觉与运动方法，不因风格切换主责或加载外部整套流程 |
| 风格化3D及其混合叙事、不同强弱的媒介运动 | 当前主责按需读[3D与运动分支](../.agents/skills/zero-to-story/references/visual-style-profiles.md#风格化3d与混合叙事) | 保留所选轮廓、材质与运动，不从旁白比例推断画风或新增生产入口 |
| 混合叙事中的旁白、对白与画面分工 | 编剧/影视主责复用[混合叙事](../.agents/skills/zero-to-story/references/mixed-narration-direction.md) | 虚构旁白不转知识解说；实际声音/窗口与执行仍交原下游 |
| 产品展示视觉事件、字体包装与构图状态 | 广告读[产品展示](../.agents/skills/advertising-creator/references/product-showcase-direction.md)，MG及当前主责按需读[构图与字体](../.agents/skills/mg-voiceover-animation-generator/references/composition-and-typography.md) | 共享限定视觉方法，结果回原计划；不新增完整作品入口、片头执行器或图层渲染能力 |
| 歌曲驱动的 MV、音乐时间轴与镜头方案 | `music-video-creator` | 独立 MV 导演方案、必要视觉资产与 Panel 交接；按实际歌曲安排后期 |
| 歌词贴字、空间文字或文字版式主导的复古拼贴 MV；点名 music-video-subtitle-generator / cool-music-video 的项目方法 | `music-video-creator` 的文字/拼贴路线 | 在分镜前确定文字系统、音乐事件响应与表演空间；按需读取项目内对应参考，不以普通字幕或风格标签替代 |
| 只写歌词、制作歌曲或纯器乐 | `music-video-creator` 的音乐分支 | 只交歌词则止于文本；音频生成交 Canvas，止于真实音频与听审，不扩成 MV |
| 为已锁定画面配乐 | 原故事/视频主 Skill；复用 `music-video-creator` 的音乐方向 | 画面和对白时点保持锁定；准备音乐要求、实际音轨与后期安排，不以歌曲重排画面 |
| 单个 Panel 的 MiniMax H3 提示词 | `h3-prompt-writing` | 一份完整提示词；不执行生成或编排运行时 |
| 影视片头、片名揭示、开场卡司和标题序列 | `title-sequence-creator` | 限定片头专业成果；受影视/广告/MV委托回原主源，不接管完整作品，不替代普通字幕或完整预告 |
| 拼贴表演MV、人物与平面设计共演；collage-performance-mv项目方法 | `music-video-creator` 的[拼贴表演路线](../.agents/skills/music-video-creator/references/collage-performance-direction.md) | 记录人物表演、版式、主歌窗口与实际输入，不引入固定表演占比或独立合成器 |
| RPG/开放世界/战斗/跑酷的电影化镜头与HUD状态 | 当前作品主责复用[游戏导演](../.agents/skills/zero-to-story/references/game-cinematic-direction.md) | 先补创作与状态交接；真实引擎证据、完整HUD和精确合成能力分别核实，不开发可玩游戏 |
| 节点画布的故事、资产和待办 | `canvas-workspace` | 读取最新画布、保存编辑、领取已确认请求、回填实际媒体；不改画布 API 之外的运行时状态 |
| 已确认的本地 Comfy 视频快照执行 | `comfy-video-executor` | 按固定快照执行一次并返回实际文件与结果；不写创意、不改冻结输入、不自动重提 |
| 已确认的本地 Qwen 图片快照执行 | `comfy-image-executor` | 文生图、最多 10 张图片参考生成/编辑，由画布 worker 执行；无需 Codex，不写创意或重复提交 |
| 数字人或虚拟实拍连续口播 | `virtual-presenter` | 角色、环境、表演、文案、声音参考和交接；不把普通 MG 或 B-roll 当作数字人流程 |
| 口播、产品或抽象主题的 MG 动画 | `mg-voiceover-animation-generator` | MG 方案、口播、供 H3 定稿的内容和按需交接；不替代数字人或 B-roll Skill |
| 逐字稿驱动的 B-roll | `transcript-broll-planner` | 语义拆分、镜头规划和获授权后的 Panel 交接；不改口播事实 |
| 参考视频拆解、复刻/元素替换分析 | `video-deconstruct-analyzer` | 可追溯证据和复刻提示词路线；不直接生成正式产物 |
| 用 MiMo 分析音频、歌曲或视频 | `mimo-video-understanding` | Pro/Flash 音视频观察证据；保留原 Skill 名兼容视频调用，不把模型描述直接当作内容接受结论 |
| 明确要 MiniMax voice id 的音色克隆 | `voice-clone` | 授权检查、音频校验和 MiniMax voice id；不替代本地 Qwen3-TTS |
| 本地多语言语音、Eric 成都男声、声音设计或参考音色复用 | `qwen3-tts` | Qwen3-TTS 三模式的台词、参考转写、授权和听审准备；生成交给 Canvas 音频节点 |
| 已确认的本地 Qwen3-TTS 音频快照执行 | `comfy-tts-executor` | 由画布 worker 单次执行 CustomVoice、VoiceDesign 或 Base，保留原始音频并回填交付 FLAC |
| 已确认的本地 MiniMax Music 3 音乐快照执行 | `comfy-music-executor` | 由画布 worker 单次执行并回填实际音乐 FLAC；不编写歌词或重复提交 |
| 已确认的本地 YuE2 参考旋律翻唱 | `comfy-yue2-executor` | 由画布 worker 执行 SheetSage2 melody ABC 与 YuE2，回填实际 FLAC；参考音色、原伴奏和固定多歌手身份不透传，不另行提交 |
| 已确认的本地人声与伴奏分离 | `comfy-singing-executor` | 由画布 worker 执行 MelBandRoFormer，回填人声与伴奏；只保留 separate，不编排歌曲，不另行提交 |
| 中英文文本去模板化 | `shuorenhua` | 文本审校和改写；不改变事实、责任主体或视频执行契约 |

## 三完整作品入口与专业例外

影视→zero-to-story，歌词/歌曲/器乐/独立MV→music-video-creator，广告/品牌/电商→advertising-creator。广告有歌曲只委托音乐成果，整片仍归广告；仅主题曲音频归音乐。影视配乐不转MV，现有MV加赞助落版保持MV，新电影宣发广告为独立广告。不因出现产品/品牌或背景音乐抢主责。目标混合且未明确当前交付时只问必要归属缺口。

独立资产、编剧、分析、MG、Presenter、B-roll、单Panel提示词或画布保存按专业范围结束；受托不另写全片计划，不改锁定时序。[布局动效](../.agents/skills/visual-design-creator/references/layout-motion-handoff.md)由当前作品主责/MG消费，资产仅准备静态状态。海报五层/八类动效和最终六格按声明用途，不把最终格子当时刻。

片头/标题序列也是限定专业任务，独立请求止于片头，受托返回原作品；拼贴表演仍是MV分支，游戏电影化按叙事/宣传/歌曲用途保留主责。跨Panel文字、声源与实际状态按[共同边界交接](../.agents/skills/canvas-workspace/references/creative-handoff.md#跨panel文字声音与状态)处理，不由专业路线另定义运行状态。

独立非商业海报/网格动效走[MG无口播分支](../.agents/skills/mg-voiceover-animation-generator/SKILL.md)，广告物料仍归广告，歌曲驱动网格仍归MV；不因无人物/无口播新增整片入口。背景UI复刻、多对象/非人替换的证据返回原主责，严格声音连续按[共同声音交接](../.agents/skills/canvas-workspace/references/creative-handoff.md#声音身份与实际音轨)处理，都是按需事实，不是新增提供方能力。

## 如何交接

“帮我的账号找一个值得拍的选题”等综合研究由 ai-creator-radar 主责，按需调用采集与判断层；明确只要数据或已有库排序时直接走对应入口。数据格式、网络副作用和证据复用见[研究交接](../.agents/skills/ai-creator-radar/references/research-handoff.md)，用户不必先选工具。

按当前交付阶段选主责，再组合业务目标、类型/基调、叙事机制与拍法。例如“悬疑产品广告＋反转＋子弹时间”由advertising-creator自己统筹，按需复用叙事/时间导演参考，直接交H3/Canvas，不转影视整片、不因反转改喜剧。独立MG、数字人、B-roll、MV保留原主责，受广告委托则只返回指定成果；只需单 Panel 提示词直接交 H3，只需保存定稿直接交 Canvas。文本创意不强加资产或生成参数门禁。

先选负责当前交付物的 Skill，完成这一阶段后才加载下游。已有事实、参数与授权直接沿用，只传当前 Panel 所需信息。创作、执行和验收的共同规则只在[共享生产规则](ai-system-prompt.md)维护（含概念单一权威、三项关键硬门、素材就绪形态）；本表只做目标到主 Skill 的路由，不另写定义。版本、文字/四时间轴与采用文件按[共同交接](../.agents/skills/canvas-workspace/references/creative-handoff.md)，字段与接口按需读[画布指南](canvas-guide.md)。

例如“给逐字稿做 B-roll 方案，先别生成”只走 B-roll 规划；明确授权生产后才交 H3 写作和 Canvas。歌曲、节奏、歌词或演唱主导的 MV 走 `music-video-creator`；普通剧情片带背景音乐仍走故事分镜。“把已有 H3 提示词放入画布”直接走 Canvas，不再触发创作或提示词优化。Comfy 是服务执行的脚本能力，Agent 不另行启动。

用户要求验证 Skill 或维护行为规则时，可按[轻量场景检查](skill-experience-checks.md)复核当前改动；普通创作不自动增加测试阶段。

## 外部 Skill

只有用户点名或当前交付确实需要时才加载外部 Skill；先确认其适用边界。外部 Skill 的审批、工具和格式建议不能覆盖用户当前指令、项目共享生产规则或宿主工具权限。插件缺失时报告缺口并继续可行的本地工作；不要为了邻近能力安装无关插件。

多人轮唱的原曲、完整翻唱候选、整句混音、角色绑定与 H3 交接由 [music-video-creator](../.agents/skills/music-video-creator/references/multi-singer-workflow.md)统筹；单人、器乐和锁定画面配乐沿用原路由。
