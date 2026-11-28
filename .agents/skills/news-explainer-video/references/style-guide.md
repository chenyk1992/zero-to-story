# 18套风格：Design 迁移指南

这些配置来自 creator-style-kit 的固定提交；原始文件保留以便查确切色值、字体角色、节奏和风格约束。**只按需读取选定配置**，不要一次加载全部。此包仅提供设计定义，不附字体、音效、CSS皮肤或HyperFrames运行时。

## 如何选与应用

优先按内容形状选主风格，保持一套主风格，至多一套有明确作用的点缀。先看原素材是否有角色、现场或产品演示；丰富素材优先全屏剪辑，风格统一叠字和转场，不能因为资讯题材强制套报纸底板。以数据为主时可选 data-journal；论文用 paper-figure；结构与流程用 blueprint 或 isometric-stack；人文资讯用 editorial-paper 或 ink-wash。不要因为主模型叫Opus就自动采用clay-serif。

| ID与配置 | 名称 | 适用内容 | 背景 / 强调色 | 动作语言 |
|---|---|---|---|---|
| [dark-keynote](styles/dark-keynote/style.yaml) | 暗场发布会 | 口播开场、产品/功能展示、结论时刻 | #08090B / #C8F25A | blur-rise → accent-glint；light-sweep |
| [swiss-grid](styles/swiss-grid/style.yaml) | 瑞士网格 | 机制讲解、数据/对比、流程拆解 | #EAE9E5 / #E30613 | clip-rise → knife-underline；column-wipe |
| [editorial-paper](styles/editorial-paper/style.yaml) | 报刊纸感 | 行业故事、历史/人文题材、「为什么会这样」类叙事 | #F2ECDF / #FFD200 | paper-slap → highlighter；sheet-wipe |
| [warm-notebook](styles/warm-notebook/style.yaml) | 暖调手账 | 新手教程、概念讲解、亲切的口播片尾 | #FFF8EC / #FF5A36 | spring-pop → scribble；card-zoom |
| [poster-kinetic](styles/poster-kinetic/style.yaml) | 海报撞色 | 前 3 秒钩子、章节标题、金句 | #111111 / #D7FF3A | drop-letters → recolor-char；ground-slats |
| [dev-console](styles/dev-console/style.yaml) | 终端控制台 | Claude Code / AI 工具录屏、提示词展示、代码与命令 | #0D1117 / #3FB950 | type-scramble → selection；glitch-slice |
| [data-journal](styles/data-journal/style.yaml) | 数据新闻 | 模型评测结果、跑分对比、价格/速度/上下文对比 | #FFF1E5 / #0F5499 | clip-rise → knife-underline；edge-wipe |
| [paper-figure](styles/paper-figure/style.yaml) | 论文图表 | 论文解读、技术报告拆解、公式与定义 | #FDFCF8 / #1F77B4 | fade-up → boxed；dip |
| [manim-morph](styles/manim-morph/style.yaml) | 数学动画 | 原理科普、注意力/嵌入等概念、公式推导 | #000000 / #F7D96F | write → circumscribe；dip |
| [blueprint](styles/blueprint/style.yaml) | 蓝图线稿 | 系统架构、Agent 工作流、机制拆解 | #0B3A66 / #7FD3FF | draft-in → dimension；draft-wipe |
| [benchmark-hud](styles/benchmark-hud/style.yaml) | 评测仪表 | 跑分揭晓、新旧版本对比、速度/延迟/成本读数 | #020809 / #FFBF47 | scan-in → bracket-lock；edge-wipe |
| [particle-field](styles/particle-field/style.yaml) | 粒子星云 | 片头/章节、模型能力概念（涌现、规模）、抽象原理 | #05060A / #9B8CFF | converge → halo；particle-warp |
| [frosted-aurora](styles/frosted-aurora/style.yaml) | 弥散玻璃 | 新模型发布开场、功能亮点、产品级展示 | #07070C / #62DCFF | blur-rise → gradient-sweep；frost |
| [isometric-stack](styles/isometric-stack/style.yaml) | 等轴架构 | 技术栈/分层架构、Agent 与工具的关系、上下文窗口构成 | #EEF0F4 / #4F46E5 | clip-rise → knife-underline；iso-slide |
| [bauhaus-geometry](styles/bauhaus-geometry/style.yaml) | 包豪斯构成 | 概念拆解、分类/框架、三要素类结构 | #F0EBE0 / #E1362C | slide-block → shape-mark；shape-iris |
| [ink-wash](styles/ink-wash/style.yaml) | 水墨留白 | 人文/历史类科普、AI 与传统文化、年度回顾/金句 | #F2ECDE / #9D2933 | ink-bleed → seal-stamp；ink-spread |
| [clay-serif](styles/clay-serif/style.yaml) | 暖陶书卷 | Opus / Claude 专题、深度思考类口播、教程开场与总结 | #F0EEE6 / #D97757 | fade-up → underline-soft；dip |
| [instrument-panel](styles/instrument-panel/style.yaml) | 仪器面板 | 参数/规格对比、价格/速度/上下文长度、工具与配置教程 | #E5E5E5 / #F05A24 | segment-on → led-tag；shutter |

## 从上游配置到实际画面

- `colors` 是可直接使用的配色值。`type` 是1080×1920参考字号，不是所有比例的固定尺寸；按手机预览及内容重排。
- `fonts.family/file` 描述上游字体及文件名，本包未附字体。平台有授权字体时映射标题/正文/数字角色；缺字体选择同类中文覆盖完整的替代，不能声称原字体已经加载。若自行取得字体，查实际许可并随作品保留要求的许可文件；MiSans与优设标题黑不随包再分发。
- `motion.*` 是原仓库动作标识。先翻译为可见动作，再由 Design 可用图层/关键帧或代码实现，例如 `bar-grow` 为条形从相同基线按真实数值延展，`leader-lines` 为对象出现后引线连接标签。名字本身不是可调用API，不保证一比一复现。
- 风格中的布局、留白、页眉和色彩不能挤压源素材主体；原片可保留原色与景别。媒体镜与图解镜通过同一标签、字体和转场保持统一，不要求每帧都有大标题。
- `layout` 和 `lookbook` 是上游版式/标记参考，不原样粘贴假定能运行。特别避免把三种标准章节/列表/大数字版式当成全片唯一画面；自定义主体与图解继续继承同样色彩/字体/动效语言。
- `sound.kit.src` 是未随包提供的声音索引，不能直接加载。参考 `sound.character` 选平台可用授权音色；`maxPerSecond` 等是克制程度的参考，执行时以人声可懂和真实声音事件为准，不虚称运行过上游声音检查器。
- `not` 约束用于维持选定视觉气质，但不能覆盖用户要求与事实中立性。data-journal 中“竞品灰、主角强调色”改为按解释焦点强调；真实品牌身份/Logo可在有使用依据时出现，不继承上游的普遍禁Logo规则。蓝图纯线稿风格与真实证据照片分别构图，必要时采用点缀段，不把照片伪装成工程图。

## 节奏与运动继承

沿用上游的一个主要焦点、动作完成后停留、关键值锁定时揭晓、稀疏声音和确定性跳转原则。数字计数动画是表现手法，不代表数据实际随时间变化；历史趋势只能按真实序列画。对数据比较不使用误导的3D体积和装饰性仪表。

海报撞色、HUD、粒子等高刺激风格适合短强调段，不默认铺满全片。纸感或极简不等于文字卡轮播；即使只有两种颜色，也能用对象的连接、筛选、展开和前后状态讲清内容。

主工程写一张简短视觉卡：`主风格/点缀、实际字体、精确色值、画幅与布局、主体与文字比例、语义运动、声音规则、上游适配差异`。不可用特效用同样含义的简单动作替代，不为装饰改动事实。
